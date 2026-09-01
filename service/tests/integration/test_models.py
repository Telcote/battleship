import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import GameSession, Shot


async def test_game_session_and_shot_roundtrip(session: AsyncSession) -> None:
    session_id = uuid.uuid4()
    game_session = GameSession(
        id=session_id,
        status="active",
        turn="self",
        ships=[{"cells": ["A1"], "hits": []}],
    )
    session.add(game_session)
    await session.flush()

    session.add(Shot(session_id=session_id, seq=1, direction="outgoing", coordinate="B2"))
    await session.commit()

    stored = await session.scalar(
        select(GameSession)
        .where(GameSession.id == session_id)
        .options(selectinload(GameSession.shots))
    )
    assert stored is not None
    assert stored.status == "active"
    assert len(stored.shots) == 1
    assert stored.shots[0].coordinate == "B2"

    await session.delete(stored)
    await session.commit()
