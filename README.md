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

The script prompts for min price, max price (EUR), and scarcity, then pauses
for you to complete authentication before producing the BUY and SELL reports.

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
  and hold) has no offer, so its value falls back to `publicMinPrices`
  (the card's public floor, also in `eurCents`). `null` everywhere → unpriced.
  `priceRange { min max }` values are wei strings and are not used.
- The market list comes from `tokens.liveSingleSaleOffers`.

**SELL "vs History" caveat:** the public schema does not expose a per-card
recent-sales list without deeper auth, so the SELL report compares your
card's asking price against the current **market floor** (`publicMinPrices`),
not a trailing sales average. It still catches "priced well above the floor,"
but read it as "vs floor," not "vs my own sale history."

Upcoming-fixture difficulty is not exposed in a simple numeric form by the
public schema, so the fixture nudge is currently neutral (multiplier 1.0) and
projections rest on recent form × minutes-reliability.

## Design & plan

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
