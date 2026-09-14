import random

import pytest

from app.domain import placement

VALID_FLEET = [
    ["A1", "A2", "A3", "A4"],
    ["C1", "C2", "C3"],
    ["E1", "E2", "E3"],
    ["G1", "G2"],
    ["G4", "G5"],
    ["G7", "G8"],
    ["A6"],
    ["A8"],
    ["A10"],
    ["C10"],
]


def test_valid_fleet_passes() -> None:
    placement.validate(VALID_FLEET)


def test_wrong_ship_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="expected 10 ships, got 9"):
        placement.validate(VALID_FLEET[:-1])


def test_wrong_fleet_composition_is_rejected() -> None:
    # неправильный состав
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[1] = ["C1", "C2", "C3", "C4"]
    with pytest.raises(ValueError, match="fleet composition mismatch"):
        placement.validate(fleet)


def test_ship_not_in_a_straight_line_is_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["G1", "H2"]  # диагональ вместо прямой
    with pytest.raises(ValueError, match="not a straight line"):
        placement.validate(fleet)


def test_ship_with_gap_is_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["G1", "G3"]  # прямая, но с разрывом
    with pytest.raises(ValueError, match="not contiguous"):
        placement.validate(fleet)


def test_ship_with_duplicate_cells_is_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["G1", "G1"]
    with pytest.raises(ValueError, match="duplicate cells"):
        placement.validate(fleet)


def test_ship_with_invalid_coordinate_is_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["G1", "Z9"]
    with pytest.raises(ValueError, match="invalid coordinate"):
        placement.validate(fleet)


def test_empty_ship_is_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = []
    with pytest.raises(ValueError, match="no cells"):
        placement.validate(fleet)


def test_overlapping_ships_are_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["A1", "A2"]  # совпадает с клетками первого корабля
    with pytest.raises(ValueError, match="overlaps"):
        placement.validate(fleet)


def test_orthogonally_adjacent_ships_are_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["B1", "B2"]  # вплотную сбоку к A1-A4, без пересечения клеток
    with pytest.raises(ValueError, match="touches"):
        placement.validate(fleet)


def test_diagonally_adjacent_ships_are_rejected() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    # I2 и J3 соседи строго по диагонали
    fleet[3] = ["I1", "I2"]
    fleet[4] = ["J3", "J4"]
    with pytest.raises(ValueError, match="touches"):
        placement.validate(fleet)


def test_ships_one_cell_apart_are_accepted() -> None:
    fleet = [ship[:] for ship in VALID_FLEET]
    fleet[3] = ["C6", "C7"]
    placement.validate(fleet)


@pytest.mark.parametrize("seed", range(50))
def test_generate_always_produces_a_valid_fleet(seed: int) -> None:
    ships = placement.generate(random.Random(seed))
    placement.validate(ships)


def test_generate_is_deterministic_for_a_given_seed() -> None:
    first = placement.generate(random.Random(42))
    second = placement.generate(random.Random(42))
    assert first == second


def test_generate_places_ships_within_board_bounds() -> None:
    from app.domain import coordinates

    for seed in range(20):
        ships = placement.generate(random.Random(seed))
        for ship in ships:
            for cell in ship:
                assert coordinates.is_valid(cell)
