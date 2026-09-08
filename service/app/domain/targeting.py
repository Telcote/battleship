import random
from collections import Counter
from functools import cache

from app.domain import coordinates, placement
from app.domain.board import ShotResult
from app.domain.coordinates import Cell

Placement = frozenset[Cell]


def choose(shots: list[tuple[str, ShotResult]], rng: random.Random | None = None) -> str:
    """Следующая координата выстрела. `shots` — свои выстрелы в любом порядке."""
    rng = rng or random.Random()

    fired: set[Cell] = set()
    misses: set[Cell] = set()
    hits: set[Cell] = set()
    kills: set[Cell] = set()
    for coordinate, result in shots:
        cell = coordinates.parse(coordinate)
        fired.add(cell)
        if result == "miss":
            misses.add(cell)
        else:
            hits.add(cell)
            if result == "kill":
                kills.add(cell)

    remaining_sizes = Counter(placement.FLEET_SIZES)
    sunk_cells: set[Cell] = set()
    unresolved: list[Placement] = []
    for component in _connected_components(hits):
        if component & kills:
            sunk_cells |= component
            remaining_sizes[len(component)] -= 1
        else:
            unresolved.append(component)

    blocked = misses | sunk_cells | coordinates.halo(list(sunk_cells))
    density = _density_map(remaining_sizes, blocked, unresolved)

    best = max((count for cell, count in density.items() if cell not in fired), default=0)
    top = sorted(cell for cell, count in density.items() if count == best and cell not in fired)
    if not top:
        # Выстрелы уже покрыли все клетки, куда влезает хоть один корабль: добиваем оставшееся.
        top = sorted(set(_all_cells()) - fired - blocked) or sorted(set(_all_cells()) - fired)
    return coordinates.format(rng.choice(top))


def _density_map(
    remaining_sizes: Counter[int], blocked: set[Cell], unresolved: list[Placement]
) -> Counter[Cell]:
    """Сколько положений ещё не потопленных кораблей проходит через каждую клетку.
    Одинаковые размеры считаются один раз и умножаются на количество таких кораблей."""
    density: Counter[Cell] = Counter()
    for size, ships_left in remaining_sizes.items():
        if ships_left <= 0:
            continue
        for cells in _candidates(size, unresolved):
            if cells & blocked:
                continue
            for cell in cells:
                density[cell] += ships_left
    return density


def _candidates(size: int, unresolved: list[Placement]) -> tuple[Placement, ...]:
    """Положения корабля длины `size`, достойные рассмотрения.

    Раненый, но не потопленный корабль — его клетки все известны, значит любое положение,
    которое его достраивает, обязано включать их целиком, а не одну. Поэтому вместо перебора
    всех положений берём только те, что проходят через опорную клетку компоненты."""
    if not unresolved:
        return _placements(size)

    seen: set[Placement] = set()
    for component in unresolved:
        anchor = next(iter(component))
        for cells in _placements_through(size).get(anchor, ()):
            if component <= cells:
                seen.add(cells)
    return tuple(seen)


@cache
def _placements(size: int) -> tuple[Placement, ...]:
    """Все положения корабля длины `size` на пустом поле, обеими ориентациями."""
    board = coordinates.BOARD_SIZE
    horizontal = [
        frozenset((col + i, row) for i in range(size))
        for row in range(board)
        for col in range(board - size + 1)
    ]
    if size == 1:
        return tuple(horizontal)
    vertical = [
        frozenset((col, row + i) for i in range(size))
        for col in range(board)
        for row in range(board - size + 1)
    ]
    return tuple(horizontal + vertical)


@cache
def _placements_through(size: int) -> dict[Cell, tuple[Placement, ...]]:
    """Клетка -> положения корабля длины `size`, которые её накрывают."""
    index: dict[Cell, list[Placement]] = {}
    for cells in _placements(size):
        for cell in cells:
            index.setdefault(cell, []).append(cells)
    return {cell: tuple(placements) for cell, placements in index.items()}


@cache
def _all_cells() -> tuple[Cell, ...]:
    board = coordinates.BOARD_SIZE
    return tuple((col, row) for col in range(board) for row in range(board))


def _connected_components(cells: set[Cell]) -> list[Placement]:
    """Компоненты связности по стороне. Корабли не касаются друг друга даже углами
    (см. placement.py), поэтому каждая компонента — это ровно один настоящий корабль,
    полностью или частично простреленный."""
    remaining = set(cells)
    components: list[Placement] = []
    while remaining:
        stack = [remaining.pop()]
        component = set(stack)
        while stack:
            for neighbour in coordinates.neighbours(stack.pop()):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    component.add(neighbour)
                    stack.append(neighbour)
        components.append(frozenset(component))
    return components
