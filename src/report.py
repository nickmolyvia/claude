# src/report.py
from src.buy import BuyPick
from src.sell import SellSignal


def _row(cols, widths):
    return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))


def format_buys(picks: list[BuyPick]) -> str:
    if not picks:
        return "No cards match your filters."
    widths = [3, 22, 18, 10, 9, 6, 6, 40]
    header = _row(["#", "Player", "Club", "Scarcity", "Price €", "Proj", "Value", "Why"], widths)
    lines = ["TOP VALUE-FOR-MONEY SIGNINGS", header, "-" * len(header)]
    for i, p in enumerate(picks, 1):
        lines.append(_row([
            i,
            p.card.player.display_name[:22],
            p.card.player.club[:18],
            p.card.scarcity,
            f"{p.card.price_eur:.2f}",
            f"{p.projected:.1f}",
            f"{p.value_score:.2f}",
            p.rationale[:40],
        ], widths))
    return "\n".join(lines)


def format_sells(signals: list[SellSignal]) -> str:
    if not signals:
        return "No cards in collection."
    widths = [22, 10, 9, 12, 14, 6, 30]
    header = _row(["Player", "Scarcity", "Price €", "vs History", "Outlook", "Signal", "Reason"], widths)
    lines = ["YOUR COLLECTION — SELL SIGNALS", header, "-" * len(header)]
    for s in signals:
        lines.append(_row([
            s.card.player.display_name[:22],
            s.card.scarcity,
            f"{s.card.price_eur:.2f}",
            f"{s.price_position * 100:+.0f}%",
            s.outlook,
            s.signal,
            s.reason[:30],
        ], widths))
    return "\n".join(lines)
