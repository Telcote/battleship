"""Судья: сверяет всё, что сообщают игроки, с правилами и фактическим полем.

Про HTTP не знает — получает уже разобранные ответы. Нарушение превращается в
`PlayerFault` с адресом виновника, и цикл матча отдаёт победу сопернику.
"""

from app.domain import coordinates, fleet
from app.domain.board import Board
from app.errors import InvalidPlacement, InvalidShot, Lie


def accept_placement(address: str, ships: list[list[str]]) -> Board:
    try:
        return Board(fleet.validate(ships))
    except ValueError as exc:
        raise InvalidPlacement(address, str(exc)) from exc


def accept_shot(address: str, coordinate: str, fired: set[str]) -> None:
    try:
        coordinates.parse(coordinate)
    except ValueError as exc:
        raise InvalidShot(address, str(exc)) from exc
    if coordinate in fired:
        raise InvalidShot(address, f"cell {coordinate} already fired at")


def accept_result(address: str, board: Board, coordinate: str, reported: str) -> None:
    actual = board.shoot(coordinate)
    if reported != actual:
        raise Lie(address, f"answered {reported!r} to {coordinate}, actual result is {actual!r}")
