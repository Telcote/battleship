import asyncio
import socket
import time

import httpx
import pytest

from app.services import discovery

def route_table(*routes: tuple[str, str, str]) -> str:
    """/proc/net/route ядро пишет адреса hex в little-endian."""

    def encode(ip: str) -> str:
        return socket.inet_aton(ip)[::-1].hex().upper()

    columns = ["Iface", "Destination", "Gateway", "Flags", "RefCnt", "Use", "Metric", "Mask", "MTU", "Window", "IRTT"]
    rows = [columns]
    for destination, gateway, mask in routes:
        # Важны только сеть, шлюз и маска, остальные колонки — нули.
        row = dict.fromkeys(columns, "0") | {
            "Iface": "eth0",
            "Destination": encode(destination),
            "Gateway": encode(gateway),
            "Mask": encode(mask),
        }
        rows.append(list(row.values()))
    return "".join("\t".join(row) + "\n" for row in rows)


# Контейнер в двух сетях; выход наружу — через шлюз первой.
ROUTES = route_table(
    ("0.0.0.0", "172.20.0.1", "0.0.0.0"),
    ("172.20.0.0", "0.0.0.0", "255.255.0.0"),
    ("172.28.0.0", "0.0.0.0", "255.255.255.0"),
)


class FakeNetwork:
    """Сервисы по `host:port`: игрок по контракту, жулик с режимами или кто-то посторонний."""

    def __init__(self, players: set[str] = frozenset(), rogues: set[str] = frozenset()) -> None:
        self.players = players
        self.rogues = rogues
        self.started: list[str] = []
        self.closed: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        server = f"{request.url.host}:{request.url.port}"
        path = request.url.path
        prefix = ""
        if server in self.rogues:
            if path == "/modes":
                return httpx.Response(200, json={"honest": "…", "liar": "…"})
            prefix, _, path = path[1:].partition("/")
            path = f"/{path}"
        elif server not in self.players:
            return httpx.Response(404, json={"detail": "Not Found"})

        if path == "/game" and request.method == "POST":
            self.started.append(f"{server}/{prefix}".rstrip("/"))
            return httpx.Response(201, json={"session_id": "s-1", "ships": [{"coordinates": ["A1"]}]})
        if path == "/game/s-1/close":
            self.closed.append(server)
            return httpx.Response(200, json={"status": "closed"})
        return httpx.Response(404, json={"detail": "Not Found"})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))


def test_ports_spec_accepts_lists_and_ranges() -> None:
    assert discovery.parse_ports("80, 8000-8002,,8000") == [80, 8000, 8001, 8002]


def test_hosts_come_from_attached_networks_without_the_gateway() -> None:
    hosts = discovery.candidate_hosts(ROUTES)

    assert hosts[0] == "127.0.0.1"
    assert "172.20.0.1" not in hosts  # шлюз — это хост Docker и выход в LAN
    assert "172.20.0.2" in hosts
    # Из /16 — только первые 254 адреса: Docker раздаёт их подряд.
    assert [h for h in hosts if h.startswith("172.20.")][-1] == "172.20.0.254"
    assert "172.20.1.1" not in hosts
    assert "172.28.0.254" in hosts
    # Шлюз второй сети не в маршруте по умолчанию, но и он — хост Docker.
    assert "172.28.0.1" not in hosts
    assert "172.28.0.2" in hosts


def test_no_route_table_means_only_own_loopback() -> None:
    assert discovery.candidate_hosts("") == ["127.0.0.1"]


async def test_contract_handshake_identifies_a_player_and_closes_the_session() -> None:
    network = FakeNetwork(players={"127.0.0.1:8000"})

    found = await discovery.identify("127.0.0.1", 8000, network.client())

    # Без имени контейнера в подписи нужен порт: на одном IP может быть несколько игроков.
    assert found == [discovery.KnownPlayer("http://127.0.0.1:8000", "127.0.0.1:8000", "127.0.0.1:8000")]
    assert network.closed == ["127.0.0.1:8000"]


async def test_service_outside_the_contract_is_not_a_player() -> None:
    network = FakeNetwork()

    assert await discovery.identify("127.0.0.1", 8100, network.client()) == []


async def test_rogue_is_listed_once_per_mode() -> None:
    network = FakeNetwork(rogues={"127.0.0.1:8200"})

    found = await discovery.identify("127.0.0.1", 8200, network.client())

    assert [player.base_url for player in found] == [
        "http://127.0.0.1:8200/honest",
        "http://127.0.0.1:8200/liar",
    ]
    assert {player.address for player in found} == {"127.0.0.1:8200"}


async def test_handshake_happens_once_per_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    network = FakeNetwork(players={"127.0.0.1:8000"})
    open_ports = [("127.0.0.1", 8000)]

    async def fake_open(hosts, ports):
        return list(open_ports)

    monkeypatch.setattr(discovery, "open_endpoints", fake_open)
    scanner = discovery.Scanner()

    await scanner.refresh(["127.0.0.1"], network.client())
    await scanner.refresh(["127.0.0.1"], network.client())
    assert network.started == ["127.0.0.1:8000"]
    assert [player.address for player in scanner.players] == ["127.0.0.1:8000"]

    # Порт закрылся — игрок пропал, а новый сервис на том же адресе снова проверяется.
    open_ports.clear()
    await scanner.refresh(["127.0.0.1"], network.client())
    assert scanner.players == []
    open_ports.append(("127.0.0.1", 8000))
    await scanner.refresh(["127.0.0.1"], network.client())
    assert len(network.started) == 2


async def test_open_ports_are_found_and_closed_ones_skipped() -> None:
    server = await asyncio.start_server(lambda reader, writer: writer.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        found = await discovery.open_endpoints(["127.0.0.1"], [port, 9])
    finally:
        server.close()
        await server.wait_closed()

    assert found == [("127.0.0.1", port)]


async def test_stale_results_are_served_while_refreshing_in_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scanner = discovery.Scanner()
    calls = 0

    async def fake_refresh(*args, **kwargs):
        nonlocal calls
        calls += 1
        scanner.scanned_at = time.monotonic()

    monkeypatch.setattr(scanner, "refresh", fake_refresh)

    await scanner.current()  # первый вызов ждёт обход
    assert calls == 1
    scanner.scanned_at = time.monotonic() - 3600
    await scanner.current()  # устаревшее — отдаём сразу, обновляем в фоне
    await asyncio.sleep(0)
    assert calls == 2
