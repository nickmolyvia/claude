# src/api.py
import json
import os
from src.models import Appearance, Fixture, Player, Card

SORARE_GRAPHQL_URL = "https://api.sorare.com/federation/graphql"


def load_credentials(path: str = "credentials.json") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Copy credentials.example.json to "
            f"credentials.json and fill in your Sorare login."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def player_from_json(node: dict) -> Player:
    club = ""
    active_club = node.get("activeClub") or {}
    club = active_club.get("name", "")
    appearances = [
        Appearance(
            so5_score=float(a.get("score", 0.0)),
            minutes_played=int(a.get("minutesPlayed", 0)),
            started=bool(a.get("started", False)),
        )
        for a in node.get("recentAppearances", [])
    ]
    fixtures = [
        Fixture(
            opponent=f.get("opponentName", ""),
            difficulty=float(f.get("difficulty", 0.5)),
        )
        for f in node.get("upcomingFixtures", [])
    ]
    return Player(
        slug=node.get("slug", ""),
        display_name=node.get("displayName", ""),
        club=club,
        recent_appearances=appearances,
        upcoming_fixtures=fixtures,
    )


def card_from_json(node: dict) -> Card:
    return Card(
        slug=node.get("slug", ""),
        player=player_from_json(node.get("player", {})),
        scarcity=node.get("rarity", ""),
        price_eur=float(node.get("priceEur", 0.0)),
        recent_sale_prices_eur=[float(x) for x in node.get("recentSalesEur", [])],
    )


class SorareClient:
    def __init__(self, session=None):
        self.session = session
        self.authenticated = False

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
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        payload = resp.json()
        if payload.get("errors"):
            messages = "; ".join(e.get("message", "?") for e in payload["errors"])
            raise RuntimeError(f"GraphQL error: {messages}")
        return payload.get("data", {})

    def fetch_market_cards(self, scarcity: str) -> list:
        query = """
        query MarketCards($rarity: String!) {
          cards(rarity: $rarity) {
            nodes { slug rarity priceEur recentSalesEur
              player { slug displayName activeClub { name }
                recentAppearances { score minutesPlayed started }
                upcomingFixtures { opponentName difficulty } } }
          }
        }
        """
        data = self._post(query, {"rarity": scarcity})
        nodes = (data.get("cards") or {}).get("nodes", [])
        return [card_from_json(n) for n in nodes]

    def fetch_my_cards(self) -> list:
        query = """
        query MyCards {
          currentUser {
            cards {
              nodes { slug rarity priceEur recentSalesEur
                player { slug displayName activeClub { name }
                  recentAppearances { score minutesPlayed started }
                  upcomingFixtures { opponentName difficulty } } }
            }
          }
        }
        """
        data = self._post(query, {})
        nodes = ((data.get("currentUser") or {}).get("cards") or {}).get("nodes", [])
        return [card_from_json(n) for n in nodes]
