"""Checks the hand-made sense fixture is valid and, when WordNet is installed, matches WordNet."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.dictionary.types import Dictionary, DictionaryUnavailableError
from app.dictionary.wordnet import WordNetDictionary

FIXTURE = Path(__file__).parent / "data" / "sense_cases.json"
POS_VALUES = {"noun", "verb", "adjective", "adverb"}
CASE_COUNT = 40
MIN_NOT_FIRST = 25


@pytest.fixture(scope="module")
def cases() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture(scope="module")
def dictionary() -> Dictionary:
    settings = get_settings()
    try:
        return WordNetDictionary(settings.dictionary_dir, settings.dictionary.lexicon, 10)
    except DictionaryUnavailableError as error:
        pytest.skip(f"WordNet isn't available: {error}")


def test_fixture_has_40_complete_cases(cases: list[dict[str, Any]]) -> None:
    assert len(cases) == CASE_COUNT
    for case in cases:
        assert set(case) == {"lemma", "pos", "sentence", "expected"}, case
        assert case["lemma"] == case["lemma"].lower(), case
        assert case["pos"] in POS_VALUES, case
        assert 10 <= len(case["sentence"].split()) <= 35, case
        assert 3 <= len(case["expected"].split()) <= 8, case


def test_sentence_uses_the_lemma(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        assert case["lemma"][:4] in case["sentence"].lower(), case


def test_expected_meaning_is_a_unique_wordnet_definition(
    cases: list[dict[str, Any]], dictionary: Dictionary
) -> None:
    not_first = 0
    for case in cases:
        senses = [s for s in dictionary.senses(case["lemma"]) if s.pos == case["pos"]]
        assert len(senses) >= 2, case
        matches = [i for i, s in enumerate(senses) if case["expected"] in s.definition]
        assert len(matches) == 1, (case, [s.definition for s in senses])
        if matches[0] != 0:
            not_first += 1
    assert not_first >= MIN_NOT_FIRST, not_first
