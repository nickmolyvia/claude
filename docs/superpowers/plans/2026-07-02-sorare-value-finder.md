# Sorare Value Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that ranks the top 50 value-for-money Sorare signings (filtered by per-run EUR price range and scarcity) and flags when to sell owned cards.

**Architecture:** A single CLI entry point collects filters interactively and runs two reports. All live-API access is isolated behind a thin `api.py` client so the pure logic (fair-value engine, buy ranking, sell signals) is fully unit-tested against mocked data. The fair-value engine is shared by both the BUY and SELL paths so the two directions stay consistent.

**Tech Stack:** Python 3.10+, `requests` (HTTP/GraphQL), `pytest` (tests). Standard library elsewhere (`dataclasses`, `json`, `statistics`).

## Global Constraints

- Python 3.10+ (uses `dataclass`, `list[...]` builtin generics, `X | None` unions).
- Prices are handled and displayed in **EUR** everywhere. Sorare's API returns money amounts in wei (integer, 18 decimals) plus fiat conversions; the `api.py` layer normalizes everything to a float EUR value before it reaches any logic module.
- No secrets in the repo. `credentials.json` and `gh_token.txt` are gitignored; only `credentials.example.json` (placeholder values) is committed.
- All logic modules (`fair_value.py`, `buy.py`, `sell.py`) are **pure**: they take plain Python data (lists of dataclasses/dicts) and return values. They never call the network. Only `api.py` touches the network.
- Live-API field names are NOT assumed correct from memory. `api.py` is the single place they live; its unit tests use mocked JSON. A short "schema verification" task confirms real field names against the live API before wiring the CLI end to end.
- SO5 score: Sorare's Score of Five / player game score. Treated as a float per player-appearance.
- Scarcity tiers (lowercase strings): `limited`, `rare`, `super_rare`, `unique`.

---

### Task 1: Project scaffold, gitignore, credentials template

**Files:**
- Create: `.gitignore`
- Create: `credentials.example.json`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: repo layout; `credentials.example.json` documents the credential fields other tasks read: `{"email": str, "password": str, "api_key": str}` (api_key optional, empty string if unused).

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Secrets — never commit
credentials.json
gh_token.txt
.env

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
*.egg-info/
```

- [ ] **Step 2: Create `credentials.example.json`**

```json
{
  "email": "your-sorare-email@example.com",
  "password": "your-sorare-password",
  "api_key": ""
}
```

- [ ] **Step 3: Create `requirements.txt`**

```text
requests>=2.31,<3
pytest>=8,<9
```

- [ ] **Step 4: Create `src/__init__.py` and `tests/__init__.py`**

Both files are empty. They make `src` and `tests` importable packages.

- [ ] **Step 5: Create `README.md`**

```markdown
# Sorare Value Finder

CLI tool that ranks the top 50 value-for-money Sorare signings (filtered by
EUR price range and scarcity) and flags when to sell cards you already own.

## Setup

1. `pip install -r requirements.txt`
2. Copy `credentials.example.json` to `credentials.json` and fill in your
   Sorare login. `credentials.json` is gitignored — it never leaves your machine.

## Run

```bash
python sorare_value.py
```

The script prompts for min price, max price (EUR), and scarcity, then pauses
for you to complete authentication before producing the BUY and SELL reports.

## Design & plan

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
```

- [ ] **Step 6: Verify layout**

Run: `ls src tests credentials.example.json .gitignore requirements.txt README.md`
Expected: all listed without error.

- [ ] **Step 7: Commit**

```bash
git add .gitignore credentials.example.json requirements.txt README.md src/__init__.py tests/__init__.py
git commit -m "chore: scaffold project, gitignore, credentials template"
```

---

### Task 2: Domain models

**Files:**
- Create: `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass Appearance(so5_score: float, minutes_played: int, started: bool)`
  - `@dataclass Fixture(opponent: str, difficulty: float)` — difficulty in 0.0 (easiest) to 1.0 (hardest).
  - `@dataclass Player(slug: str, display_name: str, club: str, recent_appearances: list[Appearance], upcoming_fixtures: list[Fixture])`
  - `@dataclass Card(slug: str, player: Player, scarcity: str, price_eur: float, recent_sale_prices_eur: list[float])` — `price_eur` is the current asking/floor price; `recent_sale_prices_eur` are recent comparable sales (oldest→newest).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from src.models import Appearance, Fixture, Player, Card


def _player():
    return Player(
        slug="lionel-messi",
        display_name="Lionel Messi",
        club="Inter Miami",
        recent_appearances=[Appearance(so5_score=72.0, minutes_played=90, started=True)],
        upcoming_fixtures=[Fixture(opponent="Orlando", difficulty=0.4)],
    )


def test_card_holds_player_and_price():
    card = Card(
        slug="card-123",
        player=_player(),
        scarcity="limited",
        price_eur=25.0,
        recent_sale_prices_eur=[24.0, 26.0, 25.5],
    )
    assert card.player.display_name == "Lionel Messi"
    assert card.scarcity == "limited"
    assert card.price_eur == 25.0
    assert card.recent_sale_prices_eur[-1] == 25.5
    assert card.player.recent_appearances[0].so5_score == 72.0
    assert card.player.upcoming_fixtures[0].difficulty == 0.4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models'`.

