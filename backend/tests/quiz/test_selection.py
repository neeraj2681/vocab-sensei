from collections import Counter
from datetime import date
from random import Random

from app.core.enums import QuestionType
from app.quiz.selection import (
    DailyGoal,
    Pool,
    choose_pool,
    choose_question_type,
    closest_or_oldest,
    learning_cap,
    spacing_rules,
    streak,
)

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


TEN = DailyGoal(10)


def day(offset: int) -> date:
    return date.fromordinal(TODAY.toordinal() - offset)


def test_streak_counts_days_in_a_row_that_met_the_goal() -> None:
    answers = {day(0): 12, day(1): 10, day(2): 30, day(3): 4, day(4): 10}

    assert streak(answers, TODAY, goal=TEN) == 3  # day 3 broke it


def test_today_counts_once_its_goal_is_met() -> None:
    answers = {day(0): 3, day(1): 10, day(2): 10}

    assert streak(answers, TODAY, goal=TEN) == 2  # yesterday's streak is still alive
    assert streak({**answers, day(0): 10}, TODAY, goal=TEN) == 3


def test_a_missed_day_resets_the_streak() -> None:
    assert streak({day(2): 10, day(3): 10}, TODAY, goal=TEN) == 0
    assert streak({}, TODAY, goal=TEN) == 0


def test_raising_the_goal_keeps_the_streak_already_earned() -> None:
    raised_today = DailyGoal(20, steps=((day(30), 10), (day(0), 20)))
    answers = {day(0): 20, day(1): 10, day(2): 12}

    assert streak(answers, TODAY, goal=raised_today) == 3  # earlier days judged by 10
    assert streak({**answers, day(0): 15}, TODAY, goal=raised_today) == 2  # today needs 20


def test_every_past_day_keeps_the_goal_it_had() -> None:
    # 10 at first, 50 from two days ago, and today 50 -> 20 -> 50 again.
    goal = DailyGoal(50, steps=((day(30), 10), (day(2), 50), (day(0), 50)))
    answers = {day(0): 60, day(1): 55, day(2): 50, day(3): 11}

    assert [goal.on(day(n)) for n in (3, 2, 1, 0)] == [10, 50, 50, 50]
    assert streak(answers, TODAY, goal=goal) == 4  # day 3's 11 met the 10 it had


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


def test_the_learning_cap_is_the_daily_goal_within_bounds() -> None:
    assert [learning_cap(goal, 15, 50) for goal in (5, 20, 50, 200)] == [15, 20, 50, 50]


def test_right_answers_wait_and_wrong_ones_come_back_after_a_few() -> None:
    recent = [(1, True), (2, False), (3, True), (4, False), (5, False), (1, True)]  # newest first

    too_soon, retry = spacing_rules(recent, spacing=10, retry_after=3)

    assert too_soon == {1, 2, 3}  # 2 was missed only 1 answer ago: not yet
    assert retry == [5, 4]  # oldest miss first


def test_a_missed_word_gets_one_retry() -> None:
    recent = [
        (1, True),
        (2, True),
        (3, True),
        (7, False),
        (4, True),
        (5, True),
        (6, True),
        (7, False),
    ]

    assert spacing_rules(recent, 10, 3) == ({1, 2, 3, 4, 5, 6, 7}, [])  # missed on the retry too


def test_a_missed_word_answered_right_since_waits_again() -> None:
    assert spacing_rules([(7, True), (8, True), (9, True), (7, False)], 10, 3) == ({7, 8, 9}, [])


def test_half_the_time_the_closest_to_learned_otherwise_the_oldest() -> None:
    words = [("oldest", 10), ("middle", 80), ("newest", 40)]
    picks = Counter(
        closest_or_oldest(words, lambda w: w[1], Random(seed))[0] for seed in range(400)
    )

    assert set(picks) == {"oldest", "middle"}
    assert 150 < picks["middle"] < 250


def test_wrong_answers_in_a_row_dont_cycle_the_same_few_words() -> None:
    # Seven words, each missed every seventh answer: each miss had its retry long ago.
    cycle = [(word, False) for word in (7, 6, 5, 4, 3, 2, 1)] * 3

    too_soon, retry = spacing_rules(cycle, 10, 3)

    assert retry == []
    assert too_soon == {1, 2, 3, 4, 5, 6, 7}  # so the quiz moves on to other words
