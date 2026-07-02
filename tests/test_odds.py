# tests/test_odds.py
from src import odds


def test_team_matches_exact_and_filler():
    assert odds.team_matches("FC Bayern München", "Bayern Munich")
    assert odds.team_matches("Real Madrid CF", "Real Madrid")
    assert odds.team_matches("Paris Saint-Germain FC", "Paris Saint Germain")


def test_team_matches_rejects_different_clubs():
    assert not odds.team_matches("Real Madrid", "Real Sociedad")
    assert not odds.team_matches("Manchester United", "Manchester City")


def test_team_matches_empty_is_false():
    assert not odds.team_matches("", "Bayern")
    assert not odds.team_matches("Bayern", "")


def test_normalize_strips_accents_and_fillers():
    assert odds._normalize_team("FC Bayern München") == "bayern munich"
    assert odds._normalize_team("Real Madrid CF") == "real madrid"
