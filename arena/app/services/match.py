import random
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field

import httpx

from app.clients.player import PlayerClient
from app.config import settings
from app.domain.board import Board
from app.errors import ArenaError, PlayerFault
from app.services import referee
from app.services.log import MatchLog, Verdict

# 100 клеток у каждого игрока - 200 выстрелов максимум(на всякий случай)
MAX_SHOTS = 200


@dataclass
class Side:
    client: PlayerClient
    session_id: uuid.UUID
    board: Board
    fired: set[str] = field(default_factory=set)

    @property
    def address(self) -> str:
        return self.client.address


async def play(
    log: MatchLog,
    rng: random.Random | None = None,
    http: httpx.AsyncClient | None = None,
) -> None:
    rng = rng or random.Random()
    owned = httpx.AsyncClient(timeout=settings.player_timeout) if http is None else nullcontext(http)
    async with owned as http:
        log.status = "running"
        sessions: list[tuple[PlayerClient, uuid.UUID]] = []
        sides: list[Side] = []
        try:
            for player in log.players:
                client = PlayerClient(player.address, player.base_url, http)
                started = await client.start_game()
                sessions.append((client, started.session_id))
                ships = [ship.coordinates for ship in started.ships]
                log.ships[player.address] = ships
                board = referee.accept_placement(player.address, ships)
                sides.append(Side(client, started.session_id, board))

            if rng.random() < 0.5:
                sides.reverse()
            log.first_move = sides[0].address
            verdict = await _relay(log, *sides)

        except PlayerFault as exc:
            opponent = next((p.address for p in log.players if p.address != exc.address), None)
            verdict = Verdict(opponent, exc.address, exc.reason, str(exc))

        except Exception as exc:
            # Без этого матч навсегда остался бы в "running".
            verdict = Verdict(None, None, "arena_error", f"{type(exc).__name__}: {exc}")

        finally:
            for client, session_id in sessions:
                try:
                    await client.close_game(session_id)
                except ArenaError:
                    pass

    log.finish(verdict)


async def _relay(log: MatchLog, attacker: Side, defender: Side) -> Verdict:
    for _ in range(MAX_SHOTS):
        coordinate = await attacker.client.ask_shot(attacker.session_id)
        referee.accept_shot(attacker.address, coordinate, attacker.fired)
        attacker.fired.add(coordinate)
        result = await defender.client.send_opponent_shot(defender.session_id, coordinate)
        referee.accept_result(defender.address, defender.board, coordinate, result)
        await attacker.client.send_shot_result(attacker.session_id, result)
        log.add(attacker.address, coordinate, result)

        if defender.board.defeated:
            detail = f"fleet of {defender.address} is destroyed"
            return Verdict(attacker.address, defender.address, "fleet_destroyed", detail)
        if result == "miss":
            attacker, defender = defender, attacker

    return Verdict(None, None, "shot_limit", f"match exceeded {MAX_SHOTS} shots")
