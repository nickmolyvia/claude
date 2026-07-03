# FLIP Table — Seller + Time-Left — Design

**Date:** 2026-07-03
**Status:** Approved (pending spec review)

## Purpose

Add two columns to the FLIP table so a trader can act on a flip:

- **Seller** — the listing seller's nickname (recognise repeat sellers, look
  them up in the app).
- **Time Left** — a coarse relative countdown until the offer expires.

And **hide the user's own listings** from the FLIP table — a card you are
already selling is not a buy opportunity.

## Verified Against Live API

Introspection is disabled, so both fields were confirmed by probing real
queries:

- **Seller:** the offer's `sender` is a GraphQL **union**; selections need an
  inline fragment: `sender { ... on User { nickname slug } }`. Returns real
  nicknames (e.g. `satonio`).
- **Time left:** the offer node exposes `endDate`, an ISO-8601 UTC timestamp
  (e.g. `2026-07-03T09:11:19Z`).

Both live on the `liveSingleSaleOffers.nodes[]` offer wrapper — the same node
the price fix already reads — so no new top-level query is needed.

## Data Flow

1. **`api.py` — extend the market query.** Add `endDate` and
   `sender { ... on User { nickname slug } }` to the offer node in
   `fetch_market_cards`'s query (alongside the existing `receiverSide` /
   `senderSide`).
2. **`models.py` — extend `Card`** with two optional, defaulted fields so no
   other caller breaks:
   - `seller_nickname: str = ""`
   - `offer_end_date: str = ""`  (raw ISO-8601 string; parsing/formatting is
     deferred to display time to keep the model dumb).
3. **`api.py` — populate + filter in `fetch_market_cards`.** The offer wrapper
   is not visible to `card_from_json`, so set the two new fields on each card
   where the offer is already read (next to the authoritative price
   assignment). Before adding a card, **skip the whole offer when the seller is
   the user** (self-listing filter, below).
4. **`report.py` — render** the two new columns, formatting `offer_end_date`
   into a countdown via a testable helper.

## Self-Listing Filter

In `fetch_market_cards`, for each offer read `sender.slug` (via the inline
fragment). If it equals `self.username` (case-insensitive, after strip), skip
every card in that offer — the user's own listings never enter the FLIP list.

- Matching on `slug` (stable identifier), not `nickname`.
- If `self.username` is empty, no filtering happens (nothing to match).
- Filtering at the source keeps `flip.py` pure ranking logic.

## Time-Left Formatting

A helper `format_time_left(iso_str: str, now: datetime) -> str`:

- Empty / missing `iso_str` → `"—"`.
- Parse ISO-8601 (`endDate` ends in `Z` = UTC). On any parse failure → `"—"`.
- `delta = end - now`. If `delta <= 0` (already expired) → `"—"`.
- Otherwise coarse buckets:
  - `>= 1 day` → `"{d}d {h}h"` (e.g. `2d 4h`)
  - `>= 1 hour` → `"{h}h {m}m"` (e.g. `1h 30m`)
  - else → `"{m}m"` (e.g. `45m`)

`now` is a **parameter**, never read inside the helper, so the function is
deterministic and unit-testable without mocking the clock. The real wall-clock
is taken once at the top (see Time Source) and threaded down.

## Time Source

`Date.now()`-style calls are avoided inside pure helpers. `run()` computes the
current time once — `now = datetime.now(timezone.utc)` — and passes it to
`report.format_flips(flips, now)`, which passes it to `format_time_left`.
Real clock at the top, injected everywhere below.

## Report Columns

`format_flips(picks, now)` gains two columns. New column order:

`Player · Club · Scarcity · Price € · Comp Avg € · Discount · Sales · Season · Seller · Time Left`

The row already holds `p.card`, so it reads `p.card.seller_nickname` and
`format_time_left(p.card.offer_end_date, now)`. Seller is truncated to the
column width like the other string columns. Existing style is preserved (shared
`_row` helper, fixed widths, UTF-8 `€`). Empty list → the existing
"No flips found" line (unchanged).

## Wiring

`sorare_value.py run()` already calls `report.format_flips(flips)`. Change the
call to `report.format_flips(flips, now)` where
`now = datetime.now(timezone.utc)` is computed once at the top of the flip
block. No other change to the run order (BUY → SELL → FLIP).

## Testing

- **Market mapping:** an offer with `endDate` and `sender.nickname` yields a
  card with `seller_nickname` and `offer_end_date` set.
- **Self-listing filter:** an offer whose `sender.slug == username` is
  excluded; an offer from another seller is kept. Empty username → no
  filtering.
- **`format_time_left`:** days (`2d 4h`), hours (`1h 30m`), minutes (`45m`),
  already-expired → `—`, empty string → `—`, malformed string → `—`. All with
  an injected fixed `now`.
- **`format_flips`:** header includes `Seller` and `Time Left`; a sample row
  renders the nickname and a countdown, given a fixed `now`.

## Error Handling

Same defensive posture as the rest of the tool:

- Missing `sender` / `nickname` → `seller_nickname` stays `""` (blank cell, no
  crash).
- Missing / malformed / expired `endDate` → `"—"`, never a crash.
- Union field absent (non-User sender) → treated as no nickname / no slug, so
  the card is kept and shows a blank seller.

## Out of Scope (YAGNI)

- Seller reputation / trade history / rating.
- Auction market (still only `liveSingleSaleOffers`).
- Sorting or filtering the FLIP table by time-left or seller.

## Delivery

After implementation and green tests, commit and push to `main`
(`origin` = `github.com/nickmolyvia/claude.git`).
