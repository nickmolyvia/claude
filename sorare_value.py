# sorare_value.py
import requests

from src import api, buy, sell, report
from src.prompts import prompt_filters


def run(client, filters, output_fn=print) -> None:
    client.wait_for_authentication()

    market = client.fetch_market_cards(filters.scarcity)
    picks = buy.rank_buys(
        market, filters.min_price, filters.max_price, filters.scarcity, limit=50
    )
    output_fn(report.format_buys(picks))

    output_fn("")  # spacer

    mine = client.fetch_my_cards()
    signals = sell.rank_sells(mine)
    output_fn(report.format_sells(signals))


def main() -> None:
    creds = api.load_credentials()  # validates presence; raises with guidance if missing
    filters = prompt_filters()
    client = api.SorareClient(
        session=requests.Session(),
        api_key=creds.get("api_key", ""),
        username=creds.get("username", ""),
    )
    run(client, filters)


if __name__ == "__main__":
    main()
