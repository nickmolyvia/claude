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
