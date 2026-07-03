# tests/test_report.py
from datetime import datetime, timezone
from src.models import Appearance, Fixture, Player, Card
from src.buy import BuyPick
from src.sell import SellSignal
from src.flip import FlipPick
from src import report
from src.report import format_time_left


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


def _flip_now():
    return datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def test_format_flips_includes_player_and_headers():
    card = _card(name="Bargain", price=8.0)
    card.seller_nickname = "satonio"
    card.offer_end_date = "2026-07-03T13:30:00Z"  # 1h 30m ahead of _flip_now
    pick = FlipPick(card, comp_avg=12.0, discount=0.3333, sale_count=6,
                    rationale="comp avg €12.00 · 33% under · 6 recent sales")
    out = report.format_flips([pick], _flip_now())
    assert "Bargain" in out
    assert "Discount" in out
    assert "Seller" in out
    assert "Time Left" in out
    assert "satonio" in out
    assert "1h 30m" in out


def test_format_flips_blank_seller_and_no_end_date():
    card = _card(name="NoMeta", price=8.0)  # seller_nickname="" , offer_end_date=""
    pick = FlipPick(card, comp_avg=12.0, discount=0.3333, sale_count=6,
                    rationale="x")
    out = report.format_flips([pick], _flip_now())
    assert "NoMeta" in out
    assert "—" in out  # no end date -> dash


def test_format_flips_empty():
    assert "No flips found" in report.format_flips([], _flip_now())


def _now():
    return datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def test_time_left_days():
    # 2 days 4 hours ahead
    assert format_time_left("2026-07-05T16:00:00Z", _now()) == "2d 4h"


def test_time_left_hours_with_minutes():
    # 1 hour 30 minutes ahead
    assert format_time_left("2026-07-03T13:30:00Z", _now()) == "1h 30m"


def test_time_left_minutes_only():
    # 45 minutes ahead
    assert format_time_left("2026-07-03T12:45:00Z", _now()) == "45m"


def test_time_left_expired_is_dash():
    # already past
    assert format_time_left("2026-07-03T11:00:00Z", _now()) == "—"


def test_time_left_empty_is_dash():
    assert format_time_left("", _now()) == "—"


def test_time_left_malformed_is_dash():
    assert format_time_left("not-a-date", _now()) == "—"