- [ ] **Step 3: Write minimal implementation**

```python
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


@dataclass
class Card:
    slug: str
    player: Player
    scarcity: str
    price_eur: float
    recent_sale_prices_eur: list[float] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add domain models"
```

---

### Task 3: Fair-value engine

**Files:**
- Create: `src/fair_value.py`
- Test: `tests/test_fair_value.py`

**Interfaces:**
- Consumes: `src.models.Player`, `src.models.Appearance`, `src.models.Fixture`.
- Produces:
  - `RELIABILITY_MIN_MINUTES = 60` (module constant).
  - `form_score(player: Player) -> float` — mean SO5 over recent appearances; `0.0` if none.
  - `minutes_reliability(player: Player) -> float` — fraction of recent appearances where `started and minutes_played >= RELIABILITY_MIN_MINUTES`; `0.0` if none.
  - `fixture_multiplier(player: Player) -> float` — `1.0` if no fixtures; else `1.0 + 0.2 * (0.5 - mean_difficulty)` clamped to `[0.9, 1.1]` (easier fixtures → up to +10%, harder → down to −10%).
  - `projected_points(player: Player) -> float` — `form_score * minutes_reliability * fixture_multiplier`.

Rationale: multiplying by `minutes_reliability` drops bench players whose past points are a fluke; the fixture multiplier is the light, traceable projection nudge. No black box.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fair_value.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.fair_value'`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fair_value.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/fair_value.py tests/test_fair_value.py
git commit -m "feat: add shared fair-value engine"
```

---

### Task 4: BUY logic — filter and rank top 50

**Files:**
- Create: `src/buy.py`
- Test: `tests/test_buy.py`

**Interfaces:**
- Consumes: `src.models.Card`, `src.fair_value.projected_points`.
- Produces:
  - `@dataclass BuyPick(card: Card, projected: float, value_score: float, rationale: str)`
  - `value_score(card: Card) -> float` — `projected_points(card.player) / card.price_eur`; `0.0` if price <= 0.
  - `rank_buys(cards: list[Card], min_price: float, max_price: float, scarcity: str, limit: int = 50) -> list[BuyPick]` — keep cards whose `scarcity` matches and `min_price <= price_eur <= max_price`, sort by `value_score` descending, return up to `limit` picks. Rationale string example: `"form 72.0 · reliability 1.00 · fixtures 1.05 → 12.3 pts/€"` (built from the engine's parts).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_buy.py
from src.models import Appearance, Fixture, Player, Card
from src import buy


def _card(slug, price, scarcity, score, started=True, minutes=90):
    player = Player(
        slug=slug, display_name=slug.title(), club="Club",
        recent_appearances=[Appearance(score, minutes, started)],
        upcoming_fixtures=[Fixture("x", 0.5)],
    )
    return Card(slug=slug, player=player, scarcity=scarcity, price_eur=price,
                recent_sale_prices_eur=[price])


def test_value_score_is_points_per_euro():
    c = _card("a", price=10.0, scarcity="limited", score=50.0)  # projected 50
    assert buy.value_score(c) == 5.0


def test_value_score_zero_price_is_zero():
    c = _card("a", price=0.0, scarcity="limited", score=50.0)
    assert buy.value_score(c) == 0.0


def test_rank_filters_by_scarcity():
    cards = [
        _card("a", 10.0, "limited", 50.0),
        _card("b", 10.0, "rare", 50.0),
    ]
    picks = buy.rank_buys(cards, min_price=0, max_price=100, scarcity="limited")
    assert [p.card.slug for p in picks] == ["a"]


def test_rank_filters_by_price_range():
    cards = [
        _card("cheap", 5.0, "limited", 50.0),
        _card("inrange", 20.0, "limited", 50.0),
        _card("expensive", 500.0, "limited", 50.0),  # Yamal-style: over budget
    ]
    picks = buy.rank_buys(cards, min_price=10, max_price=100, scarcity="limited")
    assert [p.card.slug for p in picks] == ["inrange"]


def test_rank_sorts_by_value_desc_and_limits():
    cards = [
        _card("low", 50.0, "limited", 50.0),   # value 1.0
        _card("high", 10.0, "limited", 50.0),  # value 5.0
        _card("mid", 25.0, "limited", 50.0),   # value 2.0
    ]
    picks = buy.rank_buys(cards, 0, 100, "limited", limit=2)
    assert [p.card.slug for p in picks] == ["high", "mid"]
    assert len(picks) == 2


def test_pick_has_rationale():
    picks = buy.rank_buys([_card("a", 10.0, "limited", 50.0)], 0, 100, "limited")
    assert "pts/€" in picks[0].rationale
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_buy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.buy'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/buy.py
from dataclasses import dataclass
from src.models import Card
from src import fair_value


@dataclass
class BuyPick:
    card: Card
    projected: float
    value_score: float
    rationale: str


def value_score(card: Card) -> float:
    if card.price_eur <= 0:
        return 0.0
    return fair_value.projected_points(card.player) / card.price_eur


def _rationale(card: Card, projected: float, vscore: float) -> str:
    p = card.player
    return (
        f"form {fair_value.form_score(p):.1f} · "
        f"reliability {fair_value.minutes_reliability(p):.2f} · "
        f"fixtures {fair_value.fixture_multiplier(p):.2f} → "
        f"{vscore:.1f} pts/€"
    )


def rank_buys(cards, min_price, max_price, scarcity, limit=50):
    candidates = [
        c for c in cards
        if c.scarcity == scarcity and min_price <= c.price_eur <= max_price
    ]
    picks = []
    for c in candidates:
        projected = fair_value.projected_points(c.player)
        vscore = value_score(c)
        picks.append(BuyPick(c, projected, vscore, _rationale(c, projected, vscore)))
    picks.sort(key=lambda p: p.value_score, reverse=True)
    return picks[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_buy.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/buy.py tests/test_buy.py
git commit -m "feat: add BUY filtering and top-50 ranking"
```

