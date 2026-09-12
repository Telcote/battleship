import random
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import (
    AcceptedResponse,
    CloseGameResponse,
    OpponentShotRequest,
    OpponentShotResponse,
    ShipPlacement,
    ShotResponse,
    ShotResultRequest,
    StartGameResponse,
)
from app.services import game, turn

router = APIRouter()


@router.post("/game", response_model=StartGameResponse, status_code=status.HTTP_201_CREATED)
async def start_game(session: AsyncSession = Depends(get_session)) -> StartGameResponse:
    game_session = await game.create_session(session, random.Random())
    await session.commit()
    ships = [ShipPlacement(coordinates=ship["cells"]) for ship in game_session.ships]
    return StartGameResponse(session_id=game_session.id, ships=ships)


@router.post("/game/{session_id}/shot", response_model=ShotResponse)
async def shot(
    session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ShotResponse:
    coordinate = await turn.choose_next_shot(session, session_id, random.Random())
    await session.commit()
    return ShotResponse(coordinate=coordinate)


@router.post("/game/{session_id}/shot/result", response_model=AcceptedResponse)
async def shot_result(
    session_id: uuid.UUID,
    body: ShotResultRequest,
    session: AsyncSession = Depends(get_session),
) -> AcceptedResponse:
    await game.handle_shot_result(session, session_id, body.result)
    await session.commit()
    return AcceptedResponse(status="accepted")


@router.post("/game/{session_id}/opponent-shot", response_model=OpponentShotResponse)
async def opponent_shot(
    session_id: uuid.UUID,
    body: OpponentShotRequest,
    session: AsyncSession = Depends(get_session),
) -> OpponentShotResponse:
    result = await game.handle_opponent_shot(session, session_id, body.coordinate)
    await session.commit()
    return OpponentShotResponse(result=result)


@router.post("/game/{session_id}/close", response_model=CloseGameResponse)
async def close_game(
    session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> CloseGameResponse:
    await game.handle_close(session, session_id)
    await session.commit()
    return CloseGameResponse(status="closed")
