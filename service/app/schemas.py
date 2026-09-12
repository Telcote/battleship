import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel

from app.domain import coordinates


def validate_coordinate(value: str) -> str:
    if coordinates.is_valid(value):
        return value
    raise ValueError(f"invalid coordinate: {value!r}")


Coordinate = Annotated[str, AfterValidator(validate_coordinate)]
ShotResult = Literal["miss", "hit", "killed"]


class ShipPlacement(BaseModel):
    coordinates: list[Coordinate]


# POST /game (арена -> сервис)
class StartGameResponse(BaseModel):
    session_id: uuid.UUID
    ships: list[ShipPlacement]


# POST /game/{session_id}/shot (арена -> сервис)
class ShotResponse(BaseModel):
    coordinate: str


# POST /game/{session_id}/shot/result (арена -> сервис)
class ShotResultRequest(BaseModel):
    # тут специально str, а не Literal — иначе pydantic сам отгрызёт кривой result
    # своим 422, а нам надо, чтобы за это отвечал сервис и отдавал 400
    result: str


class AcceptedResponse(BaseModel):
    status: Literal["accepted"]


# POST /game/{session_id}/opponent-shot (арена -> сервис)
class OpponentShotRequest(BaseModel):
    coordinate: Coordinate


class OpponentShotResponse(BaseModel):
    result: ShotResult


# POST /game/{session_id}/close (арена -> сервис)
class CloseGameResponse(BaseModel):
    status: Literal["closed"]


class ErrorResponse(BaseModel):
    detail: str
