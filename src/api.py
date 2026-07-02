# src/api.py
#
# Sorare GraphQL client. Field names here were reconciled against the LIVE
# Sorare schema (Task 10) — introspection is disabled, so they were confirmed
# by probing real queries. Key facts discovered:
#   - Endpoint: https://api.sorare.com/federation/graphql
#   - Anonymous queries are capped at depth 7; an API key raises it to 13.
#     The market scan needs the key, so it is sent as the `APIKEY` header.
#   - Scarcity is `rarityTyped` (e.g. "limited"), not `rarity`.
#   - Prices are EUR cents via MonetaryAmount.eurCents (may be null for
#     crypto-only listings) or wei strings via priceRange{min,max}.
#   - Scores are `so5Scores(last: N) { score playerGameStats { minsPlayed
#     onGameSheet } }`. `onGameSheet` is used as the best available proxy
#     for "started".
import json
import os
from src.models import Appearance, Fixture, Player, Card

SORARE_GRAPHQL_URL = "https://api.sorare.com/federation/graphql"

# How many recent So5 scores to pull per player.
RECENT_SCORES = 5


def load_credentials(path: str = "credentials.json") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Copy credentials.example.json to "
            f"credentials.json and fill in your Sorare login."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def eur_from_cents(eur_cents) -> float:
    """MonetaryAmount.eurCents -> float EUR. None/missing -> 0.0."""
    if eur_cents is None:
        return 0.0
    return float(eur_cents) / 100.0


def appearance_from_so5(node: dict) -> Appearance:
    """Map one So5Score node to an Appearance.

    Real fields: `score`, and nested `playerGameStats { minsPlayed
    onGameSheet }`. onGameSheet is the closest available signal for
    "started"; combined with minsPlayed the fair-value engine still filters
    out low-minute cameos.
    """
    stats = node.get("playerGameStats") or {}
    return Appearance(
        so5_score=float(node.get("score") or 0.0),
        minutes_played=int(stats.get("minsPlayed") or 0),
        started=bool(stats.get("onGameSheet", False)),
    )


def player_from_json(node: dict) -> Player:
    active_club = node.get("activeClub") or {}
    appearances = [
        appearance_from_so5(s) for s in (node.get("so5Scores") or [])
    ]
    # Upcoming fixtures with a numeric difficulty are not exposed in a simple
    # form by the public schema, so this stays empty; fixture_multiplier()
    # then returns 1.0 and projections rest on form x minutes-reliability.
    fixtures: list[Fixture] = []
    return Player(
        slug=node.get("slug", ""),
        display_name=node.get("displayName", ""),
        club=active_club.get("name", ""),
        recent_appearances=appearances,
        upcoming_fixtures=fixtures,
    )


def _price_eur_from_card(node: dict) -> float:
    """Prefer a live single-sale offer's eurCents; fall back to 0.0.

    (priceRange values are wei strings needing an ETH/EUR rate to convert;
    the live offer's eurCents is already fiat, so it is the reliable source.)
    """
    offer = node.get("liveSingleSaleOffer") or {}
    receiver = offer.get("receiverSide") or {}
    amounts = receiver.get("amounts") or {}
    return eur_from_cents(amounts.get("eurCents"))


def card_from_json(node: dict) -> Card:
    """Map an anyCard node to a Card.

    `anyPlayer` is the player behind the card; scarcity is `rarityTyped`.
    """
    player_node = node.get("anyPlayer") or node.get("player") or {}
    price = _price_eur_from_card(node)
    if price == 0.0 and node.get("priceEur") is not None:
        price = float(node.get("priceEur"))
    return Card(
        slug=node.get("slug", ""),
        player=player_from_json(player_node),
        scarcity=node.get("rarityTyped", node.get("rarity", "")),
        price_eur=price,
        recent_sale_prices_eur=[
            eur_from_cents(x) for x in node.get("recentSaleEurCents", [])
        ],
    )


# GraphQL fragment reused by both queries: the player + score data the
# fair-value engine needs.
_PLAYER_FIELDS = """
  slug
  displayName
  activeClub { name }
  so5Scores(last: %d) {
    score
    playerGameStats { minsPlayed onGameSheet }
  }
""" % RECENT_SCORES

_CARD_FIELDS = """
  slug
  rarityTyped
  liveSingleSaleOffer { receiverSide { amounts { eurCents } } }
  anyPlayer { ... on Player { %s } }
""" % _PLAYER_FIELDS


class SorareClient:
    def __init__(self, session=None, api_key: str = ""):
        self.session = session
        self.api_key = api_key
        self.authenticated = False

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["APIKEY"] = self.api_key
        return headers

    def wait_for_authentication(self, prompt_fn=input) -> None:
        print(
            "\nAuthentication required.\n"
            "Complete the Sorare login in your browser / app now.\n"
        )
        prompt_fn("Press Enter once you have authenticated... ")
        self.authenticated = True

    def _post(self, query: str, variables: dict) -> dict:
        resp = self.session.post(
            SORARE_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=self._headers(),
            timeout=30,
        )
        payload = resp.json()
        if payload.get("errors"):
            messages = "; ".join(e.get("message", "?") for e in payload["errors"])
            raise RuntimeError(f"GraphQL error: {messages}")
        return payload.get("data", {})

    def fetch_market_cards(self, scarcity: str, first: int = 50) -> list:
        """Cards currently listed for single-sale, filtered by scarcity.

        Uses tokens.liveSingleSaleOffers; each offer exposes its cards and
        their player. Requires the API key (depth > 7).
        """
        query = """
        query MarketCards($first: Int!) {
          tokens {
            liveSingleSaleOffers(first: $first) {
              nodes {
                receiverSide { amounts { eurCents } }
                senderSide {
                  anyCards {
                    %s
                  }
                }
              }
            }
          }
        }
        """ % _CARD_FIELDS
        data = self._post(query, {"first": first})
        offers = ((data.get("tokens") or {})
                  .get("liveSingleSaleOffers") or {}).get("nodes", [])
        cards = []
        for offer in offers:
            price = eur_from_cents(
                ((offer.get("receiverSide") or {}).get("amounts") or {}).get("eurCents")
            )
            for card_node in (offer.get("senderSide") or {}).get("anyCards", []):
                card = card_from_json(card_node)
                if card.price_eur == 0.0:
                    card.price_eur = price
                if card.scarcity == scarcity:
                    cards.append(card)
        return cards

    def fetch_my_cards(self) -> list:
        """The authenticated user's cards. Requires a real login session."""
        query = """
        query MyCards {
          currentUser {
            anyCards(first: 200) {
              nodes {
                %s
              }
            }
          }
        }
        """ % _CARD_FIELDS
        data = self._post(query, {})
        nodes = (((data.get("currentUser") or {})
                  .get("anyCards") or {}).get("nodes", []))
        return [card_from_json(n) for n in nodes]
