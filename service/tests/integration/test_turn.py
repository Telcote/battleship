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


async def _seed_active_session(session: AsyncSession, game_id: uuid.UUID) -> None:
    session.add(
        GameSession(id=game_id, status="active", turn="self", pending_shot=None, ships=SHIPS)
    )
    await session.commit()


async def test_choose_next_shot_persists_pending_shot_and_journal_row(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await _seed_active_session(session, game_id)

    coordinate = await turn.choose_next_shot(session, game_id, random.Random(1))
    await session.commit()

    stored = await _reread_session(session, game_id)
    assert stored.pending_shot == coordinate

    shots = await _reread_shots(session, game_id)
    assert len(shots) == 1
    assert shots[0].direction == "outgoing"
    assert shots[0].coordinate == coordinate
    assert shots[0].result is None


async def test_choose_next_shot_never_repeats_previous_outgoing_shots(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await _seed_active_session(session, game_id)
    rng = random.Random(2)
    fired: set[str] = set()

    for _ in range(15):
        coordinate = await turn.choose_next_shot(session, game_id, rng)
        await session.commit()
        assert coordinate not in fired
        fired.add(coordinate)

        stored = await _reread_session(session, game_id)
        stored.pending_shot = None
        pending_row = (await session.execute(
            select(Shot)
            .where(Shot.session_id == game_id, Shot.direction == "outgoing", Shot.result.is_(None))
            .order_by(Shot.seq.desc())
            .limit(1)
        )).scalar_one()
        pending_row.result = "miss"
        await session.commit()


async def test_choose_next_shot_rejects_when_not_our_turn(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    session.add(
        GameSession(id=game_id, status="active", turn="opponent", pending_shot=None, ships=SHIPS)
    )
    await session.commit()

    try:
        await turn.choose_next_shot(session, game_id)
        raise AssertionError("expected NotYourTurn")
    except NotYourTurn:
        pass


async def test_choose_next_shot_rejects_when_a_shot_is_already_pending(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    session.add(
        GameSession(id=game_id, status="active", turn="self", pending_shot="D7", ships=SHIPS)
    )
    await session.commit()

    try:
        await turn.choose_next_shot(session, game_id)
        raise AssertionError("expected NotYourTurn")
    except NotYourTurn:
        pass


async def test_choose_next_shot_rejects_closed_session(
    session: AsyncSession, game_id: uuid.UUID
) -> None:
    await game.create_session(session, game_id, SHIPS)
    await game.handle_close(session, game_id, "opponent_defeated")
    await session.commit()

    try:
        await turn.choose_next_shot(session, game_id)
        raise AssertionError("expected SessionClosed")
    except SessionClosed:
        pass
