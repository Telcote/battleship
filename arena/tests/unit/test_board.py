from app.domain import fleet
from app.domain.board import Board
from tests.conftest import VALID_FLEET


def make_board() -> Board:
    return Board(fleet.validate(VALID_FLEET))


def test_empty_cell_is_a_miss() -> None:
    assert make_board().shoot("J10") == "miss"


def test_ship_is_hit_until_its_last_cell() -> None:
    board = make_board()

    assert [board.shoot(cell) for cell in ["C1", "C2", "C3"]] == ["hit", "hit", "killed"]


def test_single_cell_ship_is_killed_at_once() -> None:
    assert make_board().shoot("G1") == "killed"


def test_repeated_shots_repeat_the_answer() -> None:
    board = make_board()
    board.shoot("A1")
    board.shoot("G3")

    assert board.shoot("A1") == "hit"
    assert board.shoot("G3") == "killed"
    assert board.shoot("J10") == "miss"


def test_fleet_is_defeated_only_when_every_cell_is_hit() -> None:
    board = make_board()
    cells = [cell for ship in VALID_FLEET for cell in ship]

    for cell in cells[:-1]:
        board.shoot(cell)
    assert not board.defeated

    board.shoot(cells[-1])
    assert board.defeated
