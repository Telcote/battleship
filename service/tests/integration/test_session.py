import random
import uuid

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import placement
from app.errors import (
    AlreadyClosed,
    InvalidCoordinate,
    InvalidShotResult,
    OutOfSequence,
    SessionClosed,
    SessionNotFound,
)
from app.models import GameSession, Shot
from app.services import game

SHIPS = [
    {"cells": ["A1", "A2", "A3", "A4"], "hits": []},
    {"cells": ["J1"], "hits": []},
]


@pytest_asyncio.fixture
async def session_id(session: AsyncSession) -> uuid.UUID:
    new_id = uuid.uuid4()
    session.add(GameSession(id=new_id, status="active", turn="unknown", ships=SHIPS))
    await session.commit()
    yield new_id
    stored = await session.get(GameSession, new_id)
    if stored is not None:
        await session.delete(stored)
        await session.commit()


async def _reread_session(session: AsyncSession, session_id: uuid.UUID) -> GameSession | None:
    session.expire_all()
    return await session.get(GameSession, session_id)


async def _reread_shots(session: AsyncSession, session_id: uuid.UUID) -> list[Shot]:
    session.expire_all()
    result = await session.execute(
        select(Shot).where(Shot.session_id == session_id).order_by(Shot.seq)
    )
    return list(result.scalars().all())


async def test_create_session_persists_generated_placement(session: AsyncSession) -> None:
    game_session = await game.create_session(session, random.Random(1))
    await session.commit()
    created_id = game_session.id

    stored = await _reread_session(session, created_id)
    assert stored is not None
    assert stored.status == "active"
    assert stored.turn == "unknown"  # жеребьёвку арена не сообщает
    assert stored.pending_shot is None
    placement.validate([ship["cells"] for ship in stored.ships])
    assert all(ship["hits"] == [] for ship in stored.ships)

    await session.delete(stored)
    await session.commit()


async def test_create_session_generates_unique_ids(session: AsyncSession) -> None:
    first = await game.create_session(session, random.Random(1))
    second = await game.create_session(session, random.Random(1))
    await session.commit()

    assert first.id != second.id

    for stored in (first, second):
        await session.delete(stored)
    await session.commit()


async def test_opponent_shot_hit_persists_ship_hits_and_own_hits(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    result = await game.handle_opponent_shot(session, session_id, "A2")
    await session.commit()
    assert result == "hit"

    stored = await _reread_session(session, session_id)
    assert stored.own_hits == 1
    assert stored.ships[0]["hits"] == ["A2"]
    assert stored.turn == "opponent"  # серия продолжается у противника

    shots = await _reread_shots(session, session_id)
    assert len(shots) == 1
    assert shots[0].direction == "incoming"
    assert shots[0].coordinate == "A2"
    assert shots[0].result == "hit"


async def test_opponent_shot_miss_passes_turn_to_self(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    result = await game.handle_opponent_shot(session, session_id, "H8")
    await session.commit()
    assert result == "miss"

    stored = await _reread_session(session, session_id)
    assert stored.own_hits == 0
    assert stored.turn == "self"


async def test_opponent_shot_killed_on_single_deck_ship(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    result = await game.handle_opponent_shot(session, session_id, "J1")
    await session.commit()
    assert result == "killed"

    stored = await _reread_session(session, session_id)
    assert stored.ships[1]["hits"] == ["J1"]


async def test_opponent_shot_repeated_cell_is_rejected_and_not_duplicated(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await game.handle_opponent_shot(session, session_id, "B5")
    await session.commit()

    try:
        await game.handle_opponent_shot(session, session_id, "B5")
        raise AssertionError("expected InvalidCoordinate")
    except InvalidCoordinate:
        pass

    shots = await _reread_shots(session, session_id)
    assert len(shots) == 1  # повтор не долетел до журнала


async def test_opponent_shot_against_unknown_session(session: AsyncSession) -> None:
    try:
        await game.handle_opponent_shot(session, uuid.uuid4(), "A1")
        raise AssertionError("expected SessionNotFound")
    except SessionNotFound:
        pass


async def test_opponent_shot_against_closed_session_is_rejected(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await game.handle_close(session, session_id)
    await session.commit()

    try:
        await game.handle_opponent_shot(session, session_id, "A1")
        raise AssertionError("expected SessionClosed")
    except SessionClosed:
        pass


async def _seed_pending_shot(session: AsyncSession, session_id: uuid.UUID, coordinate: str) -> None:
    stored = await session.get(GameSession, session_id)
    stored.turn = "self"
    stored.pending_shot = coordinate
    session.add(Shot(session_id=session_id, seq=1, direction="outgoing", coordinate=coordinate))
    await session.commit()


async def test_shot_result_hit_clears_pending_shot_and_keeps_turn(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_pending_shot(session, session_id, "D7")

    await game.handle_shot_result(session, session_id, "hit")
    await session.commit()

    stored = await _reread_session(session, session_id)
    assert stored.pending_shot is None
    assert stored.turn == "self"  # попал — стреляет ещё раз

    shots = await _reread_shots(session, session_id)
    assert shots[0].result == "hit"


async def test_shot_result_miss_passes_turn_to_opponent(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_pending_shot(session, session_id, "D7")

    await game.handle_shot_result(session, session_id, "miss")
    await session.commit()

    stored = await _reread_session(session, session_id)
    assert stored.turn == "opponent"


async def test_shot_result_invalid_value_is_rejected_and_db_unchanged(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_pending_shot(session, session_id, "D7")

    try:
        await game.handle_shot_result(session, session_id, "sunk")
        raise AssertionError("expected InvalidShotResult")
    except InvalidShotResult:
        pass

    stored = await _reread_session(session, session_id)
    assert stored.pending_shot == "D7"  # не тронуто
    shots = await _reread_shots(session, session_id)
    assert shots[0].result is None


async def test_shot_result_without_pending_shot_is_out_of_sequence(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    try:
        await game.handle_shot_result(session, session_id, "hit")
        raise AssertionError("expected OutOfSequence")
    except OutOfSequence:
        pass


async def test_close_persists_status_without_deleting_row(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await game.handle_close(session, session_id)
    await session.commit()

    stored = await _reread_session(session, session_id)
    assert stored is not None  # партия остаётся в БД для разбора
    assert stored.status == "closed"


async def test_close_twice_is_rejected(session: AsyncSession, session_id: uuid.UUID) -> None:
    await game.handle_close(session, session_id)
    await session.commit()

    try:
        await game.handle_close(session, session_id)
        raise AssertionError("expected AlreadyClosed")
    except AlreadyClosed:
        pass


async def test_close_unknown_session(session: AsyncSession) -> None:
    try:
        await game.handle_close(session, uuid.uuid4())
        raise AssertionError("expected SessionNotFound")
    except SessionNotFound:
        pass
