import random

from app.domain import coordinates, placement, targeting


def test_never_repeats_a_fired_cell() -> None:
    rng = random.Random(1)
    shots: list[tuple[str, str]] = []
    for _ in range(100):
        coordinate = targeting.choose(shots, rng)
        assert coordinate not in {c for c, _ in shots}
        shots.append((coordinate, "miss"))


def test_after_single_hit_next_shot_is_a_neighbour() -> None:
    rng = random.Random(2)
    shots = [("E5", "hit")]
    coordinate = targeting.choose(shots, rng)
    assert coordinates.parse(coordinate) in coordinates.neighbours(coordinates.parse("E5"))


def test_after_two_collinear_hits_continues_the_line() -> None:
    rng = random.Random(3)
    shots = [("E5", "hit"), ("E6", "hit")]
    coordinate = targeting.choose(shots, rng)
    assert coordinate in ("E4", "E7")


def test_after_kill_does_not_shoot_into_the_halo() -> None:
    rng = random.Random(4)
    shots = [("J1", "kill")]
    for _ in range(30):
        coordinate = targeting.choose(shots, rng)
        assert coordinate not in ("I1", "I2", "J2")
        shots.append((coordinate, "miss"))


def test_sinks_any_generated_fleet_within_bounded_shots() -> None:
    for seed in range(20):
        rng = random.Random(seed)
        ships = placement.generate(random.Random(seed + 1000))
        ship_by_cell = {cell: index for index, ship in enumerate(ships) for cell in ship}
        sunk = [False] * len(ships)
        hits_by_ship: list[set[str]] = [set() for _ in ships]
        shots: list[tuple[str, str]] = []

        for _ in range(100):
            if all(sunk):
                break
            coordinate = targeting.choose(shots, rng)
            ship_index = ship_by_cell.get(coordinate)
            if ship_index is None:
                shots.append((coordinate, "miss"))
                continue
            hits_by_ship[ship_index].add(coordinate)
            if len(hits_by_ship[ship_index]) == len(ships[ship_index]):
                sunk[ship_index] = True
                shots.append((coordinate, "kill"))
            else:
                shots.append((coordinate, "hit"))

        assert all(sunk), f"seed {seed}: fleet not sunk within 100 shots"
