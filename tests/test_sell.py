from src.models import Appearance, Fixture, Player, Card
from src import sell


def _card(price, sales, appearances):
    player = Player("p", "P", "Club", appearances, [Fixture("x", 0.5)])
    return Card("card", player, "limited", price, sales)


def _apps(scores):
    return [Appearance(s, 90, True) for s in scores]


def test_price_position_above_history_positive():
    c = _card(price=110.0, sales=[100.0, 100.0], appearances=_apps([50, 50]))
    assert abs(sell.price_position(c) - 0.10) < 1e-9


def test_price_position_no_sales_zero():
    c = _card(price=110.0, sales=[], appearances=_apps([50]))
    assert sell.price_position(c) == 0.0


def test_outlook_weakening():
    c = _card(100.0, [100.0], appearances=_apps([80, 80, 20, 20]))  # old 80, new 20
    assert sell.outlook_trend(c) == "weakening"


def test_outlook_strengthening():
    c = _card(100.0, [100.0], appearances=_apps([20, 20, 80, 80]))
    assert sell.outlook_trend(c) == "strengthening"


def test_sell_when_price_high():
    c = _card(price=130.0, sales=[100.0], appearances=_apps([50, 50]))  # +30%
    sig = sell.evaluate_sell(c)
    assert sig.signal == "SELL"


def test_sell_when_weakening_even_if_price_fair():
    c = _card(price=100.0, sales=[100.0], appearances=_apps([80, 80, 20, 20]))
    sig = sell.evaluate_sell(c)
    assert sig.signal == "SELL"


def test_hold_when_fair_and_steady():
    c = _card(price=100.0, sales=[100.0], appearances=_apps([50, 50]))
    sig = sell.evaluate_sell(c)
    assert sig.signal == "HOLD"


def test_rank_sells_orders_by_strength_desc():
    weak_expensive = _card(150.0, [100.0], _apps([80, 80, 10, 10]))  # high price + weakening
    fair_steady = _card(100.0, [100.0], _apps([50, 50]))            # hold, strength 0
    ranked = sell.rank_sells([fair_steady, weak_expensive])
    assert ranked[0].card is weak_expensive
