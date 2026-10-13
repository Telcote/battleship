import asyncio
import random
from collections import Counter

import httpx

from app.services import tournament
from app.services.log import Player, Tournament
from app.services.storage import TournamentStorage
from tests.conftest import FakePlayer, make_http

ALPHA = "alpha:80"
BRAVO = "bravo:80"
CHARLIE = "charlie:80"


def make_tournament(*players: FakePlayer, games_per_pair: int = 1) -> Tournament:
    entries = [Player(player.base_url, player.address) for player in players]
    return TournamentStorage().create(entries, games_per_pair)


async def run(*players: FakePlayer, games_per_pair: int = 1) -> Tournament:
    """По одной партии за раз: заглушка держит одно поле и не умеет играть две партии сразу."""
    created = make_tournament(*players, games_per_pair=games_per_pair)
    async with make_http(*players) as http:
        await tournament.run(created, random.Random(0), http, parallel=1)
    return created


async def test_every_pair_plays_the_whole_series() -> None:
    result = await run(
        FakePlayer("alpha"), FakePlayer("bravo"), FakePlayer("charlie"), games_per_pair=2
    )

    assert result.status == "finished"
    assert result.finished_at is not None
    assert len(result.matches) == result.matches_total == 6
    pairs = Counter(frozenset(p.address for p in log.players) for log in result.matches)
    assert pairs == {
        frozenset({ALPHA, BRAVO}): 2,
        frozenset({ALPHA, CHARLIE}): 2,
        frozenset({BRAVO, CHARLIE}): 2,
    }
    assert all(log.status == "finished" for log in result.matches)


async def test_standings_add_up() -> None:
    result = await run(
        FakePlayer("alpha"), FakePlayer("bravo"), FakePlayer("charlie"), games_per_pair=2
    )

    table = tournament.standings(result)

    assert {row.address for row in table} == {ALPHA, BRAVO, CHARLIE}
    assert sum(row.wins for row in table) == 6
    for row in table:
        assert row.played == 4
        assert row.wins + row.losses + row.draws == row.played
        assert row.faults == {}
    assert [row.wins for row in table] == sorted((row.wins for row in table), reverse=True)


async def test_liar_ends_last_with_technical_losses() -> None:
    result = await run(
        FakePlayer("alpha"), FakePlayer("bravo"), FakePlayer("charlie", always="miss"),
        games_per_pair=2,
    )

    table = tournament.standings(result)

    liar = table[-1]
    assert liar.address == CHARLIE
    assert (liar.wins, liar.losses) == (0, 4)
    assert liar.faults == {"lie": 4}


async def test_parallel_matches_are_capped() -> None:
    """Каждая партия здесь — один запрос (`/game` падает), так что запросов в полёте
    ровно столько, сколько партий идёт одновременно."""
    players = [FakePlayer(host, fail_on="/game") for host in ("alpha", "bravo", "charlie", "delta")]
    by_host = {player.host: player for player in players}
    in_flight = peak = 0

    async def router(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return by_host[request.url.host].handle(request)

    created = make_tournament(*players)
    async with httpx.AsyncClient(transport=httpx.MockTransport(router)) as http:
        await tournament.run(created, random.Random(0), http, parallel=2)

    assert len(created.matches) == 6
    assert peak == 2
