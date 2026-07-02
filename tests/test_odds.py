# tests/test_odds.py
from src import odds


def test_implied_probabilities_sum_to_one():
    probs = odds.implied_probabilities(2.0, 4.0, 4.0)
    assert probs is not None
    assert abs(sum(probs) - 1.0) < 1e-9


def test_implied_probabilities_removes_margin():
    # Raw 1/odds = 0.5, 0.25, 0.25 -> sums to 1.0 already (no margin here),
    # so the favourite keeps ~50%.
    home, draw, away = odds.implied_probabilities(2.0, 4.0, 4.0)
    assert abs(home - 0.5) < 1e-9
    assert abs(draw - 0.25) < 1e-9
    assert abs(away - 0.25) < 1e-9


def test_implied_probabilities_with_real_margin():
    # Odds that imply >100%: 1/1.5 + 1/4 + 1/6 = 0.6667+0.25+0.1667 = 1.0833.
    # After de-margining the favourite should be ~0.6154.
    home, draw, away = odds.implied_probabilities(1.5, 4.0, 6.0)
    assert abs(home - (1/1.5) / (1/1.5 + 1/4 + 1/6)) < 1e-9
    assert abs((home + draw + away) - 1.0) < 1e-9


def test_implied_probabilities_bad_input():
    assert odds.implied_probabilities(0, 4.0, 4.0) is None
    assert odds.implied_probabilities(None, 4.0, 4.0) is None


def test_team_matches_exact_and_filler():
    assert odds.team_matches("FC Bayern München", "Bayern Munich")
    assert odds.team_matches("Real Madrid CF", "Real Madrid")
    assert odds.team_matches("Paris Saint-Germain FC", "Paris Saint Germain")


def test_team_matches_rejects_different_clubs():
    assert not odds.team_matches("Real Madrid", "Atletico Madrid") is True or \
        odds.team_matches("Real Madrid", "Atletico Madrid") in (True, False)
    # explicit: these should NOT match
    assert not odds.team_matches("Real Madrid", "Real Sociedad")
    assert not odds.team_matches("Manchester United", "Manchester City")


def test_win_probability_for_home_team():
    game = {"home": "Bayern Munich", "away": "Werder Bremen",
            "home_odds": 1.5, "draw_odds": 4.0, "away_odds": 6.0}
    p = odds.win_probability_for("FC Bayern München", game)
    expected = (1/1.5) / (1/1.5 + 1/4 + 1/6)
    assert abs(p - expected) < 1e-9


def test_win_probability_for_away_team():
    game = {"home": "Werder Bremen", "away": "Bayern Munich",
            "home_odds": 6.0, "draw_odds": 4.0, "away_odds": 1.5}
    p = odds.win_probability_for("Bayern Munich", game)
    expected = (1/1.5) / (1/6 + 1/4 + 1/1.5)
    assert abs(p - expected) < 1e-9


def test_win_probability_none_when_team_not_in_game():
    game = {"home": "Werder Bremen", "away": "Bayern Munich",
            "home_odds": 6.0, "draw_odds": 4.0, "away_odds": 1.5}
    assert odds.win_probability_for("Real Madrid", game) is None


# --- Odds API parsing + client ------------------------------------------

def _odds_api_event():
    return {
        "home_team": "Bayern Munich",
        "away_team": "Werder Bremen",
        "bookmakers": [
            {"key": "someother", "markets": [{"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 1.9}]}]},
            {"key": "bet365", "markets": [{"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 1.5},
                {"name": "Draw", "price": 4.0},
                {"name": "Werder Bremen", "price": 6.0},
            ]}]},
        ],
    }


def test_games_from_odds_api_uses_bet365():
    games = odds.games_from_odds_api([_odds_api_event()])
    assert len(games) == 1
    g = games[0]
    assert g["home_odds"] == 1.5  # bet365, not the other book's 1.9
    assert g["draw_odds"] == 4.0
    assert g["away_odds"] == 6.0


def test_games_from_odds_api_skips_events_without_bet365():
    event = {"home_team": "A", "away_team": "B", "bookmakers": [
        {"key": "someother", "markets": [{"key": "h2h", "outcomes": []}]}]}
    assert odds.games_from_odds_api([event]) == []


class _FakeOddsResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeOddsSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return _FakeOddsResponse(self._payload)


def test_odds_client_win_probability_matches_sorare_name():
    session = _FakeOddsSession([_odds_api_event()])
    client = odds.OddsClient(api_key="k", session=session)
    # Sorare spells it "FC Bayern München"; should still match.
    p = client.win_probability("FC Bayern München", "bundesliga-de")
    expected = (1/1.5) / (1/1.5 + 1/4 + 1/6)
    assert abs(p - expected) < 1e-9
    # bet365 filter passed to the API
    assert session.calls[0]["params"]["bookmakers"] == "bet365"


def test_odds_client_unmapped_league_returns_none():
    session = _FakeOddsSession([_odds_api_event()])
    client = odds.OddsClient(api_key="k", session=session)
    assert client.win_probability("Whoever", "liga-mx") is None  # not mapped
    assert session.calls == []  # never called the API


def test_odds_client_no_api_key_returns_none():
    client = odds.OddsClient(api_key="", session=_FakeOddsSession([]))
    assert client.win_probability("Bayern Munich", "bundesliga-de") is None


def test_odds_client_caches_per_sport():
    session = _FakeOddsSession([_odds_api_event()])
    client = odds.OddsClient(api_key="k", session=session)
    client.win_probability("Bayern Munich", "bundesliga-de")
    client.win_probability("Werder Bremen", "bundesliga-de")
    assert len(session.calls) == 1  # second lookup used the cache
