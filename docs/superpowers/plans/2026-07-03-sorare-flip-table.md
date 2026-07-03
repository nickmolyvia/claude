# Sorare FLIP Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third report — FLIP — that surfaces live market listings priced below their recent-sales comps, as arbitrage candidates a trader can buy under market value and resell.

**Architecture:** A new isolated module `src/flip.py` (mirroring `src/buy.py`) holds the tiered-threshold logic and ranking. `src/report.py` gains a `format_flips` function. The market cards already pulled for BUY are enriched with recent sales (reusing the cached `fetch_recent_sales` pattern proven in `fetch_my_cards`), then ranked and printed after the SELL table in `sorare_value.py`.

**Tech Stack:** Python 3.11, `requests`, `pytest`. No new dependencies.

## Global Constraints

- Python 3.11; deps limited to `requests>=2.31,<3` and `pytest>=8,<9` (no new deps).
- Floor price: `FLOOR_PRICE_EUR = 3.50`, inclusive (a €3.50 card qualifies, €3.49 does not).
- Liquidity gate: `MIN_SALE_COUNT = 5`, inclusive (5 sales qualifies, 4 does not).
- Discount tiers (single source of truth in `threshold_for`): `price <= 10` → `0.30`; `10 < price <= 25` → `0.25`; `price > 25` → `0.225`.
- FLIP keeps duplicate listings — **no dedupe by player** (unlike BUY).
- Ranking: discount descending.
- Comps are read from `card.recent_sale_prices_eur`; a card with `< 5` sales or a non-positive comp average is never a flip and never crashes.
- Match existing code style: module-level comment header, `@dataclass`, fixed-width report rows via the existing `_row(cols, widths)` helper, UTF-8 `€` in headers.
- Commit after each task. After the final task, push to `origin` (`github.com/nickmolyvia/claude.git`).

---

### Task 1: `flip.py` — tiered threshold helper

**Files:**
- Create: `src/flip.py`
- Test: `tests/test_flip.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces: `FLOOR_PRICE_EUR = 3.50`, `MIN_SALE_COUNT = 5`, `threshold_for(price: float) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flip.py
from src import flip


def test_threshold_tiers_and_boundaries():
    # <= 10 -> 30%
    assert flip.threshold_for(3.50) == 0.30
    assert flip.threshold_for(10.0) == 0.30      # boundary: exactly 10 -> 30%
    # 10 < price <= 25 -> 25%
    assert flip.threshold_for(10.01) == 0.25
    assert flip.threshold_for(25.0) == 0.25      # boundary: exactly 25 -> 25%
    # price > 25 -> 22.5%
    assert flip.threshold_for(25.01) == 0.225
    assert flip.threshold_for(100.0) == 0.225
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_flip.py::test_threshold_tiers_and_boundaries -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.flip'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/flip.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_flip.py::test_threshold_tiers_and_boundaries -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/flip.py tests/test_flip.py
git commit -m "feat: flip threshold tiers"
```

---

### Task 2: `flip.py` — `FlipPick` and `rank_flips`

**Files:**
- Modify: `src/flip.py`
- Test: `tests/test_flip.py`

**Interfaces:**
- Consumes: `threshold_for`, `FLOOR_PRICE_EUR`, `MIN_SALE_COUNT` from Task 1; `Card` from `src.models` (fields: `player`, `scarcity`, `price_eur`, `recent_sale_prices_eur`, `season_year`; `player.display_name`, `player.club`, `player.slug`).
- Produces: `@dataclass FlipPick(card, comp_avg: float, discount: float, sale_count: int, rationale: str)` and `rank_flips(cards, limit: int = 50) -> list[FlipPick]`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_flip.py
from src.models import Appearance, Player, Card


def _card(name, slug, price, sales, scarcity="limited", season=2024):
    p = Player(slug, name, "Some FC", [Appearance(50, 90, True)])
    return Card(slug + "-card", p, scarcity, price, list(sales), season)


def _sales(avg, n):
    # n identical sales averaging `avg`
    return [avg] * n


def test_qualifies_when_discount_and_liquidity_met():
    # €8 card, comps avg €12 -> discount 33% >= 30% tier, 5 sales -> flip
    card = _card("Cheap", "cheap", 8.0, _sales(12.0, 5))
    picks = flip.rank_flips([card])
    assert len(picks) == 1
    assert picks[0].sale_count == 5
    assert round(picks[0].comp_avg, 2) == 12.0
    assert round(picks[0].discount, 4) == round((12.0 - 8.0) / 12.0, 4)


def test_rejected_below_floor_price():
    # €3.49 is under the €3.50 floor even with a huge discount
    card = _card("Tiny", "tiny", 3.49, _sales(20.0, 6))
    assert flip.rank_flips([card]) == []


def test_floor_price_inclusive():
    # exactly €3.50 clears the floor; comps €6 -> 41.7% discount >= 30%
    card = _card("Edge", "edge", 3.50, _sales(6.0, 5))
    assert len(flip.rank_flips([card])) == 1


def test_rejected_too_few_sales():
    # 4 sales < MIN_SALE_COUNT even with a big discount
    card = _card("Thin", "thin", 8.0, _sales(20.0, 4))
    assert flip.rank_flips([card]) == []


def test_rejected_discount_below_tier():
    # €8 card, comps €10 -> 20% discount < 30% tier
    card = _card("Meh", "meh", 8.0, _sales(10.0, 5))
    assert flip.rank_flips([card]) == []


def test_zero_comp_average_is_skipped_not_crash():
    card = _card("Zero", "zero", 8.0, _sales(0.0, 5))
    assert flip.rank_flips([card]) == []


def test_duplicates_are_kept_and_ranked_by_discount():
    # same player listed 3 times, all below comps -> 3 rows, best discount first
    comps = _sales(20.0, 5)
    a = _card("Dup", "dup", 14.0, comps)   # 30% discount (14 vs 20), tier@25%
    b = _card("Dup", "dup", 10.0, comps)   # 50% discount, tier@30%
    c = _card("Dup", "dup", 12.0, comps)   # 40% discount, tier@25%
    picks = flip.rank_flips([a, b, c])
    assert len(picks) == 3  # no dedupe
    discounts = [round(p.discount, 4) for p in picks]
    assert discounts == sorted(discounts, reverse=True)
    assert round(picks[0].discount, 4) == round((20.0 - 10.0) / 20.0, 4)


def test_limit_caps_results():
    cards = [_card("P", f"p{i}", 8.0, _sales(20.0, 5)) for i in range(60)]
    assert len(flip.rank_flips(cards, limit=50)) == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_flip.py -v`
