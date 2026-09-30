"""HTTP-клиент одного сервиса-игрока: пять ручек контракта и ничего больше.

Беда на транспорте — не тот код ответа, тело не по схеме — превращается в
`PlayerUnavailable`, просрочка — в `PlayerTimeout`. Нарушения правил (кривая расстановка,
ложный результат) сюда не относятся: их ловит судья, у него есть картина партии.
"""

import asyncio
import uuid
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app import protocol
from app.config import settings
from app.errors import PlayerTimeout, PlayerUnavailable

Model = TypeVar("Model", bound=BaseModel)


class PlayerClient:
    def __init__(self, address: str, base_url: str, http: httpx.AsyncClient) -> None:
        self.address = address
        self.base_url = base_url.rstrip("/")
        self._http = http

    async def start_game(self) -> protocol.StartGameResponse:
        """Ручка 1. Возвращает session_id и расстановку — дальше её проверяет судья."""
        return await self._post("/game", 201, protocol.StartGameResponse)

    async def ask_shot(self, session_id: uuid.UUID) -> str:
        """Ручка 2. Координата, куда игрок хочет стрелять."""
        response = await self._post(f"/game/{session_id}/shot", 200, protocol.ShotResponse)
        return response.coordinate

    async def send_shot_result(self, session_id: uuid.UUID, result: str) -> None:
        """Ручка 3. Сообщаем исход выстрела тому, кто стрелял. Координата не передаётся."""
        await self._post(
            f"/game/{session_id}/shot/result",
            200,
            protocol.AcceptedResponse,
            json={"result": result},
        )

    async def send_opponent_shot(self, session_id: uuid.UUID, coordinate: str) -> str:
        """Ручка 4. Отдаём выстрел соперника и получаем результат по его флоту."""
        response = await self._post(
            f"/game/{session_id}/opponent-shot",
            200,
            protocol.OpponentShotResponse,
            json={"coordinate": coordinate},
        )
        return response.result

    async def close_game(self, session_id: uuid.UUID) -> None:
        """Ручка 5. Закрываем сессию; повторное закрытие по контракту — 400."""
        await self._post(f"/game/{session_id}/close", 200, protocol.CloseGameResponse)

    async def _post(
        self,
        path: str,
        expected_status: int,
        model: type[Model],
        json: dict[str, Any] | None = None,
    ) -> Model:
        # Таймаут httpx считается по фазам (connect, read между порциями байтов...), а бюджет
        # контракта — на весь ответ целиком, поэтому поверх него общий asyncio.timeout.
        try:
            async with asyncio.timeout(settings.player_timeout):
                response = await self._http.post(f"{self.base_url}{path}", json=json)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise PlayerTimeout(
                self.address, f"POST {path} took longer than {settings.player_timeout}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise PlayerUnavailable(self.address, f"POST {path} failed: {exc}") from exc

        if response.status_code != expected_status:
            raise PlayerUnavailable(
                self.address,
                f"POST {path} returned {response.status_code}, expected {expected_status}",
            )

        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise PlayerUnavailable(self.address, f"POST {path} returned malformed body: {exc}") from exc