---

### Task 5: SELL logic — sell/hold signal per owned card

**Files:**
- Create: `src/sell.py`
- Test: `tests/test_sell.py`

**Interfaces:**
- Consumes: `src.models.Card`, `src.fair_value` (`form_score`, `projected_points`).
- Produces:
  - `@dataclass SellSignal(card: Card, signal: str, price_position: float, outlook: str, strength: float, reason: str)` — `signal` is `"SELL"` or `"HOLD"`.
  - `price_position(card: Card) -> float` — where the current price sits vs. recent sales: `(price_eur - mean(sales)) / mean(sales)`; `0.0` if no sales or mean is 0. Positive = priced above its own history.
  - `outlook_trend(card: Card) -> str` — compare mean of the newer half of recent appearances vs. the older half: `"weakening"` if newer < older, `"strengthening"` if newer > older, else `"steady"`. `"steady"` if fewer than 2 appearances.
  - `evaluate_sell(card: Card, price_high_threshold: float = 0.10) -> SellSignal` — `SELL` when `price_position >= price_high_threshold` (priced ≥10% above history) OR `outlook == "weakening"`; else `HOLD`. `strength = max(price_position, 0) + (0.5 if weakening else 0.0)` for ranking.
  - `rank_sells(cards: list[Card]) -> list[SellSignal]` — evaluate all, sort by `strength` descending.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sell.py
from src.models import Appearance, Fixture, Player, Card
from src import sell


def _card(price, sales, appearances):
    player = Player("p", "P", "Club", appearances, [Fixture("x", 0.5)])
    return Card("card", player, "limited", price, sales)


def _apps(scores):
    return [Appearance(s, 90, True) for s in scores]


def test_price_position_above_history_positive():
    c = _card(price=110.0, sales=[100.0, 100.0], appearances=_apps([50, 50]))
    assert abs(sell.price_position(c) - 0.10) < 1e-9


def test_price_position_no_sales_zero():
    c = _card(price=110.0, sales=[], appearances=_apps([50]))
    assert sell.price_position(c) == 0.0


def test_outlook_weakening():
    c = _card(100.0, [100.0], appearances=_apps([80, 80, 20, 20]))  # old 80, new 20
    assert sell.outlook_trend(c) == "weakening"


def test_outlook_strengthening():
    c = _card(100.0, [100.0], appearances=_apps([20, 20, 80, 80]))
    assert sell.outlook_trend(c) == "strengthening"