Expected: FAIL with `AttributeError: module 'src.flip' has no attribute 'rank_flips'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/flip.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_flip.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/flip.py tests/test_flip.py
git commit -m "feat: rank_flips with liquidity gate, no dedupe"
```

---

### Task 3: `format_flips` report

**Files:**
- Modify: `src/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `FlipPick` from `src.flip` (Task 2); the existing `_row(cols, widths)` helper in `report.py`.
- Produces: `format_flips(picks: list[FlipPick]) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_report.py
from src.flip import FlipPick


def test_format_flips_includes_player_and_headers():
    pick = FlipPick(_card(name="Bargain", price=8.0), comp_avg=12.0,
                    discount=0.3333, sale_count=6,
                    rationale="comp avg €12.00 · 33% under · 6 recent sales")
    out = report.format_flips([pick])
    assert "Bargain" in out
    assert "Discount" in out
    assert "Comp Avg" in out
    assert "Sales" in out


def test_format_flips_empty():
    assert "No flips found" in report.format_flips([])
```

Note: the existing `_card` helper in `test_report.py` builds a `Card` with a
`limited` scarcity and `season_year` default — no change needed there.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ImportError` / `AttributeError: module 'src.report' has no attribute 'format_flips'`

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `src/report.py` (next to the other imports):

```python
from src.flip import FlipPick
```

Append the function:

```python
def format_flips(picks: list[FlipPick]) -> str:
    if not picks:
        return "No flips found (no listings below comps)."
    widths = [22, 18, 12, 9, 10, 10, 7, 7]
    header = _row([
        "Player", "Club", "Scarcity", "Price €", "Comp Avg €",
        "Discount", "Sales", "Season",
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
        ], widths))
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/report.py tests/test_report.py
git commit -m "feat: format_flips report table"
```

---

### Task 4: Enrich market cards with comps (`api.py`)

