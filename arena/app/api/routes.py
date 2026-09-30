import random
import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.errors import InvalidMatchRequest
from app.schemas import CreateMatchRequest, MatchLogResponse, MatchResponse
from app.services import identity, match
from app.services.log import MatchLog, Player
from app.services.storage import storage

router = APIRouter()


@router.post("/match", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def create_match(body: CreateMatchRequest, background: BackgroundTasks) -> MatchResponse:
    players = [
        Player(base_url=entry.base_url, address=await identity.resolve(entry.base_url))
        for entry in body.players
    ]

    if players[0].address == players[1].address:
        raise InvalidMatchRequest(
            f"both entrants resolve to {players[0].address}: "
            "a service cannot play against itself"
        )

    log = storage.create(players)
    background.add_task(match.play, log, random.Random(body.seed))
    return _to_response(log)


@router.get("/match", response_model=list[MatchResponse])
async def list_matches() -> list[MatchResponse]:
    return [_to_response(log) for log in storage.list()]


@router.get("/match/{match_id}", response_model=MatchResponse)
async def get_match(match_id: uuid.UUID) -> MatchResponse:
    return _to_response(storage.get(match_id))


@router.get("/match/{match_id}/log", response_model=MatchLogResponse)
async def get_match_log(match_id: uuid.UUID) -> MatchLogResponse:
    log = storage.get(match_id)
    return MatchLogResponse.model_validate({"match_id": log.id, "events": log.events})


def _to_response(log: MatchLog) -> MatchResponse:
    """Вложенные dataclass'ы лога pydantic разбирает сам — модели схем с `from_attributes`."""
    return MatchResponse.model_validate(
        {
            "match_id": log.id,
            "status": log.status,
            "players": log.players,
            "first_move": log.first_move,
            "shots": len(log.events),
            "result": log.verdict,
            "created_at": log.created_at,
            "finished_at": log.finished_at,
        }
    )
