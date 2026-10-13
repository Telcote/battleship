BOARD_SIZE = 10
COLUMNS = "ABCDEFGHIJ"
_ROWS = {str(n) for n in range(1, BOARD_SIZE + 1)}

Cell = tuple[int, int]  # (col, row), оба 0..9


def parse(coordinate: str) -> Cell:
    """"D7" -> (3, 6). Бросает ValueError, если координата не по формату A1-J10."""
    column, row = coordinate[:1], coordinate[1:]
    if not column or column not in COLUMNS or row not in _ROWS:
        raise ValueError(f"invalid coordinate: {coordinate!r}")
    return COLUMNS.index(column), int(row) - 1


def halo(cells: list[Cell]) -> set[Cell]:
    """Все 8 соседей каждой клетки в пределах поля, без самих клеток."""
    around = {
        (col + dc, row + dr)
        for col, row in cells
        for dc in (-1, 0, 1)
        for dr in (-1, 0, 1)
        if 0 <= col + dc < BOARD_SIZE and 0 <= row + dr < BOARD_SIZE
    }
    return around - set(cells)
