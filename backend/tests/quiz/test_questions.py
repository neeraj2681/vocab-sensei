from random import Random

import pytest

from app.core.enums import QuestionType
from app.quiz.questions import (
    Candidate,
    DefinitionQuestionGenerator,
    NotEnoughDistractorsError,
    Target,
)

TARGET = Target(
    lemma="lugubrious",
    definition="excessively mournful",
    synonyms=frozenset({"doleful", "mournful"}),
    context_sentence="A lugubrious tune played.",
)
POOL = [
    Candidate("ebullient", "joyously unrestrained"),
    Candidate("perfunctory", "hasty and without attention"),
    Candidate("obsequious", "attempting to win favor by flattery"),
    Candidate("sanguine", "confidently optimistic"),
]


def generate(target: Target = TARGET, pool: list[Candidate] = POOL, seed: int = 1) -> list[str]:
    draft = DefinitionQuestionGenerator().generate(target, pool, Random(seed))
    return draft.options


def test_one_correct_definition_and_three_wrong_ones() -> None:
    draft = DefinitionQuestionGenerator().generate(TARGET, POOL, Random(1))

    assert draft.type == QuestionType.DEFINITION_MCQ
    assert draft.prompt == "lugubrious"
    assert len(draft.options) == 4
    assert draft.options[draft.correct_index] == "excessively mournful"
    assert set(draft.options) - {"excessively mournful"} <= {c.definition for c in POOL}
    assert draft.generator == "wordnet-rules"
    assert draft.source_sentence == "A lugubrious tune played."


def test_options_close_in_length_to_the_answer_are_preferred() -> None:
    pool = [Candidate("prolix", "using or containing too many words; tediously lengthy"), *POOL]

    options = generate(pool=pool)  # the answer, "excessively mournful", is 20 characters

    assert "using or containing too many words; tediously lengthy" not in options


def test_synonyms_and_the_word_itself_are_never_options() -> None:
    pool = [
        Candidate("doleful", "filled with or evoking sadness"),
        Candidate("lugubrious", "mournful in a slow, heavy way"),
        *POOL,
    ]

    options = generate(pool=pool)

    assert "filled with or evoking sadness" not in options
    assert "mournful in a slow, heavy way" not in options


def test_an_option_matching_the_answer_is_skipped() -> None:
    pool = [Candidate("dolorous", "Excessively  mournful"), *POOL]

    options = generate(pool=pool)

    assert sum(o.lower() == "excessively mournful" for o in options) == 1


def test_option_order_changes_between_asks() -> None:
    orders = {tuple(generate(seed=seed)) for seed in range(10)}

    assert len(orders) > 1


def test_too_few_candidates() -> None:
    with pytest.raises(NotEnoughDistractorsError):
        generate(pool=POOL[:2])


def test_number_of_options_is_configurable() -> None:
    draft = DefinitionQuestionGenerator(options=3).generate(TARGET, POOL, Random(1))

    assert len(draft.options) == 3
