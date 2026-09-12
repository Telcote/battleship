import random
import uuid

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotYourTurn, SessionClosed
from app.models import GameSession, Shot
from app.services import game, turn

SHIPS = [
    {"cells": ["A1", "A2", "A3", "A4"], "hits": []},
    {"cells": ["J1"], "hits": []},
]


@pytest_asyncio.fixture
async def session_id(session: AsyncSession) -> uuid.UUID:
    new_id = uuid.uuid4()
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


async def _seed_session(session: AsyncSession, session_id: uuid.UUID, **kwargs) -> None:
    session.add(GameSession(id=session_id, status="active", ships=SHIPS, **kwargs))
    await session.commit()


async def test_choose_next_shot_persists_pending_shot_and_journal_row(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_session(session, session_id, turn="self")

    coordinate = await turn.choose_next_shot(session, session_id, random.Random(1))
    await session.commit()

    stored = await _reread_session(session, session_id)
    assert stored.pending_shot == coordinate

    shots = await _reread_shots(session, session_id)
    assert len(shots) == 1
    assert shots[0].direction == "outgoing"
    assert shots[0].coordinate == coordinate
    assert shots[0].result is None


async def test_first_shot_settles_unknown_turn_to_self(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    # Жеребьёвку арена не сообщает: раз она пришла за выстрелом первой, ходим мы.
    await _seed_session(session, session_id, turn="unknown")

    await turn.choose_next_shot(session, session_id, random.Random(1))
    await session.commit()

    stored = await _reread_session(session, session_id)
    assert stored.turn == "self"


async def test_choose_next_shot_never_repeats_previous_outgoing_shots(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_session(session, session_id, turn="self")
    rng = random.Random(2)
    fired: set[str] = set()

    for _ in range(15):
        coordinate = await turn.choose_next_shot(session, session_id, rng)
        await session.commit()
        assert coordinate not in fired
        fired.add(coordinate)

        await game.handle_shot_result(session, session_id, "miss")
        await session.commit()
        stored = await _reread_session(session, session_id)
        stored.turn = "self"  # промах отдаёт ход, но нам нужен следующий выстрел
        await session.commit()


async def test_choose_next_shot_rejects_when_not_our_turn(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_session(session, session_id, turn="opponent")

    try:
        await turn.choose_next_shot(session, session_id)
        raise AssertionError("expected NotYourTurn")
    except NotYourTurn:
        pass


async def test_choose_next_shot_rejects_when_a_shot_is_already_pending(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_session(session, session_id, turn="self", pending_shot="D7")

    try:
        await turn.choose_next_shot(session, session_id)
        raise AssertionError("expected NotYourTurn")
    except NotYourTurn:
        pass


async def test_choose_next_shot_rejects_closed_session(
    session: AsyncSession, session_id: uuid.UUID
) -> None:
    await _seed_session(session, session_id, turn="self")
    await game.handle_close(session, session_id)
    await session.commit()

    try:
        await turn.choose_next_shot(session, session_id)
        raise AssertionError("expected SessionClosed")
    except SessionClosed:
        pass
