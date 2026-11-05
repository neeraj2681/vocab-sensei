from datetime import UTC, date, datetime, timedelta

from app.quiz.selection import DailyGoal
from app.quiz.shop import Freeze, freezes_to_use, shop_window

SUNDAY = date(2026, 11, 8)
GOAL = DailyGoal(10)


def day(n: int) -> date:
    return SUNDAY + timedelta(days=n)


def test_the_shop_is_open_all_of_sunday() -> None:
    sunday = shop_window(datetime(2026, 11, 8, 23, 59, tzinfo=UTC))
    friday = shop_window(datetime(2026, 11, 6, 9, 0, tzinfo=UTC))

    assert sunday.open
    assert (sunday.opens_at.date(), sunday.closes_at.date()) == (SUNDAY, day(1))
    assert not friday.open
    assert friday.opens_at == datetime(2026, 11, 8, tzinfo=UTC)  # this coming Sunday


def test_a_freeze_covers_a_missed_day_and_keeps_the_streak() -> None:
    answers = {day(0): 10, day(1): 12}  # day 2 missed

    used = freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(2), day(2))

    assert used == [(day(2), 1)]


def test_days_whose_goal_was_met_use_nothing() -> None:
    answers = {day(0): 10, day(1): 12, day(2): 10}

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(1), day(2)) == []


def test_no_streak_to_protect_no_freeze_used() -> None:
    answers = {day(0): 3}  # the goal wasn't met before the missed day either

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(1), day(1)) == []


def test_a_freeze_bought_after_the_missed_day_cant_cover_it() -> None:
    answers = {day(0): 10}

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(2))], day(1), day(1)) == []


def test_several_missed_days_use_one_freeze_each_until_they_run_out() -> None:
    answers = {day(0): 10}  # days 1, 2 and 3 missed, two freezes

    used = freezes_to_use(
        answers, GOAL, set(), [Freeze(1, day(0)), Freeze(2, day(0))], day(1), day(3)
    )

    assert used == [(day(1), 1), (day(2), 2)]  # day 3 breaks the streak
