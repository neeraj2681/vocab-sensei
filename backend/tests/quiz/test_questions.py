from random import Random

import pytest

from app.core.enums import QuestionType
from app.quiz.questions import (
    Candidate,
    DefinitionQuestionGenerator,
    FillInBlankQuestionGenerator,
    NotEnoughDistractorsError,
    QuestionNotPossibleError,
    ReverseQuestionGenerator,
    Target,
    blank_out,
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


def test_reverse_questions_show_the_meaning_and_offer_words() -> None:
    draft = ReverseQuestionGenerator().generate(TARGET, POOL, Random(1))

    assert draft.type == QuestionType.REVERSE
    assert draft.prompt == "excessively mournful"
    assert draft.options[draft.correct_index] == "lugubrious"
    assert set(draft.options) <= {"lugubrious", *(c.lemma for c in POOL)}
    assert len(set(draft.options)) == 4


def test_fill_in_the_blank_hides_the_word_in_the_books_sentence() -> None:
    target = Target(
        lemma="perambulate",
        definition="walk with no particular goal",
        synonyms=frozenset(),
        context_sentence="The sailors were Perambulating along the docks.",
        context_form="Perambulating",
    )

    draft = FillInBlankQuestionGenerator().generate(target, POOL, Random(1))

    assert draft.type == QuestionType.FILL_IN_BLANK
    assert draft.prompt == "The sailors were _____ along the docks."
    assert draft.options[draft.correct_index] == "perambulate"


@pytest.mark.parametrize(
    ("sentence", "form", "expected"),
    [
        ("He felt the spleen rise.", "spleen", "He felt the _____ rise."),
        ("Spleen, again.", "spleen", "_____, again."),  # any case
        ("A splendid spleenful day; spleen.", "spleen", "A splendid spleenful day; _____."),
        ("No such word here.", "spleen", None),
        (None, "spleen", None),
        ("A sentence.", None, None),
    ],
)
def test_blank_out_replaces_the_whole_word_only(
    sentence: str | None, form: str | None, expected: str | None
) -> None:
    assert blank_out(sentence, form) == expected


def test_fill_in_the_blank_needs_the_word_in_the_sentence() -> None:
    with pytest.raises(QuestionNotPossibleError):
        FillInBlankQuestionGenerator().generate(TARGET, POOL, Random(1))  # form unknown
