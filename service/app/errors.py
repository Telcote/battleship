from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class GameError(Exception):
    """Базовый класс доменных ошибок игровой сессии."""


class SessionNotFound(GameError):
    """game_id не существует. Ручки 2, 3, 4, 5 → 404."""


class SessionAlreadyExists(GameError):
    """Сессия с таким game_id уже создана. Ручка 1 → 409."""


class SessionClosed(GameError):
    """Сессия уже закрыта, игровые запросы к ней отклоняются. Ручки 2, 3, 4 → 410."""


class AlreadyClosed(GameError):
    """Повторное закрытие той же сессии. Ручка 5 → 400."""


class NotYourTurn(GameError):
    """Нарушена очерёдность хода. Ручки 2, 4 → 409."""


class InvalidPlacement(GameError):
    """Расстановка не соответствует правилам. Ручка 1 → 400."""


class InvalidCoordinate(GameError):
    """Координата не по формату или уже обстреляна. Ручки 2, 3 → 400."""


class InvalidShotResult(GameError):
    """Недопустимый result или координата не совпадает с ожидаемым выстрелом. Ручка 4 → 400."""


_STATUS_BY_ERROR: dict[type[GameError], int] = {
    SessionNotFound: status.HTTP_404_NOT_FOUND,
    SessionAlreadyExists: status.HTTP_409_CONFLICT,
    SessionClosed: status.HTTP_410_GONE,
    AlreadyClosed: status.HTTP_400_BAD_REQUEST,
    NotYourTurn: status.HTTP_409_CONFLICT,
    InvalidPlacement: status.HTTP_400_BAD_REQUEST,
    InvalidCoordinate: status.HTTP_400_BAD_REQUEST,
    InvalidShotResult: status.HTTP_400_BAD_REQUEST,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GameError)
    async def game_error_handler(request: Request, exc: GameError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
