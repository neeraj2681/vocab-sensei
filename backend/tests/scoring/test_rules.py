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


def test_correct_answer_adds_five() -> None:
    result = apply_answer(WordProgress(score=40), correct=True, now=NOW, rules=RULES)

    assert result == WordProgress(score=45, status=WordStatus.LEARNING)


def test_wrong_answer_subtracts_ten() -> None:
    result = apply_answer(WordProgress(score=40), correct=False, now=NOW, rules=RULES)

    assert result.score == 30


def test_score_never_goes_below_floor() -> None:
    result = apply_answer(WordProgress(score=5), correct=False, now=NOW, rules=RULES)

    assert result.score == 0


def test_new_word_needs_twenty_correct_answers() -> None:
    progress = WordProgress()
    for _ in range(19):
        progress = apply_answer(progress, correct=True, now=NOW, rules=RULES)
    assert progress.status is WordStatus.LEARNING

    progress = apply_answer(progress, correct=True, now=NOW, rules=RULES)

    assert progress == WordProgress(score=100, status=WordStatus.LEARNED, learned_at=NOW)


@pytest.mark.parametrize(("weeks_ago", "expected"), [(0, 100), (0.9, 100), (1, 95), (3, 85)])
def test_learned_score_decays_five_per_full_week(weeks_ago: float, expected: int) -> None:
    assert effective_score(learned(weeks_ago=weeks_ago), NOW, RULES) == expected


def test_decay_stops_at_floor() -> None:
    assert effective_score(learned(weeks_ago=100), NOW, RULES) == 0


def test_decay_only_applies_to_learned_words() -> None:
    assert effective_score(WordProgress(score=60, status=WordStatus.LEARNING), NOW, RULES) == 60


def test_learned_word_returns_to_learning_after_a_week() -> None:
    assert current_status(learned(weeks_ago=0), NOW, RULES) is WordStatus.LEARNED
    assert current_status(learned(weeks_ago=1), NOW, RULES) is WordStatus.LEARNING


def test_correct_answer_on_decayed_word_relearns_it_and_restarts_decay() -> None:
    result = apply_answer(learned(weeks_ago=1), correct=True, now=NOW, rules=RULES)

    assert result == WordProgress(score=100, status=WordStatus.LEARNED, learned_at=NOW)


def test_wrong_answer_on_decayed_word_starts_from_decayed_score() -> None:
    result = apply_answer(learned(weeks_ago=2), correct=False, now=NOW, rules=RULES)

    assert result == WordProgress(score=80, status=WordStatus.LEARNING)


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
    [(0, True, 5), (50, False, -10), (0, False, 0), (4, False, -4)],
)
def test_answer_points_always_move_the_total_but_never_below_zero(
    total: int, correct: bool, expected: int
) -> None:
    assert answer_points(total, correct=correct, counted=True, rules=RULES) == expected


def test_answers_that_do_not_count_give_no_points() -> None:
    assert answer_points(50, correct=False, counted=False, rules=RULES) == 0
