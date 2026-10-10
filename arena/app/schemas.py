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
    # Адрес -> корабли. Игрока, не приславшего расстановку, здесь нет.
    ships: dict[str, list[list[str]]]
    events: list[MatchEvent]


# POST /tournament
class CreateTournamentRequest(BaseModel):
    players: list[PlayerEntry] = Field(min_length=2)
    games_per_pair: int = Field(default=1, ge=1, le=100)
    seed: int | None = None


class StandingRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    address: str
    base_url: str
    played: int
    wins: int
    losses: int
    draws: int
    faults: dict[str, int]


class TournamentResponse(BaseModel):
    tournament_id: uuid.UUID
    status: MatchStatus
    players: list[PlayerRef]
    games_per_pair: int
    matches_total: int
    matches_finished: int
    match_ids: list[uuid.UUID]
    # Сводки партий без событий: просмотрщику не нужен отдельный запрос на каждую.
    matches: list[MatchResponse]
    standings: list[StandingRow]
    created_at: dt.datetime
    finished_at: dt.datetime | None


class ErrorResponse(BaseModel):
    detail: str
