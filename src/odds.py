# src/odds.py
#
# Club-name matching helpers, shared by the fixture-strength layer.
#
# Different data sources spell the same club differently (Sorare uses local
# names like "FC Bayern München"; clubelo uses short English ones like
# "Bayern"). These helpers normalise names so the same club lines up. Any
# club that still doesn't match falls back to a neutral fixture multiplier
# upstream, so mismatches degrade gracefully rather than mislead.

import re

# Token-level aliases for the same club spelled differently across languages.
# Applied after accent-stripping. Covers the well-known top-league cases.
_TOKEN_ALIASES = {
    "munchen": "munich",
    "munchengladbach": "monchengladbach",
    "koln": "cologne",
    "wolverhampton": "wolves",
    "internazionale": "inter",
}


def _normalize_team(name: str) -> str:
    """Loosely normalise a club name for matching across data sources.

    Lowercase, strip accents/punctuation, drop filler words (fc, cf, sc...),
    and apply language aliases (münchen->munich) so the cores line up.
    """
    if not name:
        return ""
    s = name.lower()
    accents = str.maketrans("áàâäãéèêëíìîïóòôöõúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")
    s = s.translate(accents)
    s = re.sub(r"[^a-z0-9 ]", " ", s)  # drop punctuation
    fillers = {"fc", "cf", "sc", "afc", "ac", "as", "ss", "club", "de",
               "futbol", "football", "calcio", "spor", "kulubu", "cp", "cd"}
    tokens = [_TOKEN_ALIASES.get(t, t) for t in s.split()
              if t and t not in fillers]
    return " ".join(tokens)


def team_matches(name_a: str, name_b: str) -> bool:
    """True if two club names refer to the same team, after normalisation.

    Matches when the normalised cores are equal, or the shorter name's tokens
    are a subset of the longer's (handles "bayern" vs "bayern munich").
    """
    a = _normalize_team(name_a)
    b = _normalize_team(name_b)
    if not a or not b:
        return False
    if a == b:
        return True
    at, bt = set(a.split()), set(b.split())
    shorter, longer = (at, bt) if len(at) <= len(bt) else (bt, at)
    return shorter.issubset(longer)
