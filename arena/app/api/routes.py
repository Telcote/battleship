import random
import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.errors import InvalidMatchRequest
from app.schemas import (
    CreateMatchRequest,
    CreateTournamentRequest,
    MatchLogResponse,
    MatchResponse,
    TournamentResponse,
)
from app.services import identity, match, tournament
from app.services.log import MatchLog, Player, Tournament
from app.services.storage import storage, tournaments

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


@router.post(
    "/tournament", response_model=TournamentResponse, status_code=status.HTTP_201_CREATED
)
async def create_tournament(
    body: CreateTournamentRequest, background: BackgroundTasks
) -> TournamentResponse:
    players = [
        Player(base_url=entry.base_url, address=await identity.resolve(entry.base_url))
        for entry in body.players
    ]

    addresses = [player.address for player in players]
    duplicates = sorted({address for address in addresses if addresses.count(address) > 1})
    if duplicates:
        raise InvalidMatchRequest(
            f"{', '.join(duplicates)} entered more than once: "
            "a service cannot play against itself"
        )

    created = tournaments.create(players, body.games_per_pair)
    background.add_task(tournament.run, created, random.Random(body.seed))
    return _to_tournament_response(created)


@router.get("/tournament", response_model=list[TournamentResponse])
async def list_tournaments() -> list[TournamentResponse]:
    return [_to_tournament_response(item) for item in tournaments.list()]


@router.get("/tournament/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(tournament_id: uuid.UUID) -> TournamentResponse:
    return _to_tournament_response(tournaments.get(tournament_id))


def _to_tournament_response(item: Tournament) -> TournamentResponse:
    return TournamentResponse.model_validate(
        {
            "tournament_id": item.id,
            "status": item.status,
            "players": item.players,
            "games_per_pair": item.games_per_pair,
            "matches_total": item.matches_total,
            "matches_finished": sum(log.status == "finished" for log in item.matches),
            "match_ids": [log.id for log in item.matches],
            "standings": tournament.standings(item),
            "created_at": item.created_at,
            "finished_at": item.finished_at,
        }
    )


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
