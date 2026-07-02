# tests/test_api.py
import json
import pytest
from src import api
from src.models import Card


SAMPLE_PLAYER = {
    "slug": "kylian-mbappe",
    "displayName": "Kylian Mbappe",
    "activeClub": {"name": "Real Madrid"},
    "recentAppearances": [
        {"score": 65.0, "minutesPlayed": 90, "started": True},
        {"score": 40.0, "minutesPlayed": 30, "started": False},
    ],
    "upcomingFixtures": [
        {"opponentName": "Getafe", "difficulty": 0.3},
    ],
}

SAMPLE_CARD = {
    "slug": "card-abc",
    "rarity": "limited",
    "priceEur": 42.5,
    "recentSalesEur": [40.0, 44.0, 43.0],
    "player": SAMPLE_PLAYER,
}


def test_player_from_json_maps_fields():
    p = api.player_from_json(SAMPLE_PLAYER)
    assert p.slug == "kylian-mbappe"
    assert p.display_name == "Kylian Mbappe"
    assert p.club == "Real Madrid"
    assert p.recent_appearances[0].so5_score == 65.0
    assert p.recent_appearances[1].started is False
    assert p.upcoming_fixtures[0].difficulty == 0.3


def test_card_from_json_maps_fields():
    c = api.card_from_json(SAMPLE_CARD)
    assert isinstance(c, Card)
    assert c.slug == "card-abc"
    assert c.scarcity == "limited"
    assert c.price_eur == 42.5
    assert c.recent_sale_prices_eur == [40.0, 44.0, 43.0]
    assert c.player.display_name == "Kylian Mbappe"


def test_load_credentials_missing_file_points_to_template(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        api.load_credentials(str(tmp_path / "nope.json"))
    assert "credentials.example.json" in str(exc.value)


def test_load_credentials_reads_json(tmp_path):
    p = tmp_path / "credentials.json"
    p.write_text(json.dumps({"email": "a@b.com", "password": "x", "api_key": ""}))
    creds = api.load_credentials(str(p))
    assert creds["email"] == "a@b.com"


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json})
        return _FakeResponse(self._payload)


def test_fetch_market_cards_maps_nodes():
    payload = {"data": {"cards": {"nodes": [SAMPLE_CARD]}}}
    client = api.SorareClient(session=_FakeSession(payload))
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].player.display_name == "Kylian Mbappe"


def test_post_raises_on_graphql_errors():
    payload = {"errors": [{"message": "bad query"}]}
    client = api.SorareClient(session=_FakeSession(payload))
    with pytest.raises(RuntimeError) as exc:
        client._post("query {}", {})
    assert "bad query" in str(exc.value)


def test_wait_for_authentication_blocks_until_confirmed():
    client = api.SorareClient(session=_FakeSession({"data": {}}))
    client.wait_for_authentication(prompt_fn=lambda _="": "")
    assert client.authenticated is True
