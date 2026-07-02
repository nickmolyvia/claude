from dataclasses import dataclass

VALID_SCARCITIES = ["limited", "rare", "super_rare", "unique"]
# League tiers for the BUY filter (see src/leagues.py). "all" = no restriction.
VALID_TIERS = ["top5", "top7", "top10", "all"]


@dataclass
class Filters:
    min_price: float
    max_price: float
    scarcity: str
    tier: str = "all"


def _ask_float(input_fn, label: str) -> float:
    while True:
        raw = input_fn(f"{label}: ").strip()
        try:
            return float(raw)
        except ValueError:
            print(f"'{raw}' is not a number. Try again.")


def prompt_filters(input_fn=input) -> Filters:
    min_price = _ask_float(input_fn, "Min price (EUR)")
    while True:
        max_price = _ask_float(input_fn, "Max price (EUR)")
        if max_price >= min_price:
            break
        print("Max must be >= min. Try again.")
    while True:
        scarcity = input_fn(
            f"Scarcity {VALID_SCARCITIES}: "
        ).strip().lower()
        if scarcity in VALID_SCARCITIES:
            break
        print(f"Unknown scarcity. Choose one of {VALID_SCARCITIES}.")
    while True:
        tier = input_fn(
            "League tier (top5 / top7 / top10 / all): "
        ).strip().lower()
        if tier in VALID_TIERS:
            break
        print(f"Unknown tier. Choose one of {VALID_TIERS}.")
    return Filters(min_price, max_price, scarcity, tier)
