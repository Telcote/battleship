import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import targeting
from app.errors import NotYourTurn, SessionClosed
from app.models import Shot
from app.services.game import lock_session, next_seq


async def choose_next_shot(
    session: AsyncSession, session_id: uuid.UUID, rng: random.Random | None = None
) -> str:
    game_session = await lock_session(session, session_id)
    if game_session.status == "closed":
        raise SessionClosed(f"session {session_id} is closed")
    if game_session.turn not in ("self", "unknown") or game_session.pending_shot is not None:
        raise NotYourTurn(f"session {session_id} is not awaiting a shot from us")

    history = await session.execute(
        select(Shot.coordinate, Shot.result).where(
            Shot.session_id == session_id, Shot.direction == "outgoing"
        )
    )
    shots = [(coordinate, result) for coordinate, result in history]

    coordinate = targeting.choose(shots, rng)

    game_session.turn = "self"
    game_session.pending_shot = coordinate
    session.add(
        Shot(
            session_id=session_id,
            seq=await next_seq(session, session_id),
            direction="outgoing",
            coordinate=coordinate,
            result=None,
        )
    )
    await session.flush()
    return coordinate
