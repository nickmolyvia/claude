# tests/test_fair_value.py
from src.models import Appearance, Player
from src import fair_value


def _player(appearances, win_probability=None, league=""):
    return Player("p", "P", "Club", appearances, [],
                  league_slug=league, win_probability=win_probability)


def test_form_score_is_mean():
    p = _player([Appearance(60, 90, True), Appearance(80, 90, True)])
    assert fair_value.form_score(p) == 70.0


def test_form_score_empty_is_zero():
    assert fair_value.form_score(_player([])) == 0.0


def test_minutes_reliability_fraction_of_true_starts():
    p = _player([
        Appearance(50, 90, True),   # counts
        Appearance(50, 30, True),   # too few minutes
        Appearance(50, 90, False),  # not started
        Appearance(50, 75, True),   # counts
    ])
    assert fair_value.minutes_reliability(p) == 0.5


def test_fixture_multiplier_no_probability_is_one():
    assert fair_value.fixture_multiplier(_player([])) == 1.0


def test_fixture_multiplier_even_odds_is_one():
    p = _player([], win_probability=0.5, league="laliga-es")
    assert abs(fair_value.fixture_multiplier(p) - 1.0) < 1e-9


def test_fixture_multiplier_top5_favourite_boosts_30pct():
    # certain win (prob 1.0) in a top-5 league -> +30%
    p = _player([], win_probability=1.0, league="laliga-es")
    assert abs(fair_value.fixture_multiplier(p) - 1.30) < 1e-9


def test_fixture_multiplier_top5_underdog_cuts_30pct():
    p = _player([], win_probability=0.0, league="laliga-es")
    assert abs(fair_value.fixture_multiplier(p) - 0.70) < 1e-9


def test_fixture_multiplier_other_league_swings_20pct():
    p = _player([], win_probability=1.0, league="mlspa")  # not top-5
    assert abs(fair_value.fixture_multiplier(p) - 1.20) < 1e-9


def test_fixture_multiplier_top5_favourite_partial():
    # 75% win prob, top-5: 1 + 0.30*(0.75-0.5)*2 = 1 + 0.30*0.5 = 1.15
    p = _player([], win_probability=0.75, league="serie-a-it")
    assert abs(fair_value.fixture_multiplier(p) - 1.15) < 1e-9


def test_projected_points_combines_all():
    p = _player(
        [Appearance(80, 90, True), Appearance(80, 90, True)],  # form 80, reliability 1.0
        win_probability=0.5, league="laliga-es",  # multiplier 1.0
    )
    assert fair_value.projected_points(p) == 80.0


def test_projected_points_applies_fixture_boost():
    # form 80, reliability 1.0, top-5 favourite (prob 1.0) -> x1.30 = 104
    p = _player(
        [Appearance(80, 90, True), Appearance(80, 90, True)],
        win_probability=1.0, league="laliga-es",
    )
    assert abs(fair_value.projected_points(p) - 104.0) < 1e-9


def test_projected_points_penalizes_unreliable_starter():
    p = _player(
        [Appearance(80, 90, True), Appearance(80, 20, False)],  # form 80, reliability 0.5
        win_probability=0.5, league="laliga-es",  # multiplier 1.0
    )
    assert fair_value.projected_points(p) == 40.0
