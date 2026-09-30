"""API самой арены: то, чем ею управляют снаружи. К контракту «Арена ↔ Сервис» отношения не имеет.

Участник везде обозначается своим `address` (`ip:port`) — см. services/identity.py.
Имён у игроков нет: адрес и есть имя.

Модели ответов собираются прямо из dataclass'ов services/log.py (`from_attributes`).
"""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.services.log import EndReason, MatchStatus


class PlayerEntry(BaseModel):
    """Заявка игрока: только то, что задаёт оператор."""

    base_url: str = Field(min_length=1)


class PlayerRef(BaseModel):
    """Участник матча: как его записали и во что арена развернула адрес."""

    model_config = ConfigDict(from_attributes=True)

    base_url: str
    address: str


# POST /match
class CreateMatchRequest(BaseModel):
    players: list[PlayerEntry] = Field(min_length=2, max_length=2)
    # Фиксированный seed делает жеребьёвку воспроизводимой — удобно в тестах.
    seed: int | None = None


class MatchEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    attacker: str
    coordinate: str
    result: str


class MatchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    winner: str | None
    loser: str | None
    reason: EndReason
    detail: str


class MatchResponse(BaseModel):
    match_id: uuid.UUID
    status: MatchStatus
    players: list[PlayerRef]
    first_move: str | None
    shots: int
    result: MatchResult | None
    created_at: dt.datetime
    finished_at: dt.datetime | None


# GET /match/{match_id}/log
class MatchLogResponse(BaseModel):
    match_id: uuid.UUID
    events: list[MatchEvent]


class ErrorResponse(BaseModel):
    detail: str
