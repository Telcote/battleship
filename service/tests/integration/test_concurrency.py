import asyncio
import random
import time
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotYourTurn
from app.models import GameSession, Shot
from app.services import game, turn
from tests.conftest import SessionFactory

SHIPS = [
    {"cells": ["A1", "A2", "A3", "A4"], "hits": []},
    {"cells": ["J1"], "hits": []},
]

HOLD_SECONDS = 0.3


@pytest_asyncio.fixture
async def session_id(session: AsyncSession) -> uuid.UUID:
    new_id = uuid.uuid4()
    session.add(GameSession(id=new_id, status="active", turn="self", ships=SHIPS))
    await session.commit()
    yield new_id
    stored = await session.get(GameSession, new_id)
    if stored is not None:
        await session.delete(stored)
        await session.commit()


async def test_concurrent_shot_requests_are_serialized_by_row_lock(
    session: AsyncSession, make_session: SessionFactory, session_id: uuid.UUID
) -> None:
    # две арены бьют по одной сессии
    holder_locked = asyncio.Event()
    contender_session = await make_session()

    async def holder() -> None:
        game_session = await game.lock_session(session, session_id)
        holder_locked.set()
        await asyncio.sleep(HOLD_SECONDS)
        game_session.pending_shot = "D7"
        await session.commit()

    async def contender() -> float:
        await holder_locked.wait()
        started = time.monotonic()
        with pytest.raises(NotYourTurn):
            await turn.choose_next_shot(contender_session, session_id, random.Random(2))
        await contender_session.rollback()
        return time.monotonic() - started

    _, elapsed = await asyncio.gather(holder(), contender())

    assert elapsed >= HOLD_SECONDS * 0.8, (
        "вторая транзакция вернулась слишком быстро"
    )

    session.expire_all()
    stored = await session.get(GameSession, session_id)
    assert stored.pending_shot == "D7"

    shots = (
        (await session.execute(select(Shot).where(Shot.session_id == session_id)))
        .scalars()
        .all()
    )
    assert shots == []  # вторая транзакция не успела ничего записать в журнал
