from collections import Counter
from datetime import date
from random import Random

from app.core.enums import QuestionType
from app.quiz.selection import Pool, choose_pool, choose_question_type, streak

WEIGHTS = {Pool.NEW: 6, Pool.LEARNING: 3, Pool.REVIEW: 1}
TODAY = date(2026, 10, 30)


def test_pools_are_chosen_in_proportion_to_their_weights() -> None:
    rng = Random(7)

    counts = Counter(choose_pool(list(Pool), WEIGHTS, rng) for _ in range(10_000))

    assert 0.57 < counts[Pool.NEW] / 10_000 < 0.63
    assert 0.27 < counts[Pool.LEARNING] / 10_000 < 0.33
    assert 0.08 < counts[Pool.REVIEW] / 10_000 < 0.12


def test_only_pools_with_words_are_chosen() -> None:
    rng = Random(7)

    picks = {choose_pool([Pool.LEARNING, Pool.REVIEW], WEIGHTS, rng) for _ in range(100)}

    assert picks == {Pool.LEARNING, Pool.REVIEW}


def test_a_pool_with_weight_zero_is_used_only_when_nothing_else_is_left() -> None:
    weights = {Pool.NEW: 0, Pool.LEARNING: 3, Pool.REVIEW: 0}
    rng = Random(7)

    assert {choose_pool([Pool.NEW, Pool.LEARNING], weights, rng) for _ in range(50)} == {
        Pool.LEARNING
    }
    assert choose_pool([Pool.NEW], weights, rng) == Pool.NEW


def test_no_pools() -> None:
    assert choose_pool([], WEIGHTS, Random(1)) is None


def day(offset: int) -> date:
    return date.fromordinal(TODAY.toordinal() - offset)


def test_streak_counts_days_in_a_row_that_met_the_goal() -> None:
    answers = {day(0): 12, day(1): 10, day(2): 30, day(3): 4, day(4): 10}

    assert streak(answers, TODAY, goal=10) == 3  # day 3 broke it


def test_today_counts_once_its_goal_is_met() -> None:
    answers = {day(0): 3, day(1): 10, day(2): 10}

    assert streak(answers, TODAY, goal=10) == 2  # yesterday's streak is still alive
    assert streak({**answers, day(0): 10}, TODAY, goal=10) == 3


def test_a_missed_day_resets_the_streak() -> None:
    assert streak({day(2): 10, day(3): 10}, TODAY, goal=10) == 0
    assert streak({}, TODAY, goal=10) == 0


def kinds_for(score: int, can_fill: bool = True) -> set[QuestionType]:
    rng = Random(3)
    return {
        choose_question_type(score, can_fill, rng, reverse_from=30, fill_from=70)
        for _ in range(200)
    }


def test_harder_formats_unlock_as_a_word_is_learned() -> None:
    meaning, reverse, fill = (
        QuestionType.DEFINITION_MCQ,
        QuestionType.REVERSE,
        QuestionType.FILL_IN_BLANK,
    )
    assert kinds_for(0) == kinds_for(29) == {meaning}
    assert kinds_for(30) == kinds_for(69) == {meaning, reverse}
    assert kinds_for(70) == kinds_for(150) == {meaning, reverse, fill}


def test_fill_in_needs_a_sentence() -> None:
    assert QuestionType.FILL_IN_BLANK not in kinds_for(90, can_fill=False)
