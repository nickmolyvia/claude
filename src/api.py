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


# Fallback ETH->EUR rate used only if the live rate can't be fetched. Prices
# on Sorare are quoted in wei (1 ETH = 1e18 wei); priceRange values are wei
# strings with no fiat conversion in the schema, so we convert ourselves.
FALLBACK_EUR_PER_ETH = 1440.0
WEI_PER_ETH = 1e18


def eur_from_wei(wei, eur_per_eth: float) -> float:
    """Convert a wei amount (int or string) to EUR at the given rate."""
    if wei in (None, "", 0, "0"):
        return 0.0
    try:
        eth = int(wei) / WEI_PER_ETH
    except (ValueError, TypeError):
        return 0.0
    return eth * eur_per_eth


def fetch_eur_per_eth(session=None) -> float:
    """Live ETH->EUR rate from a free public API, or the fallback on failure.

    Kept deliberately simple and defensive: any network/parse problem falls
    back to FALLBACK_EUR_PER_ETH so the tool never crashes over the rate.
    """
    try:
        import requests as _requests
        getter = session.get if session is not None else _requests.get
        resp = getter(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=ethereum&vs_currencies=eur",
            timeout=15,
        )
        rate = float(resp.json()["ethereum"]["eur"])
        return rate if rate > 0 else FALLBACK_EUR_PER_ETH
    except Exception:
        return FALLBACK_EUR_PER_ETH


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
    # Sorare's `so5Scores(last: N)` returns NEWEST-first (confirmed live via
    # game dates). The fair-value engine and sell.outlook_trend expect
    # OLDEST-first, so reverse here — otherwise "weakening" / "strengthening"
    # would be inverted.
    appearances = [
        appearance_from_so5(s) for s in reversed(node.get("so5Scores") or [])
    ]
    # Upcoming fixtures with a numeric difficulty are not exposed in a simple
    # form by the public schema, so this stays empty; fixture_multiplier()
    # then returns 1.0 and projections rest on form x minutes-reliability.
    fixtures: list[Fixture] = []
    league = (active_club.get("domesticLeague") or {}).get("slug", "")
    return Player(
        slug=node.get("slug", ""),
        display_name=node.get("displayName", ""),
        club=active_club.get("name", ""),
        recent_appearances=appearances,
        upcoming_fixtures=fixtures,
        league_slug=league,
    )


def _offer_price_eur(node: dict) -> float:
    """Price from the card's own live single-sale offer, if listed (EUR)."""
    offer = node.get("liveSingleSaleOffer") or {}
    receiver = offer.get("receiverSide") or {}
    amounts = receiver.get("amounts") or {}
    return eur_from_cents(amounts.get("eurCents"))


def _floor_price_eur(node: dict, eur_per_eth: float) -> float:
    """The card's floor price in EUR.

    Prefers `priceRange.min` (wei; populates even for unlisted/held cards),
    then falls back to `publicMinPrices.eurCents` when present. This is what
    gives owned cards a real value instead of 0.00.
    """
    price_range = node.get("priceRange") or {}
    floor = eur_from_wei(price_range.get("min"), eur_per_eth)
    if floor == 0.0:
        pmp = node.get("publicMinPrices") or {}
        floor = eur_from_cents(pmp.get("eurCents"))
    return floor


def card_from_json(node: dict, eur_per_eth: float = FALLBACK_EUR_PER_ETH) -> Card:
    """Map an anyCard node to a Card.

    `anyPlayer` is the player behind the card; scarcity is `rarityTyped`.
    Price priority: the card's live sale offer (real asking price), else its
    floor price from priceRange/publicMinPrices, else an explicit priceEur
    (used by tests). `recent_sale_prices_eur` is seeded with the floor price
    as the market reference — the public schema does not expose a per-card
    recent-sales list without deeper auth, so price_position() compares the
    asking price against the current market floor, not a trailing average.
    """
    player_node = node.get("anyPlayer") or node.get("player") or {}
    floor = _floor_price_eur(node, eur_per_eth)
    price = _offer_price_eur(node)
    if price == 0.0:
        price = floor
    if price == 0.0 and node.get("priceEur") is not None:
        price = float(node.get("priceEur"))
    market_reference = [floor] if floor > 0 else []
    return Card(
        slug=node.get("slug", ""),
        player=player_from_json(player_node),
        scarcity=node.get("rarityTyped", node.get("rarity", "")),
        price_eur=price,
        recent_sale_prices_eur=market_reference,
        season_year=int(node.get("seasonYear") or 0),
    )


# GraphQL fragment reused by both queries: the player + score data the
# fair-value engine needs.
_PLAYER_FIELDS = """
  slug
  displayName
  activeClub { name domesticLeague { slug } }
  so5Scores(last: %d) {
    score
    playerGameStats { minsPlayed onGameSheet }
  }
""" % RECENT_SCORES

_CARD_FIELDS = """
  slug
  rarityTyped
  seasonYear
  priceRange { min max }
  publicMinPrices { eurCents }
  liveSingleSaleOffer { receiverSide { amounts { eurCents } } }
  anyPlayer { ... on Player { %s } }
""" % _PLAYER_FIELDS


def _enrich_with_fixtures(cards, fixture_client) -> None:
    """Attach a model win probability to each card's player.

    Looks up the club's next-match win probability; leaves it None (neutral
    fixture multiplier) when there's no fixture or no name match.
    """
    for card in cards:
        player = card.player
        if player.win_probability is not None:
            continue
        player.win_probability = fixture_client.win_probability(
            player.club, player.league_slug
        )


