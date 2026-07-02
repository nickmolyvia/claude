from dataclasses import dataclass

VALID_SCARCITIES = ["limited", "rare", "super_rare", "unique"]


@dataclass
class Filters:
    min_price: float
    max_price: float
    scarcity: str


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
    return Filters(min_price, max_price, scarcity)
