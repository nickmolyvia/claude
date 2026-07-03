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
    "activeClub": {"name": "Real Madrid", "domesticLeague": {"slug": "laliga-es"}},
    "so5Scores": [
        {"score": 65.0, "playerGameStats": {"minsPlayed": 90, "onGameSheet": True}},
        {"score": 40.0, "playerGameStats": {"minsPlayed": 30, "onGameSheet": False}},
    ],
}

SAMPLE_CARD = {
    "slug": "kylian-mbappe-lottin-2024-limited-493",
    "rarityTyped": "limited",
    "seasonYear": 2024,
    "publicMinPrices": {"eurCents": 4000},
    "liveSingleSaleOffer": {"receiverSide": {"amounts": {"eurCents": 4250}}},
    "anyPlayer": SAMPLE_PLAYER,
}


def test_eur_from_cents():
    assert api.eur_from_cents(119) == 1.19
    assert api.eur_from_cents(None) == 0.0


def test_eur_from_wei():
    # 1 ETH (1e18 wei) at 1500 EUR/ETH = 1500 EUR
    assert api.eur_from_wei(int(1e18), 1500.0) == 1500.0
    # a small holding: 0.01 ETH at 1500 = 15 EUR
    assert abs(api.eur_from_wei(int(1e16), 1500.0) - 15.0) < 1e-6
    assert api.eur_from_wei(None, 1500.0) == 0.0
    assert api.eur_from_wei("0", 1500.0) == 0.0


def test_eur_from_usd_cents():
    # 100 US cents ($1.00) at 0.92 EUR/USD = 0.92 EUR
    assert abs(api.eur_from_usd_cents(100, 0.92) - 0.92) < 1e-9
    assert api.eur_from_usd_cents(None, 0.92) == 0.0
    assert api.eur_from_usd_cents(0, 0.92) == 0.0


def test_eur_from_gbp_cents():
    # 100 pence (£1.00) at 1.17 EUR/GBP = 1.17 EUR
    assert abs(api.eur_from_gbp_cents(100, 1.17) - 1.17) < 1e-9
    assert api.eur_from_gbp_cents(None, 1.17) == 0.0


def test_amounts_to_eur_uses_gbp_when_only_gbp_present():
    # A GBP-denominated offer: only gbpCents populated.
    eur = api._amounts_to_eur(
        {"eurCents": None, "usdCents": None, "gbpCents": 48, "wei": None},
        1500.0, 0.9, 1.17,
    )
    assert abs(eur - (0.48 * 1.17)) < 1e-9


def test_amounts_to_eur_prefers_eur_then_usd_then_wei():
    # EUR wins outright
    assert api._amounts_to_eur(
        {"eurCents": 500, "usdCents": 999, "wei": str(int(1e18))}, 1500.0, 0.9
    ) == 5.0
    # No EUR -> USD used
    assert abs(api._amounts_to_eur(
        {"eurCents": None, "usdCents": 200, "wei": None}, 1500.0, 0.9
    ) - 1.8) < 1e-9
    # No EUR/USD -> wei used
    assert abs(api._amounts_to_eur(
        {"eurCents": None, "usdCents": None, "wei": str(int(1e16))}, 1500.0, 0.9
    ) - 15.0) < 1e-9
    # Nothing priced -> 0.0
    assert api._amounts_to_eur(
        {"eurCents": None, "usdCents": None, "wei": None}, 1500.0, 0.9
    ) == 0.0


def test_offer_price_uses_usd_when_eur_null():
    # A USD-denominated live offer: eurCents/wei null, usdCents populated.
    node = {
        "liveSingleSaleOffer": {
            "receiverSide": {"amounts": {
                "eurCents": None, "usdCents": 67, "wei": None,
                "referenceCurrency": "USD",
            }}
        }
    }
    eur = api._offer_price_eur(node, eur_per_eth=1500.0, eur_per_usd=0.92)
    assert abs(eur - 0.6164) < 1e-4  # 0.67 USD * 0.92


def test_floor_price_uses_price_range_wei():
    # priceRange.min populates even when no offer/publicMinPrices exist.
    node = {
        "rarityTyped": "limited",
        "priceRange": {"min": str(int(1e16)), "max": str(int(2e16))},  # 0.01 ETH
        "anyPlayer": SAMPLE_PLAYER,
    }
    c = api.card_from_json(node, eur_per_eth=1500.0)
    assert abs(c.price_eur - 15.0) < 1e-6  # falls back to floor when unlisted
    assert abs(c.recent_sale_prices_eur[0] - 15.0) < 1e-6


def test_fetch_eur_per_eth_falls_back_on_error():
    class _BadSession:
        def get(self, *a, **k):
            raise RuntimeError("network down")
    assert api.fetch_eur_per_eth(_BadSession()) == api.FALLBACK_EUR_PER_ETH


