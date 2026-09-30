"""Правила расстановки: прямые корабли 4-3-3-2-2-2-1-1-1-1 внутри поля, без касаний даже углами."""

from app.domain.coordinates import Cell, halo, parse

FLEET_SIZES = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]


def validate(ships: list[list[str]]) -> list[list[Cell]]:
    """Клетки кораблей, если расстановка по правилам. Иначе ValueError с первым нарушением."""
    parsed: list[list[Cell]] = []
    for ship in ships:
        try:
            cells = [parse(coordinate) for coordinate in ship]
        except ValueError as exc:
            raise ValueError(f"ship {ship}: {exc}") from exc
        if not _is_straight(cells):
            raise ValueError(f"ship {ship}: not a straight contiguous line")
        parsed.append(cells)

    sizes = sorted((len(cells) for cells in parsed), reverse=True)
    if sizes != FLEET_SIZES:
        raise ValueError(f"fleet composition: expected {FLEET_SIZES}, got {sizes}")

    owner: dict[Cell, int] = {}
    for index, cells in enumerate(parsed):
        for cell in cells:
            if cell in owner:
                raise ValueError(f"ship {ships[index]} overlaps ship {ships[owner[cell]]}")
            owner[cell] = index

    for index, cells in enumerate(parsed):
        for cell in halo(cells):
            if cell in owner:
                raise ValueError(f"ship {ships[index]} touches ship {ships[owner[cell]]}")

    return parsed


def _is_straight(cells: list[Cell]) -> bool:
    if len({col for col, _ in cells}) == 1:
        line = sorted(row for _, row in cells)
    elif len({row for _, row in cells}) == 1:
        line = sorted(col for col, _ in cells)
    else:
        return False
    return line == list(range(line[0], line[0] + len(line)))
