import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import targeting
from app.errors import NotYourTurn, SessionClosed
from app.models import Shot
from app.services.game import lock_session, next_seq


async def choose_next_shot(
    session: AsyncSession, game_id: uuid.UUID, rng: random.Random | None = None
) -> str:
    """Выбирает координату своего следующего выстрела и фиксирует её в БД.

    Требует status='active', turn='self', pending_shot IS NULL — это же гарантирует, что
    все прошлые исходящие выстрелы в журнале уже имеют результат.
    """
    game_session = await lock_session(session, game_id)
    if game_session.status == "closed":
        raise SessionClosed(f"game {game_id} is closed")
    if game_session.turn != "self" or game_session.pending_shot is not None:
        raise NotYourTurn(f"game {game_id} is not awaiting a shot from us")

    history = await session.execute(
        select(Shot.coordinate, Shot.result).where(
            Shot.session_id == game_id, Shot.direction == "outgoing"
        )
    )
    shots = [(coordinate, result) for coordinate, result in history]

    coordinate = targeting.choose(shots, rng)

    game_session.pending_shot = coordinate
    session.add(
        Shot(
            session_id=game_id,
            seq=await next_seq(session, game_id),
            direction="outgoing",
            coordinate=coordinate,
            result=None,
        )
    )
    await session.flush()
    return coordinate
