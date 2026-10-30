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


def initial_progress(triage: Triage, rules: ScoringSettings) -> WordProgress:
    match triage:
        case Triage.NEW:
            return WordProgress()
        case Triage.UNSURE:
            return WordProgress(score=rules.unsure_start, status=WordStatus.LEARNING)
        case Triage.KNOWN:
            return WordProgress(status=WordStatus.KNOWN)


def effective_score(progress: WordProgress, now: datetime, rules: ScoringSettings) -> int:
    """The score right now, including weekly decay for learned words."""
    if progress.status is not WordStatus.LEARNED or progress.learned_at is None:
        return progress.score
    weeks = max(0, (now - progress.learned_at).days // 7)
    return max(rules.floor, progress.score - rules.weekly_decay * weeks)


def current_status(progress: WordProgress, now: datetime, rules: ScoringSettings) -> WordStatus:
    """A learned word whose decayed score dropped below the threshold is back to learning."""
    if (
        progress.status is WordStatus.LEARNED
        and effective_score(progress, now, rules) < rules.learned_threshold
    ):
        return WordStatus.LEARNING
    return progress.status


def apply_answer(
    progress: WordProgress, *, correct: bool, now: datetime, rules: ScoringSettings
) -> WordProgress:
    if progress.status is WordStatus.KNOWN:
        raise ValueError("known words are not quizzed")

    delta = rules.correct_delta if correct else rules.wrong_delta
    score = max(rules.floor, effective_score(progress, now, rules) + delta)

    if score >= rules.learned_threshold:
        # Reaching (or staying at) the threshold restarts the decay clock.
        return WordProgress(score=score, status=WordStatus.LEARNED, learned_at=now)
    return WordProgress(score=score, status=WordStatus.LEARNING, learned_at=None)


def mark_known(progress: WordProgress) -> WordProgress:
    """The "I know this" button."""
    return replace(progress, status=WordStatus.KNOWN)


def answer_points(
    total_before: int, *, correct: bool, counted: bool, rules: ScoringSettings
) -> int:
    """How an answer changes the lifetime score shown at the top of the quiz.

    Unlike a word's score, this always moves: +5 for a right answer, -10 for a wrong one, even
    on a word that is already at 0. Only the total itself never drops below 0. Answers that
    don't count (a word asked again too soon) change nothing.
    """
    if not counted:
        return 0
    delta = rules.correct_delta if correct else rules.wrong_delta
    return max(delta, rules.floor - total_before)
