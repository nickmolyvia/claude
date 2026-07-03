# src/report.py
from datetime import datetime
from src.buy import BuyPick
from src.sell import SellSignal
from src.flip import FlipPick


def _row(cols, widths):
    return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))


def format_buys(picks: list[BuyPick]) -> str:
    if not picks:
        return "No cards match your filters."
    widths = [3, 22, 18, 10, 9, 6, 6, 60]
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
            p.rationale[:60],
        ], widths))
    return "\n".join(lines)


def format_sells(signals: list[SellSignal]) -> str:
    if not signals:
        return "No cards in collection."
    widths = [22, 14, 9, 12, 14, 6, 40]
    header = _row(["Player", "Scarcity", "Price €", "vs Sales", "Outlook", "Signal", "Reason"], widths)
    lines = ["YOUR COLLECTION — SELL SIGNALS", header, "-" * len(header)]
    for s in signals:
        lines.append(_row([
            s.card.player.display_name[:22],
            s.card.scarcity,
            f"{s.card.price_eur:.2f}",
            f"{s.price_position * 100:+.0f}%",
            s.outlook,
            s.signal,
            s.reason[:40],
        ], widths))
    return "\n".join(lines)


def format_flips(picks: list["FlipPick"], now: datetime) -> str:
    if not picks:
        return "No flips found (no listings below comps)."
    widths = [22, 18, 12, 9, 10, 10, 7, 7, 16, 10]
    header = _row([
        "Player", "Club", "Scarcity", "Price €", "Comp Avg €",
        "Discount", "Sales", "Season", "Seller", "Time Left",
    ], widths)
    lines = ["FLIP OPPORTUNITIES — LISTED BELOW COMPS", header, "-" * len(header)]
    for p in picks:
        lines.append(_row([
            p.card.player.display_name[:22],
            p.card.player.club[:18],
            p.card.scarcity,
            f"{p.card.price_eur:.2f}",
            f"{p.comp_avg:.2f}",
            f"{p.discount * 100:.0f}%",
            p.sale_count,
            p.card.season_year,
            p.card.seller_nickname[:16],
            format_time_left(p.card.offer_end_date, now),
        ], widths))
    return "\n".join(lines)


def format_time_left(iso_str: str, now: datetime) -> str:
    """A coarse countdown until an offer expires, or '—' when unknown.

    `now` is passed in (never read from the clock here) so this is
    deterministic and unit-testable. Empty, unparseable, or already-expired
    timestamps render as '—'.
    """
    if not iso_str:
        return "—"
    try:
        # endDate ends in 'Z' (UTC); fromisoformat needs +00:00 in 3.11.
        end = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Inside the try so a tz-naive `end` (a timestamp lacking 'Z'/offset
        # parses fine but is naive) subtracted from a tz-aware `now` raises
        # TypeError here and renders '—' instead of crashing the whole report.
        total = int((end - now).total_seconds())
    except (ValueError, TypeError):
        return "—"
    if total <= 0:
        return "—"
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days >= 1:
        return f"{days}d {hours}h"
    if hours >= 1:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
