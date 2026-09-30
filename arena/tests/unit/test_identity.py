import pytest

from app.errors import InvalidMatchRequest
from app.services import identity


def test_splits_host_and_port() -> None:
    assert identity.split("http://app:8000") == ("app", 8000)


def test_default_ports_are_filled_in() -> None:
    assert identity.split("http://app") == ("app", 80)
    assert identity.split("https://app") == ("app", 443)


def test_rejects_unsupported_scheme() -> None:
    with pytest.raises(InvalidMatchRequest, match="unsupported scheme"):
        identity.split("ftp://app:8000")


def test_rejects_url_without_host() -> None:
    with pytest.raises(InvalidMatchRequest, match="no host"):
        identity.split("http://")


def test_rejects_non_numeric_port() -> None:
    with pytest.raises(InvalidMatchRequest, match="invalid port"):
        identity.split("http://app:eight")


async def test_ip_literal_needs_no_dns() -> None:
    assert await identity.resolve("http://127.0.0.1:8000") == "127.0.0.1:8000"


async def test_ipv6_literal_keeps_brackets() -> None:
    """Иначе двоеточия порта не отличить от самого адреса."""
    assert await identity.resolve("http://[::1]:8000") == "[::1]:8000"


async def test_trailing_slash_does_not_change_the_address() -> None:
    assert await identity.resolve("http://127.0.0.1:8000/") == "127.0.0.1:8000"


async def test_port_is_part_of_the_address() -> None:
    """Два сервиса законно живут на одном хосте — различает их порт."""
    first = await identity.resolve("http://127.0.0.1:8000")
    second = await identity.resolve("http://127.0.0.1:8001")

    assert first != second


async def test_unresolvable_host_is_rejected() -> None:
    with pytest.raises(InvalidMatchRequest, match="cannot resolve"):
        await identity.resolve("http://no-such-host.invalid")
