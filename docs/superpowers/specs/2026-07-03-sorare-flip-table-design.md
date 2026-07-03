# Sorare FLIP Table — Design

**Date:** 2026-07-03
**Status:** Approved (pending spec review)

## Purpose

Add a third report — **FLIP** — alongside the existing BUY and SELL tables.
The FLIP table surfaces cards currently listed on the market **below their
recent-sales comps**: pure arbitrage candidates a trader can buy under market
value and resell for profit.

This complements, and does **not** replace, the BUY table. The BUY table ranks
by projected points per euro (a reward-EV metric — high So5 scores win gameweek
rewards, which is itself monetary). The FLIP table answers a different question:
*"which live listings are underpriced versus what the card actually sells for?"*

## Key Distinction from BUY

- **BUY** dedupes by player — you only field one card, so duplicates are noise.
- **FLIP** keeps duplicates — each underpriced listing is an independent profit
  opportunity. If the same player is listed 5 times all below comps, that is 5
  flips, not 1. Deduping would discard real money.

## Data Flow

1. **Reuse the existing market scan** (`SorareClient.fetch_market_cards`) — the
   same ~300 listings already pulled for BUY. No additional market queries.
2. **Floor filter first:** keep only cards priced **≥ €3.50**. This drops the
   cheap-commons long tail *before* any comp lookups, sharply cutting API cost
   (most listings are sub-€3.50 commons).
3. For each surviving distinct `(player_slug, scarcity, season_year)`, call the
   **existing** `SorareClient.fetch_recent_sales(slug, scarcity, season_year)` —
   the same method the SELL table uses, with the same per-key caching so a
   repeated player is fetched once.
4. Compute per card:
   - `comp_avg` = mean of recent-sales EUR prices for that key
   - `sale_count` = number of recent sales
   - `discount` = `(comp_avg - price) / comp_avg`
5. **Qualify** a listing as a flip when **both** hold:
   - `sale_count >= 5` — liquidity: a trustworthy average and provable exit.
   - `discount >= threshold_for(price)` — tiered by price (see below).
6. **Rank** qualified flips by `discount` descending. **No dedupe** — every
   qualifying listing is its own row; the best flip of a repeated player floats
   to the top, the rest follow in discount order.

## Tiered Discount Threshold

Cheaper cards need a larger % cushion to clear the fixed marketplace fee + gas +
the haircut taken to resell quickly; expensive cards clear profit on a smaller
%. Boundaries are explicit so nothing falls through a crack:

| Card price (€)      | Min discount vs comps |
|---------------------|-----------------------|
| `price <= 10`       | 30%                   |
| `10 < price <= 25`  | 25%                   |
| `price > 25`        | 22.5%                 |

`threshold_for(price)` is the single source of truth for these tiers, so they
are trivially tunable after seeing real output.

## New Module: `src/flip.py`

Mirrors the shape of `src/buy.py` to keep flip logic isolated and unit-testable
without touching `buy.py` or `sell.py`.

- `FLOOR_PRICE_EUR = 3.50`
- `MIN_SALE_COUNT = 5`
- `@dataclass FlipPick` — `card`, `comp_avg`, `discount`, `sale_count`,
  `rationale`.
- `threshold_for(price) -> float` — the tier table above.
- `rank_flips(cards, limit=50) -> list[FlipPick]`:
  - filter to `card.price_eur >= FLOOR_PRICE_EUR`
  - require `len(card.recent_sale_prices_eur) >= MIN_SALE_COUNT`
  - compute `comp_avg`; skip if `comp_avg <= 0` (never a flip, never a crash)
  - compute `discount`; qualify if `discount >= threshold_for(price)`
  - rank by `discount` descending, **no dedupe**, cap at `limit`.

`rank_flips` reads comps from `card.recent_sale_prices_eur` — the market cards
must be enriched with recent sales first (see Wiring).

## Comp Enrichment for Market Cards

Market cards from `fetch_market_cards` are seeded only with a floor reference,
not real recent sales (unlike owned cards, which `fetch_my_cards` already
enriches). The FLIP pass therefore enriches the **floor-filtered** market cards
with recent sales before ranking:

- A new `SorareClient.enrich_with_sales(cards)` (or an inline pass in
  `sorare_value.py`) applies the €3.50 floor, then for each distinct
  `(slug, scarcity, season_year)` calls the cached `fetch_recent_sales` and sets
  `card.recent_sale_prices_eur`. This reuses the exact caching pattern already
  in `fetch_my_cards`, so the logic is proven.

This is the only added API cost, and it is bounded by the €3.50 floor.

## Report: `format_flips` in `src/report.py`

A new `format_flips(picks)` producing a third table, printed after SELL.

Columns: `Player · Club · Scarcity · Price € · Comp Avg € · Discount % · Sales(n) · Season`

Matches the visual style of `format_buys` / `format_sells` (fixed-width,
UTF-8 € rendering). Empty list → a clear "no flips found" line, consistent with
the other tables.

## Wiring: `sorare_value.py`

After the SELL block in `run()`:

1. Enrich the floor-filtered market cards with recent sales.
2. `flips = flip.rank_flips(market)`.
3. `output_fn(report.format_flips(flips))`.

The market list is already in hand from the BUY pass, so no re-scan.

## Testing

New `tests/test_flip.py`:

- `threshold_for` at each tier and at the exact boundaries (10, 25).
- The €3.50 floor (a €3.49 card is excluded, €3.50 included).
- The `>= 5` sales gate (4 sales excluded, 5 included).
- Discount math and qualification for a card just above/below its threshold.
- Zero/empty comp safety (`comp_avg == 0` → skipped, no crash).
- **Duplicates kept:** the same player listed multiple times below comps yields
  multiple rows, ranked by discount.
- Ranking order (discount descending).

Plus a `tests/test_report.py` case for `format_flips` formatting (header,
a sample row, and the empty case).

## Error Handling

Same defensive posture as the rest of the tool:

- Missing or zero comps → the card is simply not a flip (never a crash).
- A failed `fetch_recent_sales` returns `[]` → the card has too few sales and is
  silently skipped.
- Zero/negative prices are already excluded by the €3.50 floor.

## Out of Scope (YAGNI)

Noted as possible future work, not built now:

- Auction / primary market (only `liveSingleSaleOffers` is scanned).
- Live price trend (week-over-week floor direction).
- Injuries / suspensions / rotation risk.
- Sale velocity / days-to-sell liquidity modelling.

## Delivery

After implementation and green tests, commit and **push to GitHub**
(`origin` = `github.com/nickmolyvia/claude.git`).
