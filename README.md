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
  playerGameStats { minsPlayed onGameSheet } }`. `onGameSheet` is used as the
  proxy for "started".
- Scarcity is `rarityTyped` (e.g. `limited`), not `rarity`.
- Prices come as `MonetaryAmount.eurCents` on a card's
  `liveSingleSaleOffer` (already in EUR cents; may be `null` for crypto-only
  listings, which the mapper treats as unpriced). `priceRange { min max }`
  values are wei strings and are not used.
- The market list comes from `tokens.liveSingleSaleOffers`.

Upcoming-fixture difficulty is not exposed in a simple numeric form by the
public schema, so the fixture nudge is currently neutral (multiplier 1.0) and
projections rest on recent form × minutes-reliability.

## Design & plan

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
