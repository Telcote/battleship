from typing import ClassVar

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.log import EndReason


class ArenaError(Exception):
    """Базовый класс ошибок арены."""


class MatchNotFound(ArenaError):
    """match_id не существует. GET /match/{id} → 404."""


class TournamentNotFound(ArenaError):
    """tournament_id не существует. GET /tournament/{id} → 404."""


class InvalidMatchRequest(ArenaError):
    """Некорректная заявка: битый адрес, неразрешимый хост, оба участника — один сервис. → 400."""


class PlayerFault(ArenaError):
    """Игрок нарушил правила или контракт — матч отдаётся сопернику. `reason` уходит в вердикт."""

    reason: ClassVar[EndReason]

    def __init__(self, address: str, message: str) -> None:
        super().__init__(f"{address}: {message}")
        self.address = address


class PlayerUnavailable(PlayerFault):
    """Не ответил, ответил не тем кодом или телом не по схеме."""

    reason = "unavailable"


class PlayerTimeout(PlayerFault):
    """Не уложился в бюджет на ответ (`player_timeout`, по контракту 1 секунда)."""

    reason = "timeout"


class InvalidPlacement(PlayerFault):
    """Расстановка не по правилам: состав флота, форма, касания, выход за поле."""

    reason = "invalid_placement"


class InvalidShot(PlayerFault):
    """Недействительная координата выстрела: координата вне поля или уже обстрелена"""

    reason = "invalid_shot"


class Lie(PlayerFault):
    """Ответ на выстрел не совпал с выданной расстановкой."""

    reason = "lie"


_STATUS_BY_ERROR: dict[type[ArenaError], int] = {
    MatchNotFound: status.HTTP_404_NOT_FOUND,
    TournamentNotFound: status.HTTP_404_NOT_FOUND,
    InvalidMatchRequest: status.HTTP_400_BAD_REQUEST,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ArenaError)
    async def arena_error_handler(request: Request, exc: ArenaError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "invalid request body"},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
