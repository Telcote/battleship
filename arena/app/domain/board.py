from app.domain.coordinates import Cell, parse
from app.protocol import ShotResult


class Board:
    """Фактическое поле одной стороны: то, что игрок обязан ответить на выстрел."""

    def __init__(self, ships: list[list[Cell]]) -> None:
        self._ships = [set(cells) for cells in ships]
        self._hits: set[Cell] = set()

    def shoot(self, coordinate: str) -> ShotResult:
        """Повторный выстрел в подбитую клетку — снова `hit`, по потопленному кораблю — `killed`."""
        cell = parse(coordinate)
        ship = next((cells for cells in self._ships if cell in cells), None)
        if ship is None:
            return "miss"
        self._hits.add(cell)
        return "killed" if ship <= self._hits else "hit"

    @property
    def defeated(self) -> bool:
        return all(ship <= self._hits for ship in self._ships)
