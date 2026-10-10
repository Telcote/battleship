import random
import uuid

import pytest

from app.config import settings
from app.services import match
from app.services.log import MatchLog, Player
from app.services.storage import MatchStorage
from tests.conftest import SLOW, VALID_FLEET, FakePlayer, make_http

ALPHA = "alpha:80"
BRAVO = "bravo:80"


def make_log(*players: FakePlayer) -> MatchLog:
    """Запись матча с уже разрешёнными адресами: резолвом занимается ручка, не цикл."""
    storage = MatchStorage()
    return storage.create([Player(player.base_url, player.address) for player in players])


async def play(*players: FakePlayer, seed: int = 0) -> MatchLog:
    log = make_log(*players)
    async with make_http(*players) as http:
        await match.play(log, random.Random(seed), http)
    return log


async def test_match_ends_when_ten_ships_are_killed() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo"))

    assert log.status == "finished"
    assert log.verdict is not None
    assert log.verdict.reason == "fleet_destroyed"
    assert log.verdict.winner in {ALPHA, BRAVO}
    assert log.verdict.loser != log.verdict.winner


async def test_winner_is_credited_with_exactly_ten_kills() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo"))

    assert log.verdict is not None
    kills = [
        event
        for event in log.events
        if event.attacker == log.verdict.winner and event.result == "killed"
    ]
    assert len(kills) == 10


async def test_players_are_identified_by_address() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo"))

    assert {player.address for player in log.players} == {ALPHA, BRAVO}
    assert {event.attacker for event in log.events} <= {ALPHA, BRAVO}


async def test_colliding_session_ids_do_not_confuse_the_arena() -> None:
    """Ровно тот случай, ради которого ключ — адрес: оба сервиса выдали одну сессию."""
    shared = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    alpha = FakePlayer("alpha", session_id=shared)
    bravo = FakePlayer("bravo", session_id=shared)

    log = await play(alpha, bravo)

    assert alpha.session_id == bravo.session_id
    assert log.verdict is not None
    assert log.verdict.reason == "fleet_destroyed"
    assert {log.verdict.winner, log.verdict.loser} == {ALPHA, BRAVO}


async def test_shot_reaches_the_opponent_unchanged() -> None:
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo")

    log = await play(alpha, bravo)

    alpha_shots = [event.coordinate for event in log.events if event.attacker == ALPHA]
    assert bravo.shots_received == alpha_shots


async def test_result_returns_to_the_shooter_unchanged() -> None:
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo")

    await play(alpha, bravo)

    assert alpha.results_received == bravo.results_reported


async def test_log_records_what_was_relayed() -> None:
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo")

    log = await play(alpha, bravo)

    relayed = [event.result for event in log.events if event.attacker == ALPHA]
    assert relayed == bravo.results_reported
    assert [event.number for event in log.events] == list(range(1, len(log.events) + 1))


async def test_turn_passes_only_after_a_miss() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo"))

    for previous, current in zip(log.events, log.events[1:]):
        if previous.result == "miss":
            assert current.attacker != previous.attacker
        else:
            assert current.attacker == previous.attacker


async def test_match_closes_both_sessions() -> None:
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo")

    await play(alpha, bravo)

    assert alpha.closed and bravo.closed


async def test_first_move_is_recorded() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo"))

    assert log.first_move == log.events[0].attacker


async def test_seed_decides_who_moves_first() -> None:
    first_moves = set()
    for seed in range(8):
        log = await play(FakePlayer("alpha"), FakePlayer("bravo"), seed=seed)
        first_moves.add(log.first_move)

    assert first_moves == {ALPHA, BRAVO}


async def test_broken_player_loses_by_default() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo", fail_on="/game"))

    assert log.verdict is not None
    assert log.verdict.reason == "unavailable"
    assert log.verdict.loser == BRAVO
    assert log.verdict.winner == ALPHA


async def test_player_that_breaks_mid_match_loses() -> None:
    log = await play(FakePlayer("alpha"), FakePlayer("bravo", fail_on="/opponent-shot"))

    assert log.verdict is not None
    assert log.verdict.reason == "unavailable"
    assert log.verdict.loser == BRAVO
    assert log.events == []


# Судейство


@pytest.mark.parametrize(
    "ships",
    [
        VALID_FLEET[:-1],
        [*VALID_FLEET[:-1], ["J9", "J10"]],
        [*VALID_FLEET[:-1], ["B1"]],
        [*VALID_FLEET[:-1], ["K1"]],
    ],
    ids=["missing ship", "wrong sizes", "touching", "off the board"],
)
async def test_invalid_placement_loses(ships: list[list[str]]) -> None:
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo", ships=ships)

    log = await play(alpha, bravo)

    assert log.verdict is not None
    assert log.verdict.reason == "invalid_placement"
    assert (log.verdict.winner, log.verdict.loser) == (ALPHA, BRAVO)
    assert log.events == []
    assert alpha.closed and bravo.closed


async def test_liar_loses_on_the_first_lie() -> None:
    """Браво всегда отвечает `miss`, а ALPHA первым же выстрелом в A1 попадает в корабль."""
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo", always="miss")

    log = await play(alpha, bravo)

    assert log.verdict is not None
    assert log.verdict.reason == "lie"
    assert (log.verdict.winner, log.verdict.loser) == (ALPHA, BRAVO)
    assert "A1" in log.verdict.detail
    assert alpha.results_received == []  # ложь не переслана стрелявшему


@pytest.mark.parametrize("seed", [0, 1])
async def test_invalid_shot_blames_the_shooter_not_the_target(seed: int) -> None:
    """Мусорная координата не уходит сопернику: иначе 400 честного защитника стоил бы ему матча."""
    alpha, bravo = FakePlayer("alpha", shots=["Z99"]), FakePlayer("bravo")

    log = await play(alpha, bravo, seed=seed)

    assert log.verdict is not None
    assert log.verdict.reason == "invalid_shot"
    assert (log.verdict.winner, log.verdict.loser) == (BRAVO, ALPHA)
    assert "Z99" not in bravo.shots_received


@pytest.mark.parametrize("seed", [0, 1])
async def test_repeated_shot_blames_the_shooter_not_the_target(seed: int) -> None:
    """Честный сервис на повтор отвечает 400 — пересылать повтор значит засудить защитника."""
    alpha, bravo = FakePlayer("alpha", shots=["J10", "J10"]), FakePlayer("bravo")

    log = await play(alpha, bravo, seed=seed)

    assert log.verdict is not None
    assert log.verdict.reason == "invalid_shot"
    assert (log.verdict.winner, log.verdict.loser) == (BRAVO, ALPHA)
    assert "J10" in log.verdict.detail
    assert bravo.shots_received.count("J10") == 1


async def test_slow_player_loses_by_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "player_timeout", SLOW / 4)
    alpha, bravo = FakePlayer("alpha"), FakePlayer("bravo", slow_on="/opponent-shot")

    log = await play(alpha, bravo)

    assert log.verdict is not None
    assert log.verdict.reason == "timeout"
    assert (log.verdict.winner, log.verdict.loser) == (ALPHA, BRAVO)
