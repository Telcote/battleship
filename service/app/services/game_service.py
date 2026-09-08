"""Обработка входящих ручек 3, 4, 5 (docs/contract.md v2.0): арена вызывает сервис.

Одна HTTP-обработка = одна транзакция. Строка сессии читается с `SELECT ... FOR UPDATE`,
поэтому запросы по одной сессии сериализуются, а по разным — идут параллельно
(см. docs/architecture.md, п. 5.1, 5.5).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.domain import board
from app.errors import (
    AlreadyClosed,
    InvalidCoordinate,
    InvalidShotResult,
    NotYourTurn,
    SessionAlreadyExists,
    SessionClosed,
    SessionNotFound,
)
from app.models import GameSession, Shot


async def _lock_session(session: AsyncSession, game_id: uuid.UUID) -> GameSession:
    result = await session.execute(
        select(GameSession).where(GameSession.id == game_id).with_for_update()
    )
    game_session = result.scalar_one_or_none()
    if game_session is None:
        raise SessionNotFound(f"game {game_id} not found")
    return game_session


async def _next_seq(session: AsyncSession, game_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(Shot.seq), 0)).where(Shot.session_id == game_id)
    )
    return result.scalar_one() + 1


async def create_session(
    session: AsyncSession, game_id: uuid.UUID, ships: list[board.ShipState]
) -> GameSession:
    """Заводит строку сессии в статусе `starting` до обращения к арене (ручка 1)."""
    existing = await session.execute(select(GameSession.id).where(GameSession.id == game_id))
    if existing.scalar_one_or_none() is not None:
        raise SessionAlreadyExists(f"game {game_id} already exists")

    game_session = GameSession(
        id=game_id,
        status="starting",
        turn="opponent",
        ships=ships,
    )
    session.add(game_session)
    await session.flush()
    return game_session


async def handle_opponent_shot(
    session: AsyncSession, game_id: uuid.UUID, coordinate: str
) -> board.ShotResult:
    """Ручка 3 — арена сообщает координату своего выстрела, сервис бьёт по своему полю."""
    game_session = await _lock_session(session, game_id)
    if game_session.status == "closed":
        raise SessionClosed(f"game {game_id} is closed")

    repeated = await session.execute(
        select(Shot.id).where(
            Shot.session_id == game_id,
            Shot.direction == "incoming",
            Shot.coordinate == coordinate,
        )
    )
    if repeated.scalar_one_or_none() is not None:
        raise InvalidCoordinate(f"cell {coordinate} already shot at")

    result = board.apply_opponent_shot(game_session.ships, coordinate)
    flag_modified(game_session, "ships")  # мутация вложенного JSONB "на месте" не отслеживается
    session.add(
        Shot(
            session_id=game_id,
            seq=await _next_seq(session, game_id),
            direction="incoming",
            coordinate=coordinate,
            result=result,
        )
    )
    if result != "miss":
        game_session.own_hits += 1
    game_session.turn = "opponent" if result != "miss" else "self"
    await session.flush()
    return result


async def handle_shot_result(
    session: AsyncSession, game_id: uuid.UUID, coordinate: str, result: board.ShotResult
) -> None:
    """Ручка 4 — арена подтверждает результат последнего выстрела сервиса."""
    game_session = await _lock_session(session, game_id)
    if game_session.status == "closed":
        raise SessionClosed(f"game {game_id} is closed")
    if game_session.pending_shot is None:
        raise NotYourTurn(f"game {game_id} has no shot awaiting a result")
    if game_session.pending_shot != coordinate:
        raise InvalidShotResult(
            f"coordinate {coordinate!r} does not match the pending shot "
            f"{game_session.pending_shot!r}"
        )

    pending = await session.execute(
        select(Shot)
        .where(
            Shot.session_id == game_id,
            Shot.direction == "outgoing",
            Shot.result.is_(None),
        )
        .order_by(Shot.seq.desc())
        .limit(1)
    )
    outgoing_shot = pending.scalar_one()
    outgoing_shot.result = result

    game_session.pending_shot = None
    game_session.turn = "self" if result != "miss" else "opponent"
    await session.flush()


async def handle_close(session: AsyncSession, game_id: uuid.UUID, reason: str) -> None:
    """Ручка 5 — арена закрывает сессию. Повторное закрытие не идемпотентно (400)."""
    game_session = await _lock_session(session, game_id)
    if game_session.status == "closed":
        raise AlreadyClosed(f"game {game_id} is already closed")

    game_session.status = "closed"
    game_session.close_reason = reason
    await session.flush()
