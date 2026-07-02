# Sorare Value Finder

CLI tool that ranks the top 50 value-for-money Sorare signings (filtered by
EUR price range and scarcity) and flags when to sell cards you already own.

## Setup

1. `pip install -r requirements.txt`
2. Copy `credentials.example.json` to `credentials.json` and fill in your
   Sorare login. `credentials.json` is gitignored — it never leaves your machine.

## Run

```bash
python sorare_value.py
```

The script prompts for min price, max price (EUR), and scarcity, then pauses
for you to complete authentication before producing the BUY and SELL reports.

## Design & plan

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
