# src/buy.py
from dataclasses import dataclass
from src.models import Card
from src import fair_value


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
        f"fixtures {fair_value.fixture_multiplier(p):.2f} → "
        f"{vscore:.1f} pts/€"
    )


def rank_buys(cards, min_price, max_price, scarcity, limit=50):
    candidates = [
        c for c in cards
        if c.scarcity == scarcity and min_price <= c.price_eur <= max_price
    ]
    picks = []
    for c in candidates:
        projected = fair_value.projected_points(c.player)
        vscore = value_score(c)
        picks.append(BuyPick(c, projected, vscore, _rationale(c, projected, vscore)))
    picks.sort(key=lambda p: p.value_score, reverse=True)
    return picks[:limit]
