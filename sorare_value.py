# sorare_value.py
import sys
import requests

from src import api, buy, sell, report
from src.odds import OddsClient
from src.prompts import prompt_filters

# Windows consoles often default to a legacy codepage (e.g. Greek cp1253) that
# can't print the € symbol, crashing the report. Force UTF-8 output so prices
# render everywhere.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def run(client, filters, output_fn=print, odds_client=None) -> None:
    client.wait_for_authentication()

    market = client.fetch_market_cards(filters.scarcity, odds_client=odds_client)
    picks = buy.rank_buys(
        market, filters.min_price, filters.max_price, filters.scarcity,
        limit=50, tier=filters.tier,
    )
    output_fn(report.format_buys(picks))

    output_fn("")  # spacer

    mine = client.fetch_my_cards()
    signals = sell.rank_sells(mine)
    output_fn(report.format_sells(signals))


def main() -> None:
    creds = api.load_credentials()  # validates presence; raises with guidance if missing
    filters = prompt_filters()
    session = requests.Session()
    client = api.SorareClient(
        session=session,
        api_key=creds.get("api_key", ""),
        username=creds.get("username", ""),
    )
    # Odds are optional: with no odds_api_key the fixture multiplier stays
    # neutral and the tool works exactly as before.
    odds_client = OddsClient(api_key=creds.get("odds_api_key", ""), session=session)
    run(client, filters, odds_client=odds_client)


if __name__ == "__main__":
    main()
