from typing import Literal, TypedDict

ShotResult = Literal["miss", "hit", "kill"]


class ShipState(TypedDict):
    cells: list[str]
    hits: list[str]


def apply_opponent_shot(ships: list[ShipState], coordinate: str) -> ShotResult:
    """Мутирует `hits` найденного корабля и возвращает результат выстрела."""
    for ship in ships:
        if coordinate not in ship["cells"]:
            continue
        if coordinate not in ship["hits"]:
            ship["hits"].append(coordinate)
        return "kill" if len(ship["hits"]) == len(ship["cells"]) else "hit"
    return "miss"


def is_fleet_defeated(ships: list[ShipState]) -> bool:
    return all(len(ship["hits"]) == len(ship["cells"]) for ship in ships)
