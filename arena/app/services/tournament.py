import asyncio
import datetime as dt
import itertools
import random
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.services import match
from app.services.log import Player, Tournament
from app.services.storage import storage


@dataclass
class Standing:
    address: str
    base_url: str
    played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    # Технические поражения по причинам: всё, что не «потоплен флот».
    faults: dict[str, int] = field(default_factory=dict)


async def run(
    tournament: Tournament,
    rng: random.Random | None = None,
    http: httpx.AsyncClient | None = None,
    parallel: int | None = None,
) -> None:
    rng = rng or random.Random()
    limit = asyncio.Semaphore(parallel or settings.tournament_parallel)
    pairs = [
        pair
        for pair in itertools.combinations(tournament.players, 2)
        for _ in range(tournament.games_per_pair)
    ]
    # Сиды раздаются заранее: жеребьёвка не зависит от того, в каком порядке партии стартуют.
    seeds = [rng.getrandbits(64) for _ in pairs]

    async def play_one(pair: tuple[Player, Player], seed: int) -> None:
        async with limit:
            log = storage.create(list(pair))
            tournament.matches.append(log)
            await match.play(log, random.Random(seed), http)

    tournament.status = "running"
    await asyncio.gather(*(play_one(pair, seed) for pair, seed in zip(pairs, seeds)))
    tournament.status = "finished"
    tournament.finished_at = dt.datetime.now(dt.UTC)


def standings(tournament: Tournament) -> list[Standing]:
    """Сыгранные партии сведены в таблицу: больше побед — выше, при равенстве — меньше нарушений."""
    table = {player.address: Standing(player.address, player.base_url) for player in tournament.players}
    for log in tournament.matches:
        verdict = log.verdict
        if verdict is None:
            continue
        for player in log.players:
            table[player.address].played += 1
        if verdict.winner is None or verdict.loser is None:
            for player in log.players:
                table[player.address].draws += 1
            continue
        table[verdict.winner].wins += 1
        loser = table[verdict.loser]
        loser.losses += 1
        if verdict.reason != "fleet_destroyed":
            loser.faults[verdict.reason] = loser.faults.get(verdict.reason, 0) + 1

    return sorted(
        table.values(), key=lambda row: (-row.wins, sum(row.faults.values()), row.address)
    )
