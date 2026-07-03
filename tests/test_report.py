# tests/test_report.py
from src.models import Appearance, Fixture, Player, Card
from src.buy import BuyPick
from src.sell import SellSignal
from src.flip import FlipPick
from src import report


def _card(name="Messi", price=25.0):
    p = Player("m", name, "Inter Miami",
               [Appearance(70, 90, True)], [Fixture("x", 0.5)])
    return Card("c", p, "limited", price, [price])


def test_format_buys_includes_player_and_headers():
    pick = BuyPick(_card(), projected=70.0, value_score=2.8, rationale="form 70.0 -> 2.8 pts/EUR")
    out = report.format_buys([pick])
    assert "Messi" in out
    assert "Value" in out
    assert "Player" in out


def test_format_buys_empty():
    assert "No cards match" in report.format_buys([])


def test_format_sells_includes_signal():
    sig = SellSignal(_card(), signal="SELL", price_position=0.2,
                     outlook="weakening", strength=0.7, reason="price +20% vs history")
    out = report.format_sells([sig])
    assert "SELL" in out
    assert "Messi" in out


def test_format_sells_empty():
    assert "No cards in collection" in report.format_sells([])


def test_format_flips_includes_player_and_headers():
    pick = FlipPick(_card(name="Bargain", price=8.0), comp_avg=12.0,
                    discount=0.3333, sale_count=6,
                    rationale="comp avg €12.00 · 33% under · 6 recent sales")
    out = report.format_flips([pick])
    assert "Bargain" in out
    assert "Discount" in out
    assert "Comp Avg" in out
    assert "Sales" in out


def test_format_flips_empty():
    assert "No flips found" in report.format_flips([])
