# FLIP Seller + Time-Left Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Seller and Time-Left columns to the FLIP table, and hide the user's own listings from it.

**Architecture:** Extend the market query to capture the offer's `sender` (nickname/slug) and `endDate`; carry them on `Card` as two new optional fields set in `fetch_market_cards`; filter out offers whose seller slug equals the user; and render a countdown via a clock-injected, unit-testable `format_time_left` helper. Real wall-clock is taken once in `run()` and threaded down.

**Tech Stack:** Python 3.11, `requests`, `pytest`, stdlib `datetime`. No new dependencies.

## Global Constraints

- Python 3.11; deps limited to `requests>=2.31,<3` and `pytest>=8,<9` (no new deps).
- Two new `Card` fields, both optional & defaulted: `seller_nickname: str = ""`, `offer_end_date: str = ""` (raw ISO-8601 string).
- Seller field via GraphQL union inline fragment: `sender { ... on User { nickname slug } }`. Time-left field: `endDate` (ISO-8601 UTC, e.g. `2026-07-03T09:11:19Z`).
- Self-listing filter matches on `sender.slug == self.username` (case-insensitive, stripped). Empty username → no filtering.
- `format_time_left(iso_str, now)`: empty/malformed/expired (`delta <= 0`) → `"—"`; `>= 1 day` → `"{d}d {h}h"`; `>= 1 hour` → `"{h}h {m}m"`; else → `"{m}m"`. `now` is a parameter, never read inside.
- `now` is computed once in `run()` as `datetime.now(timezone.utc)` and passed into `report.format_flips(flips, now)`.
- FLIP column order: `Player · Club · Scarcity · Price € · Comp Avg € · Discount · Sales · Season · Seller · Time Left`.
- Match existing style: shared `_row(cols, widths)` helper, fixed widths, UTF-8 `€`, truncate string columns to width.
- The em dash for "no time" is the character `—` (U+2014), consistent with existing report copy (`YOUR COLLECTION — SELL SIGNALS`).
- Commit after each task. After the final task, push to `main` (`origin` = `github.com/nickmolyvia/claude.git`).

---

### Task 1: `Card` gains seller + end-date fields

**Files:**
- Modify: `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: existing `Card` dataclass.
- Produces: `Card.seller_nickname: str = ""` and `Card.offer_end_date: str = ""` (new optional fields, appended after `season_year`).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_models.py
from src.models import Player, Card


def test_card_has_seller_and_end_date_defaults():
    c = Card("slug", Player("p", "P", "FC"), "limited", 5.0)
    assert c.seller_nickname == ""
    assert c.offer_end_date == ""
    c2 = Card("s2", Player("p", "P", "FC"), "limited", 5.0,
              seller_nickname="satonio", offer_end_date="2026-07-03T09:11:19Z")
    assert c2.seller_nickname == "satonio"
    assert c2.offer_end_date == "2026-07-03T09:11:19Z"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py::test_card_has_seller_and_end_date_defaults -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'seller_nickname'`

- [ ] **Step 3: Add the fields**

In `src/models.py`, the `Card` dataclass currently ends with `season_year: int = 0`. Add two fields after it:

```python
@dataclass
class Card:
    slug: str
    player: Player
    scarcity: str
    price_eur: float
    recent_sale_prices_eur: list[float] = field(default_factory=list)
    season_year: int = 0  # e.g. 2024; comps are matched to the same season
    # Offer-level metadata for the FLIP table, set in fetch_market_cards. Blank
    # for cards not sourced from a live market offer (e.g. owned cards).
    seller_nickname: str = ""
    offer_end_date: str = ""  # raw ISO-8601 UTC string; formatted at display
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py::test_card_has_seller_and_end_date_defaults -v`
Expected: PASS

- [ ] **Step 5: Run the full suite (guard against a positional-arg break)**

