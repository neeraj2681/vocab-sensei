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


def streak_of(days: int) -> dict[date, int]:
    """Goal met on each of the first `days` days (day 0 onwards)."""
    return {day(i): 10 for i in range(days)}


def test_a_freeze_covers_a_missed_day_and_keeps_the_streak() -> None:
    answers = streak_of(3)  # days 0-2 met, day 3 missed

    used = freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(3), day(3))

    assert used == [(day(3), 1)]


def test_days_whose_goal_was_met_use_nothing() -> None:
    answers = {day(0): 10, day(1): 12, day(2): 10}

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(1), day(2)) == []


def test_no_streak_to_protect_no_freeze_used() -> None:
    answers = {day(0): 3}  # the goal wasn't met before the missed day either

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(1), day(1)) == []


def test_a_freeze_bought_after_the_missed_day_cant_cover_it() -> None:
    answers = streak_of(3)  # days 0-2 met, day 3 missed

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(4))], day(3), day(3)) == []


def test_a_streak_under_the_minimum_is_not_saved() -> None:
    answers = streak_of(2)  # a 2-day streak, day 2 missed

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(2), day(2)) == []


def test_a_five_day_streak_is_saved_by_one_freeze() -> None:
    answers = streak_of(5)  # days 0-4 met, day 5 missed

    used = freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(5), day(5))

    assert used == [(day(5), 1)]


def test_a_gap_longer_than_the_freezes_left_is_not_covered() -> None:
    answers = streak_of(10)  # a 10-day streak, days 10-12 missed

    assert freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(10), day(12)) == []


def test_a_gap_is_covered_one_freeze_per_day_when_there_are_enough() -> None:
    answers = streak_of(10)

    used = freezes_to_use(
        answers,
        GOAL,
        set(),
        [Freeze(1, day(0)), Freeze(2, day(0)), Freeze(3, day(0))],
        day(10),
        day(12),
    )

    assert used == [(day(10), 1), (day(11), 2), (day(12), 3)]


def test_a_gap_is_covered_only_by_freezes_bought_by_each_day() -> None:
    answers = streak_of(
        10
    )  # day 10 needs a freeze bought by day 10; day 11 can use one bought on it

    used = freezes_to_use(
        answers, GOAL, set(), [Freeze(1, day(0)), Freeze(2, day(11))], day(10), day(11)
    )

    assert used == [(day(10), 1), (day(11), 2)]


def test_two_separate_gaps_with_one_freeze_covers_only_the_first() -> None:
    answers = {day(i): 10 for i in range(5)} | {day(6): 10}  # day 5 and day 7 missed

    used = freezes_to_use(answers, GOAL, set(), [Freeze(1, day(0))], day(5), day(7))

    assert used == [(day(5), 1)]  # day 7 breaks the streak: nothing left to save