def test_sell_when_price_high():
    c = _card(price=130.0, sales=[100.0], appearances=_apps([50, 50]))  # +30%
    sig = sell.evaluate_sell(c)
    assert sig.signal == "SELL"


def test_sell_when_weakening_even_if_price_fair():
    c = _card(price=100.0, sales=[100.0], appearances=_apps([80, 80, 20, 20]))
    sig = sell.evaluate_sell(c)
    assert sig.signal == "SELL"


def test_hold_when_fair_and_steady():
    c = _card(price=100.0, sales=[100.0], appearances=_apps([50, 50]))
    sig = sell.evaluate_sell(c)
    assert sig.signal == "HOLD"


def test_rank_sells_orders_by_strength_desc():
    weak_expensive = _card(150.0, [100.0], _apps([80, 80, 10, 10]))  # high price + weakening
    fair_steady = _card(100.0, [100.0], _apps([50, 50]))            # hold, strength 0
    ranked = sell.rank_sells([fair_steady, weak_expensive])
    assert ranked[0].card is weak_expensive
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sell.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.sell'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/sell.py
from dataclasses import dataclass
from statistics import mean
from src.models import Card


@dataclass
class SellSignal:
    card: Card
    signal: str
    price_position: float
    outlook: str
    strength: float
    reason: str


def price_position(card: Card) -> float:
    sales = card.recent_sale_prices_eur
    if not sales:
        return 0.0
    avg = mean(sales)
    if avg == 0:
        return 0.0
    return (card.price_eur - avg) / avg


def outlook_trend(card: Card) -> str:
    apps = card.player.recent_appearances
    if len(apps) < 2:
        return "steady"
    mid = len(apps) // 2
    older = apps[:mid]
    newer = apps[mid:]
    older_mean = mean(a.so5_score for a in older)
    newer_mean = mean(a.so5_score for a in newer)
    if newer_mean < older_mean:
        return "weakening"
    if newer_mean > older_mean:
        return "strengthening"
    return "steady"


def evaluate_sell(card: Card, price_high_threshold: float = 0.10) -> SellSignal:
    pos = price_position(card)
    outlook = outlook_trend(card)
    price_high = pos >= price_high_threshold
    weakening = outlook == "weakening"
    signal = "SELL" if (price_high or weakening) else "HOLD"
    strength = max(pos, 0.0) + (0.5 if weakening else 0.0)
    reasons = []
    if price_high:
        reasons.append(f"price {pos * 100:+.0f}% vs history")
    if weakening:
        reasons.append("form weakening")
    if not reasons:
        reasons.append(f"price {pos * 100:+.0f}% vs history · {outlook}")
    return SellSignal(card, signal, pos, outlook, strength, " · ".join(reasons))


def rank_sells(cards) -> list:
    signals = [evaluate_sell(c) for c in cards]
    signals.sort(key=lambda s: s.strength, reverse=True)
    return signals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sell.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sell.py tests/test_sell.py
git commit -m "feat: add SELL sell/hold signal logic"
```

---

### Task 6: Report formatting

**Files:**
- Create: `src/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `src.buy.BuyPick`, `src.sell.SellSignal`.
- Produces:
  - `format_buys(picks: list[BuyPick]) -> str` — a titled text table with columns: `#`, `Player`, `Club`, `Scarcity`, `Price €`, `Proj`, `Value`, `Why`. If empty, returns a line containing `"No cards match"`.
  - `format_sells(signals: list[SellSignal]) -> str` — titled text table with columns: `Player`, `Scarcity`, `Price €`, `vs History`, `Outlook`, `Signal`, `Reason`. If empty, returns a line containing `"No cards in collection"`.

Both return plain strings (no direct printing) so they are testable. The CLI prints them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from src.models import Appearance, Fixture, Player, Card
from src.buy import BuyPick
from src.sell import SellSignal
from src import report


def _card(name="Messi", price=25.0):
    p = Player("m", name, "Inter Miami",
               [Appearance(70, 90, True)], [Fixture("x", 0.5)])
    return Card("c", p, "limited", price, [price])


def test_format_buys_includes_player_and_headers():
    pick = BuyPick(_card(), projected=70.0, value_score=2.8, rationale="form 70.0 → 2.8 pts/€")
    out = report.format_buys([pick])
    assert "Messi" in out
    assert "Value" in out
    assert "Player" in out


def test_format_buys_empty():
    assert "No cards match" in report.format_buys([])


