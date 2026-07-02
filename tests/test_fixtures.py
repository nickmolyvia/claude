# tests/test_fixtures.py
from src import fixtures


# A trimmed clubelo /Fixtures CSV: header + two rows. Column order matches the
# real feed's win/draw/lose layout.
_HEADER = ("Date,Country,Home,Away,GD<-5,GD=-5,GD=-4,GD=-3,GD=-2,GD=-1,"
           "GD=0,GD=1,GD=2,GD=3,GD=4,GD=5,GD>5")


def _row(home, away, lose_vals, draw, win_vals):
    # lose_vals: 6 numbers (GD<-5..GD=-1); win_vals: 6 numbers (GD=1..GD>5)
    cells = ["2026-08-15", "ENG", home, away] + \
        [str(x) for x in lose_vals] + [str(draw)] + [str(x) for x in win_vals]
    return ",".join(cells)


def _csv(*rows):
    return "\n".join([_HEADER, *rows])


def test_parse_fixtures_sums_win_columns():
    # Home win cols sum to 0.6, away lose cols sum to 0.1, draw 0.3.
    csv_text = _csv(_row(
        "Bayern", "Freiburg",
        lose_vals=[0.0, 0.0, 0.0, 0.0, 0.02, 0.08],   # away win = 0.10
        draw=0.30,
        win_vals=[0.30, 0.15, 0.10, 0.03, 0.01, 0.01],  # home win = 0.60
    ))
    games = fixtures.parse_fixtures(csv_text)
    assert len(games) == 1
    g = games[0]
    assert abs(g["home_win"] - 0.60) < 1e-9
    assert abs(g["away_win"] - 0.10) < 1e-9
    assert g["home"] == "Bayern"


def test_win_probability_for_matches_home_and_away():
    csv_text = _csv(_row(
        "Bayern", "Freiburg",
        lose_vals=[0, 0, 0, 0, 0.02, 0.08],
        draw=0.30,
        win_vals=[0.30, 0.15, 0.10, 0.03, 0.01, 0.01],
    ))
    game = fixtures.parse_fixtures(csv_text)[0]
    # Sorare name "FC Bayern München" should match clubelo "Bayern"
    assert abs(fixtures.win_probability_for("FC Bayern München", game) - 0.60) < 1e-9
    assert abs(fixtures.win_probability_for("SC Freiburg", game) - 0.10) < 1e-9
    assert fixtures.win_probability_for("Real Madrid", game) is None


class _FakeResp:
    def __init__(self, text):
        self.text = text


class _FakeSession:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        return _FakeResp(self.text)


def test_client_win_probability_and_cache():
    csv_text = _csv(_row(
        "Bayern", "Freiburg",
        lose_vals=[0, 0, 0, 0, 0.02, 0.08],
        draw=0.30,
        win_vals=[0.30, 0.15, 0.10, 0.03, 0.01, 0.01],
    ))
    session = _FakeSession(csv_text)
    client = fixtures.FixtureClient(session=session)
    p1 = client.win_probability("FC Bayern München", "bundesliga-de")
    p2 = client.win_probability("SC Freiburg", "bundesliga-de")
    assert abs(p1 - 0.60) < 1e-9
    assert abs(p2 - 0.10) < 1e-9
    assert len(session.calls) == 1  # fetched once, then cached


def test_client_degrades_to_none_on_error():
    class _BadSession:
        def get(self, *a, **k):
            raise RuntimeError("network blocked")
    client = fixtures.FixtureClient(session=_BadSession())
    assert client.win_probability("Bayern", "bundesliga-de") is None
