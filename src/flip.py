# The FLIP table surfaces live market listings priced below their recent-sales
# comps — pure arbitrage candidates to buy under market value and resell.
# Unlike buy.py, duplicate listings of the same player are KEPT: each
# underpriced listing is an independent flip.
from dataclasses import dataclass
from statistics import mean
from src.models import Card

# A listing must be at least this price (EUR, inclusive) to be considered — the
# comp fetch happens only for cards that clear this floor, and cheap commons
# can't clear fees anyway.
FLOOR_PRICE_EUR = 3.50

# Minimum recent comparable sales for a trustworthy average and a provable exit.
MIN_SALE_COUNT = 5


def threshold_for(price: float) -> float:
    """Minimum discount vs comps required to call a listing a flip.

    Cheaper cards need a bigger % cushion to clear fees/gas + the resale
    haircut; expensive cards clear profit on a smaller %.
    """
    if price <= 10:
        return 0.30
    if price <= 25:
        return 0.25
    return 0.225


@dataclass
class FlipPick:
    card: Card
    comp_avg: float
    discount: float
    sale_count: int
    rationale: str


def _rationale(comp_avg: float, discount: float, sale_count: int) -> str:
    return (
        f"comp avg €{comp_avg:.2f} · "
        f"{discount * 100:.0f}% under · "
        f"{sale_count} recent sales"
    )


def rank_flips(cards, limit: int = 50) -> list:
    """Live listings priced below recent-sales comps, ranked by discount.

    Keeps duplicate listings of the same player — each underpriced listing is
    its own flip. A card qualifies when it clears the price floor, has at least
    MIN_SALE_COUNT recent comps with a positive average, and is discounted at
    least threshold_for(price) below that average.
    """
    picks = []
    for card in cards:
        if card.price_eur < FLOOR_PRICE_EUR:
            continue
        sales = card.recent_sale_prices_eur
        if len(sales) < MIN_SALE_COUNT:
            continue
        comp_avg = mean(sales)
        if comp_avg <= 0:
            continue
        discount = (comp_avg - card.price_eur) / comp_avg
        if discount < threshold_for(card.price_eur):
            continue
        picks.append(FlipPick(
            card, comp_avg, discount, len(sales),
            _rationale(comp_avg, discount, len(sales)),
        ))
    picks.sort(key=lambda p: p.discount, reverse=True)
    return picks[:limit]
