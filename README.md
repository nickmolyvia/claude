# Sorare Value Finder

CLI tool that ranks the top 50 value-for-money Sorare signings (filtered by
EUR price range and scarcity) and flags when to sell cards you already own.

## Setup

1. `pip install -r requirements.txt`
2. Copy `credentials.example.json` to `credentials.json` and fill in your
   Sorare login. `credentials.json` is gitignored — it never leaves your machine.
3. Add your **Sorare API key** to the `api_key` field (see "API key" below).

## Run

```bash
python sorare_value.py
```

The script prompts for min price, max price (EUR), scarcity, and a league
tier, then pauses for you to complete authentication before producing the
BUY and SELL reports.

**League tier (BUY filter):** choose how wide to cast the buy list —
- `top5` — Premier League, LaLiga, Serie A, Bundesliga, Ligue 1
- `top7` — top 5 plus Eredivisie and Primeira Liga
- `top10` — top 7 plus Süper Lig, MLS, and the Jupiler Pro League
- `all` — every league (no restriction)

Cards from stronger leagues trade richer, so the best *value* picks often sit
in smaller leagues — expect `top5` to return a short list and `all` to return
the most options. The tier filters the BUY list only; the SELL report always
shows every card you own.

**Season-matched comps:** each card carries a `seasonYear` (e.g. 2024). The
SELL "vs Sales" comparison pulls recent sales for the *same* season only, so a
2024 card is compared to 2024 sales — otherwise cheaper old-season sales would
drag the average down and distort the signal.

## API key (required for the market scan)

The Sorare GraphQL API caps **anonymous** queries at a nesting depth of 7.
The market-scan query is deeper than that, so an API key (which raises the
limit to 13) is required for the BUY report. Request a key from your Sorare
account settings and put it in `credentials.json` under `api_key`. It is sent
as the `APIKEY` request header.

The SELL report reads your own collection (`currentUser`), which additionally
requires a signed/authenticated session — this is the login you complete
during the pause.

## Live schema notes (Task 10)

Field names were reconciled against the live Sorare schema (introspection is
disabled, so they were confirmed by probing real queries):

- Endpoint: `https://api.sorare.com/federation/graphql`
- Players: `football.player(slug:)`, scores via `so5Scores(last: N) { score
  playerGameStats { minsPlayed onGameSheet } }`. `onGameSheet` is the proxy
  for "started". `so5Scores` is returned **newest-first**, so the mapper
  reverses it to oldest-first (otherwise the SELL outlook would be inverted).
- Scarcity is `rarityTyped` (e.g. `limited`), not `rarity`.
- Prices: a listed card's `liveSingleSaleOffer` gives EUR via
  `MonetaryAmount.eurCents`. A card that is **not listed** (e.g. one you own
  and hold) has no offer, so its value falls back to `priceRange.min` (wei,
  converted to EUR at the live ETH rate) and then `publicMinPrices.eurCents`.
  `null` everywhere → unpriced.
- The market list comes from `tokens.liveSingleSaleOffers`.
- ETH→EUR conversion: `priceRange` is quoted in wei, and the schema exposes
  no fiat rate, so the live rate is fetched from CoinGecko (free, no key)
  with a hardcoded fallback if unreachable.

**SELL "vs Sales":** recent completed sales come from
`tokens.tokenPrices(playerSlug:, rarity:)` — real sale prices (eurCents +
date, newest-first). For each owned card the report pulls that player's
recent sales and compares the card's current price against their average.
A negative % means the card is priced **below** its recent sales (cheap — a
poor time to sell); a positive % means it's priced **above** recent sales
(rich — a better time to sell). This costs one extra API call per distinct
player in your collection, so the SELL report takes a few seconds.

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

Each flip row also shows the **Seller** (the listing's Sorare nickname) and
**Time Left** — a coarse countdown to the offer's expiry (`2d 4h`, `1h 30m`,
`45m`, or `—` when an offer has no end date). Your **own listings are hidden**
from the FLIP table, since a card you are already selling is not a buy
opportunity.

## Fixture strength from clubelo (Elo model)

The `Proj` value includes a **fixture multiplier** based on how hard the
player's next match is. The strength signal comes from **clubelo.com** — a
free, no-key, non-gambling Elo model (the same Elo foundation bookmakers build
their prices on):

- clubelo's `/Fixtures` feed gives, per upcoming match, a full goal-difference
  probability distribution. Summing the "home wins by N" columns yields a clean
  home-win probability (mirror for the away side). No bookmaker margin to
  remove — a model distribution already sums to 1.
- That win probability drives the multiplier: 50% = neutral; a favourite is
  boosted, an underdog cut. The swing is **±30% for top-5-league** clubs and
  **±20%** for everyone else.
- Club names differ between Sorare and clubelo ("FC Bayern München" vs
  "Bayern"), so a normaliser + alias table (`src/odds.py`) matches them
  best-effort; unmatched clubs fall back to neutral.
- No API key needed. If clubelo can't be reached, the multiplier stays neutral
  (1.0) and the tool works exactly as before.

**Seasonal:** clubelo only lists *upcoming* fixtures, so mid-summer the feed is
nearly empty and almost every player stays neutral — which is fine, since this
script is meant to be run as the new season approaches, when fixtures (and the
multiplier) are fully populated.

## Design & plan

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