Run: `python -m pytest -q`
Expected: PASS (all tests). The new fields are appended and defaulted, so existing positional `Card(...)` constructions are unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: Card carries seller nickname and offer end date"
```

---

### Task 2: `format_time_left` countdown helper

**Files:**
- Modify: `src/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: stdlib `datetime`.
- Produces: `format_time_left(iso_str: str, now: datetime) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_report.py
from datetime import datetime, timezone
from src.report import format_time_left


def _now():
    return datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def test_time_left_days():
    # 2 days 4 hours ahead
    assert format_time_left("2026-07-05T16:00:00Z", _now()) == "2d 4h"


def test_time_left_hours_with_minutes():
    # 1 hour 30 minutes ahead
    assert format_time_left("2026-07-03T13:30:00Z", _now()) == "1h 30m"


def test_time_left_minutes_only():
    # 45 minutes ahead
    assert format_time_left("2026-07-03T12:45:00Z", _now()) == "45m"


def test_time_left_expired_is_dash():
    # already past
    assert format_time_left("2026-07-03T11:00:00Z", _now()) == "—"


def test_time_left_empty_is_dash():
    assert format_time_left("", _now()) == "—"


def test_time_left_malformed_is_dash():
    assert format_time_left("not-a-date", _now()) == "—"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_report.py -k time_left -v`
Expected: FAIL with `ImportError: cannot import name 'format_time_left'`

- [ ] **Step 3: Implement the helper**

Add to `src/report.py` (top of file, after the existing imports add `from datetime import datetime`; then add the function):

```python
from datetime import datetime


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
    except (ValueError, TypeError):
        return "—"
    delta = end - now
    total = int(delta.total_seconds())
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -k time_left -v`
Expected: PASS (all 6)

- [ ] **Step 5: Commit**

```bash
git add src/report.py tests/test_report.py
git commit -m "feat: format_time_left countdown helper"
```

---

### Task 3: `format_flips` shows Seller + Time Left

**Files:**
- Modify: `src/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `format_time_left` (Task 2), `FlipPick` (from `src.flip`), `Card.seller_nickname` / `Card.offer_end_date` (Task 1).
- Produces: `format_flips(picks, now)` — a `now: datetime` parameter is added; two new columns appended.

- [ ] **Step 1: Write the failing tests**

The existing `test_report.py` has an `_card(name, price)` helper and flip tests
(`test_format_flips_includes_player_and_headers`, `test_format_flips_empty`).
Those call `format_flips([...])` / `format_flips([])` with ONE argument and
must be updated to pass `now`. Replace those two existing flip tests and add a
new one:

```python
# in tests/test_report.py — replace the two existing format_flips tests with these three
from src.flip import FlipPick
from datetime import datetime, timezone


def _flip_now():
    return datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def test_format_flips_includes_player_and_headers():
    card = _card(name="Bargain", price=8.0)
    card.seller_nickname = "satonio"
    card.offer_end_date = "2026-07-03T13:30:00Z"  # 1h 30m ahead of _flip_now
    pick = FlipPick(card, comp_avg=12.0, discount=0.3333, sale_count=6,
                    rationale="comp avg €12.00 · 33% under · 6 recent sales")
    out = report.format_flips([pick], _flip_now())
    assert "Bargain" in out
    assert "Discount" in out
    assert "Seller" in out
    assert "Time Left" in out
    assert "satonio" in out
    assert "1h 30m" in out


def test_format_flips_blank_seller_and_no_end_date():
    card = _card(name="NoMeta", price=8.0)  # seller_nickname="" , offer_end_date=""
    pick = FlipPick(card, comp_avg=12.0, discount=0.3333, sale_count=6,
                    rationale="x")
    out = report.format_flips([pick], _flip_now())
    assert "NoMeta" in out
    assert "—" in out  # no end date -> dash


def test_format_flips_empty():
    assert "No flips found" in report.format_flips([], _flip_now())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_report.py -k flips -v`
Expected: FAIL — `format_flips()` currently takes 1 arg (TypeError on the 2-arg call) and lacks the Seller/Time Left columns.

- [ ] **Step 3: Update `format_flips`**

Replace the existing `format_flips` in `src/report.py` with:

```python
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
```

Note: the `FlipPick` import already exists at the top of `report.py` from the
original FLIP work (`from src.flip import FlipPick`); keep it. The string
annotation `"FlipPick"` in the signature is fine either way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -k flips -v`
Expected: PASS (all 3)

- [ ] **Step 5: Commit**

```bash
git add src/report.py tests/test_report.py
git commit -m "feat: FLIP table shows seller and time-left columns"
```

---

### Task 4: Capture seller + endDate and filter own listings in `fetch_market_cards`

