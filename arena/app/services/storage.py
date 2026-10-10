import datetime as dt
import uuid
from collections import OrderedDict

from app.config import settings
from app.errors import MatchNotFound, TournamentNotFound
from app.services.log import MatchLog, Player, Tournament


class MatchStorage:
    def __init__(self, limit: int | None = None) -> None:
        self._limit = limit or settings.match_history_limit
        self._matches: OrderedDict[uuid.UUID, MatchLog] = OrderedDict()

    def create(self, players: list[Player]) -> MatchLog:
        log = MatchLog(id=uuid.uuid4(), players=players, created_at=dt.datetime.now(dt.UTC))
        self._matches[log.id] = log
        while len(self._matches) > self._limit:
            self._matches.popitem(last=False)
        return log

    def get(self, match_id: uuid.UUID) -> MatchLog:
        log = self._matches.get(match_id)
        if log is None:
            raise MatchNotFound(f"match {match_id} not found")
        return log

    def list(self) -> list[MatchLog]:
        return list(reversed(self._matches.values()))


storage = MatchStorage()


class TournamentStorage:
    """Турниры не вытесняются: их единицы, а таблица нужна до конца."""

    def __init__(self) -> None:
        self._tournaments: dict[uuid.UUID, Tournament] = {}

    def create(self, players: list[Player], games_per_pair: int) -> Tournament:
        tournament = Tournament(
            id=uuid.uuid4(),
            players=players,
            games_per_pair=games_per_pair,
            created_at=dt.datetime.now(dt.UTC),
        )
        self._tournaments[tournament.id] = tournament
        return tournament

    def get(self, tournament_id: uuid.UUID) -> Tournament:
        tournament = self._tournaments.get(tournament_id)
        if tournament is None:
            raise TournamentNotFound(f"tournament {tournament_id} not found")
        return tournament

    def list(self) -> list[Tournament]:
        return list(reversed(self._tournaments.values()))


tournaments = TournamentStorage()
