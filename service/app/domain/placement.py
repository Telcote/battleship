import random
from functools import cache

from app.domain import coordinates
from app.domain.coordinates import Cell

FLEET_SIZES = sorted([4, 3, 3, 2, 2, 2, 1, 1, 1, 1], reverse=True)
MAX_RESTARTS = 200
LAYOUT_SAMPLES = 200

Ship = list[str]


def validate(ships: list[Ship]) -> None:
    """Бросает ValueError с описанием первого найденного нарушения, иначе не возвращает ничего."""
    if len(ships) != len(FLEET_SIZES):
        raise ValueError(f"expected {len(FLEET_SIZES)} ships, got {len(ships)}")

    parsed: list[list[Cell]] = []
    for ship in ships:
        if not ship:
            raise ValueError("ship has no cells")
        try:
            cells = [coordinates.parse(c) for c in ship]
        except ValueError as exc:
            raise ValueError(f"ship {ship}: {exc}") from exc
        if len(set(cells)) != len(cells):
            raise ValueError(f"ship {ship}: duplicate cells")
        _validate_straight(ship, cells)
        parsed.append(cells)

    sizes = sorted((len(cells) for cells in parsed), reverse=True)
    if sizes != FLEET_SIZES:
        raise ValueError(f"fleet composition mismatch: expected {FLEET_SIZES}, got {sizes}")

    _validate_no_overlap_or_touch(ships, parsed)


def _validate_straight(ship: Ship, cells: list[Cell]) -> None:
    if len(cells) == 1:
        return
    cols = {c for c, _ in cells}
    rows = {r for _, r in cells}
    if len(cols) == 1:
        ordered = sorted(r for _, r in cells)
    elif len(rows) == 1:
        ordered = sorted(c for c, _ in cells)
    else:
        raise ValueError(f"ship {ship}: not a straight line")
    if ordered != list(range(ordered[0], ordered[0] + len(ordered))):
        raise ValueError(f"ship {ship}: cells not contiguous")


def _validate_no_overlap_or_touch(ships: list[Ship], parsed: list[list[Cell]]) -> None:
    occupied: dict[Cell, int] = {}
    for index, cells in enumerate(parsed):
        for cell in cells:
            if cell in occupied:
                raise ValueError(f"ship {ships[index]} overlaps ship {ships[occupied[cell]]}")
            occupied[cell] = index

    for index, cells in enumerate(parsed):
        for neighbour_cell in coordinates.halo(cells):
            owner = occupied.get(neighbour_cell)
            if owner is not None and owner != index:
                raise ValueError(f"ship {ships[index]} touches ship {ships[owner]}")


def generate(rng: random.Random | None = None) -> list[Ship]:
    """Расстановка по https://habr.com/en/articles/82221/: труднее всего найти однопалубник,
    поэтому крупные корабли прижаты к краю поля и оставляют однопалубникам как можно больше
    открытой воды. Равномерная расстановка, наоборот, ставит крупные ближе к центру — туда,
    куда охотник по плотности стреляет первым.

    `rng` — для детерминированных тестов (фиксированный seed)."""
    rng = rng or random.Random()

    for _ in range(MAX_RESTARTS):
        layout = _roomiest_border_layout(rng)
        if layout is None:
            continue
        placed, blocked = layout
        if _place_singles(rng, placed, blocked):
            ships = [[coordinates.format(cell) for cell in cells] for cells in placed]
            validate(ships)
            return ships

    raise RuntimeError("failed to generate a valid placement")


def _roomiest_border_layout(
    rng: random.Random,
) -> tuple[list[list[Cell]], set[Cell]] | None:
    """Из LAYOUT_SAMPLES случайных раскладок у края — одна из тех, что заняли меньше всего
    клеток (вместе с ореолом). Выбор среди равных случаен: расстановка не повторяется."""
    layouts = [
        layout for _ in range(LAYOUT_SAMPLES) if (layout := _border_layout(rng)) is not None
    ]
    if not layouts:
        return None
    least = min(len(blocked) for _, blocked in layouts)
    return rng.choice([layout for layout in layouts if len(layout[1]) == least])


def _border_layout(rng: random.Random) -> tuple[list[list[Cell]], set[Cell]] | None:
    placed: list[list[Cell]] = []
    blocked: set[Cell] = set()
    for size in FLEET_SIZES:
        if size == 1:
            break
        options = [cells for cells in _border_spots(size) if blocked.isdisjoint(cells)]
        if not options:
            return None
        cells = rng.choice(options)
        placed.append(cells)
        blocked |= coordinates.halo(cells) | set(cells)
    return placed, blocked


def _place_singles(rng: random.Random, placed: list[list[Cell]], blocked: set[Cell]) -> bool:
    """Однопалубники — в любую свободную клетку открытой воды."""
    for _ in range(FLEET_SIZES.count(1)):
        free = [cell for cell in _all_cells() if cell not in blocked]
        if not free:
            return False
        cell = rng.choice(free)
        placed.append([cell])
        blocked |= coordinates.halo([cell]) | {cell}
    return True


@cache
def _border_spots(size: int) -> tuple[list[Cell], ...]:
    """Положения корабля длины `size`, целиком лежащие в крайнем ряду или столбце."""
    last = coordinates.BOARD_SIZE - 1
    spots = []
    for start in range(coordinates.BOARD_SIZE - size + 1):
        for line in (0, last):
            spots.append([(start + i, line) for i in range(size)])
            spots.append([(line, start + i) for i in range(size)])
    return tuple(spots)


@cache
def _all_cells() -> tuple[Cell, ...]:
    board = coordinates.BOARD_SIZE
    return tuple((col, row) for col in range(board) for row in range(board))
