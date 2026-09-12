BOARD_SIZE = 10
COLUMNS = "ABCDEFGHIJ"
_ROWS = {str(n) for n in range(1, BOARD_SIZE + 1)}

Cell = tuple[int, int]  # (col, row), оба 0..9


def parse(coordinate: str) -> Cell:
    """"D7" -> (3, 6). Бросает ValueError, если координата не по формату A1-J10."""
    column, row = coordinate[:1], coordinate[1:]
    if column not in COLUMNS or row not in _ROWS:
        raise ValueError(f"invalid coordinate: {coordinate!r}")
    return COLUMNS.index(column), int(row) - 1


def format(cell: Cell) -> str:
    """(3, 6) -> "D7"."""
    col, row = cell
    return f"{COLUMNS[col]}{row + 1}"


def is_valid(coordinate: str) -> bool:
    try:
        parse(coordinate)
    except ValueError:
        return False
    return True


def neighbours(cell: Cell) -> list[Cell]:
    """До 4 соседей по стороне, отфильтрованных по границам поля."""
    col, row = cell
    candidates = [(col - 1, row), (col + 1, row), (col, row - 1), (col, row + 1)]
    return [(c, r) for c, r in candidates if 0 <= c < BOARD_SIZE and 0 <= r < BOARD_SIZE]


def halo(cells: list[Cell]) -> set[Cell]:
    """Ореол вокруг набора клеток (все 8 соседей каждой), включая границы, без самих cells."""
    cell_set = set(cells)
    result: set[Cell] = set()
    for col, row in cells:
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                c, r = col + dc, row + dr
                if 0 <= c < BOARD_SIZE and 0 <= r < BOARD_SIZE:
                    result.add((c, r))
    return result - cell_set
