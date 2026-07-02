# src/fair_value.py
from statistics import mean
from src.models import Player

RELIABILITY_MIN_MINUTES = 60


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
    fixtures = player.upcoming_fixtures
    if not fixtures:
        return 1.0
    mean_difficulty = mean(f.difficulty for f in fixtures)
    raw = 1.0 + 0.2 * (0.5 - mean_difficulty)
    return max(0.9, min(1.1, raw))


def projected_points(player: Player) -> float:
    return form_score(player) * minutes_reliability(player) * fixture_multiplier(player)
