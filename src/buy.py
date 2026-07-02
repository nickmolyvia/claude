# src/buy.py
from dataclasses import dataclass
from src.models import Card
from src import fair_value, leagues


@dataclass
class BuyPick:
    card: Card
    projected: float
    value_score: float
    rationale: str


def value_score(card: Card) -> float:
    if card.price_eur <= 0:
        return 0.0
    return fair_value.projected_points(card.player) / card.price_eur


def _rationale(card: Card, projected: float, vscore: float) -> str:
    p = card.player
    return (
        f"form {fair_value.form_score(p):.1f} · "
        f"reliability {fair_value.minutes_reliability(p):.2f} · "
        f"fixtures {fair_value.fixture_multiplier(p):.2f} -> "
        f"{vscore:.1f} pts/EUR"
    )


def rank_buys(cards, min_price, max_price, scarcity, limit=50, tier="all"):
    picks = []
    for c in cards:
        # Filter: right scarcity, within budget, in the chosen league tier, and
        # actually usable — a card with no price (0) can't have a value
        # computed, and a player with no projected points (0 recent form) is
        # noise, not a "value" pick. All are dropped so the list shows real,
        # priced, in-form signings from the leagues you asked for.
        if c.scarcity != scarcity:
            continue
        if not (min_price <= c.price_eur <= max_price):
            continue
        if c.price_eur <= 0:
            continue
        if not leagues.in_tier(c.player.league_slug, tier):
            continue
        projected = fair_value.projected_points(c.player)
        if projected <= 0:
            continue
        vscore = value_score(c)
        picks.append(BuyPick(c, projected, vscore, _rationale(c, projected, vscore)))
    picks.sort(key=lambda p: p.value_score, reverse=True)
    return picks[:limit]
