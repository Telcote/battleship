from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

DEAD = "http://127.0.0.1:9"
OTHER_DEAD = "http://127.0.0.2:9"
THIRD_DEAD = "http://127.0.0.3:9"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://arena") as ac:
        yield ac


def match_body(first: str = DEAD, second: str = OTHER_DEAD) -> dict:
    return {"players": [{"base_url": first}, {"base_url": second}]}


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_match_returns_201_and_the_match(client: AsyncClient) -> None:
    response = await client.post("/match", json=match_body())

    assert response.status_code == 201
    body = response.json()
    assert body["result"] is None
    assert body["shots"] == 0


async def test_players_are_reported_with_resolved_addresses(client: AsyncClient) -> None:
    body = (await client.post("/match", json=match_body())).json()

    assert [player["address"] for player in body["players"]] == ["127.0.0.1:9", "127.0.0.2:9"]
    assert [player["base_url"] for player in body["players"]] == [DEAD, OTHER_DEAD]


async def test_match_is_played_out_in_the_background(client: AsyncClient) -> None:
    match_id = (await client.post("/match", json=match_body())).json()["match_id"]

    body = (await client.get(f"/match/{match_id}")).json()

    assert body["status"] == "finished"
    assert body["result"]["reason"] == "unavailable"


async def test_service_cannot_play_against_itself(client: AsyncClient) -> None:
    response = await client.post("/match", json=match_body(DEAD, DEAD))

    assert response.status_code == 400
    assert "cannot play against itself" in response.json()["detail"]


async def test_the_same_service_under_two_urls_is_still_rejected(client: AsyncClient) -> None:
    """Разные строки, один адрес: запрет ловит именно сервис, а не написание URL."""
    response = await client.post("/match", json=match_body(DEAD, DEAD + "/"))

    assert response.status_code == 400
    assert "127.0.0.1:9" in response.json()["detail"]


async def test_unresolvable_host_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/match", json=match_body("http://no-such-host.invalid", DEAD))

    assert response.status_code == 400
    assert "cannot resolve" in response.json()["detail"]


async def test_bad_scheme_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/match", json=match_body("ftp://127.0.0.3:9", DEAD))

    assert response.status_code == 400
    assert "unsupported scheme" in response.json()["detail"]


async def test_single_player_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/match", json={"players": [{"base_url": DEAD}]})

    assert response.status_code == 400


async def test_unknown_match_is_404(client: AsyncClient) -> None:
    response = await client.get("/match/550e8400-e29b-41d4-a716-446655440000")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


async def test_non_uuid_match_id_is_400(client: AsyncClient) -> None:
    response = await client.get("/match/not-a-uuid")

    assert response.status_code == 400


async def test_match_log_is_available(client: AsyncClient) -> None:
    match_id = (await client.post("/match", json=match_body())).json()["match_id"]

    response = await client.get(f"/match/{match_id}/log")

    assert response.status_code == 200
    assert response.json()["match_id"] == match_id
    assert response.json()["events"] == []


async def test_matches_are_listed_newest_first(client: AsyncClient) -> None:
    first = (await client.post("/match", json=match_body())).json()["match_id"]
    second = (await client.post("/match", json=match_body())).json()["match_id"]

    listed = [item["match_id"] for item in (await client.get("/match")).json()]

    assert listed.index(second) < listed.index(first)


def tournament_body(*base_urls: str, games_per_pair: int = 1) -> dict:
    return {
        "players": [{"base_url": url} for url in base_urls],
        "games_per_pair": games_per_pair,
    }


async def test_create_tournament_returns_201_and_the_schedule(client: AsyncClient) -> None:
    response = await client.post(
        "/tournament", json=tournament_body(DEAD, OTHER_DEAD, THIRD_DEAD, games_per_pair=2)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["matches_total"] == 6
    assert body["games_per_pair"] == 2
    assert len(body["standings"]) == 3


async def test_tournament_is_played_out_in_the_background(client: AsyncClient) -> None:
    created = await client.post(
        "/tournament", json=tournament_body(DEAD, OTHER_DEAD, THIRD_DEAD)
    )
    tournament_id = created.json()["tournament_id"]

    body = (await client.get(f"/tournament/{tournament_id}")).json()

    assert body["status"] == "finished"
    assert body["matches_finished"] == body["matches_total"] == 3
    assert sum(row["played"] for row in body["standings"]) == 6
    for match_id in body["match_ids"]:
        assert (await client.get(f"/match/{match_id}")).status_code == 200


async def test_tournament_rejects_the_same_service_twice(client: AsyncClient) -> None:
    response = await client.post(
        "/tournament", json=tournament_body(DEAD, OTHER_DEAD, DEAD + "/")
    )

    assert response.status_code == 400
    assert "127.0.0.1:9" in response.json()["detail"]


async def test_tournament_needs_two_players(client: AsyncClient) -> None:
    response = await client.post("/tournament", json=tournament_body(DEAD))

    assert response.status_code == 400


async def test_unknown_tournament_is_404(client: AsyncClient) -> None:
    response = await client.get("/tournament/550e8400-e29b-41d4-a716-446655440000")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