**Files:**
- Modify: `src/api.py` (the `fetch_market_cards` query + loop)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Card.seller_nickname` / `Card.offer_end_date` (Task 1); existing `_amounts_to_eur`, `card_from_json`.
- Produces: market cards populated with `seller_nickname` and `offer_end_date`; offers whose `sender.slug == self.username` (case-insensitive) are skipped.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_api.py
def _market_payload_with_seller(nickname, slug, end_date, card=SAMPLE_CARD):
    return {"data": {"tokens": {"liveSingleSaleOffers": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [{
            "endDate": end_date,
            "sender": {"nickname": nickname, "slug": slug},
            "receiverSide": {"amounts": {"eurCents": 4250, "usdCents": None,
                                         "gbpCents": None, "wei": None}},
            "senderSide": {"anyCards": [card]},
        }],
    }}}}


def test_market_card_captures_seller_and_end_date():
    payload = _market_payload_with_seller(
        "satonio", "satonio", "2026-07-03T09:11:19Z")
    client = api.SorareClient(session=_FakeSession(payload), api_key="k")
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].seller_nickname == "satonio"
    assert cards[0].offer_end_date == "2026-07-03T09:11:19Z"


def test_market_skips_own_listings_case_insensitive():
    payload = _market_payload_with_seller("Me", "MyName", "2026-07-03T09:11:19Z")
    # username differs only by case -> the offer is the user's own -> skipped
    client = api.SorareClient(session=_FakeSession(payload), api_key="k",
                              username="myname")
    cards = client.fetch_market_cards("limited")
    assert cards == []


def test_market_keeps_other_sellers():
    payload = _market_payload_with_seller("other", "otherguy",
                                          "2026-07-03T09:11:19Z")
    client = api.SorareClient(session=_FakeSession(payload), api_key="k",
                              username="myname")
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].seller_nickname == "other"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -k "seller or own_listings or other_sellers" -v`
Expected: FAIL — the query does not request `sender`/`endDate`, and the loop neither sets the fields nor filters (seller is blank, own listings not skipped).

- [ ] **Step 3: Update the query**

In `src/api.py` `fetch_market_cards`, add `endDate` and `sender` to the offer
node. Change the `nodes { ... }` block to:

```graphql
              nodes {
                endDate
                sender { ... on User { nickname slug } }
                receiverSide { amounts { eurCents usdCents gbpCents wei } }
                senderSide {
                  anyCards {
                    %s
                  }
                }
              }
```

- [ ] **Step 4: Update the loop to filter + populate**

In the `for offer in offers:` loop, right after computing `offer_price`, insert
the seller read + self-filter, and set the two fields on each card. Replace the
loop body with:

```python
            for offer in offers:
                # The offer wrapper's receiverSide is the actual price the buyer
                # pays for this listing — in whatever currency the seller chose.
                offer_price = _amounts_to_eur(
                    (offer.get("receiverSide") or {}).get("amounts"),
                    rate, usd_rate, gbp_rate,
                )
                sender = offer.get("sender") or {}
                seller_nickname = sender.get("nickname") or ""
                seller_slug = sender.get("slug") or ""
                # A card the user is already selling is not a buy opportunity —
                # skip their own listings entirely (case-insensitive slug match).
                if (self.username
                        and seller_slug.strip().lower()
                        == self.username.strip().lower()):
                    continue
                end_date = offer.get("endDate") or ""
                for card_node in (offer.get("senderSide") or {}).get("anyCards", []):
                    card = card_from_json(card_node, rate, usd_rate, gbp_rate)
                    if offer_price > 0.0:
                        card.price_eur = offer_price
                    card.seller_nickname = seller_nickname
                    card.offer_end_date = end_date
                    if card.scarcity == scarcity:
                        cards.append(card)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -k "seller or own_listings or other_sellers" -v`
Expected: PASS (all 3)

- [ ] **Step 6: Run the full API suite (guard existing market tests)**

Run: `python -m pytest tests/test_api.py -q`
Expected: PASS. Existing market tests use payloads without a `sender` key; `offer.get("sender") or {}` yields `""` seller and (with the default empty username in those clients) no filtering, so they still pass.

- [ ] **Step 7: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: capture seller + endDate, filter own listings in market scan"
```

---

### Task 5: Wire the clock through `run()`

**Files:**
- Modify: `sorare_value.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `report.format_flips(flips, now)` (Task 3).
- Produces: `run()` computes `now = datetime.now(timezone.utc)` once and passes it to `format_flips`.

- [ ] **Step 1: Read the existing CLI test's fake client**

Run: `python -m pytest tests/test_cli.py -q` first to confirm the current suite
is green, then open `tests/test_cli.py`. The existing `_FakeClientWithFlip`
seeds a market card and stubs `enrich_market_with_sales`; the flip it produces
will now also render seller/time-left columns. No fake-client method changes are
needed (the new columns read Card fields that default to `""`).

