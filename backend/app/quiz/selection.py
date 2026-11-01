"""Choosing what to ask next, and the daily streak, for the never-ending quiz."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from random import Random

from app.core.enums import QuestionType


class Pool(StrEnum):
    NEW = "new"  # next words from the learning list
    LEARNING = "learning"  # started, not learned yet
    REVIEW = "review"  # learned, but weekly decay took the score back under the threshold


def choose_pool(available: Sequence[Pool], weights: Mapping[Pool, int], rng: Random) -> Pool | None:
    """A random pool among those with words, in proportion to its weight (6:3:1 by default).

    If every available pool has weight 0, the first one is used, so the quiz never stalls.
    """
    if not available:
        return None
    weighted = [pool for pool in available if weights.get(pool, 0) > 0]
    if not weighted:
        return available[0]
    return rng.choices(weighted, weights=[weights[pool] for pool in weighted])[0]


@dataclass(frozen=True)
class DailyGoal:
    """Answers a day that keep the streak going.

    Days before `since` (the day the user last changed it) are judged by the goal they had then,
    so raising the goal never breaks a streak already earned.
    """

    goal: int
    earlier: int | None = None
    since: date | None = None

    def on(self, day: date) -> int:
        if self.earlier is not None and self.since is not None and day < self.since:
            return self.earlier
        return self.goal


def streak(answers_per_day: Mapping[date, int], today: date, goal: DailyGoal) -> int:
    """Days in a row that reached the daily goal, ending today.

    Today only counts once its goal is met; until then the streak still includes yesterday,
    so it doesn't look broken first thing in the morning.
    """

    def met(day: date) -> bool:
        return answers_per_day.get(day, 0) >= goal.on(day)

    day = today if met(today) else today - timedelta(days=1)
    days = 0
    while met(day):
        days += 1
        day -= timedelta(days=1)
    return days


def choose_question_type(
    score: int, can_fill: bool, rng: Random, *, reverse_from: int, fill_from: int
) -> QuestionType:
    """Harder formats as a word gets learned: meaning only at first, then also reverse, then
    also fill-in-the-blank (only when the book's sentence for the word is known)."""
    kinds = [QuestionType.DEFINITION_MCQ]
    if score >= reverse_from:
        kinds.append(QuestionType.REVERSE)
    if score >= fill_from and can_fill:
        kinds.append(QuestionType.FILL_IN_BLANK)
    return rng.choice(kinds)
