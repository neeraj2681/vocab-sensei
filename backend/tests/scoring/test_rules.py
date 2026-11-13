from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import ScoringSettings
from app.core.enums import WordStatus
from app.scoring.rules import (
    Triage,
    WordProgress,
    answer_points,
    apply_answer,
    current_status,
    effective_score,
    initial_progress,
    mark_known,
    miss_penalty,
)

RULES = ScoringSettings()
NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def learned(score: int = 100, weeks_ago: float = 0) -> WordProgress:
    return WordProgress(
        score=score, status=WordStatus.LEARNED, learned_at=NOW - timedelta(weeks=weeks_ago)
    )


@pytest.mark.parametrize(
    ("triage", "expected"),
    [
        (Triage.NEW, WordProgress(score=0, status=WordStatus.NEW)),
        (Triage.UNSURE, WordProgress(score=50, status=WordStatus.LEARNING)),
        (Triage.KNOWN, WordProgress(score=0, status=WordStatus.KNOWN)),
    ],
)
def test_initial_progress_from_triage(triage: Triage, expected: WordProgress) -> None:
    assert initial_progress(triage, RULES) == expected


def test_correct_answer_adds_ten() -> None:
    result = apply_answer(WordProgress(score=40), correct=True, now=NOW, rules=RULES)

    assert result == WordProgress(score=50, status=WordStatus.LEARNING)


def test_wrong_answer_subtracts_five() -> None:
    result = apply_answer(WordProgress(score=40), correct=False, now=NOW, rules=RULES)

    assert result.score == 35


def test_score_never_goes_below_floor() -> None:
    result = apply_answer(WordProgress(score=5), correct=False, now=NOW, rules=RULES)

    assert result.score == 0


def test_new_word_needs_ten_correct_answers() -> None:
    progress = WordProgress()
    for _ in range(9):
        progress = apply_answer(progress, correct=True, now=NOW, rules=RULES)
    assert progress.status is WordStatus.LEARNING

    progress = apply_answer(progress, correct=True, now=NOW, rules=RULES)

    assert progress == WordProgress(
        score=100, status=WordStatus.LEARNED, learned_at=NOW, was_learned=True
    )


@pytest.mark.parametrize(("weeks_ago", "expected"), [(0, 100), (0.9, 100), (1, 95), (3, 85)])
def test_learned_score_decays_five_per_full_week(weeks_ago: float, expected: int) -> None:
    assert effective_score(learned(weeks_ago=weeks_ago), NOW, RULES) == expected


def test_a_learned_word_never_decays_below_fifty() -> None:
    assert effective_score(learned(weeks_ago=100), NOW, RULES) == 50


def test_decay_only_applies_to_learned_words() -> None:
    assert effective_score(WordProgress(score=60, status=WordStatus.LEARNING), NOW, RULES) == 60


def test_learned_word_returns_to_learning_after_a_week() -> None:
    assert current_status(learned(weeks_ago=0), NOW, RULES) is WordStatus.LEARNED
    assert current_status(learned(weeks_ago=1), NOW, RULES) is WordStatus.LEARNING


def test_correct_answer_on_decayed_word_relearns_it_and_restarts_decay() -> None:
    result = apply_answer(learned(weeks_ago=1), correct=True, now=NOW, rules=RULES)

    # 95 + 10 is capped at 100; the review was due, so the gap doubles to two weeks
    assert result == WordProgress(
        score=100, status=WordStatus.LEARNED, learned_at=NOW, was_learned=True, interval_weeks=2
    )


def test_wrong_answer_on_decayed_word_starts_from_decayed_score() -> None:
    result = apply_answer(learned(weeks_ago=2), correct=False, now=NOW, rules=RULES)

    # 90 after two weeks; a miss on a word learned before costs 10
    assert result == WordProgress(score=80, status=WordStatus.LEARNING, was_learned=True)


def test_known_words_cannot_be_answered() -> None:
    with pytest.raises(ValueError, match="known words"):
        apply_answer(WordProgress(status=WordStatus.KNOWN), correct=True, now=NOW, rules=RULES)


def test_mark_known_keeps_score() -> None:
    assert mark_known(WordProgress(score=35, status=WordStatus.LEARNING)) == WordProgress(
        score=35, status=WordStatus.KNOWN
    )


def test_rules_come_from_settings() -> None:
    gentle = ScoringSettings(correct_delta=10, wrong_delta=-5)

    assert apply_answer(WordProgress(score=40), correct=True, now=NOW, rules=gentle).score == 50
    assert apply_answer(WordProgress(score=40), correct=False, now=NOW, rules=gentle).score == 35


