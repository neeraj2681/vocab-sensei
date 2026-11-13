"""The Shop: open on Sundays, selling streak freezes, double coins and name changes. Pure rules.

- A streak freeze covers one missed day, used automatically, but only to save a streak of at least
  MIN_STREAK_TO_FREEZE days, and only by a freeze bought before that day ended: a run of missed
  days is covered whole or not at all. Days whose goal was met use nothing.
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
    NAME_CHANGE = "name_change"  # one more username change, after the free one


# A freeze is about 3-4 days of keen play (~400 coins a day); double coins are a leaderboard boost
# (30 good minutes earn a few hundred back); a name change is rare and deliberate.
PRICES = {Item.STREAK_FREEZE: 1_500, Item.DOUBLE_COINS: 1_000, Item.NAME_CHANGE: 5_000}
MAX_OWNED = {Item.STREAK_FREEZE: 3, Item.DOUBLE_COINS: 1, Item.NAME_CHANGE: 1}  # held at once
DOUBLE_COINS_FOR = timedelta(minutes=30)
DOUBLE_COINS_MULTIPLIER = 2
OPEN_WEEKDAY = 6  # Sunday (Monday is 0)
MIN_STREAK_TO_FREEZE = 3  # a freeze only saves a streak of at least this many days


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
    freeze id). Missed days come in runs of consecutive days. A run is covered only if the streak
    just before it is at least MIN_STREAK_TO_FREEZE days, every day of it can get its own freeze
    bought on or before that day, and the run is not longer than the freezes left. A run that is
    not covered breaks the streak, so later runs are not covered either."""

    def met(day: date) -> bool:
        return answers_per_day.get(day, 0) >= goal.on(day)

    def missed(day: date) -> bool:
        return not met(day) and day not in covered

    covered = set(frozen)
    left = sorted(unused, key=lambda f: (f.bought_on, f.id))
    used: list[tuple[date, int]] = []
    day = first
    while day <= last:
        if not missed(day):
            day += timedelta(days=1)
            continue
        run: list[date] = []
        while day <= last and missed(day):
            run.append(day)
            day += timedelta(days=1)
        before = run[0] - timedelta(days=1)
        # the streak just before the run: 0 if the day right before it was itself missed
        alive = met(before) or before in covered
        length = streak(answers_per_day, before, goal, covered) if alive else 0
        if length < MIN_STREAK_TO_FREEZE:
            break
        pool = list(left)
        plan: list[tuple[date, Freeze]] = []
        for missed_day in run:
            freeze = next((f for f in pool if f.bought_on <= missed_day), None)
            if freeze is None:
                break
            pool.remove(freeze)
            plan.append((missed_day, freeze))
        if len(plan) < len(run):
            break
        for missed_day, freeze in plan:
            left.remove(freeze)
            covered.add(missed_day)
            used.append((missed_day, freeze.id))
    return used
