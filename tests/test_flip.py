from src import flip
from src.models import Appearance, Player, Card


def _card(name, slug, price, sales, scarcity="limited", season=2024):
    p = Player(slug, name, "Some FC", [Appearance(50, 90, True)])
    return Card(slug + "-card", p, scarcity, price, list(sales), season)


def _sales(avg, n):
    # n identical sales averaging `avg`
    return [avg] * n


def test_qualifies_when_discount_and_liquidity_met():
    # €8 card, comps avg €12 -> discount 33% >= 30% tier, 5 sales -> flip
    card = _card("Cheap", "cheap", 8.0, _sales(12.0, 5))
    picks = flip.rank_flips([card])
    assert len(picks) == 1
    assert picks[0].sale_count == 5
    assert round(picks[0].comp_avg, 2) == 12.0
    assert round(picks[0].discount, 4) == round((12.0 - 8.0) / 12.0, 4)


def test_rejected_below_floor_price():
    # €3.49 is under the €3.50 floor even with a huge discount
    card = _card("Tiny", "tiny", 3.49, _sales(20.0, 6))
    assert flip.rank_flips([card]) == []


def test_floor_price_inclusive():
    # exactly €3.50 clears the floor; comps €6 -> 41.7% discount >= 30%
    card = _card("Edge", "edge", 3.50, _sales(6.0, 5))
    assert len(flip.rank_flips([card])) == 1


def test_rejected_too_few_sales():
    # 4 sales < MIN_SALE_COUNT even with a big discount
    card = _card("Thin", "thin", 8.0, _sales(20.0, 4))
    assert flip.rank_flips([card]) == []


def test_rejected_discount_below_tier():
    # €8 card, comps €10 -> 20% discount < 30% tier
    card = _card("Meh", "meh", 8.0, _sales(10.0, 5))
    assert flip.rank_flips([card]) == []


def test_zero_comp_average_is_skipped_not_crash():
    card = _card("Zero", "zero", 8.0, _sales(0.0, 5))
    assert flip.rank_flips([card]) == []


def test_duplicates_are_kept_and_ranked_by_discount():
    # same player listed 3 times, all below comps -> 3 rows, best discount first
    comps = _sales(20.0, 5)
    a = _card("Dup", "dup", 14.0, comps)   # 30% discount (14 vs 20), tier@25%
    b = _card("Dup", "dup", 10.0, comps)   # 50% discount, tier@30%
    c = _card("Dup", "dup", 12.0, comps)   # 40% discount, tier@25%
    picks = flip.rank_flips([a, b, c])
    assert len(picks) == 3  # no dedupe
    discounts = [round(p.discount, 4) for p in picks]
    assert discounts == sorted(discounts, reverse=True)
    assert round(picks[0].discount, 4) == round((20.0 - 10.0) / 20.0, 4)


def test_limit_caps_results():
    cards = [_card("P", f"p{i}", 8.0, _sales(20.0, 5)) for i in range(60)]
    assert len(flip.rank_flips(cards, limit=50)) == 50


def test_threshold_tiers_and_boundaries():
    # <= 10 -> 30%
    assert flip.threshold_for(3.50) == 0.30
    assert flip.threshold_for(10.0) == 0.30      # boundary: exactly 10 -> 30%
    # 10 < price <= 25 -> 25%
    assert flip.threshold_for(10.01) == 0.25
    assert flip.threshold_for(25.0) == 0.25      # boundary: exactly 25 -> 25%
    # price > 25 -> 22.5%
    assert flip.threshold_for(25.01) == 0.225
    assert flip.threshold_for(100.0) == 0.225