def test_format_sells_includes_signal():
    sig = SellSignal(_card(), signal="SELL", price_position=0.2,
                     outlook="weakening", strength=0.7, reason="price +20% vs history")
    out = report.format_sells([sig])
    assert "SELL" in out
    assert "Messi" in out


def test_format_sells_empty():
    assert "No cards in collection" in report.format_sells([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.report'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/report.py
from src.buy import BuyPick
from src.sell import SellSignal


def _row(cols, widths):
    return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))


def format_buys(picks: list[BuyPick]) -> str:
    if not picks:
        return "No cards match your filters."
    widths = [3, 22, 18, 10, 9, 6, 6, 40]
    header = _row(["#", "Player", "Club", "Scarcity", "Price €", "Proj", "Value", "Why"], widths)
    lines = ["TOP VALUE-FOR-MONEY SIGNINGS", header, "-" * len(header)]
    for i, p in enumerate(picks, 1):
        lines.append(_row([
            i,
            p.card.player.display_name[:22],
            p.card.player.club[:18],
            p.card.scarcity,
            f"{p.card.price_eur:.2f}",
            f"{p.projected:.1f}",
            f"{p.value_score:.2f}",
            p.rationale[:40],
        ], widths))
    return "\n".join(lines)


def format_sells(signals: list[SellSignal]) -> str:
    if not signals:
        return "No cards in collection."
    widths = [22, 10, 9, 12, 14, 6, 30]
    header = _row(["Player", "Scarcity", "Price €", "vs History", "Outlook", "Signal", "Reason"], widths)
    lines = ["YOUR COLLECTION — SELL SIGNALS", header, "-" * len(header)]
    for s in signals:
        lines.append(_row([
            s.card.player.display_name[:22],
            s.card.scarcity,
            f"{s.card.price_eur:.2f}",
            f"{s.price_position * 100:+.0f}%",
            s.outlook,
            s.signal,
            s.reason[:30],
        ], widths))
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/report.py tests/test_report.py
git commit -m "feat: add report table formatting"
```

---

### Task 7: Interactive filter prompts

**Files:**
- Create: `src/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `VALID_SCARCITIES = ["limited", "rare", "super_rare", "unique"]`
  - `@dataclass Filters(min_price: float, max_price: float, scarcity: str)`
  - `prompt_filters(input_fn=input) -> Filters` — asks for min price, max price (EUR), and scarcity. Re-prompts on invalid input (non-numeric price, min > max, unknown scarcity). `input_fn` is injected so tests can drive it without real stdin.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prompts.py
import pytest
from src import prompts


def _feed(answers):
    it = iter(answers)
    return lambda _prompt="": next(it)


def test_prompt_filters_happy_path():
    f = prompts.prompt_filters(_feed(["5", "50", "limited"]))
    assert f.min_price == 5.0
    assert f.max_price == 50.0
    assert f.scarcity == "limited"


def test_prompt_reprompts_on_bad_number_then_succeeds():
    f = prompts.prompt_filters(_feed(["abc", "5", "50", "rare"]))
    assert f.min_price == 5.0
    assert f.scarcity == "rare"


def test_prompt_reprompts_when_min_greater_than_max():
    f = prompts.prompt_filters(_feed(["100", "10", "50", "unique"]))
    # first max (10) < min (100) -> re-ask max; then 50 accepted
    assert f.min_price == 100.0
    assert f.max_price == 50.0


def test_prompt_reprompts_on_bad_scarcity():
    f = prompts.prompt_filters(_feed(["5", "50", "diamond", "super_rare"]))
    assert f.scarcity == "super_rare"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.prompts'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/prompts.py
from dataclasses import dataclass

VALID_SCARCITIES = ["limited", "rare", "super_rare", "unique"]


@dataclass
class Filters:
    min_price: float
    max_price: float
    scarcity: str


def _ask_float(input_fn, label: str) -> float:
    while True:
        raw = input_fn(f"{label}: ").strip()
        try:
            return float(raw)
        except ValueError:
            print(f"'{raw}' is not a number. Try again.")


def prompt_filters(input_fn=input) -> Filters:
    min_price = _ask_float(input_fn, "Min price (EUR)")
    while True:
        max_price = _ask_float(input_fn, "Max price (EUR)")
        if max_price >= min_price:
            break
        print("Max must be >= min. Try again.")
    while True:
        scarcity = input_fn(
            f"Scarcity {VALID_SCARCITIES}: "
        ).strip().lower()
        if scarcity in VALID_SCARCITIES:
            break
        print(f"Unknown scarcity. Choose one of {VALID_SCARCITIES}.")
    return Filters(min_price, max_price, scarcity)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/prompts.py tests/test_prompts.py
