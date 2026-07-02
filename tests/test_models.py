# tests/test_models.py
from src.models import Appearance, Fixture, Player, Card


def _player():
    return Player(
        slug="lionel-messi",
        display_name="Lionel Messi",
        club="Inter Miami",
        recent_appearances=[Appearance(so5_score=72.0, minutes_played=90, started=True)],
        upcoming_fixtures=[Fixture(opponent="Orlando", difficulty=0.4)],
    )


def test_card_holds_player_and_price():
    card = Card(
        slug="card-123",
        player=_player(),
        scarcity="limited",
        price_eur=25.0,
        recent_sale_prices_eur=[24.0, 26.0, 25.5],
    )
    assert card.player.display_name == "Lionel Messi"
    assert card.scarcity == "limited"
    assert card.price_eur == 25.0
    assert card.recent_sale_prices_eur[-1] == 25.5
    assert card.player.recent_appearances[0].so5_score == 72.0
    assert card.player.upcoming_fixtures[0].difficulty == 0.4
