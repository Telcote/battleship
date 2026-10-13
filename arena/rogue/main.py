import asyncio
import json
import random
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

FLEET = [
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

TOUCHING_FLEET = [*FLEET[:-1], ["B5"]]

ALL_CELLS = [f"{column}{row}" for column in "ABCDEFGHIJ" for row in range(1, 11)]
SLOW_SECONDS = 1.5
CRASH_ON = 3

MODES = {
    "honest": "играет честно — контрольный прогон",
    "liar": "отвечает наоборот: попадание — «мимо», промах — «попал»",
    "nonsense": "отвечает на выстрел значением не из контракта",
    "slow": "отвечает на выстрел соперника дольше секунды",
    "drip": "отдаёт ответ по байту, растягивая его дольше секунды",
    "crash": f"падает с 500 на {CRASH_ON}-м выстреле соперника",
    "malformed": "называет свой выстрел в поле не по схеме",
    "touching": "выдаёт расстановку с касающимися кораблями",
    "garbage": "стреляет за пределы поля",
    "repeat": "стреляет в одну и ту же клетку",
}


@dataclass
class Session:
    mode: str
    shots: Iterator[str]
    hits: set[str] = field(default_factory=set)
    received: int = 0


class OpponentShot(BaseModel):
    coordinate: str


app = FastAPI(title="battleship-rogue")
sessions: dict[str, Session] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/modes")
async def modes() -> dict[str, str]:
    return MODES


@app.post("/{mode}/game", status_code=201)
async def start_game(mode: str) -> dict:
    if mode not in MODES:
        raise HTTPException(404, f"unknown mode {mode!r}")
    session_id = str(uuid.uuid4())
    sessions[session_id] = Session(mode, iter(random.sample(ALL_CELLS, len(ALL_CELLS))))
    ships = TOUCHING_FLEET if mode == "touching" else FLEET
    return {"session_id": session_id, "ships": [{"coordinates": ship} for ship in ships]}


@app.post("/{mode}/game/{session_id}/shot")
async def shot(mode: str, session_id: str) -> dict:
    session = _get(session_id)
    if mode == "garbage":
        return {"coordinate": "K11"}
    if mode == "repeat":
        return {"coordinate": "J10"}
    if mode == "malformed":
        return {"coord": next(session.shots)}
    return {"coordinate": next(session.shots)}


@app.post("/{mode}/game/{session_id}/shot/result")
async def shot_result(mode: str, session_id: str) -> dict:
    _get(session_id)
    return {"status": "accepted"}


@app.post("/{mode}/game/{session_id}/opponent-shot", response_model=None)
async def opponent_shot(
    mode: str, session_id: str, body: OpponentShot
) -> dict | JSONResponse | StreamingResponse:
    session = _get(session_id)
    session.received += 1
    if mode == "crash" and session.received >= CRASH_ON:
        return JSONResponse(status_code=500, content={"detail": "boom"})
    if mode == "slow":
        await asyncio.sleep(SLOW_SECONDS)

    result = _honest_answer(session, body.coordinate)
    if mode == "liar":
        result = "hit" if result == "miss" else "miss"
    if mode == "nonsense":
        result = "sunk"
    if mode == "drip":
        return StreamingResponse(_drip(json.dumps({"result": result})), media_type="application/json")
    return {"result": result}


@app.post("/{mode}/game/{session_id}/close")
async def close(mode: str, session_id: str) -> dict:
    if sessions.pop(session_id, None) is None:
        raise HTTPException(400, f"session {session_id} is already closed")
    return {"status": "closed"}


def _get(session_id: str) -> Session:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"session {session_id} not found")
    return session


def _honest_answer(session: Session, coordinate: str) -> str:
    for ship in FLEET:
        if coordinate in ship:
            session.hits.add(coordinate)
            return "killed" if all(cell in session.hits for cell in ship) else "hit"
    return "miss"


async def _drip(payload: str) -> AsyncIterator[bytes]:
    """Каждая пауза короче таймаута httpx на чтение — ловится только общим бюджетом."""
    for char in payload:
        yield char.encode()
        await asyncio.sleep(SLOW_SECONDS / len(payload))
