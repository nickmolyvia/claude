# tests/test_api.py
#
# These mocks mirror the REAL Sorare schema shapes confirmed live in Task 10:
#   - player: displayName, activeClub.name, so5Scores[].score,
#     so5Scores[].playerGameStats.{minsPlayed,onGameSheet}
#   - card: rarityTyped, liveSingleSaleOffer.receiverSide.amounts.eurCents,
#     anyPlayer (the player behind the card)
#   - market: tokens.liveSingleSaleOffers.nodes[].senderSide.anyCards[]
import json
import pytest
from src import api
from src.models import Card


SAMPLE_PLAYER = {
    "slug": "kylian-mbappe-lottin",
    "displayName": "Kylian Mbappe",
    "activeClub": {"name": "Real Madrid"},
    "so5Scores": [
        {"score": 65.0, "playerGameStats": {"minsPlayed": 90, "onGameSheet": True}},
        {"score": 40.0, "playerGameStats": {"minsPlayed": 30, "onGameSheet": False}},
    ],
}

SAMPLE_CARD = {
    "slug": "kylian-mbappe-lottin-2024-limited-493",
    "rarityTyped": "limited",
    "publicMinPrices": {"eurCents": 4000},
    "liveSingleSaleOffer": {"receiverSide": {"amounts": {"eurCents": 4250}}},
    "anyPlayer": SAMPLE_PLAYER,
}


def test_eur_from_cents():
    assert api.eur_from_cents(119) == 1.19
    assert api.eur_from_cents(None) == 0.0


def test_player_from_json_reverses_to_oldest_first():
    # SAMPLE_PLAYER lists scores NEWEST-first (65 is newest, 40 is older),
    # mirroring Sorare's so5Scores(last:N). The mapper must reverse to
    # oldest-first so outlook_trend reads chronology correctly.
    p = api.player_from_json(SAMPLE_PLAYER)
    assert p.slug == "kylian-mbappe-lottin"
    assert p.display_name == "Kylian Mbappe"
    assert p.club == "Real Madrid"
    # oldest first after reversal:
    assert p.recent_appearances[0].so5_score == 40.0
    assert p.recent_appearances[0].started is False
    assert p.recent_appearances[-1].so5_score == 65.0
    assert p.recent_appearances[-1].minutes_played == 90
    assert p.recent_appearances[-1].started is True


def test_card_from_json_prefers_offer_price():
    c = api.card_from_json(SAMPLE_CARD)
    assert isinstance(c, Card)
    assert c.slug == "kylian-mbappe-lottin-2024-limited-493"
    assert c.scarcity == "limited"
    assert c.price_eur == 42.5  # 4250 cents offer beats 4000 floor
    assert c.player.display_name == "Kylian Mbappe"


def test_card_from_json_falls_back_to_floor_when_unlisted():
    # An owned/held card has no live offer; floor price gives it real value.
    node = {**SAMPLE_CARD, "liveSingleSaleOffer": None}
    c = api.card_from_json(node)
    assert c.price_eur == 40.0  # 4000 cents floor
    assert c.recent_sale_prices_eur == [40.0]  # floor seeded as market reference


def test_card_from_json_handles_crypto_only_null_price():
    node = {
        **SAMPLE_CARD,
        "publicMinPrices": None,
        "liveSingleSaleOffer": {"receiverSide": {"amounts": {"eurCents": None}}},
    }
    c = api.card_from_json(node)
    assert c.price_eur == 0.0  # null everywhere -> 0.0, no crash
    assert c.recent_sale_prices_eur == []


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
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResponse(self._payload)


def test_fetch_market_cards_maps_offers_and_filters_scarcity():
    rare_card = {**SAMPLE_CARD, "rarityTyped": "rare"}
    payload = {"data": {"tokens": {"liveSingleSaleOffers": {"nodes": [
        {"receiverSide": {"amounts": {"eurCents": 4250}},
         "senderSide": {"anyCards": [SAMPLE_CARD]}},
        {"receiverSide": {"amounts": {"eurCents": 9000}},
         "senderSide": {"anyCards": [rare_card]}},
    ]}}}}
    client = api.SorareClient(session=_FakeSession(payload))
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].player.display_name == "Kylian Mbappe"
    assert cards[0].scarcity == "limited"


def test_api_key_sent_as_header():
    payload = {"data": {"tokens": {"liveSingleSaleOffers": {"nodes": []}}}}
    session = _FakeSession(payload)
    client = api.SorareClient(session=session, api_key="secret-key")
    client.fetch_market_cards("limited")
    assert session.calls[0]["headers"]["APIKEY"] == "secret-key"


def test_no_api_key_omits_header():
    payload = {"data": {"tokens": {"liveSingleSaleOffers": {"nodes": []}}}}
    session = _FakeSession(payload)
    client = api.SorareClient(session=session)  # no key
    client.fetch_market_cards("limited")
    assert "APIKEY" not in session.calls[0]["headers"]


def test_post_raises_on_graphql_errors():
    payload = {"errors": [{"message": "bad query"}]}
    client = api.SorareClient(session=_FakeSession(payload))
    with pytest.raises(RuntimeError) as exc:
        client._post("query {}", {})
    assert "bad query" in str(exc.value)


def test_post_raises_on_http_error_status():
    session = _FakeSession({"whatever": True})
    session._payload = {"whatever": True}
    client = api.SorareClient(session=session)
    # Force a 429 response from the fake session.
    orig_post = session.post

    def post_429(*a, **k):
        resp = orig_post(*a, **k)
        resp.status_code = 429
        return resp

    session.post = post_429
    with pytest.raises(RuntimeError) as exc:
        client._post("query {}", {})
    assert "429" in str(exc.value)


def test_wait_for_authentication_blocks_until_confirmed():
    client = api.SorareClient(session=_FakeSession({"data": {}}))
    client.wait_for_authentication(prompt_fn=lambda _="": "")
    assert client.authenticated is True
