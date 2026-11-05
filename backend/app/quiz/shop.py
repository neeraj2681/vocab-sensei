"""The Shop: open on Sundays, selling streak freezes and double coins. Pure rules, no database.

- A streak freeze covers one missed day, used automatically, but only when there is a streak to
  protect and only by a freeze bought before that day ended. Days whose goal was met use nothing.
- Double coins, once used, double the coins of right answers for half an hour (with Ninja Mode:
  four times).
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from app.quiz.selection import DailyGoal, streak


class Item(StrEnum):
    STREAK_FREEZE = "streak_freeze"
    DOUBLE_COINS = "double_coins"


PRICES = {Item.STREAK_FREEZE: 10_000, Item.DOUBLE_COINS: 50_000}
MAX_OWNED = {Item.STREAK_FREEZE: 3, Item.DOUBLE_COINS: 1}  # in the inventory at once
DOUBLE_COINS_FOR = timedelta(minutes=30)
DOUBLE_COINS_MULTIPLIER = 2
OPEN_WEEKDAY = 6  # Sunday (Monday is 0)


@dataclass(frozen=True)
class Window:
    open: bool
    opens_at: datetime  # the start of this Sunday if open, else the next Sunday
    closes_at: datetime  # the end of that Sunday


def shop_window(now: datetime) -> Window:
    """When the Shop is open, in `now`'s time zone: all of Sunday."""
    today = now.date()
    days_ahead = (OPEN_WEEKDAY - today.weekday()) % 7
    sunday = today + timedelta(days=days_ahead)
    opens = datetime.combine(sunday, time.min, now.tzinfo)
    return Window(days_ahead == 0, opens, opens + timedelta(days=1))


@dataclass(frozen=True)
class Freeze:
    id: int
    bought_on: date  # in the user's time zone


def freezes_to_use(
    answers_per_day: Mapping[date, int],
    goal: DailyGoal,
    frozen: Collection[date],
    unused: Sequence[Freeze],
    first: date,
    last: date,
) -> list[tuple[date, int]]:
    """Which freezes cover which missed days from `first` to `last` (oldest first), as (day,
    freeze id). A day is covered only if the streak up to it was alive and a freeze bought on or
    before that day is left."""
    covered = set(frozen)
    left = sorted(unused, key=lambda f: (f.bought_on, f.id))
    used: list[tuple[date, int]] = []
    day = first
    while day <= last:
        met = answers_per_day.get(day, 0) >= goal.on(day)
        if not met and day not in covered:
            alive = streak(answers_per_day, day - timedelta(days=1), goal, covered) > 0
            freeze = next((f for f in left if f.bought_on <= day), None)
            if alive and freeze:
                left.remove(freeze)
                covered.add(day)
                used.append((day, freeze.id))
        day += timedelta(days=1)
    return used
