import uuid

import pytest

from app.errors import MatchNotFound
from app.services.log import Player
from app.services.storage import MatchStorage, find_match, tournaments

PLAYERS = [Player("http://alpha", "alpha:80"), Player("http://bravo", "bravo:80")]


def test_evicted_tournament_match_is_still_found() -> None:
    """Партия лежит только в турнире — как после вытеснения из реестра матчей."""
    log = MatchStorage().create(PLAYERS)
    tournament = tournaments.create(PLAYERS, games_per_pair=1)
    tournament.matches.append(log)

    assert find_match(log.id) is log


def test_unknown_match_is_not_found() -> None:
    with pytest.raises(MatchNotFound):
        find_match(uuid.uuid4())
