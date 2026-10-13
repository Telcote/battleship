"""Заглушки игроков.

Настоящий сервис поднимать ради тестов арены не нужно: он за HTTP, а значит заменяется
транспортом. `FakePlayer` — минимальный игрок по контракту.

Поле и попадания заглушка считает сама, как настоящий сервис; арена сверяет её ответы
со своим полем. Для проверки судьи заглушку можно сломать: заставить врать (`always`),
тормозить (`slow_on`) или падать (`fail_on`).
"""

import asyncio
import json
import uuid
from collections.abc import Iterator

import httpx

VALID_FLEET = [
    ["A1", "A2", "A3", "A4"],
    ["C1", "C2", "C3"],
    ["E1", "E2", "E3"],
    ["A6", "A7"],
    ["C5", "C6"],
    ["E5", "E6"],
    ["G1"],
    ["G3"],
    ["I1"],
    ["I3"],
]

# Тупой перебор поля по порядку: A1, A2, ... J10. Для тестов важна воспроизводимость,
# а не качество стрельбы.
SCAN_ORDER = [f"{column}{row}" for column in "ABCDEFGHIJ" for row in range(1, 11)]

# Задержка медленной заглушки. Тест на таймаут опускает player_timeout ниже неё,
# чтобы не ждать настоящую секунду.
SLOW = 0.2


class FakePlayer:
    def __init__(
        self,
        host: str,
        ships: list[list[str]] | None = None,
        shots: list[str] | None = None,
        *,
        fail_on: str | None = None,
        slow_on: str | None = None,
        always: str | None = None,
        session_id: uuid.UUID | None = None,
    ) -> None:
        self.host = host
        self.address = f"{host}:80"  # так же, как арена разрешит http://<host>
        self.base_url = f"http://{host}"
        self.ships = ships if ships is not None else [list(s) for s in VALID_FLEET]
        self.fail_on = fail_on
        self.slow_on = slow_on
        # Лжец: на любой выстрел отвечает одно и то же, что бы ни было на поле.
        self.always = always
        # Фиксированный session_id нужен там, где проверяется, что арена не путает
        # игроков с одинаковыми сессиями.
        self.fixed_session_id = session_id

        self.session_id: uuid.UUID | None = None
        self.hits: set[str] = set()
        self.shots = shots if shots is not None else SCAN_ORDER
        self.next_shot: Iterator[str] = iter(self.shots)
        self.results_received: list[str] = []
        self.results_reported: list[str] = []
        self.shots_received: list[str] = []
        self.closed = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if self.fail_on and self.fail_on in path:
            return httpx.Response(500, json={"detail": "boom"})

        if path == "/game":
            return self._start_game()
        if path.endswith("/shot/result"):
            self.results_received.append(json.loads(request.content)["result"])
            return httpx.Response(200, json={"status": "accepted"})
        if path.endswith("/shot"):
            return httpx.Response(200, json={"coordinate": next(self.next_shot)})
        if path.endswith("/opponent-shot"):
            return self._opponent_shot(json.loads(request.content)["coordinate"])
        if path.endswith("/close"):
            self.closed = True
            return httpx.Response(200, json={"status": "closed"})

        return httpx.Response(404, json={"detail": "not found"})

    def _start_game(self) -> httpx.Response:
        # Новая партия — чистое поле и стрельба с начала: в турнире заглушка играет много раз.
        self.hits = set()
        self.next_shot = iter(self.shots)
        self.session_id = self.fixed_session_id or uuid.uuid4()
        return httpx.Response(
            201,
            json={
                "session_id": str(self.session_id),
                "ships": [{"coordinates": ship} for ship in self.ships],
            },
        )

    def _opponent_shot(self, coordinate: str) -> httpx.Response:
        self.shots_received.append(coordinate)
        result = self.always or self._apply(coordinate)
        self.results_reported.append(result)
        return httpx.Response(200, json={"result": result})

    def _apply(self, coordinate: str) -> str:
        for ship in self.ships:
            if coordinate not in ship:
                continue
            self.hits.add(coordinate)
            return "killed" if all(cell in self.hits for cell in ship) else "hit"
        return "miss"


def make_http(*players: FakePlayer) -> httpx.AsyncClient:
    """Клиент, который разводит запросы по заглушкам: base_url игрока — http://<host>."""
    by_host = {player.host: player for player in players}

    async def router(request: httpx.Request) -> httpx.Response:
        player = by_host.get(request.url.host)
        if player is None:
            return httpx.Response(502, json={"detail": f"unknown host {request.url.host}"})
        if player.slow_on and player.slow_on in request.url.path:
            await asyncio.sleep(SLOW)
        return player.handle(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(router))