class SorareClient:
    def __init__(self, session=None, api_key: str = "", username: str = ""):
        self.session = session
        self.api_key = api_key
        self.username = username
        self.authenticated = False
        self._eur_per_eth = None  # lazily fetched once, then cached

    def eur_per_eth(self) -> float:
        """ETH->EUR rate, fetched once per client and cached."""
        if self._eur_per_eth is None:
            self._eur_per_eth = fetch_eur_per_eth(self.session)
        return self._eur_per_eth

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
        status = getattr(resp, "status_code", 200)
        if status >= 400:
            # Surface HTTP failures (rate limits, 5xx, auth) with a clear
            # message instead of an opaque JSON-decode error on an error page.
            raise RuntimeError(
                f"Sorare API HTTP {status}. If this is a rate limit (429), "
                f"wait and retry; if it persists, check your API key."
            )
        payload = resp.json()
        if payload.get("errors"):
            messages = "; ".join(e.get("message", "?") for e in payload["errors"])
            raise RuntimeError(f"GraphQL error: {messages}")
        return payload.get("data", {})

    def fetch_market_cards(self, scarcity: str, max_pages: int = 6,
                           fixture_client=None) -> list:
        """Cards currently listed for single-sale, filtered by scarcity.

        Sorare caps liveSingleSaleOffers at 50 per request, so to scan more of
        the market this paginates with the pageInfo cursor: up to `max_pages`
        pages (6 * 50 = 300 offers by default). Requires the API key (depth>7).

        If `fixture_client` is given, each card's player is enriched with a
        model win probability (clubelo) for the fixture multiplier.
        """
        query = """
        query MarketCards($after: String) {
          tokens {
            liveSingleSaleOffers(first: 50, after: $after) {
              pageInfo { hasNextPage endCursor }
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
        rate = self.eur_per_eth()
        cards = []
        after = None
        for _ in range(max_pages):
            data = self._post(query, {"after": after})
            conn = ((data.get("tokens") or {}).get("liveSingleSaleOffers") or {})
            offers = conn.get("nodes", [])
            for offer in offers:
                price = eur_from_cents(
                    ((offer.get("receiverSide") or {}).get("amounts") or {}).get("eurCents")
                )
                for card_node in (offer.get("senderSide") or {}).get("anyCards", []):
                    card = card_from_json(card_node, rate)
                    if card.price_eur == 0.0:
                        card.price_eur = price
                    if card.scarcity == scarcity:
                        cards.append(card)
            page_info = conn.get("pageInfo") or {}
            after = page_info.get("endCursor")
            if not page_info.get("hasNextPage") or not after:
                break
        if fixture_client is not None:
            _enrich_with_fixtures(cards, fixture_client)
        return cards

    def fetch_my_cards(self) -> list:
        """The cards on a public Sorare profile, read by username.

        Uses `user(slug:)` rather than `currentUser` — the API key raises the
        data-depth limit but does NOT authenticate as a specific account
        (currentUser returns null). Reading a public profile by username needs
        only the API key. Requires `self.username` to be set.
        """
        if not self.username:
            raise RuntimeError(
                "No Sorare username set. Add \"username\": \"your-sorare-name\" "
                "to credentials.json so the SELL report can read your collection."
            )
        query = """
        query MyCards($slug: String!) {
          user(slug: $slug) {
            cards(first: 200) {
              nodes {
                %s
              }
            }
          }
        }
        """ % _CARD_FIELDS
        data = self._post(query, {"slug": self.username})
        nodes = (((data.get("user") or {})
                  .get("cards") or {}).get("nodes", []))
        rate = self.eur_per_eth()
        cards = [card_from_json(n, rate) for n in nodes]
        # Enrich each card with its player's real recent sales so the SELL
        # report's "vs history" is a true recent-sales comparison, not a
        # floor self-comparison. One extra call per distinct (player, rarity);
        # cached so repeated players in a collection don't re-fetch.
        sales_cache: dict = {}
        for card in cards:
            slug = card.player.slug
            # Match comps to the card's own season-year: a 2024 card is only
            # compared to 2024 sales, otherwise cheaper old-season sales drag
            # the average down and distort "vs Sales".
            key = (slug, card.scarcity, card.season_year)
            if key not in sales_cache:
                sales_cache[key] = self.fetch_recent_sales(
                    slug, card.scarcity, card.season_year
                )
            sales = sales_cache[key]
            if sales:
                card.recent_sale_prices_eur = sales
        return cards

    def fetch_recent_sales(self, player_slug: str, scarcity: str,
                           season_year: int = 0) -> list:
        """Recent primary-market sale prices (EUR) for a player+scarcity.

        Uses tokens.tokenPrices, which returns real completed sales (newest
        first) with an eurCents amount and a date. When season_year is given
        (> 0), comps are restricted to that season so cards are compared
        like-for-like. Returns oldest-first EUR floats so callers can average
        or trend them. Empty list on any issue.
        """
        variables = {"slug": player_slug, "rarity": scarcity}
        if season_year:
            query = """
            query RecentSales($slug: String!, $rarity: Rarity!, $season: Int!) {
              tokens {
                tokenPrices(playerSlug: $slug, rarity: $rarity, season: $season) {
                  date
                  amounts { eurCents }
                }
              }
            }
            """
            variables["season"] = season_year
        else:
            query = """
            query RecentSales($slug: String!, $rarity: Rarity!) {
              tokens {
                tokenPrices(playerSlug: $slug, rarity: $rarity) {
                  date
                  amounts { eurCents }
                }
              }
            }
            """
        try:
            data = self._post(query, variables)
        except RuntimeError:
            return []
        rows = ((data.get("tokens") or {}).get("tokenPrices")) or []
        prices = []
        for row in reversed(rows):  # API is newest-first; return oldest-first
            eur = eur_from_cents(((row.get("amounts") or {}).get("eurCents")))
            if eur > 0:
                prices.append(eur)
        return prices