def test_card_maps_season_year_and_league():
    c = api.card_from_json(SAMPLE_CARD)
    assert c.season_year == 2024
    assert c.player.league_slug == "laliga-es"


def test_fetch_recent_sales_passes_season_when_given():
    payload = {"data": {"tokens": {"tokenPrices": [
        {"date": "2026-07-02", "amounts": {"eurCents": 100}},
    ]}}}
    session = _FakeSession(payload)
    client = api.SorareClient(session=session, api_key="k")
    client.fetch_recent_sales("declan-john", "limited", season_year=2024)
    sent = session.calls[0]["json"]["variables"]
    assert sent["season"] == 2024  # season-matched comps


def test_fetch_recent_sales_omits_season_when_zero():
    payload = {"data": {"tokens": {"tokenPrices": []}}}
    session = _FakeSession(payload)
    client = api.SorareClient(session=session, api_key="k")
    client.fetch_recent_sales("declan-john", "limited", season_year=0)
    sent = session.calls[0]["json"]["variables"]
    assert "season" not in sent


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


def test_card_from_json_uses_offer_wei_not_floor_when_eur_null():
    # Regression: most live listings are priced in ETH, so the offer's
    # `eurCents` is null but `wei` is populated. The tool must price from the
    # REAL offer (wei -> EUR), NOT fall through to priceRange.min (a historical
    # floor that isn't the current asking price). Priced-from-floor cards were
    # phantom listings — cheap numbers nobody was actually offering.
    node = {
        "rarityTyped": "limited",
        "seasonYear": 2024,
        "priceRange": {"min": str(int(1e15)), "max": str(int(2e16))},  # floor 0.001 ETH = €1.50
        "liveSingleSaleOffer": {
            "receiverSide": {"amounts": {"eurCents": None, "wei": str(int(5e15))}}  # 0.005 ETH = €7.50
        },
        "anyPlayer": SAMPLE_PLAYER,
    }
    c = api.card_from_json(node, eur_per_eth=1500.0)
    # Must be the real offer price (€7.50), not the €1.50 floor.
    assert abs(c.price_eur - 7.50) < 1e-6


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


def _market_payload_with_seller(nickname, slug, end_date, card=SAMPLE_CARD):
    return {"data": {"tokens": {"liveSingleSaleOffers": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [{
            "endDate": end_date,
            "sender": {"nickname": nickname, "slug": slug},
            "receiverSide": {"amounts": {"eurCents": 4250, "usdCents": None,
                                         "gbpCents": None, "wei": None}},
            "senderSide": {"anyCards": [card]},
        }],
    }}}}


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


class _PagingSession:
    """Fake session that returns a sequence of payloads, one per call."""
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(json)
        payload = self.payloads[min(len(self.calls) - 1, len(self.payloads) - 1)]
        return _FakeResponse(payload)


def _offer_page(card, has_next, cursor):
    return {"data": {"tokens": {"liveSingleSaleOffers": {
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "nodes": [{"receiverSide": {"amounts": {"eurCents": 4250}},
                   "senderSide": {"anyCards": [card]}}],
    }}}}


def test_fetch_market_cards_paginates_until_no_next_page():
    page1_card = {**SAMPLE_CARD, "slug": "card-page-1"}
    page2_card = {**SAMPLE_CARD, "slug": "card-page-2"}
    session = _PagingSession([
        _offer_page(page1_card, has_next=True, cursor="CURSOR1"),
        _offer_page(page2_card, has_next=False, cursor=None),
    ])
    client = api.SorareClient(session=session, api_key="k")
    cards = client.fetch_market_cards("limited", max_pages=6)
    slugs = {c.slug for c in cards}
    assert slugs == {"card-page-1", "card-page-2"}
    # stopped after 2 calls because page 2 had hasNextPage=False
    assert len(session.calls) == 2
    # second call passed the cursor from page 1
    assert session.calls[1]["variables"]["after"] == "CURSOR1"


def test_fetch_market_cards_respects_max_pages():
    card = {**SAMPLE_CARD, "slug": "endless"}
    # Always says there's a next page; max_pages must cap the loop.
    session = _PagingSession([_offer_page(card, has_next=True, cursor="C")])
    client = api.SorareClient(session=session, api_key="k")
    client.fetch_market_cards("limited", max_pages=3)
    assert len(session.calls) == 3


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


class _RoutingSession:
    """Fake session that returns different payloads per query keyword."""
    def __init__(self, routes, default):
        self.routes = routes  # list of (keyword, payload)
        self.default = default
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(json)
        q = (json or {}).get("query", "")
        for keyword, payload in self.routes:
            if keyword in q:
                return _FakeResponse(payload)
        return _FakeResponse(self.default)


