"""Choosing what to ask next, and the daily streak, for the never-ending quiz."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from enum import StrEnum
from random import Random


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


def streak(answers_per_day: Mapping[date, int], today: date, goal: int) -> int:
    """Days in a row that reached the daily goal, ending today.

    Today only counts once its goal is met; until then the streak still includes yesterday,
    so it doesn't look broken first thing in the morning.
    """
    day = today if answers_per_day.get(today, 0) >= goal else today - timedelta(days=1)
    days = 0
    while answers_per_day.get(day, 0) >= goal:
        days += 1
        day -= timedelta(days=1)
    return days
