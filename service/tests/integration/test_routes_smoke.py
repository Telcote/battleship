import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import coordinates, placement
from app.models import GameSession

SHIPS = [
    {"cells": ["A1", "A2", "A3", "A4"], "hits": []},
    {"cells": ["J1"], "hits": []},
]


@pytest_asyncio.fixture
async def session_id(session: AsyncSession) -> uuid.UUID:
    new_id = uuid.uuid4()
    session.add(GameSession(id=new_id, status="active", turn="unknown", ships=SHIPS))
    await session.commit()
    yield new_id
    stored = await session.get(GameSession, new_id)
    if stored is not None:
        await session.delete(stored)
        await session.commit()


async def test_start_game_route_returns_session_id_and_valid_placement(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post("/game")
    assert response.status_code == 201

    body = response.json()
    created_id = uuid.UUID(body["session_id"])
    placement.validate([ship["coordinates"] for ship in body["ships"]])

    stored = await session.get(GameSession, created_id)
    assert stored is not None
    await session.delete(stored)
    await session.commit()


async def test_shot_route_returns_coordinate(client: AsyncClient, session_id: uuid.UUID) -> None:
    response = await client.post(f"/game/{session_id}/shot")
    assert response.status_code == 200

    coordinate = response.json()["coordinate"]
    assert coordinates.is_valid(coordinate)


async def test_shot_route_twice_without_result_is_409(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    await client.post(f"/game/{session_id}/shot")
    response = await client.post(f"/game/{session_id}/shot")
    assert response.status_code == 409


async def test_shot_result_route_accepts_result(client: AsyncClient, session_id: uuid.UUID) -> None:
    await client.post(f"/game/{session_id}/shot")
    response = await client.post(f"/game/{session_id}/shot/result", json={"result": "hit"})
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


async def test_shot_result_route_without_pending_shot_is_409(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    response = await client.post(f"/game/{session_id}/shot/result", json={"result": "hit"})
    assert response.status_code == 409


async def test_shot_result_route_invalid_result_is_400(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    response = await client.post(f"/game/{session_id}/shot/result", json={"result": "sunk"})
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid result: 'sunk'"}


async def test_opponent_shot_route_returns_result(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    response = await client.post(f"/game/{session_id}/opponent-shot", json={"coordinate": "J1"})
    assert response.status_code == 200
    assert response.json() == {"result": "killed"}


async def test_opponent_shot_route_unknown_session_404(client: AsyncClient) -> None:
    missing_id = uuid.uuid4()
    response = await client.post(f"/game/{missing_id}/opponent-shot", json={"coordinate": "A1"})
    assert response.status_code == 404
    assert response.json() == {"detail": f"session {missing_id} not found"}


async def test_shot_route_unknown_session_404(client: AsyncClient) -> None:
    missing_id = uuid.uuid4()
    response = await client.post(f"/game/{missing_id}/shot")
    assert response.status_code == 404
    assert response.json() == {"detail": f"session {missing_id} not found"}


async def test_shot_result_route_unknown_session_404(client: AsyncClient) -> None:
    missing_id = uuid.uuid4()
    response = await client.post(f"/game/{missing_id}/shot/result", json={"result": "hit"})
    assert response.status_code == 404
    assert response.json() == {"detail": f"session {missing_id} not found"}


async def test_close_route_unknown_session_404(client: AsyncClient) -> None:
    missing_id = uuid.uuid4()
    response = await client.post(f"/game/{missing_id}/close")
    assert response.status_code == 404
    assert response.json() == {"detail": f"session {missing_id} not found"}


async def test_route_with_malformed_session_id_is_404(client: AsyncClient) -> None:
    # Не-UUID в пути — «сессия не найдена», а не 422: кода 422 в контракте нет.
    response = await client.post("/game/not-a-uuid/opponent-shot", json={"coordinate": "A1"})
    assert response.status_code == 404


async def test_opponent_shot_route_invalid_coordinate_is_400(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    response = await client.post(f"/game/{session_id}/opponent-shot", json={"coordinate": "Z9"})
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid coordinate: 'Z9'"}


async def test_opponent_shot_route_malformed_body_is_400(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    # Тело не по схеме — тоже 400: 422 контракт не предусматривает ни у одной ручки.
    response = await client.post(f"/game/{session_id}/opponent-shot", json={})
    assert response.status_code == 400


async def test_closed_session_rejects_game_requests_with_410(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    await client.post(f"/game/{session_id}/close")

    for response in (
        await client.post(f"/game/{session_id}/shot"),
        await client.post(f"/game/{session_id}/shot/result", json={"result": "miss"}),
        await client.post(f"/game/{session_id}/opponent-shot", json={"coordinate": "A1"}),
    ):
        assert response.status_code == 410


async def test_close_route_returns_status_closed(
    client: AsyncClient, session_id: uuid.UUID
) -> None:
    response = await client.post(f"/game/{session_id}/close")
    assert response.status_code == 200
    assert response.json() == {"status": "closed"}


async def test_close_route_twice_returns_400(client: AsyncClient, session_id: uuid.UUID) -> None:
    await client.post(f"/game/{session_id}/close")
    response = await client.post(f"/game/{session_id}/close")
    assert response.status_code == 400
