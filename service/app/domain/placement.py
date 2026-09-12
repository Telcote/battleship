import random

from app.domain import coordinates
from app.domain.coordinates import Cell

FLEET_SIZES = sorted([4, 3, 3, 2, 2, 2, 1, 1, 1, 1], reverse=True)
MAX_ATTEMPTS_PER_SHIP = 200
MAX_RESTARTS = 200

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
    """Случайная расстановка с откатом. `rng` — для детерминированных тестов (фиксированный seed)."""
    rng = rng or random.Random()

    for _ in range(MAX_RESTARTS):
        placed: list[list[Cell]] = []
        occupied_halo: set[Cell] = set()

        if _try_place_fleet(rng, placed, occupied_halo):
            ships = [[coordinates.format(cell) for cell in cells] for cells in placed]
            validate(ships)
            return ships

    raise RuntimeError("failed to generate a valid placement")


def _try_place_fleet(
    rng: random.Random, placed: list[list[Cell]], occupied_halo: set[Cell]
) -> bool:
    for size in FLEET_SIZES:
        cells = _try_place_ship(rng, size, occupied_halo)
        if cells is None:
            return False
        placed.append(cells)
        occupied_halo |= coordinates.halo(cells) | set(cells)
    return True


def _try_place_ship(
    rng: random.Random, size: int, occupied_halo: set[Cell]
) -> list[Cell] | None:
    for _ in range(MAX_ATTEMPTS_PER_SHIP):
        horizontal = rng.choice([True, False])
        if horizontal:
            col = rng.randint(0, coordinates.BOARD_SIZE - size)
            row = rng.randint(0, coordinates.BOARD_SIZE - 1)
            cells = [(col + i, row) for i in range(size)]
        else:
            col = rng.randint(0, coordinates.BOARD_SIZE - 1)
            row = rng.randint(0, coordinates.BOARD_SIZE - size)
            cells = [(col, row + i) for i in range(size)]

        if not any(cell in occupied_halo for cell in cells):
            return cells

    return None