**Files:**
- Modify: `src/api.py` (add a method on `SorareClient`, after `fetch_recent_sales`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: existing `SorareClient.fetch_recent_sales(slug, scarcity, season_year)`; `flip.FLOOR_PRICE_EUR`.
- Produces: `SorareClient.enrich_market_with_sales(cards) -> None` — mutates each card at/above the floor by setting `card.recent_sale_prices_eur` to its cached recent sales.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_api.py
from src import api
from src.models import Appearance, Player, Card


def _mkcard(slug, price, scarcity="limited", season=2024):
    p = Player(slug, slug.title(), "FC", [Appearance(50, 90, True)])
    return Card(slug + "-c", p, scarcity, price, [], season)


def test_enrich_market_with_sales_floors_and_caches(monkeypatch):
    client = api.SorareClient(session=None, api_key="k", username="u")
    calls = []

    def fake_recent(slug, scarcity, season_year=0):
        calls.append((slug, scarcity, season_year))
        return [10.0, 11.0, 12.0, 13.0, 14.0]

    monkeypatch.setattr(client, "fetch_recent_sales", fake_recent)

    below = _mkcard("cheap", 2.0)     # under €3.50 floor -> not enriched, no call
    above1 = _mkcard("star", 8.0)     # enriched
    above2 = _mkcard("star", 9.0)     # same key -> served from cache, no 2nd call
    client.enrich_market_with_sales([below, above1, above2])

    assert below.recent_sale_prices_eur == []          # untouched
    assert above1.recent_sale_prices_eur == [10.0, 11.0, 12.0, 13.0, 14.0]
    assert above2.recent_sale_prices_eur == [10.0, 11.0, 12.0, 13.0, 14.0]
    # only one fetch for the shared (slug, scarcity, season) key
    assert calls == [("star", "limited", 2024)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_enrich_market_with_sales_floors_and_caches -v`
Expected: FAIL with `AttributeError: 'SorareClient' object has no attribute 'enrich_market_with_sales'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/api.py` — first the import near the top (with the other `from src...` imports):

```python
from src import flip
```

Then add this method to `SorareClient` (place it right after `fetch_recent_sales`):

```python
    def enrich_market_with_sales(self, cards) -> None:
        """Attach real recent-sales comps to market cards above the price floor.

        Market cards from fetch_market_cards carry only a floor reference, not
        real recent sales (unlike owned cards). The FLIP pass needs true comps,
        so this fills them in — but only for cards at/above flip.FLOOR_PRICE_EUR,
        which bounds the added API cost. One fetch per distinct
        (slug, scarcity, season_year), cached like fetch_my_cards.
        """
        sales_cache: dict = {}
        for card in cards:
            if card.price_eur < flip.FLOOR_PRICE_EUR:
                continue
            key = (card.player.slug, card.scarcity, card.season_year)
            if key not in sales_cache:
                sales_cache[key] = self.fetch_recent_sales(
                    card.player.slug, card.scarcity, card.season_year
                )
            sales = sales_cache[key]
            if sales:
                card.recent_sale_prices_eur = sales
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_enrich_market_with_sales_floors_and_caches -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: enrich market cards with recent-sales comps above floor"
```

---

### Task 5: Wire the FLIP table into the CLI run

**Files:**
- Modify: `sorare_value.py` (the `run` function)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `client.enrich_market_with_sales` (Task 4), `flip.rank_flips` (Task 2), `report.format_flips` (Task 3).
- Produces: the `run()` function now prints a third (FLIP) table after SELL.

- [ ] **Step 1: Read the current CLI test to match its fakes**

Run: `sed -n '1,80p' tests/test_cli.py` (or open it). It exercises `run()` with a
fake client exposing `wait_for_authentication`, `fetch_market_cards`,
`fetch_my_cards`. The new call `enrich_market_with_sales` must be added to that
fake. If the existing fake is a class, add a no-op method; if a `types.SimpleNamespace`
or `Mock`, add the attribute. Match whatever pattern the file already uses.

- [ ] **Step 2: Write the failing test**

```python
# add to tests/test_cli.py — adjust the fake-client construction to match the
# file's existing style; the key additions are the enrich no-op and the flip row.
import sorare_value
from src.models import Appearance, Player, Card


class _FakeClientWithFlip:
    def __init__(self):
        # a market card that is a clear flip: €8, comps avg €12 (5 sales)
        p = Player("bargain", "Bargain", "FC", [Appearance(50, 90, True)])
        self._market = [Card("b-c", p, "limited", 8.0, [], 2024)]

    def wait_for_authentication(self):
        pass

    def fetch_market_cards(self, scarcity, fixture_client=None):
        return self._market

    def enrich_market_with_sales(self, cards):
        for c in cards:
            c.recent_sale_prices_eur = [12.0, 12.0, 12.0, 12.0, 12.0]

    def fetch_my_cards(self):
        return []


def test_run_prints_flip_table():
    lines = []
    from src.prompts import Filters
    filters = Filters(min_price=0.0, max_price=1000.0, scarcity="limited", tier="all")
    sorare_value.run(_FakeClientWithFlip(), filters, output_fn=lines.append)
    joined = "\n".join(lines)
    assert "FLIP OPPORTUNITIES" in joined
    assert "Bargain" in joined
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_run_prints_flip_table -v`
Expected: FAIL — output has no "FLIP OPPORTUNITIES" (and/or `AttributeError` if the
real `run` doesn't call `enrich_market_with_sales`).

- [ ] **Step 4: Update `run()` in `sorare_value.py`**

Add `flip` to the imports:

```python
from src import api, buy, sell, report, flip
```

Extend `run()` — after the SELL block, before it returns:

```python
    output_fn("")  # spacer

    client.enrich_market_with_sales(market)
    flips = flip.rank_flips(market)
    output_fn(report.format_flips(flips))
```

The `market` list is already in scope from the BUY pass, so no re-scan.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_run_prints_flip_table -v`
Expected: PASS

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS (all tests, including the pre-existing ones)

- [ ] **Step 7: Commit**

```bash
git add sorare_value.py tests/test_cli.py
git commit -m "feat: print FLIP table after SELL in CLI run"
```

---

### Task 6: Docs + push to GitHub

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a FLIP section to `README.md`**

Add after the SELL description, matching the README's existing tone:

```markdown
## FLIP table (arbitrage)

A third report lists **live market listings priced below their recent-sales
comps** — cards to buy under market value and resell. Unlike the BUY table
(which dedupes by player), the FLIP table **keeps duplicate listings**: each
underpriced listing is an independent flip.

A listing qualifies when it clears a **€3.50 floor**, has **≥ 5 recent
comparable sales** (a trustworthy average and a provable exit), and is
discounted below comps by at least a **price-tiered threshold**:

- ≤ €10 → 30% · €10–25 → 25% · > €25 → 22.5%

Cheaper cards need a bigger cushion to clear fees; expensive cards clear profit
on a smaller %. Comps reuse the same `tokens.tokenPrices` source as the SELL
report, fetched only for cards above the floor to bound the API cost.
```

- [ ] **Step 2: Run the app end-to-end to confirm the table renders**

Run: `printf '5\n50\nlimited\nall\n\n' | python sorare_value.py 2>&1 | tail -20`
Expected: output ends with the "FLIP OPPORTUNITIES — LISTED BELOW COMPS" table
(or its "No flips found" line if the live market has none right now — both are a
pass; a crash or traceback is a fail).

- [ ] **Step 3: Commit the docs**

```bash
git add README.md
git commit -m "docs: document the FLIP arbitrage table"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```
Expected: push succeeds to `github.com/nickmolyvia/claude.git`.

---

## Self-Review

**Spec coverage:**
- Purpose / third table → Tasks 2, 3, 5. ✓
- BUY-vs-FLIP dedupe distinction (duplicates kept) → Task 2 `rank_flips` (no dedupe) + `test_duplicates_are_kept_and_ranked_by_discount`. ✓
- Reuse market scan, floor filter first → Task 4 enrich (floor before fetch) + Task 5 (reuses `market`). ✓
- Comps from cached `fetch_recent_sales` → Task 4. ✓
- Liquidity gate ≥5 → Task 2 `MIN_SALE_COUNT` + test. ✓
- Tiered discount (≤10/10–25/>25) with explicit boundaries → Task 1 `threshold_for` + boundary test. ✓
- Rank by discount desc → Task 2 + test. ✓
- `src/flip.py` module w/ `FlipPick`, `threshold_for`, `rank_flips` → Tasks 1–2. ✓
- `format_flips` columns (Player·Club·Scarcity·Price·Comp Avg·Discount·Sales·Season) → Task 3. ✓
- Wiring after SELL → Task 5. ✓
- Tests (tiers, floor, ≥5 gate, discount math, zero-comp safety, duplicates, ranking, report formatting) → Tasks 1–3. ✓
- Error handling (missing/zero comps skipped, failed fetch → [] skipped) → Task 2 (`comp_avg <= 0`, `len < 5`) + Task 4 (`if sales`). ✓
- Push to GitHub → Task 6. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. Task 5 Step 1 asks the engineer to read the existing `test_cli.py` fake style before adding to it — the concrete additions are given in Step 2.

**Type consistency:** `FlipPick(card, comp_avg, discount, sale_count, rationale)` defined in Task 2 and consumed identically in Task 3. `threshold_for`, `FLOOR_PRICE_EUR`, `MIN_SALE_COUNT` names consistent across Tasks 1, 2, 4. `enrich_market_with_sales(cards)` defined in Task 4, called in Task 5. `format_flips(picks)` defined in Task 3, called in Task 5. All consistent.
