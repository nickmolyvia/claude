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
    f = prompts.prompt_filters(_feed(["100", "50", "100", "limited"]))
    # first max (50) < min (100) -> re-ask max; then 100 accepted
    assert f.min_price == 100.0
    assert f.max_price == 100.0


def test_prompt_reprompts_on_bad_scarcity():
    f = prompts.prompt_filters(_feed(["5", "50", "diamond", "super_rare"]))
    assert f.scarcity == "super_rare"