- [ ] **Step 2: Write the failing test**

```python
# add to tests/test_cli.py
def test_run_flip_table_has_seller_and_time_left_headers():
    lines = []
    from src.prompts import Filters
    filters = Filters(min_price=0.0, max_price=1000.0, scarcity="limited", tier="all")
    sorare_value.run(_FakeClientWithFlip(), filters, output_fn=lines.append)
    joined = "\n".join(lines)
    assert "Seller" in joined
    assert "Time Left" in joined
```

(If `_FakeClientWithFlip` is defined in the same file from the original FLIP
work, reuse it; this test only asserts the new headers reach output.)

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_run_flip_table_has_seller_and_time_left_headers -v`
Expected: FAIL — `run()` still calls `format_flips(flips)` with one arg, raising `TypeError` (missing `now`), or headers absent.

- [ ] **Step 4: Update `run()`**

In `sorare_value.py`, add the import at the top (with the other imports):

```python
from datetime import datetime, timezone
```

Change the flip block at the end of `run()` from:

```python
    client.enrich_market_with_sales(market)
    flips = flip.rank_flips(market)
    output_fn(report.format_flips(flips))
```

to:

```python
    client.enrich_market_with_sales(market)
    flips = flip.rank_flips(market)
    now = datetime.now(timezone.utc)
    output_fn(report.format_flips(flips, now))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py::test_run_flip_table_has_seller_and_time_left_headers -v`
Expected: PASS

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add sorare_value.py tests/test_cli.py
git commit -m "feat: thread current time into FLIP report for time-left"
```

---

### Task 6: Docs + end-to-end run + push

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the FLIP section in `README.md`**

Append to the existing "FLIP table (arbitrage)" section:

```markdown
Each flip row also shows the **Seller** (the listing's Sorare nickname) and
**Time Left** — a coarse countdown to the offer's expiry (`2d 4h`, `1h 30m`,
`45m`, or `—` when an offer has no end date). Your **own listings are hidden**
from the FLIP table, since a card you are already selling is not a buy
opportunity.
```

- [ ] **Step 2: Run the app end-to-end**

Run: `printf '3\n60\nlimited\nall\n\n' | python sorare_value.py 2>&1 | tail -20`
Expected: the run completes without a traceback and the FLIP section prints its
header row including `Seller` and `Time Left` (or the "No flips found" line if
the live market has none right now — both are a pass; a crash is a fail).
Capture the tail output in the report.

- [ ] **Step 3: Commit the docs**

```bash
git add README.md
git commit -m "docs: document FLIP seller and time-left columns"
```

- [ ] **Step 4: (Controller handles) merge to main + push**

The implementer should NOT push. The controller merges the feature branch to
`main` (fast-forward), runs `python -m pytest -q` on the merged result, and
pushes to `origin main`.

---

## Self-Review

**Spec coverage:**
- Seller column (nickname) → Task 4 (capture) + Task 3 (render). ✓
- Time-Left column (countdown) → Task 2 (helper) + Task 3 (render) + Task 5 (clock). ✓
- Hide own listings → Task 4 (`sender.slug == username`, case-insensitive). ✓
- Verified fields (`sender { ... on User { nickname slug } }`, `endDate`) → Task 4 query. ✓
- `Card` optional fields `seller_nickname` / `offer_end_date` → Task 1. ✓
- `format_time_left` buckets (days `2d 4h`, hours `1h 30m`, minutes `45m`, expired/empty/malformed → `—`), clock injected → Task 2. ✓
- `now` computed once in `run()` and threaded → Task 5. ✓
- Column order Player…Season·Seller·Time Left → Task 3. ✓
- Empty-list "No flips found" preserved → Task 3 (`test_format_flips_empty`). ✓
- Error handling (missing sender/nickname → blank; missing/malformed/expired endDate → `—`) → Task 2 tests + Task 4 (`or ""`). ✓
- Push to main → Task 6. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. Task 5 Step 1 asks the engineer to read the existing `_FakeClientWithFlip`; the concrete new test is in Step 2.

**Type consistency:** `format_time_left(iso_str, now)` defined Task 2, called in Task 3 and (indirectly) Task 5. `format_flips(picks, now)` signature changed in Task 3, called with `now` in Task 5. `Card.seller_nickname` / `Card.offer_end_date` defined Task 1, set in Task 4, read in Task 3. `datetime`/`timezone` imports added where used (report.py Task 2, sorare_value.py Task 5). All consistent.
