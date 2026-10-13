"""Идентификация участника матча.

`session_id` на эту роль не годится: он уникален внутри своего сервиса, но два разных
сервиса вправе выдать один и тот же. Участника опознаёт адрес — `ip:port`.

Сравниваем именно разрешённый адрес, а не строку `base_url`: `http://app:8000` и
`http://172.18.0.3:8000` — один и тот же сервис под двумя именами, и без резолва
запрет «сервис не играет сам с собой» обходится опечаткой в заявке.

Порт входит в идентификатор: два сервиса вполне законно живут на одном хосте.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from app.errors import InvalidMatchRequest

DEFAULT_PORTS = {"http": 80, "https": 443}


def split(base_url: str) -> tuple[str, int]:
    """"http://app:8000" -> ("app", 8000). Бросает InvalidMatchRequest на мусоре."""
    parts = urlsplit(base_url)
    if parts.scheme not in DEFAULT_PORTS:
        raise InvalidMatchRequest(f"unsupported scheme in {base_url!r}: expected http or https")
    if not parts.hostname:
        raise InvalidMatchRequest(f"no host in {base_url!r}")

    try:
        port = parts.port or DEFAULT_PORTS[parts.scheme]
    except ValueError as exc:  # urlsplit ругается на нечисловой порт только при обращении
        raise InvalidMatchRequest(f"invalid port in {base_url!r}") from exc

    return parts.hostname, port


async def resolve(base_url: str) -> str:
    """Адрес участника в виде `ip:port` — то, чем арена его и различает."""
    host, port = split(base_url)
    ip = await resolve_host(host)
    # IPv6 в идентификаторе — в скобках, иначе двоеточия порта не отличить от адреса.
    return f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"


async def resolve_host(host: str) -> str:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass  # не литерал — идём в DNS

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise InvalidMatchRequest(f"cannot resolve host {host!r}") from exc

    return str(infos[0][4][0])