git commit -m "feat: add interactive filter prompts"
```

---

### Task 8: Sorare API client (mocked tests)

**Files:**
- Create: `src/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `src.models` (`Appearance`, `Fixture`, `Player`, `Card`).
- Produces:
  - `SORARE_GRAPHQL_URL = "https://api.sorare.com/federation/graphql"` (single source of truth for the endpoint; corrected in Task 10 if schema verification shows otherwise).
  - `load_credentials(path: str = "credentials.json") -> dict` — reads JSON; raises `FileNotFoundError` with a message pointing to `credentials.example.json` if missing.
  - `class SorareClient:`
    - `__init__(self, session=None)` — `session` is a `requests.Session`-like object (injected for tests).
    - `wait_for_authentication(self, prompt_fn=input) -> None` — prints instructions and blocks on `prompt_fn` until the user confirms they've completed login (the "script waits" behavior). Stores nothing beyond a flag `self.authenticated = True`.
    - `_post(self, query: str, variables: dict) -> dict` — POSTs GraphQL, returns parsed `data`; raises `RuntimeError` on HTTP error or GraphQL `errors`.
    - `fetch_market_cards(self, scarcity: str) -> list[Card]` — returns market cards for a scarcity tier (maps raw JSON → `Card`).
    - `fetch_my_cards(self) -> list[Card]` — returns the authenticated user's cards.
  - Two pure mapper functions, tested directly with fixture JSON:
    - `card_from_json(node: dict) -> Card`
    - `player_from_json(node: dict) -> Player`

The mappers are the only place raw field names appear, so Task 10's schema check touches just these.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py
import json
import pytest
from src import api
from src.models import Card


SAMPLE_PLAYER = {
    "slug": "kylian-mbappe",
    "displayName": "Kylian Mbappe",
    "activeClub": {"name": "Real Madrid"},
    "recentAppearances": [
        {"score": 65.0, "minutesPlayed": 90, "started": True},
        {"score": 40.0, "minutesPlayed": 30, "started": False},
    ],
    "upcomingFixtures": [
        {"opponentName": "Getafe", "difficulty": 0.3},
    ],
}

SAMPLE_CARD = {
    "slug": "card-abc",
    "rarity": "limited",
    "priceEur": 42.5,
    "recentSalesEur": [40.0, 44.0, 43.0],
    "player": SAMPLE_PLAYER,
}


def test_player_from_json_maps_fields():
    p = api.player_from_json(SAMPLE_PLAYER)
    assert p.slug == "kylian-mbappe"
    assert p.display_name == "Kylian Mbappe"
    assert p.club == "Real Madrid"
    assert p.recent_appearances[0].so5_score == 65.0
    assert p.recent_appearances[1].started is False
    assert p.upcoming_fixtures[0].difficulty == 0.3


def test_card_from_json_maps_fields():
    c = api.card_from_json(SAMPLE_CARD)
    assert isinstance(c, Card)
    assert c.slug == "card-abc"
    assert c.scarcity == "limited"
    assert c.price_eur == 42.5
    assert c.recent_sale_prices_eur == [40.0, 44.0, 43.0]
    assert c.player.display_name == "Kylian Mbappe"


def test_load_credentials_missing_file_points_to_template(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        api.load_credentials(str(tmp_path / "nope.json"))
    assert "credentials.example.json" in str(exc.value)


def test_load_credentials_reads_json(tmp_path):
    p = tmp_path / "credentials.json"
    p.write_text(json.dumps({"email": "a@b.com", "password": "x", "api_key": ""}))
    creds = api.load_credentials(str(p))
    assert creds["email"] == "a@b.com"


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json})
        return _FakeResponse(self._payload)


def test_fetch_market_cards_maps_nodes():
    payload = {"data": {"cards": {"nodes": [SAMPLE_CARD]}}}
    client = api.SorareClient(session=_FakeSession(payload))
    cards = client.fetch_market_cards("limited")
    assert len(cards) == 1
    assert cards[0].player.display_name == "Kylian Mbappe"


def test_post_raises_on_graphql_errors():
    payload = {"errors": [{"message": "bad query"}]}
    client = api.SorareClient(session=_FakeSession(payload))
    with pytest.raises(RuntimeError) as exc:
        client._post("query {}", {})
    assert "bad query" in str(exc.value)


def test_wait_for_authentication_blocks_until_confirmed():
    client = api.SorareClient(session=_FakeSession({"data": {}}))
    client.wait_for_authentication(prompt_fn=lambda _="": "")
    assert client.authenticated is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.api'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/api.py
