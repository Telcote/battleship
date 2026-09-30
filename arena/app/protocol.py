import uuid
from typing import Literal

from pydantic import BaseModel

ShotResult = Literal["miss", "hit", "killed"]


class ShipPlacement(BaseModel):
    coordinates: list[str]


# POST /game
class StartGameResponse(BaseModel):
    session_id: uuid.UUID
    ships: list[ShipPlacement]


# POST /game/{session_id}/shot
class ShotResponse(BaseModel):
    coordinate: str


# POST /game/{session_id}/shot/result
class ShotResultRequest(BaseModel):
    result: ShotResult


class AcceptedResponse(BaseModel):
    status: Literal["accepted"]


# POST /game/{session_id}/opponent-shot
class OpponentShotRequest(BaseModel):
    coordinate: str


class OpponentShotResponse(BaseModel):
    result: ShotResult


# POST /game/{session_id}/close
class CloseGameResponse(BaseModel):
    status: Literal["closed"]
