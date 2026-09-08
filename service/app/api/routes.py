"""Входящие ручки 3, 4, 5 (docs/contract.md v2.0): арена вызывает сервис.

Тонкий слой: валидация тела уже сделана Pydantic-схемами, вся игровая логика и
проверки — в app.services.game_service. Здесь только вызов сервиса, коммит
транзакции и упаковка ответа по контракту.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import (
    CloseGameRequest,
    CloseGameResponse,
    OpponentShotRequest,
    OpponentShotResponse,
    ShotResultRequest,
)
from app.services import game_service

router = APIRouter()


@router.post("/game/{game_id}/opponent-shot", response_model=OpponentShotResponse)
async def opponent_shot(
    game_id: uuid.UUID,
    body: OpponentShotRequest,
    session: AsyncSession = Depends(get_session),
) -> OpponentShotResponse:
    result = await game_service.handle_opponent_shot(session, game_id, body.coordinate)
    await session.commit()
    return OpponentShotResponse(result=result)


@router.post("/game/{game_id}/shot/result", status_code=status.HTTP_200_OK)
async def shot_result(
    game_id: uuid.UUID,
    body: ShotResultRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await game_service.handle_shot_result(session, game_id, body.coordinate, body.result)
    await session.commit()
    return Response(status_code=status.HTTP_200_OK)


@router.post("/game/{game_id}", response_model=CloseGameResponse)
async def close_game(
    game_id: uuid.UUID,
    body: CloseGameRequest,
    session: AsyncSession = Depends(get_session),
) -> CloseGameResponse:
    await game_service.handle_close(session, game_id, body.reason)
    await session.commit()
    return CloseGameResponse(status="closed")
