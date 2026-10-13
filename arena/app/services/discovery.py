import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import settings

ROUTES = Path("/proc/net/route")
MAX_HOSTS_PER_NETWORK = 254
CONNECT_TIMEOUT = 0.3
PARALLEL_CONNECTS = 512

Endpoint = tuple[str, int]  # (ip, port)


@dataclass
class KnownPlayer:
    base_url: str
    address: str
    # Имя контейнера DNS Docker.
    name: str


class Scanner:
    def __init__(self) -> None:
        self.players: list[KnownPlayer] = []
        self.scanned_at: float | None = None
        # Вердикт рукопожатия по каждому открытому порту: игроки на нём или пусто.
        self._verdicts: dict[Endpoint, list[KnownPlayer]] = {}
        self._running: asyncio.Task | None = None

    async def current(self) -> list[KnownPlayer]:
        if self.scanned_at is None:
            await self.refresh()
        elif time.monotonic() - self.scanned_at > settings.discovery_interval:
            if self._running is None or self._running.done():
                self._running = asyncio.create_task(self.refresh())
        return self.players

    async def refresh(self, hosts: list[str] | None = None, http: httpx.AsyncClient | None = None) -> None:
        hosts = hosts if hosts is not None else candidate_hosts()
        ports = parse_ports(settings.discovery_ports)
        open_now = set(await open_endpoints(hosts, ports))

        self._verdicts = {endpoint: v for endpoint, v in self._verdicts.items() if endpoint in open_now}
        fresh = sorted(open_now - self._verdicts.keys())
        if fresh:
            owned = http is None
            # Мимо прокси: ищем только в своей сети.
            http = http or httpx.AsyncClient(timeout=settings.player_timeout, trust_env=False)
            try:
                found = await asyncio.gather(*(identify(ip, port, http) for ip, port in fresh))
            finally:
                if owned:
                    await http.aclose()
            self._verdicts.update(zip(fresh, found))

        self.players = sorted(
            (player for endpoint in sorted(open_now) for player in self._verdicts[endpoint]),
            key=lambda player: (player.name, player.base_url),
        )
        self.scanned_at = time.monotonic()


scanner = Scanner()


async def identify(ip: str, port: int, http: httpx.AsyncClient) -> list[KnownPlayer]:
    name = await asyncio.to_thread(container_name, ip)
    base_url = f"http://{name}:{port}"
    address = f"{ip}:{port}"
    # Без имени контейнера игроков на одном IP различает только порт.
    label = name if name != ip else address
    if await plays_by_contract(base_url, http):
        return [KnownPlayer(base_url, address, label)]
    #rouge/modes
    modes = await rogue_modes(base_url, http)
    if modes and await plays_by_contract(f"{base_url}/{modes[0]}", http):
        return [KnownPlayer(f"{base_url}/{mode}", address, f"{label}/{mode}") for mode in modes]
    return []


async def plays_by_contract(base_url: str, http: httpx.AsyncClient) -> bool:
    try:
        started = await http.post(f"{base_url}/game")
        if started.status_code != 201:
            return False
        body = started.json()
        session_id, ships = body["session_id"], body["ships"]
        if not isinstance(session_id, str) or not isinstance(ships, list):
            return False
        await http.post(f"{base_url}/game/{session_id}/close")
        return True
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return False


async def rogue_modes(base_url: str, http: httpx.AsyncClient) -> list[str]:
    try:
        response = await http.get(f"{base_url}/modes")
        modes = response.json() if response.is_success else {}
    except (httpx.HTTPError, ValueError):
        return []
    return [mode for mode in modes if isinstance(mode, str)] if isinstance(modes, dict) else []


def container_name(ip: str) -> str:
    if ipaddress.ip_address(ip).is_loopback:
        return ip
    try:
        return socket.gethostbyaddr(ip)[0].split(".")[0]
    except OSError:
        return ip


async def open_endpoints(hosts: list[str], ports: list[int]) -> list[Endpoint]:
    limit = asyncio.Semaphore(PARALLEL_CONNECTS)

    async def probe(host: str, port: int) -> Endpoint | None:
        async with limit:
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), CONNECT_TIMEOUT)
            except (OSError, asyncio.TimeoutError):
                return None
            writer.close()
            return host, port

    results = await asyncio.gather(*(probe(host, port) for host in hosts for port in ports))
    return [endpoint for endpoint in results if endpoint is not None]


def candidate_hosts(routes: str | None = None) -> list[str]:
    """Свой loopback и адреса подключённых напрямую подсетей, кроме шлюзов."""
    if routes is None:
        try:
            routes = ROUTES.read_text()
        except OSError:
            routes = ""
    networks, gateways = [], set()
    for line in routes.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8:
            continue
        destination, gateway, mask = (_hex_ip(fields[i]) for i in (1, 2, 7))
        if gateway != "0.0.0.0":
            gateways.add(gateway)
        elif mask != "0.0.0.0":
            networks.append(ipaddress.ip_network(f"{destination}/{mask}", strict=False))

    hosts = ["127.0.0.1"]
    for network in networks:
        # Первый адрес сети Docker отдаёт шлюзу — это хост, даже если маршрута через него нет.
        for index, ip in enumerate(network.hosts()):
            if index >= MAX_HOSTS_PER_NETWORK:
                break
            if index > 0 and str(ip) not in gateways:
                hosts.append(str(ip))
    return list(dict.fromkeys(hosts))


def parse_ports(spec: str) -> list[int]:
    """"80,8000-8002" -> [80, 8000, 8001, 8002]."""
    ports: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        low, _, high = part.partition("-")
        ports.update(range(int(low), int(high or low) + 1))
    return sorted(ports)


def _hex_ip(value: str) -> str:
    """Адреса в /proc/net/route — 32-битное число в порядке байт машины (little-endian)."""
    return socket.inet_ntoa(int(value, 16).to_bytes(4, "little"))