def test_fetch_recent_sales_returns_oldest_first_eur():
    payload = {"data": {"tokens": {"tokenPrices": [
        {"date": "2026-07-02", "amounts": {"eurCents": 300}},  # newest
        {"date": "2026-07-01", "amounts": {"eurCents": 100}},  # oldest
    ]}}}
    client = api.SorareClient(session=_FakeSession(payload), api_key="k")
    sales = client.fetch_recent_sales("declan-john", "limited")
    assert sales == [1.0, 3.0]  # reversed to oldest-first, in EUR


def test_fetch_my_cards_enriches_with_recent_sales():
    # First query (MyCards) returns one owned card; RecentSales returns comps.
    my_cards = {"data": {"user": {"cards": {"nodes": [SAMPLE_CARD]}}}}
    sales = {"data": {"tokens": {"tokenPrices": [
        {"date": "2026-07-02", "amounts": {"eurCents": 5000}},
        {"date": "2026-07-01", "amounts": {"eurCents": 3000}},
    ]}}}
    session = _RoutingSession(
        routes=[("RecentSales", sales), ("MyCards", my_cards)],
        default={"data": {}},
    )
    client = api.SorareClient(session=session, api_key="k", username="me")
    cards = client.fetch_my_cards()
    assert len(cards) == 1
    # real recent sales replaced the floor self-reference:
    assert cards[0].recent_sale_prices_eur == [30.0, 50.0]


def test_fetch_my_cards_reads_by_username():
    payload = {"data": {"user": {"cards": {"nodes": [SAMPLE_CARD]}}}}
    session = _FakeSession(payload)
    client = api.SorareClient(session=session, api_key="k", username="nickmolyvia")
    cards = client.fetch_my_cards()
    assert len(cards) == 1
    assert cards[0].player.display_name == "Kylian Mbappe"
    # the username is sent as the slug variable
    assert session.calls[0]["json"]["variables"]["slug"] == "nickmolyvia"


def test_fetch_my_cards_without_username_raises():
    client = api.SorareClient(session=_FakeSession({"data": {}}), api_key="k")
    with pytest.raises(RuntimeError) as exc:
        client.fetch_my_cards()
    assert "username" in str(exc.value).lower()


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


def _mkcard(slug, price, scarcity="limited", season=2024):
    from src.models import Appearance, Player
    p = Player(slug, slug.title(), "FC", [Appearance(50, 90, True)])
    return Card(slug + "-c", p, scarcity, price, [], season)


def test_enrich_market_with_sales_floors_and_caches(monkeypatch):
    client = api.SorareClient(session=None, api_key="k", username="u")
    calls = []

    def fake_recent(slug, scarcity, season_year=0):
        calls.append((slug, scarcity, season_year))
        return [10.0, 11.0, 12.0, 13.0, 14.0]

    monkeypatch.setattr(client, "fetch_recent_sales", fake_recent)

    below = _mkcard("cheap", 2.0)     # under €3.50 floor -> not enriched, no call
    above1 = _mkcard("star", 8.0)     # enriched
    above2 = _mkcard("star", 9.0)     # same key -> served from cache, no 2nd call
    client.enrich_market_with_sales([below, above1, above2])

    assert below.recent_sale_prices_eur == []          # untouched
    assert above1.recent_sale_prices_eur == [10.0, 11.0, 12.0, 13.0, 14.0]
    assert above2.recent_sale_prices_eur == [10.0, 11.0, 12.0, 13.0, 14.0]
    # only one fetch for the shared (slug, scarcity, season) key
    assert calls == [("star", "limited", 2024)]


def test_market_card_captures_seller_and_end_date():
    payload = _market_payload_with_seller(
        "satonio", "satonio", "2026-07-03T09:11:19Z")
    client = api.SorareClient(session=_FakeSession(payload), api_key="k")
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].seller_nickname == "satonio"
    assert cards[0].offer_end_date == "2026-07-03T09:11:19Z"


def test_market_skips_own_listings_case_insensitive():
    payload = _market_payload_with_seller("Me", "MyName", "2026-07-03T09:11:19Z")
    # username differs only by case -> the offer is the user's own -> skipped
    client = api.SorareClient(session=_FakeSession(payload), api_key="k",
                              username="myname")
    cards = client.fetch_market_cards("limited")
    assert cards == []


def test_market_keeps_other_sellers():
    payload = _market_payload_with_seller("other", "otherguy",
                                          "2026-07-03T09:11:19Z")
    client = api.SorareClient(session=_FakeSession(payload), api_key="k",
                              username="myname")
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].seller_nickname == "other"
