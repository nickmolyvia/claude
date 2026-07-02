# src/leagues.py
#
# League tiers for the BUY filter. Slugs confirmed against the live Sorare
# schema (Club.domesticLeague.slug). Cards from stronger leagues trade richer,
# so the tiers let the user narrow the buy list to a comparable band.

TOP_5 = [
    "premier-league-gb-eng",
    "laliga-es",
    "serie-a-it",
    "bundesliga-de",
    "ligue-1-fr",
]

# Top 7 = top 5 plus the Dutch and Portuguese top flights.
TOP_7 = TOP_5 + [
    "eredivisie",
    "primeira-liga-pt",
]

# Top 10 = top 7 plus the Turkish, US, and Belgian top flights.
TOP_10 = TOP_7 + [
    "spor-toto-super-lig",
    "mlspa",
    "jupiler-pro-league",
]

# Tier name -> allowed league slugs. "all" means no league restriction.
TIERS = {
    "top5": TOP_5,
    "top7": TOP_7,
    "top10": TOP_10,
    "all": None,  # None == every league allowed
}


def in_tier(league_slug: str, tier: str) -> bool:
    """True if a league belongs to the given tier. 'all' always passes."""
    allowed = TIERS.get(tier, None)
    if allowed is None:  # "all" or unknown tier -> no restriction
        return True
    return league_slug in allowed
