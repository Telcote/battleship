import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GameSession
from app.services import game_service

SHIPS = [
    {"cells": ["A1", "A2", "A3", "A4"], "hits": []},
    {"cells": ["J1"], "hits": []},
]


@pytest_asyncio.fixture
async def game_id(session: AsyncSession) -> uuid.UUID:
    new_id = uuid.uuid4()
    await game_service.create_session(session, new_id, SHIPS)
    await session.commit()
    yield new_id
    stored = await session.get(GameSession, new_id)
    if stored is not None:
        await session.delete(stored)
        await session.commit()


async def test_opponent_shot_route_returns_result(client: AsyncClient, game_id: uuid.UUID) -> None:
    response = await client.post(f"/game/{game_id}/opponent-shot", json={"coordinate": "J1"})
    assert response.status_code == 200
    assert response.json() == {"result": "kill"}


async def test_opponent_shot_route_unknown_session_404(client: AsyncClient) -> None:
    missing_id = uuid.uuid4()
    response = await client.post(f"/game/{missing_id}/opponent-shot", json={"coordinate": "A1"})
    assert response.status_code == 404
    assert response.json() == {"detail": f"game {missing_id} not found"}


async def test_close_route_returns_status_closed(client: AsyncClient, game_id: uuid.UUID) -> None:
    response = await client.post(f"/game/{game_id}", json={"reason": "opponent_defeated"})
    assert response.status_code == 200
    assert response.json() == {"status": "closed"}


async def test_close_route_twice_returns_400(client: AsyncClient, game_id: uuid.UUID) -> None:
    await client.post(f"/game/{game_id}", json={"reason": "opponent_defeated"})
    response = await client.post(f"/game/{game_id}", json={"reason": "opponent_defeated"})
    assert response.status_code == 400


async def test_opponent_shot_route_invalid_coordinate_is_422(
    client: AsyncClient, game_id: uuid.UUID
) -> None:
    response = await client.post(f"/game/{game_id}/opponent-shot", json={"coordinate": "Z9"})
    assert response.status_code == 422
