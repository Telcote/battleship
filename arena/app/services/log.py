"""Протокол матча.

Событие лога — один пересланный выстрел: кто стрелял (адрес), куда и что ответил соперник.
Сюда попадает только то, что судья уже принял.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Literal

MatchStatus = Literal["pending", "running", "finished"]
EndReason = Literal[
    "fleet_destroyed",
    "shot_limit",
    "unavailable",
    "timeout",
    "invalid_placement",
    "invalid_shot",
    "lie",
    "arena_error",
]


@dataclass
class Player:
    """Участник матча: как его записали и во что арена развернула адрес."""

    base_url: str
    address: str


@dataclass
class Event:
    number: int
    attacker: str
    coordinate: str
    result: str


@dataclass
class Verdict:
    winner: str | None
    loser: str | None
    reason: EndReason
    detail: str


@dataclass
class MatchLog:
    id: uuid.UUID
    players: list[Player]
    created_at: dt.datetime
    status: MatchStatus = "pending"
    first_move: str | None = None
    events: list[Event] = field(default_factory=list)
    verdict: Verdict | None = None
    finished_at: dt.datetime | None = None

    def add(self, attacker: str, coordinate: str, result: str) -> None:
        self.events.append(Event(len(self.events) + 1, attacker, coordinate, result))

    def finish(self, verdict: Verdict) -> None:
        self.verdict = verdict
        self.status = "finished"
        self.finished_at = dt.datetime.now(dt.UTC)