@pytest.mark.parametrize(
    ("total", "correct", "expected"),
    [(0, True, 5), (50, False, -5), (0, False, 0), (4, False, -4)],
)
def test_answer_points_always_move_the_total_but_never_below_zero(
    total: int, correct: bool, expected: int
) -> None:
    assert answer_points(total, correct=correct, counted=True, rules=RULES) == expected


def test_answers_that_do_not_count_give_no_points() -> None:
    assert answer_points(50, correct=False, counted=False, rules=RULES) == 0


def test_a_miss_costs_five() -> None:
    after = apply_answer(WordProgress(score=40), correct=False, now=NOW, rules=RULES)

    assert (after.score, after.was_learned) == (35, False)


def test_a_miss_on_a_word_learned_before_costs_ten_until_it_falls_to_fifty() -> None:
    learned = WordProgress(score=100, status=WordStatus.LEARNED, learned_at=NOW, was_learned=True)
    week_later = NOW + timedelta(days=7)  # decayed to 95: back to learning, asked again

    scores = []
    progress = learned
    for _ in range(7):
        progress = apply_answer(progress, correct=False, now=week_later, rules=RULES)
        scores.append((progress.score, progress.was_learned))

    assert scores == [
        (85, True),  # 95 - 10
        (75, True),
        (65, True),
        (55, True),
        (45, False),  # 55 - 10: at or below 50, so the word is treated as new again...
        (40, False),  # ...and misses are back to -5
        (35, False),
    ]


def test_learning_a_word_again_makes_its_misses_cost_ten_again() -> None:
    progress = WordProgress(score=95, status=WordStatus.LEARNING)  # never learned yet

    learned = apply_answer(progress, correct=True, now=NOW, rules=RULES)
    slipped = apply_answer(learned, correct=False, now=NOW, rules=RULES)

    assert (learned.status, learned.was_learned) == (WordStatus.LEARNED, True)
    assert (slipped.score, slipped.status, slipped.was_learned) == (
        90,  # 100 - 10: scores no longer go above 100
        WordStatus.LEARNING,
        True,
    )


def test_the_miss_penalty_follows_the_word() -> None:
    reviewed = WordProgress(score=80, status=WordStatus.LEARNING, was_learned=True)

    assert miss_penalty(WordProgress(score=80), NOW, RULES) == -5
    assert miss_penalty(reviewed, NOW, RULES) == -10
    assert miss_penalty(replace(reviewed, score=50), NOW, RULES) == -5
    assert answer_points(100, correct=False, counted=True, rules=RULES, miss=-10) == -10
    assert answer_points(100, correct=False, counted=True, rules=RULES, miss=-5) == -5


def _reviewed(progress: WordProgress, weeks_later: int, correct: bool = True) -> WordProgress:
    assert progress.learned_at is not None
    when = progress.learned_at + timedelta(weeks=weeks_later)
    return apply_answer(progress, correct=correct, now=when, rules=RULES)


def test_each_review_that_was_due_doubles_the_gap_up_to_sixteen_weeks() -> None:
    progress = apply_answer(WordProgress(score=90), correct=True, now=NOW, rules=RULES)
    gaps = [progress.interval_weeks]
    for _ in range(6):
        progress = _reviewed(progress, weeks_later=progress.interval_weeks)  # just due
        gaps.append(progress.interval_weeks)

    assert gaps == [1, 2, 4, 8, 16, 16, 16]
    assert progress.score == 100


def test_a_word_stays_at_100_until_its_review_is_due() -> None:
    word = WordProgress(
        score=100, status=WordStatus.LEARNED, learned_at=NOW, was_learned=True, interval_weeks=4
    )

    assert effective_score(word, NOW + timedelta(weeks=3, days=6), RULES) == 100
    assert effective_score(word, NOW + timedelta(weeks=4), RULES) == 95
    assert effective_score(word, NOW + timedelta(weeks=6), RULES) == 85


def test_an_early_review_keeps_the_gap() -> None:
    word = WordProgress(
        score=100, status=WordStatus.LEARNED, learned_at=NOW, was_learned=True, interval_weeks=4
    )

    assert _reviewed(word, weeks_later=1).interval_weeks == 4


def test_a_miss_halves_the_gap_instead_of_starting_over() -> None:
    word = WordProgress(
        score=100, status=WordStatus.LEARNED, learned_at=NOW, was_learned=True, interval_weeks=8
    )

    slipped = _reviewed(word, weeks_later=8, correct=False)  # due: 95, then -10
    relearned = apply_answer(slipped, correct=True, now=NOW, rules=RULES)

    assert (slipped.score, slipped.interval_weeks) == (85, 4)
    assert (relearned.status, relearned.interval_weeks) == (WordStatus.LEARNING, 4)
