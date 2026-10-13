import asyncio
import random
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest_asyncio
from httpx import AsyncClient, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import placement
from app.models import GameSession, Shot

GAMES = 20
BUDGET_SECONDS = 1.0
FLEET_CELLS = sum(placement.FLEET_SIZES)
ALL_CELLS = [f"{col}{row}" for row in range(1, 11) for col in "ABCDEFGHIJ"]


class TimedClient:
    """Обёртка над клиентом: запоминает, сколько шёл каждый запрос."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client
        self.latencies: list[tuple[str, float]] = []

    async def post(self, path: str, json: dict | None = None) -> Response:
        started = time.perf_counter()
        response = await self._client.post(path, json=json)
        self.latencies.append((path, time.perf_counter() - started))
        return response


@dataclass
class GameRecord:
    session_id: uuid.UUID
    incoming: list[str] = field(default_factory=list)
    outgoing: list[str] = field(default_factory=list)


def honest_answer(ships: list[set[str]], hits: set[str], cell: str) -> str:
    ship = next((cells for cells in ships if cell in cells), None)
    if ship is None:
        return "miss"
    hits.add(cell)
    return "killed" if ship <= hits else "hit"


@pytest_asyncio.fixture
async def created(session: AsyncSession) -> AsyncIterator[list[uuid.UUID]]:
    ids: list[uuid.UUID] = []
    yield ids
    if ids:
        await session.execute(delete(GameSession).where(GameSession.id.in_(ids)))
        await session.commit()


async def start(client: AsyncClient | TimedClient, created: list[uuid.UUID]) -> dict:
    response = await client.post("/game")
    assert response.status_code == 201
    body = response.json()
    created.append(uuid.UUID(body["session_id"]))
    return body


async def play_game(
    client: TimedClient, created: list[uuid.UUID], rng: random.Random
) -> GameRecord:

    body = await start(client, created)
    record = GameRecord(uuid.UUID(body["session_id"]))
    ships = [set(ship["coordinates"]) for ship in body["ships"]]
    placement.validate([sorted(ship) for ship in ships])

    decks = sorted(cell for ship in ships for cell in ship)
    water = sorted(cell for cell in ALL_CELLS if not any(cell in ship for ship in ships))
    rng.shuffle(decks)
    rng.shuffle(water)

    hits: set[str] = set()
    kills = 0
    base = f"/game/{record.session_id}"
    for deck, empty in zip(decks, water):
        response = await client.post(f"{base}/shot")
        assert response.status_code == 200, response.text
        record.outgoing.append(response.json()["coordinate"])

        response = await client.post(f"{base}/shot/result", json={"result": "miss"})
        assert response.status_code == 200, response.text

        for cell in (deck, empty):
            response = await client.post(f"{base}/opponent-shot", json={"coordinate": cell})
            assert response.status_code == 200, response.text
            answer = response.json()["result"]
            assert answer == honest_answer(ships, hits, cell), (
                f"session {record.session_id}: wrong answer to {cell}"
            )
            kills += answer == "killed"
            record.incoming.append(cell)

    assert kills == len(placement.FLEET_SIZES)
    return record


async def test_parallel_games_isolated(
    request_client: AsyncClient, session: AsyncSession, created: list[uuid.UUID]
) -> None:
    client = TimedClient(request_client)

    records = await asyncio.gather(
        *(play_game(client, created, random.Random(seed)) for seed in range(GAMES))
    )

    session.expire_all()
    for record in records:
        stored = await session.get(GameSession, record.session_id)
        assert stored is not None
        assert stored.own_hits == FLEET_CELLS
        assert stored.pending_shot is None
        assert all(sorted(ship["hits"]) == sorted(ship["cells"]) for ship in stored.ships)

        shots = (
            await session.execute(
                select(Shot).where(Shot.session_id == record.session_id).order_by(Shot.seq)
            )
        ).scalars().all()
        assert [shot.seq for shot in shots] == list(range(1, len(shots) + 1))
        assert [s.coordinate for s in shots if s.direction == "incoming"] == record.incoming
        assert [s.coordinate for s in shots if s.direction == "outgoing"] == record.outgoing
        assert len(set(record.outgoing)) == len(record.outgoing), "our shots repeat"

    closes = await asyncio.gather(
        *(client.post(f"/game/{record.session_id}/close") for record in records)
    )
    assert [response.status_code for response in closes] == [200] * GAMES
    repeated = await asyncio.gather(
        *(client.post(f"/game/{record.session_id}/close") for record in records)
    )
    assert [response.status_code for response in repeated] == [400] * GAMES

    path, worst = max(client.latencies, key=lambda item: item[1])
    assert worst < BUDGET_SECONDS, (
        f"{path} took {worst:.3f}s with {GAMES} parallel games "
        f"({len(client.latencies)} requests)"
    )


async def test_racing_shot_requests_produce_exactly_one_shot(
    request_client: AsyncClient, session: AsyncSession, created: list[uuid.UUID]
) -> None:
    body = await start(request_client, created)
    session_id = body["session_id"]

    responses = await asyncio.gather(
        *(request_client.post(f"/game/{session_id}/shot") for _ in range(5))
    )

    assert sorted(response.status_code for response in responses) == [200, 409, 409, 409, 409]
    winner = next(response for response in responses if response.status_code == 200)

    session.expire_all()
    stored = await session.get(GameSession, uuid.UUID(session_id))
    assert stored.pending_shot == winner.json()["coordinate"]
    shots = (
        await session.execute(select(Shot).where(Shot.session_id == uuid.UUID(session_id)))
    ).scalars().all()
    assert len(shots) == 1


async def test_racing_opponent_shots_at_one_cell_are_counted_once(
    request_client: AsyncClient, session: AsyncSession, created: list[uuid.UUID]
) -> None:
    body = await start(request_client, created)
    session_id = body["session_id"]
    deck = body["ships"][0]["coordinates"][0]

    responses = await asyncio.gather(
        *(
            request_client.post(f"/game/{session_id}/opponent-shot", json={"coordinate": deck})
            for _ in range(5)
        )
    )

    assert sorted(response.status_code for response in responses) == [200, 400, 400, 400, 400]

    session.expire_all()
    stored = await session.get(GameSession, uuid.UUID(session_id))
    assert stored.own_hits == 1
    shots = (
        await session.execute(select(Shot).where(Shot.session_id == uuid.UUID(session_id)))
    ).scalars().all()
    assert [shot.coordinate for shot in shots] == [deck]
