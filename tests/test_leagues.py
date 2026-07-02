# tests/test_leagues.py
from src import leagues


def test_top5_membership():
    assert leagues.in_tier("laliga-es", "top5")
    assert leagues.in_tier("ligue-1-fr", "top5")
    assert not leagues.in_tier("eredivisie", "top5")
    assert not leagues.in_tier("mlspa", "top5")


def test_top7_adds_dutch_and_portuguese():
    assert leagues.in_tier("eredivisie", "top7")
    assert leagues.in_tier("primeira-liga-pt", "top7")
    assert not leagues.in_tier("mlspa", "top7")


def test_top10_adds_turkish_mls_belgian():
    assert leagues.in_tier("spor-toto-super-lig", "top10")
    assert leagues.in_tier("mlspa", "top10")
    assert leagues.in_tier("jupiler-pro-league", "top10")
    assert not leagues.in_tier("liga-mx", "top10")


def test_all_tier_passes_everything():
    assert leagues.in_tier("liga-mx", "all")
    assert leagues.in_tier("some-obscure-league", "all")
    assert leagues.in_tier("", "all")


def test_unknown_tier_does_not_restrict():
    # Defensive: an unrecognized tier name should not silently drop everything.
    assert leagues.in_tier("laliga-es", "nonsense")
