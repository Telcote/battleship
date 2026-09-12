import random
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.domain import board, placement
from app.errors import (
    AlreadyClosed,
    InvalidCoordinate,
    InvalidShotResult,
    OutOfSequence,
    SessionClosed,
    SessionNotFound,
)
from app.models import GameSession, Shot

VALID_SHOT_RESULTS = {"miss", "hit", "killed"}


async def lock_session(session: AsyncSession, session_id: uuid.UUID) -> GameSession:
    result = await session.execute(
        select(GameSession).where(GameSession.id == session_id).with_for_update()
    )
    game_session = result.scalar_one_or_none()
    if game_session is None:
        raise SessionNotFound(f"session {session_id} not found")
    return game_session


async def next_seq(session: AsyncSession, session_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(Shot.seq), 0)).where(Shot.session_id == session_id)
    )
    return result.scalar_one() + 1


async def create_session(session: AsyncSession, rng: random.Random | None = None) -> GameSession:

    ships = [{"cells": cells, "hits": []} for cells in placement.generate(rng)]
    game_session = GameSession(
        id=uuid.uuid4(),
        status="active",
        turn="unknown",
        ships=ships,
    )
    session.add(game_session)
    await session.flush()
    return game_session


async def handle_opponent_shot(
    session: AsyncSession, session_id: uuid.UUID, coordinate: str
) -> board.ShotResult:

    game_session = await lock_session(session, session_id)
    if game_session.status == "closed":
        raise SessionClosed(f"session {session_id} is closed")

    repeated = await session.execute(
        select(Shot.id).where(
            Shot.session_id == session_id,
            Shot.direction == "incoming",
            Shot.coordinate == coordinate,
        )
    )
    if repeated.scalar_one_or_none() is not None:
        raise InvalidCoordinate(f"cell {coordinate} already shot at")

    result = board.apply_opponent_shot(game_session.ships, coordinate)
    flag_modified(game_session, "ships")  # обновление sqlalchemy
    session.add(
        Shot(
            session_id=session_id,
            seq=await next_seq(session, session_id),
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


async def handle_shot_result(session: AsyncSession, session_id: uuid.UUID, result: str) -> None:
    game_session = await lock_session(session, session_id)
    if game_session.status == "closed":
        raise SessionClosed(f"session {session_id} is closed")
    if result not in VALID_SHOT_RESULTS:
        raise InvalidShotResult(f"invalid result: {result!r}")
    if game_session.pending_shot is None:
        raise OutOfSequence(f"session {session_id} has no shot awaiting a result")

    pending = await session.execute(
        select(Shot)
        .where(
            Shot.session_id == session_id,
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


async def handle_close(session: AsyncSession, session_id: uuid.UUID) -> None:

    game_session = await lock_session(session, session_id)
    if game_session.status == "closed":
        raise AlreadyClosed(f"session {session_id} is already closed")

    game_session.status = "closed"
    await session.flush()
