# src/fair_value.py
from statistics import mean
from src.models import Player
from src import leagues

RELIABILITY_MIN_MINUTES = 60

# How far the fixture multiplier can swing based on de-margined win
# probability. Top-5 leagues swing wider (their odds are sharper / more
# meaningful); everyone else swings less.
FIXTURE_SWING_TOP5 = 0.30
FIXTURE_SWING_OTHER = 0.20


def form_score(player: Player) -> float:
    apps = player.recent_appearances
    if not apps:
        return 0.0
    return mean(a.so5_score for a in apps)


def minutes_reliability(player: Player) -> float:
    apps = player.recent_appearances
    if not apps:
        return 0.0
    reliable = sum(
        1 for a in apps if a.started and a.minutes_played >= RELIABILITY_MIN_MINUTES
    )
    return reliable / len(apps)


def fixture_multiplier(player: Player) -> float:
    """Boost/cut based on the club's de-margined win probability next match.

    A 50% win probability is neutral (1.0). Above 50% (favourite) boosts up to
    +swing; below 50% (underdog) cuts down to -swing. The swing is 30% for
    top-5-league clubs and 20% for everyone else. When no win probability is
    available (off-season, unmatched team) the multiplier stays neutral.
    """
    prob = player.win_probability
    if prob is None:
        return 1.0
    swing = (FIXTURE_SWING_TOP5
             if leagues.in_tier(player.league_slug, "top5")
             else FIXTURE_SWING_OTHER)
    # prob 0.5 -> 1.0; prob 1.0 -> 1+swing; prob 0.0 -> 1-swing.
    return 1.0 + swing * (prob - 0.5) * 2.0


def projected_points(player: Player) -> float:
    return form_score(player) * minutes_reliability(player) * fixture_multiplier(player)
