# Sorare Value Finder — Design

**Date:** 2026-07-02
**Status:** Approved (design), pending user review of spec

## Purpose

A single Python CLI tool that helps a Sorare player make better market decisions. Each time it runs, it produces two ranked reports:

1. **BUY** — the top 50 "value for money" card signings currently available on the market, filtered by the user's chosen price range (EUR) and scarcity.
2. **SELL** — the cards already in the user's collection, each flagged with whether now is a good time to sell.

Both halves share a single fair-value engine so the logic is consistent in both directions: buy cards priced *below* fair value, sell cards priced *above* it.

## Non-Goals (YAGNI)

- No sports betting / bookmaker functionality (explicitly out of scope).
- No automated buying or selling — the tool only advises; the user acts manually.
- No GUI or web interface — terminal CLI only.
- No pure market-arbitrage "flipping" mode in v1 (considered, deferred).
- No persistent database — each run is stateless aside from reading credentials.
- No live-API integration tests in the automated suite.

## Definitions

**Value for money (BUY):** `value_score = projected_points ÷ price`. A card is good value when its projected fantasy output is high relative to its asking price.

**Good time to sell (SELL):** flag `SELL` when the card's recent sales price is historically high AND/OR the player's forward outlook is weakening — i.e. the market is paying more than the player is currently worth. Otherwise `HOLD`.

**Fair value:** expected points ÷ the cost of an equivalent card, computed by the shared engine from real API data plus light, traceable adjustments.

## Architecture

A single Python CLI script. On each run it:
1. Interactively prompts the user for filters (min price, max price in EUR, scarcity).
2. Authenticates as the user against the Sorare GraphQL API — the script pauses and waits for the user to complete the login before continuing.
3. Runs the BUY report and the SELL report.
4. Prints both as formatted terminal tables.

### File structure

All files live at the repository root (`claude/`); the tree below shows the layout, not a nested subfolder.

```
claude/  (repo root)
├─ sorare_value.py            # entry point: prompts → auth → buy report + sell report
├─ src/
│  ├─ api.py                  # Sorare GraphQL client (queries, auth, rate-limit handling)
│  ├─ fair_value.py           # shared engine: form + minutes-reliability + fixtures → fair €/points
│  ├─ buy.py                  # market scan → filter → rank top 50
│  ├─ sell.py                 # read collection → sell-signal per card
│  └─ report.py               # formatted terminal output (tables)
├─ credentials.example.json   # committed template
├─ credentials.json           # gitignored — user fills in
├─ .gitignore
├─ requirements.txt
└─ README.md
```

Each module has one clear purpose and communicates through plain data structures (dicts / small dataclasses), so it can be understood and tested independently.

## Component: Fair-value engine (`fair_value.py`)

The heart of the tool. For any player it computes **projected points** and a **fair price**, using only real API data plus light adjustments (the agreed #1 form-based + #3 projection blend):

- **Recent form** — average SO5 score over the last N appearances (the base signal).
- **Minutes reliability** — a weight/filter: does the player actually start? Drops bench players whose past points are a fluke.
- **Fixture nudge** — upcoming opponent difficulty tilts the projection slightly up or down.

Every input is traceable to source data — no black-box model. Consumed by both BUY (find cards below fair) and SELL (find cards above fair).

## Component: BUY logic (`buy.py`)

1. Query the market for cards matching the user's **scarcity** and **price range (EUR)**.
2. For each candidate, run the fair-value engine → `value_score = projected_points ÷ price`.
3. Rank descending; take the **top 50**.
4. Over-budget players are filtered out before ranking (e.g. a star above the user's max price never appears).

**Output columns:** player, club, scarcity, current price (€), recent avg score, projected score, value score, one-line rationale.

## Component: SELL logic (`sell.py`)

1. Authenticated query → the user's collection.
2. Per card, compute fair value plus **price position** (is the recent sales price historically high for this specific card?).
3. Flag `SELL` when price is historically high AND/OR forward outlook is weakening; otherwise `HOLD`.
4. Rank by sell-strength.

**Output columns:** player, scarcity, estimated value (€), price-vs-history, outlook trend, signal (SELL/HOLD), one-line reason.

## Component: Filters & interaction

Filters are collected via **interactive prompts** each run (the user is already present for auth). Prices are entered in **EUR**.

- **Min price (€)** and **Max price (€)** — bound the BUY candidate set.
- **Scarcity** — limited / rare / super rare / unique (per Sorare's tiers).

Because filters are per-run, the tool adapts to the user's changing budget without editing any files.

## Component: Auth & credentials

- `.gitignore` excludes `credentials.json`, `.env`, `__pycache__/`, and other local artifacts.
- `credentials.example.json` is committed as a template showing the required fields.
- On run, the script loads credentials, initiates login, and **pauses/waits** for the user to complete authentication before continuing.
- Authentication mechanics themselves are handled by the user during that pause; the script's responsibility is to wait and then proceed with an authenticated session.

## Error handling

- **API down / rate-limited:** retry with backoff, then a clear message.
- **No cards match filters:** report it plainly; do not crash.
- **Auth not completed:** wait, then a clear error if it cannot proceed.
- **Missing credentials file:** point the user to `credentials.example.json`.

## Testing

Unit tests for the fair-value engine and the buy/sell ranking, using **mocked API responses** (fixed sample fixtures). Logic is verified without hitting the live API or requiring a login. No live-API tests in the suite.

## Currency

All user-facing prices are in **EUR**. (Sorare also exposes ETH; not used in v1.)

## Open questions / future work

- Optional market-arbitrage "flipping" mode (the deferred #2 approach) could be added as a third report later.
- Projection model could be deepened over time; v1 intentionally keeps adjustments light and traceable.
