import uuid

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services import game

SHIPS = [
    {"cells": ["A1", "A2", "A3", "A4"], "hits": []},
    {"cells": ["J1"], "hits": []},
]


@pytest_asyncio.fixture
async def game_id(session: AsyncSession) -> uuid.UUID:
    new_id = uuid.uuid4()
    yield new_id
    stored = await session.get(GameSession, new_id)
    if stored is not None:
        await session.delete(stored)
        await session.commit()


async def _reread_session(session: AsyncSession, game_id: uuid.UUID) -> GameSession | None:
    session.expire_all()
    return await session.get(GameSession, game_id)


async def _reread_shots(session: AsyncSession, game_id: uuid.UUID) -> list[Shot]:
    session.expire_all()
    result = await session.execute(
        select(Shot).where(Shot.session_id == game_id).order_by(Shot.seq)
    )
    return list(result.scalars().all())


async def test_create_session_persists_starting_state(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    stored = await _reread_session(session, game_id)
    assert stored is not None
    assert stored.status == "starting"
    assert stored.turn == "opponent"
    assert stored.ships == SHIPS
    assert stored.close_reason is None


async def test_create_session_rejects_duplicate_game_id(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    try:
        await game.create_session(session, game_id, SHIPS)
        raise AssertionError("expected SessionAlreadyExists")
    except SessionAlreadyExists:
        pass


async def test_opponent_shot_hit_persists_ship_hits_and_own_hits(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    result = await game.handle_opponent_shot(session, game_id, "A2")
    await session.commit()
    assert result == "hit"

    stored = await _reread_session(session, game_id)
    assert stored.own_hits == 1
    assert stored.ships[0]["hits"] == ["A2"]
    assert stored.turn == "opponent"  # серия продолжается у противника

    shots = await _reread_shots(session, game_id)
    assert len(shots) == 1
    assert shots[0].direction == "incoming"
    assert shots[0].coordinate == "A2"
    assert shots[0].result == "hit"


async def test_opponent_shot_miss_passes_turn_to_self(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    result = await game.handle_opponent_shot(session, game_id, "H8")
    await session.commit()
    assert result == "miss"

    stored = await _reread_session(session, game_id)
    assert stored.own_hits == 0
    assert stored.turn == "self"


async def test_opponent_shot_kill_on_single_deck_ship(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    result = await game.handle_opponent_shot(session, game_id, "J1")
    await session.commit()
    assert result == "kill"

    stored = await _reread_session(session, game_id)
    assert stored.ships[1]["hits"] == ["J1"]


async def test_opponent_shot_repeated_cell_is_rejected_and_not_duplicated(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()
    await game.handle_opponent_shot(session, game_id, "B5")
    await session.commit()

    try:
        await game.handle_opponent_shot(session, game_id, "B5")
        raise AssertionError("expected InvalidCoordinate")
    except InvalidCoordinate:
        pass

    shots = await _reread_shots(session, game_id)
    assert len(shots) == 1  # повтор не долетел до журнала


async def test_opponent_shot_against_unknown_session(session: AsyncSession) -> None:
    try:
        await game.handle_opponent_shot(session, uuid.uuid4(), "A1")
        raise AssertionError("expected SessionNotFound")
    except SessionNotFound:
        pass


async def test_opponent_shot_against_closed_session_is_rejected(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()
    await game.handle_close(session, game_id, "opponent_defeated")
    await session.commit()

    try:
        await game.handle_opponent_shot(session, game_id, "A1")
        raise AssertionError("expected SessionClosed")
    except SessionClosed:
        pass


async def _seed_active_session_with_pending_shot(
    session: AsyncSession, game_id: uuid.UUID, coordinate: str
) -> None:
    session.add(
        GameSession(
            id=game_id,
            status="active",
            turn="self",
            pending_shot=coordinate,
            ships=SHIPS,
        )
    )
    await session.flush()
    session.add(Shot(session_id=game_id, seq=1, direction="outgoing", coordinate=coordinate))
    await session.commit()


async def test_shot_result_hit_clears_pending_shot_and_keeps_turn(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await _seed_active_session_with_pending_shot(session, game_id, "D7")

    await game.handle_shot_result(session, game_id, "D7", "hit")
    await session.commit()

    stored = await _reread_session(session, game_id)
    assert stored.pending_shot is None
    assert stored.turn == "self"  # попал — стреляет ещё раз

    shots = await _reread_shots(session, game_id)
    assert shots[0].result == "hit"


async def test_shot_result_miss_passes_turn_to_opponent(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await _seed_active_session_with_pending_shot(session, game_id, "D7")

    await game.handle_shot_result(session, game_id, "D7", "miss")
    await session.commit()

    stored = await _reread_session(session, game_id)
    assert stored.turn == "opponent"


async def test_shot_result_coordinate_mismatch_is_rejected_and_db_unchanged(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await _seed_active_session_with_pending_shot(session, game_id, "D7")

    try:
        await game.handle_shot_result(session, game_id, "D8", "hit")
        raise AssertionError("expected InvalidShotResult")
    except InvalidShotResult:
        pass

    stored = await _reread_session(session, game_id)
    assert stored.pending_shot == "D7"  # не тронуто
    shots = await _reread_shots(session, game_id)
    assert shots[0].result is None


async def test_shot_result_without_pending_shot_is_rejected(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    try:
        await game.handle_shot_result(session, game_id, "D7", "hit")
        raise AssertionError("expected NotYourTurn")
    except NotYourTurn:
        pass


async def test_close_persists_status_and_reason_without_deleting_row(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()

    await game.handle_close(session, game_id, "opponent_defeated")
    await session.commit()

    stored = await _reread_session(session, game_id)
    assert stored is not None  # партия остаётся в БД для разбора
    assert stored.status == "closed"
    assert stored.close_reason == "opponent_defeated"


async def test_close_twice_is_rejected(session: AsyncSession, game_id: uuid.UUID) -> None:
    await game.create_session(session, game_id, SHIPS)
    await session.commit()
    await game.handle_close(session, game_id, "opponent_defeated")
    await session.commit()

    try:
        await game.handle_close(session, game_id, "opponent_defeated")
        raise AssertionError("expected AlreadyClosed")
    except AlreadyClosed:
        pass


async def test_close_unknown_session(session: AsyncSession) -> None:
    try:
        await game.handle_close(session, uuid.uuid4(), "opponent_defeated")
        raise AssertionError("expected SessionNotFound")
    except SessionNotFound:
        pass
