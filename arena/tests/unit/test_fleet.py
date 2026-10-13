import pytest

from app.domain import fleet
from tests.conftest import VALID_FLEET


def replace(ship_index: int, new_ship: list[str]) -> list[list[str]]:
    ships = [list(ship) for ship in VALID_FLEET]
    ships[ship_index] = new_ship
    return ships


def test_valid_fleet_is_accepted() -> None:
    cells = fleet.validate(VALID_FLEET)

    assert sorted(map(len, cells), reverse=True) == fleet.FLEET_SIZES


def test_ship_order_and_cell_order_do_not_matter() -> None:
    ships = [list(reversed(ship)) for ship in reversed(VALID_FLEET)]

    fleet.validate(ships)


def test_missing_ship_is_rejected() -> None:
    with pytest.raises(ValueError, match="fleet composition"):
        fleet.validate(VALID_FLEET[:-1])


def test_extra_ship_is_rejected() -> None:
    with pytest.raises(ValueError, match="fleet composition"):
        fleet.validate([*VALID_FLEET, ["J10"]])


def test_wrong_sizes_are_rejected() -> None:
    """Десять кораблей, но пятипалубный вместо четырёхпалубного."""
    with pytest.raises(ValueError, match="fleet composition"):
        fleet.validate(replace(0, ["A1", "A2", "A3", "A4", "A5"]))


def test_empty_ship_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a straight"):
        fleet.validate(replace(9, []))


def test_cell_outside_the_board_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid coordinate"):
        fleet.validate(replace(9, ["K1"]))


def test_bent_ship_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a straight"):
        fleet.validate(replace(3, ["J9", "I10"]))


def test_ship_with_a_gap_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a straight"):
        fleet.validate(replace(3, ["J8", "J10"]))


def test_ship_with_a_repeated_cell_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a straight"):
        fleet.validate(replace(3, ["J9", "J9"]))


def test_overlapping_ships_are_rejected() -> None:
    with pytest.raises(ValueError, match="overlaps"):
        fleet.validate(replace(9, ["A1"]))


def test_ships_touching_by_side_are_rejected() -> None:
    with pytest.raises(ValueError, match="touches"):
        fleet.validate(replace(9, ["B1"]))


def test_ships_touching_by_corner_are_rejected() -> None:
    with pytest.raises(ValueError, match="touches"):
        fleet.validate(replace(9, ["B5"]))
