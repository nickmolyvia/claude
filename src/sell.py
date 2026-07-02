from dataclasses import dataclass
from statistics import mean
from src.models import Card


@dataclass
class SellSignal:
    card: Card
    signal: str
    price_position: float
    outlook: str
    strength: float
    reason: str


def price_position(card: Card) -> float:
    sales = card.recent_sale_prices_eur
    if not sales:
        return 0.0
    avg = mean(sales)
    if avg == 0:
        return 0.0
    return (card.price_eur - avg) / avg


def outlook_trend(card: Card) -> str:
    apps = card.player.recent_appearances
    if len(apps) < 2:
        return "steady"
    mid = len(apps) // 2
    older = apps[:mid]
    newer = apps[mid:]
    older_mean = mean(a.so5_score for a in older)
    newer_mean = mean(a.so5_score for a in newer)
    if newer_mean < older_mean:
        return "weakening"
    if newer_mean > older_mean:
        return "strengthening"
    return "steady"


def evaluate_sell(card: Card, price_high_threshold: float = 0.10) -> SellSignal:
    pos = price_position(card)
    outlook = outlook_trend(card)
    price_high = pos >= price_high_threshold
    weakening = outlook == "weakening"
    signal = "SELL" if (price_high or weakening) else "HOLD"
    strength = max(pos, 0.0) + (0.5 if weakening else 0.0)
    reasons = []
    if price_high:
        reasons.append(f"price {pos * 100:+.0f}% vs history")
    if weakening:
        reasons.append("form weakening")
    if not reasons:
        reasons.append(f"price {pos * 100:+.0f}% vs history · {outlook}")
    return SellSignal(card, signal, pos, outlook, strength, " · ".join(reasons))


def rank_sells(cards) -> list:
    signals = [evaluate_sell(c) for c in cards]
    signals.sort(key=lambda s: s.strength, reverse=True)
    return signals
