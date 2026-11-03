"""Daily quests: three small goals a day (one easy, one medium, one hard) that pay coins.

The day's quests depend only on the user, the day and their daily goal, so they are the same on
every device and need nothing stored; only claiming a reward is saved. Progress is worked out from
the day's activity.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from random import Random


class QuestKind(StrEnum):
    ANSWER = "answer"  # answer N questions
    RIGHT = "right"  # get N right
    IN_A_ROW = "in_a_row"  # N right in a row
    NINJA = "ninja"  # reach Ninja Mode
    LEARN = "learn"  # learn N words (reach 100%)
    BOOK = "book"  # answer N questions from one of your current books
    EARLY = "early"  # reach the daily goal before noon


class Tier(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


REWARDS = {Tier.EASY: 10, Tier.MEDIUM: 15, Tier.HARD: 20}
CHEST_REWARD = 25  # for claiming all three
CHEST = "chest"  # the chest's key when claiming


@dataclass(frozen=True)
class Book:
    id: int
    title: str


@dataclass(frozen=True)
class Activity:
    """What the user did today (in their time zone)."""

    answers: int = 0
    right: int = 0
    best_run: int = 0  # most right answers in a row today
    learned: int = 0  # words that reached "learned" today
    by_book: dict[int, int] = field(default_factory=dict)  # answers per book id
    goal_before_noon: bool = False


@dataclass(frozen=True)
class Quest:
    key: str  # stable for the day, e.g. "answer-20"
    kind: QuestKind
    tier: Tier
    target: int
    title: str
    book_id: int | None = None

    @property
    def reward(self) -> int:
        return REWARDS[self.tier]

    def progress(self, activity: Activity) -> int:
        """How far along it is, capped at the target."""
        done = {
            QuestKind.ANSWER: activity.answers,
            QuestKind.RIGHT: activity.right,
            QuestKind.IN_A_ROW: activity.best_run,
            QuestKind.NINJA: activity.best_run,
            QuestKind.LEARN: activity.learned,
            QuestKind.BOOK: activity.by_book.get(self.book_id or 0, 0),
            QuestKind.EARLY: int(activity.goal_before_noon),
        }[self.kind]
        return min(done, self.target)


def _round5(value: float, low: int) -> int:
    return max(low, round(value / 5) * 5)


def daily_quests(
    user_id: int, day: date, goal: int, books: Sequence[Book], combo_after: int = 5
) -> list[Quest]:
    """Today's three quests, one per tier, never two of the same kind; sizes follow the goal."""
    rng = Random(f"{user_id}:{day.isoformat()}")  # the same three all day, on every device
    book = rng.choice(list(books)) if books else None
    easy = [
        Quest("", QuestKind.ANSWER, Tier.EASY, _round5(goal / 2, 5), ""),
        Quest("", QuestKind.RIGHT, Tier.EASY, _round5(goal / 3, 5), ""),
        Quest("", QuestKind.IN_A_ROW, Tier.EASY, 3, ""),
    ]
    medium = [
        Quest("", QuestKind.ANSWER, Tier.MEDIUM, _round5(goal, 10), ""),
        Quest("", QuestKind.RIGHT, Tier.MEDIUM, _round5(goal * 0.6, 5), ""),
        Quest("", QuestKind.NINJA, Tier.MEDIUM, combo_after, ""),
        Quest("", QuestKind.LEARN, Tier.MEDIUM, 1, ""),
    ]
    hard = [
        Quest("", QuestKind.IN_A_ROW, Tier.HARD, combo_after + 3, ""),
        Quest("", QuestKind.RIGHT, Tier.HARD, _round5(goal * 1.2, 10), ""),
        Quest("", QuestKind.EARLY, Tier.HARD, 1, ""),
        Quest("", QuestKind.LEARN, Tier.HARD, 3, ""),
    ]
    if book:
        hard.append(Quest("", QuestKind.BOOK, Tier.HARD, _round5(goal / 2, 5), "", book.id))
    chosen: list[Quest] = []
    for tier in (easy, medium, hard):
        options = [q for q in tier if q.kind not in {c.kind for c in chosen}]
        chosen.append(rng.choice(options))
    return [_named(q, book) for q in chosen]


def _named(quest: Quest, book: Book | None) -> Quest:
    titles = {
        QuestKind.ANSWER: f"Answer {quest.target} questions",
        QuestKind.RIGHT: f"Get {quest.target} right",
        QuestKind.IN_A_ROW: f"{quest.target} right in a row",
        QuestKind.NINJA: "Reach Ninja Mode",
        QuestKind.LEARN: (
            "Learn a new word" if quest.target == 1 else f"Learn {quest.target} new words"
        ),
        QuestKind.BOOK: f"Answer {quest.target} from {book.title if book else 'your book'}",
        QuestKind.EARLY: "Meet your goal before noon",
    }
    return Quest(
        key=f"{quest.kind.value}-{quest.target}",
        kind=quest.kind,
        tier=quest.tier,
        target=quest.target,
        title=titles[quest.kind],
        book_id=quest.book_id,
    )
