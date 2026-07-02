# tests/test_fair_value.py
from src.models import Appearance, Fixture, Player
from src import fair_value


def _player(appearances, fixtures=None):
    return Player("p", "P", "Club", appearances, fixtures or [])


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


def test_fixture_multiplier_no_fixtures_is_one():
    assert fair_value.fixture_multiplier(_player([])) == 1.0


def test_fixture_multiplier_easy_boosts():
    p = _player([], [Fixture("x", 0.0), Fixture("y", 0.0)])  # mean diff 0.0
    assert fair_value.fixture_multiplier(p) == 1.1  # 1 + 0.2*(0.5-0.0)=1.1


def test_fixture_multiplier_hard_reduces():
    p = _player([], [Fixture("x", 1.0)])  # mean diff 1.0
    assert fair_value.fixture_multiplier(p) == 0.9  # 1 + 0.2*(0.5-1.0)=0.9


def test_projected_points_combines_all():
    p = _player(
        [Appearance(80, 90, True), Appearance(80, 90, True)],  # form 80, reliability 1.0
        [Fixture("x", 0.5)],  # multiplier 1.0
    )
    assert fair_value.projected_points(p) == 80.0


def test_projected_points_penalizes_unreliable_starter():
    p = _player(
        [Appearance(80, 90, True), Appearance(80, 20, False)],  # form 80, reliability 0.5
        [Fixture("x", 0.5)],  # multiplier 1.0
    )
    assert fair_value.projected_points(p) == 40.0
