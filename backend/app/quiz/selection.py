"""Choosing what to ask next, and the daily streak, for the never-ending quiz."""

from collections.abc import Callable, Collection, Mapping, Sequence
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

    Every past day is judged by the goal the user had that day, so changing the goal (however
    often) never breaks a streak already earned.
    """

    goal: int  # today's
    steps: tuple[tuple[date, int], ...] = ()  # (first day, goal) for each change, oldest first

    def on(self, day: date) -> int:
        if not self.steps:
            return self.goal
        current = self.steps[0][1]  # days before the first change had the first goal
        for start, goal in self.steps:
            if start > day:
                break
            current = goal
        return current


def streak(
    answers_per_day: Mapping[date, int],
    today: date,
    goal: DailyGoal,
    frozen: Collection[date] = (),
) -> int:
    """Days in a row that reached the daily goal (or were covered by a streak freeze), ending
    today.

    Today only counts once its goal is met; until then the streak still includes yesterday,
    so it doesn't look broken first thing in the morning.
    """

    def met(day: date) -> bool:
        return answers_per_day.get(day, 0) >= goal.on(day) or day in frozen

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


def learning_cap(daily_goal: int, smallest: int, largest: int) -> int:
    """Words in progress at once: about one per daily answer, so each comes up about once a day."""
    return max(smallest, min(largest, daily_goal))


def spacing_rules(
    recent: Sequence[tuple[int, bool]], spacing: int, retry_after: int
) -> tuple[set[int], list[int]]:
    """From the last answers (newest first, as (word, right); twice `spacing` of them): the words
    too soon to ask again, and the ones answered wrong that should come back now, oldest first.

    A word waits `spacing` answers before it's asked again. A miss is the exception: the word comes
    back once after `retry_after` other answers, while it's still fresh. Only a miss of a word not
    asked in the `spacing` answers before it gets that retry, so a miss on the retry itself waits
    like any other answer (a run of wrong answers can't keep cycling the same few words).
    """
    too_soon: set[int] = set()
    retry: list[int] = []
    for position, (word_id, right) in enumerate(recent[:spacing]):
        if word_id in too_soon or word_id in retry:
            continue
        before = {earlier for earlier, _ in recent[position + 1 : position + 1 + spacing]}
        if right or position < retry_after or word_id in before:
            too_soon.add(word_id)
        else:
            retry.append(word_id)
    return too_soon, retry[::-1]


def closest_or_oldest[T](words: Sequence[T], score: Callable[[T], int], rng: Random) -> T:
    """Which word in progress to ask: half the time the one closest to learned, so nearly done
    words finish; otherwise the one waiting longest (`words` is in that order), so none is
    forgotten."""
    if rng.random() < 0.5:
        return max(words, key=score)  # ties: the one waiting longest
    return words[0]
