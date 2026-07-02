# tests/test_buy.py
from src.models import Appearance, Fixture, Player, Card
from src import buy


def _card(slug, price, scarcity, score, started=True, minutes=90):
    player = Player(
        slug=slug, display_name=slug.title(), club="Club",
        recent_appearances=[Appearance(score, minutes, started)],
        upcoming_fixtures=[Fixture("x", 0.5)],
    )
    return Card(slug=slug, player=player, scarcity=scarcity, price_eur=price,
                recent_sale_prices_eur=[price])


def test_value_score_is_points_per_euro():
    c = _card("a", price=10.0, scarcity="limited", score=50.0)  # projected 50
    assert buy.value_score(c) == 5.0


def test_value_score_zero_price_is_zero():
    c = _card("a", price=0.0, scarcity="limited", score=50.0)
    assert buy.value_score(c) == 0.0


def test_rank_drops_zero_price_cards():
    cards = [
        _card("real", 10.0, "limited", 50.0),
        _card("unpriced", 0.0, "limited", 50.0),  # no price -> dropped
    ]
    picks = buy.rank_buys(cards, 0, 100, "limited")
    assert [p.card.slug for p in picks] == ["real"]


def test_rank_drops_zero_form_cards():
    cards = [
        _card("scorer", 10.0, "limited", 50.0),
        _card("no-form", 10.0, "limited", 0.0),  # projected 0 -> dropped
    ]
    picks = buy.rank_buys(cards, 0, 100, "limited")
    assert [p.card.slug for p in picks] == ["scorer"]


def test_rank_filters_by_scarcity():
    cards = [
        _card("a", 10.0, "limited", 50.0),
        _card("b", 10.0, "rare", 50.0),
    ]
    picks = buy.rank_buys(cards, min_price=0, max_price=100, scarcity="limited")
    assert [p.card.slug for p in picks] == ["a"]


def test_rank_filters_by_price_range():
    cards = [
        _card("cheap", 5.0, "limited", 50.0),
        _card("inrange", 20.0, "limited", 50.0),
        _card("expensive", 500.0, "limited", 50.0),  # Yamal-style: over budget
    ]
    picks = buy.rank_buys(cards, min_price=10, max_price=100, scarcity="limited")
    assert [p.card.slug for p in picks] == ["inrange"]


def test_rank_sorts_by_value_desc_and_limits():
    cards = [
        _card("low", 50.0, "limited", 50.0),   # value 1.0
        _card("high", 10.0, "limited", 50.0),  # value 5.0
        _card("mid", 25.0, "limited", 50.0),   # value 2.0
    ]
    picks = buy.rank_buys(cards, 0, 100, "limited", limit=2)
    assert [p.card.slug for p in picks] == ["high", "mid"]
    assert len(picks) == 2


def test_pick_has_rationale():
    picks = buy.rank_buys([_card("a", 10.0, "limited", 50.0)], 0, 100, "limited")
    assert "pts/EUR" in picks[0].rationale
