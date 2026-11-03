from datetime import date, timedelta

from app.quiz.quests import Activity, Book, QuestKind, Tier, daily_quests

DAY = date(2026, 11, 3)


def test_three_quests_one_per_tier_never_the_same_kind() -> None:
    for offset in range(60):  # many days, many draws
        quests = daily_quests(7, DAY + timedelta(days=offset), goal=20, books=[Book(1, "Dracula")])

        assert [q.tier for q in quests] == [Tier.EASY, Tier.MEDIUM, Tier.HARD]
        assert len({q.kind for q in quests}) == 3
        assert [q.reward for q in quests] == [10, 15, 20]


def test_the_same_quests_all_day_and_different_ones_each_day() -> None:
    first = daily_quests(7, DAY, goal=20, books=[])

    assert daily_quests(7, DAY, goal=20, books=[]) == first
    days = {
        tuple(q.key for q in daily_quests(7, DAY + timedelta(days=n), 20, [])) for n in range(14)
    }
    assert len(days) > 1


def test_sizes_follow_the_daily_goal() -> None:
    def answer_targets(goal: int) -> set[int]:
        return {
            q.target
            for n in range(80)
            for q in daily_quests(3, DAY + timedelta(days=n), goal=goal, books=[])
            if q.kind is QuestKind.ANSWER
        }

    assert answer_targets(10) == {5, 10}  # half the goal (easy), the goal (medium)
    assert answer_targets(50) == {25, 50}


def test_book_quests_only_come_with_a_current_read() -> None:
    kinds = {
        q.kind for n in range(80) for q in daily_quests(5, DAY + timedelta(days=n), 20, books=[])
    }
    with_book = [
        q
        for n in range(80)
        for q in daily_quests(5, DAY + timedelta(days=n), 20, books=[Book(9, "Dracula")])
        if q.kind is QuestKind.BOOK
    ]

    assert QuestKind.BOOK not in kinds
    assert with_book
    assert with_book[0].title == "Answer 10 from Dracula"
    assert with_book[0].progress(Activity(by_book={9: 4, 2: 30})) == 4


def test_progress_is_capped_at_the_target() -> None:
    quest = next(
        q
        for n in range(80)
        for q in daily_quests(1, DAY + timedelta(days=n), 20, [])
        if q.kind is QuestKind.IN_A_ROW and q.tier is Tier.EASY
    )

    assert quest.title == "3 right in a row"
    assert quest.progress(Activity(best_run=2)) == 2
    assert quest.progress(Activity(best_run=9)) == 3
