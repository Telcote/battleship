import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel

from app.domain import coordinates


def validate_coordinate(value: str) -> str:
    if coordinates.is_valid(value):
        return value
    raise ValueError(f"invalid coordinate: {value!r}")


Coordinate = Annotated[str, AfterValidator(validate_coordinate)]
ShotResult = Literal["miss", "hit", "kill"]


class ShipPlacement(BaseModel):
    coordinates: list[Coordinate]


# POST /game (сервис -> арена)
class StartGameRequest(BaseModel):
    game_id: uuid.UUID
    ships: list[ShipPlacement]


class StartGameResponse(BaseModel):
    is_firstshot: bool


# POST /game/{game_id}/shot (сервис -> арена)
class MakeShotRequest(BaseModel):
    coordinate: Coordinate


# POST /game/{game_id}/opponent-shot (арена -> сервис)
class OpponentShotRequest(BaseModel):
    coordinate: Coordinate


class OpponentShotResponse(BaseModel):
    result: ShotResult


# POST /game/{game_id}/shot/result (арена -> сервис)
class ShotResultRequest(BaseModel):
    coordinate: Coordinate
    result: ShotResult


# POST /game/{game_id} (арена -> сервис)
class CloseGameRequest(BaseModel):
    reason: str


class CloseGameResponse(BaseModel):
    status: Literal["closed"]


class ErrorResponse(BaseModel):
    detail: str
