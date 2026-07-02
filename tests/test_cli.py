# tests/test_cli.py
from src.models import Appearance, Fixture, Player, Card
from src.prompts import Filters
import sorare_value


def _card(name, price, scarcity="limited", score=60.0):
    p = Player(name, name, "Club",
               [Appearance(score, 90, True), Appearance(score, 90, True)],
               [Fixture("x", 0.5)])
    return Card(name, p, scarcity, price, [price])


class _FakeClient:
    def __init__(self):
        self.authenticated = False
        self.market = [_card("Cheap", 10.0), _card("Pricey", 500.0)]
        self.mine = [_card("Owned", 100.0)]

    def wait_for_authentication(self, prompt_fn=input):
        self.authenticated = True

    def fetch_market_cards(self, scarcity, max_pages=6, fixture_client=None):
        return [c for c in self.market if c.scarcity == scarcity]

    def fetch_my_cards(self):
        return self.mine


def test_run_produces_both_reports_and_respects_filters():
    lines = []
    client = _FakeClient()
    filters = Filters(min_price=5.0, max_price=50.0, scarcity="limited")
    sorare_value.run(client, filters, output_fn=lines.append)

    out = "\n".join(lines)
    assert client.authenticated is True
    assert "TOP VALUE-FOR-MONEY SIGNINGS" in out
    assert "YOUR COLLECTION" in out
    assert "Cheap" in out       # within price range
    assert "Pricey" not in out  # 500 EUR filtered out by max_price
    assert "Owned" in out       # collection always shown
