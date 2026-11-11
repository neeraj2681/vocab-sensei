"""How well best_sense picks the meaning a sentence uses, on the 40 hand-checked cases.

The cases are deliberately hard (most need a meaning other than WordNet's first). What matters most
is precision: when best_sense moves away from the first meaning it must usually be right, because a
wrong switch teaches a wrong meaning (and the "which meaning" question only uses switches).
Measured 11 Nov 2026: 18/40 right (first meaning alone: 4/40); 14 of its 16 switches right.
"""

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.dictionary.senses import best_sense
from app.dictionary.types import DictionaryUnavailableError
from app.dictionary.wordnet import WordNetDictionary

FIXTURE = Path(__file__).parent / "data" / "sense_cases.json"


def test_switches_away_from_the_first_meaning_are_mostly_right() -> None:
    settings = get_settings()
    try:
        dictionary = WordNetDictionary(settings.dictionary_dir, settings.dictionary.lexicon, 10)
    except DictionaryUnavailableError as error:
        pytest.skip(f"WordNet isn't available: {error}")

    right = first_right = switched = switched_right = 0
    for case in json.loads(FIXTURE.read_text(encoding="utf-8")):
        senses = [s for s in dictionary.senses(case["lemma"]) if s.pos == case["pos"]]
        wanted = next(s.rank for s in senses if case["expected"] in s.definition)
        chosen = best_sense(case["sentence"], case["lemma"], senses)
        right += chosen == wanted
        first_right += senses[0].rank == wanted
        if chosen != senses[0].rank:
            switched += 1
            switched_right += chosen == wanted

    assert right > first_right
    assert switched >= 10
    assert switched_right / switched >= 0.8