import json
import os
from src.models import Appearance, Fixture, Player, Card

SORARE_GRAPHQL_URL = "https://api.sorare.com/federation/graphql"


def load_credentials(path: str = "credentials.json") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Copy credentials.example.json to "
            f"credentials.json and fill in your Sorare login."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def player_from_json(node: dict) -> Player:
    club = ""
    active_club = node.get("activeClub") or {}
    club = active_club.get("name", "")
    appearances = [
        Appearance(
            so5_score=float(a.get("score", 0.0)),
            minutes_played=int(a.get("minutesPlayed", 0)),
            started=bool(a.get("started", False)),
        )
        for a in node.get("recentAppearances", [])
    ]
    fixtures = [
        Fixture(
            opponent=f.get("opponentName", ""),
            difficulty=float(f.get("difficulty", 0.5)),
        )
        for f in node.get("upcomingFixtures", [])
    ]
    return Player(
        slug=node.get("slug", ""),
        display_name=node.get("displayName", ""),
        club=club,
        recent_appearances=appearances,
        upcoming_fixtures=fixtures,
    )


def card_from_json(node: dict) -> Card:
    return Card(
        slug=node.get("slug", ""),
        player=player_from_json(node.get("player", {})),
        scarcity=node.get("rarity", ""),
        price_eur=float(node.get("priceEur", 0.0)),
        recent_sale_prices_eur=[float(x) for x in node.get("recentSalesEur", [])],
    )


