# src/fixtures.py
#
# Fixture-strength signal from clubelo.com (free, no key, non-gambling).
#
# clubelo's /Fixtures endpoint returns, per upcoming match, a full
# goal-difference probability distribution from its Elo model — the same Elo
# foundation bookmakers build their prices on. Summing the "home wins by N"
# columns gives a clean home-win probability (and the mirror for the away
# side). No bookmaker margin to remove: a model distribution already sums to 1.
#
# That win probability feeds the fixture multiplier in fair_value.

import csv
import io

from src.odds import team_matches  # reuse the club-name matcher

CLUBELO_FIXTURES_URL = "http://api.clubelo.com/Fixtures"

# clubelo goal-difference columns that mean "home team wins" / "away wins".
_HOME_WIN_COLS = ["GD=1", "GD=2", "GD=3", "GD=4", "GD=5", "GD>5"]
_AWAY_WIN_COLS = ["GD<-5", "GD=-5", "GD=-4", "GD=-3", "GD=-2", "GD=-1"]


def _sum_cols(row: dict, cols) -> float:
    total = 0.0
    for c in cols:
        try:
            total += float(row.get(c, 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def parse_fixtures(csv_text: str) -> list:
    """Parse clubelo /Fixtures CSV into game dicts with win probabilities.

    Returns [{home, away, home_win, away_win}, ...] where home_win/away_win are
    model probabilities (0..1). Rows without usable numbers are skipped.
    """
    games = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        home = (row.get("Home") or "").strip()
        away = (row.get("Away") or "").strip()
        if not home or not away:
            continue
        home_win = _sum_cols(row, _HOME_WIN_COLS)
        away_win = _sum_cols(row, _AWAY_WIN_COLS)
        if home_win <= 0 and away_win <= 0:
            continue
        games.append({"home": home, "away": away,
                      "home_win": home_win, "away_win": away_win})
    return games


def win_probability_for(team_name: str, game: dict):
    """This club's model win probability in one fixture, or None if not in it."""
    if team_matches(team_name, game.get("home", "")):
        return game.get("home_win")
    if team_matches(team_name, game.get("away", "")):
        return game.get("away_win")
    return None


class FixtureClient:
    """Fetches clubelo upcoming fixtures once and answers win-probability lookups.

    No API key needed. On any network/parse error it holds an empty fixture
    list, so the fixture multiplier degrades to neutral rather than crashing.
    """

    def __init__(self, session=None):
        self.session = session
        self._games = None  # lazily fetched list of game dicts

    def _fetch(self) -> list:
        try:
            import requests as _requests
            getter = self.session.get if self.session is not None else _requests.get
            resp = getter(CLUBELO_FIXTURES_URL,
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            return parse_fixtures(resp.text)
        except Exception:
            return []

    def games(self) -> list:
        if self._games is None:
            self._games = self._fetch()
        return self._games

    def win_probability(self, team_name: str, league_slug: str = ""):
        """Model win probability for a club's next fixture, or None.

        `league_slug` is accepted for interface parity with the old odds client
        but isn't needed — clubelo's feed spans all leagues at once.
        """
        for game in self.games():
            prob = win_probability_for(team_name, game)
            if prob is not None:
                return prob
        return None
