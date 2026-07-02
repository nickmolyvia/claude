# src/odds.py
#
# Turn bookmaker (bet365) match odds into a de-margined win probability for a
# team's next fixture. That probability feeds the fixture multiplier: a heavy
# favourite gets a projection boost, a heavy underdog a cut.
#
# Odds are fetched via The Odds API (the-odds-api.com), which lists bet365 as
# one of its bookmakers. We filter to bet365 specifically, then remove the
# bookmaker margin ("vig") so the three outcome probabilities sum to 1.

import re

BET365_KEY = "bet365"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Sorare league slug -> The Odds API sport key. Only mapped leagues get odds;
# others fall back to a neutral fixture multiplier.
LEAGUE_TO_SPORT = {
    "premier-league-gb-eng": "soccer_epl",
    "laliga-es": "soccer_spain_la_liga",
    "serie-a-it": "soccer_italy_serie_a",
    "bundesliga-de": "soccer_germany_bundesliga",
    "ligue-1-fr": "soccer_france_ligue_one",
    "eredivisie": "soccer_netherlands_eredivisie",
    "primeira-liga-pt": "soccer_portugal_primeira_liga",
    "spor-toto-super-lig": "soccer_turkey_super_league",
    "mlspa": "soccer_usa_mls",
    "jupiler-pro-league": "soccer_belgium_first_div",
}


def implied_probabilities(home_odds: float, draw_odds: float, away_odds: float):
    """De-margined (home, draw, away) probabilities from decimal odds.

    Raw implied prob for an outcome is 1/odds; those sum to >1 because of the
    bookmaker margin, so we normalise them back to sum to 1.0. Returns a tuple
    of three floats, or None if any odd is missing/invalid.
    """
    try:
        raw = [1.0 / float(home_odds), 1.0 / float(draw_odds), 1.0 / float(away_odds)]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    total = sum(raw)
    if total <= 0:
        return None
    return tuple(r / total for r in raw)


# Token-level aliases for the same club spelled differently across languages
# (Sorare tends to use local names, the odds feed English ones). Applied after
# accent-stripping. Covers the well-known top-league cases; unmatched teams
# fall back to a neutral fixture multiplier upstream.
_TOKEN_ALIASES = {
    "munchen": "munich",
    "munchengladbach": "monchengladbach",
    "koln": "cologne",
    "wolverhampton": "wolves",
    "internazionale": "inter",
    "atletico": "atletico",
    "athletic": "athletic",
    "sporting": "sporting",
}


def _normalize_team(name: str) -> str:
    """Loosely normalise a club name for matching across data sources.

    Sorare and the odds feed spell clubs differently ("FC Bayern München" vs
    "Bayern Munich"). Lowercase, strip accents/punctuation, drop filler words
    (fc, cf, sc...), and apply language aliases (münchen->munich) so the cores
    line up. Best-effort: teams that still don't match fall back to a neutral
    fixture multiplier upstream.
    """
    if not name:
        return ""
    s = name.lower()
    # strip accents crudely via a translation of common cases
    accents = str.maketrans("áàâäãéèêëíìîïóòôöõúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")
    s = s.translate(accents)
    s = re.sub(r"[^a-z0-9 ]", " ", s)  # drop punctuation
    fillers = {"fc", "cf", "sc", "afc", "ac", "as", "ss", "club", "de",
               "futbol", "football", "calcio", "spor", "kulubu", "cp", "cd"}
    tokens = [_TOKEN_ALIASES.get(t, t) for t in s.split()
              if t and t not in fillers]
    return " ".join(tokens)


def team_matches(name_a: str, name_b: str) -> bool:
    """True if two club names refer to the same team, after normalisation.

    Matches when the normalised cores are equal, or one is a subset of the
    other's tokens (handles "bayern" vs "bayern munich").
    """
    a = _normalize_team(name_a)
    b = _normalize_team(name_b)
    if not a or not b:
        return False
    if a == b:
        return True
    at, bt = set(a.split()), set(b.split())
    # subset match: every token of the shorter name appears in the longer one
    shorter, longer = (at, bt) if len(at) <= len(bt) else (bt, at)
    return shorter.issubset(longer)


def win_probability_for(team_name: str, game: dict):
    """De-margined win probability for `team_name` in one odds-API game dict.

    `game` is a normalised fixture: {home, away, home_odds, draw_odds,
    away_odds}. Returns the team's win probability (float 0..1) if it is the
    home or away side and bet365 odds are present, else None.
    """
    probs = implied_probabilities(
        game.get("home_odds"), game.get("draw_odds"), game.get("away_odds")
    )
    if probs is None:
        return None
    home_p, _draw_p, away_p = probs
    if team_matches(team_name, game.get("home", "")):
        return home_p
    if team_matches(team_name, game.get("away", "")):
        return away_p
    return None


def games_from_odds_api(payload: list) -> list:
    """Normalise The Odds API response into simple game dicts using bet365.

    Each event has bookmakers[]; we pick bet365's h2h market and pull the
    home/draw/away decimal odds. Events without bet365 h2h odds are skipped.
    Returns [{home, away, home_odds, draw_odds, away_odds}, ...].
    """
    games = []
    for event in payload or []:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        bet365 = None
        for bk in event.get("bookmakers", []):
            if bk.get("key") == BET365_KEY:
                bet365 = bk
                break
        if not bet365:
            continue
        h2h = None
        for market in bet365.get("markets", []):
            if market.get("key") == "h2h":
                h2h = market
                break
        if not h2h:
            continue
        home_odds = draw_odds = away_odds = None
        for outcome in h2h.get("outcomes", []):
            name = outcome.get("name", "")
            price = outcome.get("price")
            if name == "Draw":
                draw_odds = price
            elif team_matches(name, home):
                home_odds = price
            elif team_matches(name, away):
                away_odds = price
        if home_odds and draw_odds and away_odds:
            games.append({
                "home": home, "away": away,
                "home_odds": home_odds, "draw_odds": draw_odds,
                "away_odds": away_odds,
            })
    return games


class OddsClient:
    """Fetches bet365 match odds from The Odds API and caches per league."""

    def __init__(self, api_key: str = "", session=None):
        self.api_key = api_key
        self.session = session
        self._games_by_sport: dict = {}  # sport_key -> [game dicts]

    def _get(self, url, params):
        import requests as _requests
        getter = self.session.get if self.session is not None else _requests.get
        return getter(url, params=params, timeout=30)

    def games_for_league(self, league_slug: str) -> list:
        """bet365 games for a Sorare league slug; [] if unmapped or on error.

        Cached per sport key so repeated players in the same league don't
        re-hit the API. Any failure returns [] so the tool degrades to neutral
        fixture multipliers rather than crashing.
        """
        sport = LEAGUE_TO_SPORT.get(league_slug)
        if not sport or not self.api_key:
            return []
        if sport in self._games_by_sport:
            return self._games_by_sport[sport]
        try:
            resp = self._get(
                f"{ODDS_API_BASE}/sports/{sport}/odds",
                {"apiKey": self.api_key, "regions": "uk,eu",
                 "markets": "h2h", "oddsFormat": "decimal",
                 "bookmakers": BET365_KEY},
            )
            games = games_from_odds_api(resp.json())
        except Exception:
            games = []
        self._games_by_sport[sport] = games
        return games

    def win_probability(self, team_name: str, league_slug: str):
        """De-margined bet365 win probability for a club's next game, or None."""
        for game in self.games_for_league(league_slug):
            prob = win_probability_for(team_name, game)
            if prob is not None:
                return prob
        return None
