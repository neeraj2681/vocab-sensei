"""Learning-score rules (docs/PROJECT_PLAN.md §5.4).

Decay is lazy: the stored score is the score at `learned_at`, and the weekly decay is applied
whenever the score is read. Nothing has to run on a schedule, so the result is correct even if the
app was off for weeks.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from app.core.config import ScoringSettings
from app.core.enums import WordStatus


class Triage(StrEnum):
    """What the user picked for a word on the post-upload triage screen."""

    NEW = "new"
    UNSURE = "unsure"
    KNOWN = "known"


@dataclass(frozen=True)
class WordProgress:
    score: int = 0
    status: WordStatus = WordStatus.NEW
    learned_at: datetime | None = None  # last time the score reached the threshold
    # Reached the threshold at some point and hasn't dropped to `review_strict_above` since:
    # misses on it cost `review_wrong_delta` (a slip on a word already learned).
    was_learned: bool = False
    # Weeks between reviews of a learned word: it stays at 100 until then, then loses
    # `weekly_decay` a week (never below `review_strict_above`) until it is answered again.
    interval_weeks: int = 1


def initial_progress(triage: Triage, rules: ScoringSettings) -> WordProgress:
    match triage:
        case Triage.NEW:
            return WordProgress()
        case Triage.UNSURE:
            return WordProgress(score=rules.unsure_start, status=WordStatus.LEARNING)
        case Triage.KNOWN:
            return WordProgress(status=WordStatus.KNOWN)


def effective_score(progress: WordProgress, now: datetime, rules: ScoringSettings) -> int:
    """The score right now. A learned word keeps its score until its review is due
    (`interval_weeks` after `learned_at`); from then on it loses `weekly_decay` a week, starting
    with the due week itself, but never drops below `review_strict_above`."""
    if progress.status is not WordStatus.LEARNED or progress.learned_at is None:
        return progress.score
    weeks = (now - progress.learned_at).days // 7
    if weeks < progress.interval_weeks:
        return progress.score
    overdue = weeks - progress.interval_weeks + 1
    return max(rules.review_strict_above, progress.score - rules.weekly_decay * overdue)


def current_status(progress: WordProgress, now: datetime, rules: ScoringSettings) -> WordStatus:
    """A learned word whose decayed score dropped below the threshold is back to learning."""
    if (
        progress.status is WordStatus.LEARNED
        and effective_score(progress, now, rules) < rules.learned_threshold
    ):
        return WordStatus.LEARNING
    return progress.status


def miss_penalty(progress: WordProgress, now: datetime, rules: ScoringSettings) -> int:
    """What a wrong answer costs: `wrong_delta` (-5), or `review_wrong_delta` (-10) for a word
    learned before while its score is still above `review_strict_above` (50)."""
    learned_before = progress.was_learned or progress.status is WordStatus.LEARNED
    if learned_before and effective_score(progress, now, rules) > rules.review_strict_above:
        return rules.review_wrong_delta
    return rules.wrong_delta


def apply_answer(
    progress: WordProgress, *, correct: bool, now: datetime, rules: ScoringSettings
) -> WordProgress:
    if progress.status is WordStatus.KNOWN:
        raise ValueError("known words are not quizzed")

    before = effective_score(progress, now, rules)
    delta = rules.word_correct_delta if correct else miss_penalty(progress, now, rules)
    score = min(rules.learned_threshold, max(rules.floor, before + delta))
    reviewed = progress.status is WordStatus.LEARNED  # a learned word came back (due or not)
    interval = progress.interval_weeks
    if reviewed and correct and before < rules.learned_threshold:  # a review that was due
        interval = min(rules.max_interval_weeks, interval * 2)
    elif reviewed and not correct:
        interval = max(1, interval // 2)

    if score >= rules.learned_threshold:
        # Reaching (or staying at) the threshold restarts the review clock.
        return WordProgress(
            score=score,
            status=WordStatus.LEARNED,
            learned_at=now,
            was_learned=True,
            interval_weeks=interval,
        )
    learned_before = progress.was_learned or progress.status is WordStatus.LEARNED
    return WordProgress(
        score=score,
        status=WordStatus.LEARNING,
        learned_at=None,
        was_learned=learned_before and score > rules.review_strict_above,
        interval_weeks=interval if learned_before else 1,
    )


def mark_known(progress: WordProgress) -> WordProgress:
    """The "I know this" button."""
    return replace(progress, status=WordStatus.KNOWN)


def answer_points(
    total_before: int,
    *,
    correct: bool,
    counted: bool,
    rules: ScoringSettings,
    miss: int | None = None,
) -> int:
    """How an answer changes the lifetime score shown at the top of the quiz.

    Unlike a word's score, this always moves: +5 for a right answer, and for a wrong one the
    word's miss penalty (`miss`: -5, or -10 on a word learned before; see `miss_penalty`), even
    on a word that is already at 0. Only the total itself never drops below 0. Answers that
    don't count (a word asked again too soon) change nothing.
    """
    if not counted:
        return 0
    delta = rules.correct_delta if correct else (rules.wrong_delta if miss is None else miss)
    return max(delta, rules.floor - total_before)


def combo_multiplier(run: int, rules: ScoringSettings) -> int:
    """Ninja Mode: once `run` right answers in a row reach `combo_after`, the next right answers
    earn `combo_multiplier` times the coins."""
    return rules.combo_multiplier if run >= rules.combo_after else 1