class SorareClient:
    def __init__(self, session=None):
        self.session = session
        self.authenticated = False

    def wait_for_authentication(self, prompt_fn=input) -> None:
        print(
            "\nAuthentication required.\n"
            "Complete the Sorare login in your browser / app now.\n"
        )
        prompt_fn("Press Enter once you have authenticated... ")
        self.authenticated = True

    def _post(self, query: str, variables: dict) -> dict:
        resp = self.session.post(
            SORARE_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        payload = resp.json()
        if payload.get("errors"):
            messages = "; ".join(e.get("message", "?") for e in payload["errors"])
            raise RuntimeError(f"GraphQL error: {messages}")
        return payload.get("data", {})

    def fetch_market_cards(self, scarcity: str) -> list:
        query = """
        query MarketCards($rarity: String!) {
          cards(rarity: $rarity) {
            nodes { slug rarity priceEur recentSalesEur
              player { slug displayName activeClub { name }
                recentAppearances { score minutesPlayed started }
                upcomingFixtures { opponentName difficulty } } }
          }
        }
        """
        data = self._post(query, {"rarity": scarcity})
        nodes = (data.get("cards") or {}).get("nodes", [])
        return [card_from_json(n) for n in nodes]

    def fetch_my_cards(self) -> list:
        query = """
        query MyCards {
          currentUser {
            cards {
              nodes { slug rarity priceEur recentSalesEur
                player { slug displayName activeClub { name }
                  recentAppearances { score minutesPlayed started }
                  upcomingFixtures { opponentName difficulty } } }
            }
          }
        }
        """
        data = self._post(query, {})
        nodes = ((data.get("currentUser") or {}).get("cards") or {}).get("nodes", [])
        return [card_from_json(n) for n in nodes]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add Sorare API client with mocked-JSON mappers"
```

---

### Task 9: CLI entry point wiring

**Files:**
- Create: `sorare_value.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `src.prompts`, `src.api`, `src.buy`, `src.sell`, `src.report`.
- Produces:
  - `run(client, filters, output_fn=print) -> None` — orchestrates: authenticate, fetch market cards for the chosen scarcity, rank buys, fetch owned cards, rank sells, print both reports via `output_fn`. Injectable `client`, `filters`, and `output_fn` make it testable without network or stdin.
  - `main() -> None` — real entry: load credentials, build a `requests.Session`, prompt filters, call `run`. Guarded by `if __name__ == "__main__"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from src.models import Appearance, Fixture, Player, Card
from src.prompts import Filters
import sorare_value


def _card(name, price, scarcity="limited", score=60.0):
    p = Player(name, name, "Club",
               [Appearance(score, 90, True), Appearance(score, 90, True)],
               [Fixture("x", 0.5)])
    return Card(name, p, scarcity, price, [price])


class _FakeClient:
    def __init__(self):
        self.authenticated = False
        self.market = [_card("Cheap", 10.0), _card("Pricey", 500.0)]
        self.mine = [_card("Owned", 100.0)]

    def wait_for_authentication(self, prompt_fn=input):
        self.authenticated = True

    def fetch_market_cards(self, scarcity):
        return [c for c in self.market if c.scarcity == scarcity]

    def fetch_my_cards(self):
        return self.mine


def test_run_produces_both_reports_and_respects_filters():
    lines = []
    client = _FakeClient()
    filters = Filters(min_price=5.0, max_price=50.0, scarcity="limited")
    sorare_value.run(client, filters, output_fn=lines.append)

    out = "\n".join(lines)
    assert client.authenticated is True
    assert "TOP VALUE-FOR-MONEY SIGNINGS" in out
    assert "YOUR COLLECTION" in out
    assert "Cheap" in out       # within price range
    assert "Pricey" not in out  # 500 EUR filtered out by max_price
    assert "Owned" in out       # collection always shown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sorare_value'`.

- [ ] **Step 3: Write minimal implementation**

```python
# sorare_value.py
import requests

from src import api, buy, sell, report
from src.prompts import prompt_filters


def run(client, filters, output_fn=print) -> None:
    client.wait_for_authentication()

    market = client.fetch_market_cards(filters.scarcity)
    picks = buy.rank_buys(
        market, filters.min_price, filters.max_price, filters.scarcity, limit=50
    )
    output_fn(report.format_buys(picks))

    output_fn("")  # spacer

    mine = client.fetch_my_cards()
    signals = sell.rank_sells(mine)
    output_fn(report.format_sells(signals))


def main() -> None:
    api.load_credentials()  # validates presence; raises with guidance if missing
    filters = prompt_filters()
    client = api.SorareClient(session=requests.Session())
    run(client, filters)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests from Tasks 2–9 PASS.

- [ ] **Step 6: Commit**

```bash
git add sorare_value.py tests/test_cli.py
git commit -m "feat: wire CLI entry point"
```

---

### Task 10: Live schema verification & README run notes

**Files:**
- Modify: `src/api.py` (only if live schema differs — field names, endpoint, query shape)
- Modify: `README.md`

**Interfaces:**
- Consumes: everything.
- Produces: an `api.py` whose queries and mappers match the *actual* current Sorare GraphQL schema, plus README notes on running live.

This is the one task that touches the network. All prior logic is already proven by mocked tests; here we reconcile `api.py`'s assumed field names with reality.

- [ ] **Step 1: Introspect / probe the live endpoint**

Run a minimal probe (no credentials needed for public market schema) to confirm the endpoint and top-level field names. Example:

```bash
python - <<'PY'
import requests
q = "{ __schema { queryType { fields { name } } } }"
r = requests.post("https://api.sorare.com/federation/graphql",
                  json={"query": q}, timeout=30)
print(r.status_code)
print(r.text[:2000])
PY
```

Expected: HTTP 200 and a list of query field names. If the endpoint URL is wrong, correct `SORARE_GRAPHQL_URL` in `src/api.py`.

- [ ] **Step 2: Reconcile field names**

For each field the mappers use (`cards`/`nodes`, `rarity`, `priceEur`, `recentSalesEur`, `player.displayName`, `activeClub.name`, `recentAppearances.{score,minutesPlayed,started}`, `upcomingFixtures.{opponentName,difficulty}`, `currentUser.cards`), confirm the real name via introspection. Where a name differs, update **only** `card_from_json`, `player_from_json`, and the two query strings in `src/api.py`. Do NOT change logic modules — they consume the dataclasses, not raw JSON.

If Sorare exposes prices only in wei / a `PriceRange` object rather than a flat `priceEur`, add the conversion inside `card_from_json` (wei → EUR using the returned fiat field), keeping the mapper the single conversion point per Global Constraints.

- [ ] **Step 3: Re-run the mocked suite to confirm no logic regressions**

Run: `pytest -v`
Expected: all PASS (mocked tests still green; they pin the dataclass contract).

- [ ] **Step 4: Update README with live-run notes**

Append a "Live run" section documenting the confirmed endpoint, that authentication is completed interactively during the pause, and any field-name corrections made.

- [ ] **Step 5: Commit**

```bash
git add src/api.py README.md
git commit -m "fix: reconcile api.py with live Sorare schema; document live run"
```

---

## Notes for the implementer

- Run tests from the repo root so `src` and `sorare_value` import cleanly: `pytest -v`.
- Keep logic modules network-free. If you feel tempted to call the API inside `buy.py`/`sell.py`, stop — pass data in.
- Only `api.py` and Task 10 deal with real Sorare fields; everything else is proven against mocked data.
- Commit after every green task, as the steps specify.
