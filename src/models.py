# src/models.py
from dataclasses import dataclass, field


@dataclass
class Appearance:
    so5_score: float
    minutes_played: int
    started: bool


@dataclass
class Fixture:
    opponent: str
    difficulty: float  # 0.0 easiest .. 1.0 hardest


@dataclass
class Player:
    slug: str
    display_name: str
    club: str
    recent_appearances: list[Appearance] = field(default_factory=list)
    upcoming_fixtures: list[Fixture] = field(default_factory=list)
    league_slug: str = ""  # e.g. "laliga-es"; drives the BUY league-tier filter


@dataclass
class Card:
    slug: str
    player: Player
    scarcity: str
    price_eur: float
    recent_sale_prices_eur: list[float] = field(default_factory=list)
    season_year: int = 0  # e.g. 2024; comps are matched to the same season
