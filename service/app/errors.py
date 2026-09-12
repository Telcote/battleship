from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class GameError(Exception):
    """Базовый класс доменных ошибок игровой сессии."""


class SessionNotFound(GameError):
    """session_id не существует. Ручки 2, 3, 4, 5 → 404."""


class SessionClosed(GameError):
    """Сессия уже закрыта, игровые запросы к ней отклоняются. Ручки 2, 3, 4 → 410."""


class AlreadyClosed(GameError):
    """Повторное закрытие той же сессии. Ручка 5 → 400."""


class NotYourTurn(GameError):
    """Нарушена очерёдность хода (запрошен выстрел не в свой ход). Ручка 2 → 409."""


class OutOfSequence(GameError):
    """Результат выстрела пришёл, а выстрела не было. Ручка 3 → 409."""


class InvalidPlacement(GameError):
    """Расстановка не соответствует правилам. Внутренняя проверка генератора расстановки."""


class InvalidCoordinate(GameError):
    """Координата не по формату или уже обстреляна. Ручка 4 → 400."""


class InvalidShotResult(GameError):
    """Недопустимое значение result. Ручка 3 → 400."""


_STATUS_BY_ERROR: dict[type[GameError], int] = {
    SessionNotFound: status.HTTP_404_NOT_FOUND,
    SessionClosed: status.HTTP_410_GONE,
    AlreadyClosed: status.HTTP_400_BAD_REQUEST,
    NotYourTurn: status.HTTP_409_CONFLICT,
    OutOfSequence: status.HTTP_409_CONFLICT,
    InvalidPlacement: status.HTTP_400_BAD_REQUEST,
    InvalidCoordinate: status.HTTP_400_BAD_REQUEST,
    InvalidShotResult: status.HTTP_400_BAD_REQUEST,
}


def _validation_error_detail(exc: RequestValidationError) -> str:
    for error in exc.errors():
        inner = (error.get("ctx") or {}).get("error")
        if isinstance(inner, Exception):
            return str(inner)
    return "invalid request body"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GameError)
    async def game_error_handler(request: Request, exc: GameError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()

        if errors and errors[0]["loc"] and errors[0]["loc"][0] == "path":
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND, content={"detail": "session not found"}
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": _validation_error_detail(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
