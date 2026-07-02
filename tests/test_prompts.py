import pytest
from src import prompts


def _feed(answers):
    it = iter(answers)
    return lambda _prompt="": next(it)


def test_prompt_filters_happy_path():
    f = prompts.prompt_filters(_feed(["5", "50", "limited", "top5"]))
    assert f.min_price == 5.0
    assert f.max_price == 50.0
    assert f.scarcity == "limited"
    assert f.tier == "top5"


def test_prompt_reprompts_on_bad_number_then_succeeds():
    f = prompts.prompt_filters(_feed(["abc", "5", "50", "rare", "all"]))
    assert f.min_price == 5.0
    assert f.scarcity == "rare"
    assert f.tier == "all"


def test_prompt_reprompts_when_min_greater_than_max():
    f = prompts.prompt_filters(_feed(["100", "50", "100", "limited", "top10"]))
    # first max (50) < min (100) -> re-ask max; then 100 accepted
    assert f.min_price == 100.0
    assert f.max_price == 100.0
    assert f.tier == "top10"


def test_prompt_reprompts_on_bad_scarcity():
    f = prompts.prompt_filters(_feed(["5", "50", "diamond", "super_rare", "top7"]))
    assert f.scarcity == "super_rare"
    assert f.tier == "top7"


def test_prompt_reprompts_on_bad_tier():
    f = prompts.prompt_filters(_feed(["5", "50", "limited", "bundesliga", "top5"]))
    assert f.tier == "top5"
