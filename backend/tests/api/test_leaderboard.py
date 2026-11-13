from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import QuestionType, WordStatus
from app.db.models import (
    CurrentReading,
    Document,
    GoalChange,
    QuestClaim,
    Question,
    QuizAnswer,
    User,
    UserWord,
    Word,
)
from tests.api.test_quiz import NOW, answer, book, clock, reader  # noqa: F401 (fixtures)
from tests.conftest import make_user

pytestmark = pytest.mark.usefixtures("book", "clock")


def friend(session: Session, email: str, name: str, coins: int, **extra: Any) -> User:
    """Another user on the board, with `coins` earned today (from a quest, so no questions are
    needed)."""
    user = make_user(session, email)
    user.display_name, user.show_on_leaderboard = name, True
    for key, value in extra.items():
        setattr(user, key, value)
    session.add(QuestClaim(user_id=user.id, day=NOW.date(), quest="answer-10", coins=coins))
    session.commit()
    return user


def board(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/leaderboard?tz=UTC")
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


MONDAY = NOW - timedelta(days=4)  # NOW is Friday 30 Oct 2026


def answer_on(
    session: Session, user: User, day: int, count: int, *, chosen: int | None = 0
) -> None:
    """`count` real answers by `user` on the `day`th day of the week (0 = Monday)."""
    word = session.scalars(select(Word)).first()
    assert word is not None
    for _ in range(count):
        question = Question(
            user_id=user.id,
            word_id=word.id,
            type=QuestionType.DEFINITION_MCQ,
            prompt="?",
            options=["a", "b"],
            correct_index=0,
            generator="test",
        )
        session.add(question)
        session.flush()
        session.add(
            QuizAnswer(
                user_id=user.id,
                word_id=word.id,
                question_id=question.id,
                chosen_index=chosen,
                correct=True,
                score_delta=10,
                points=50,  # lots of coins: they must not matter
                answered_at=MONDAY + timedelta(days=day),
            )
        )
    session.commit()


def learn(session: Session, user: User, lemma: str, when: Any) -> None:
    word = session.scalars(select(Word).where(Word.lemma == lemma)).one()
    session.add(
        UserWord(
            user_id=user.id,
            word_id=word.id,
            score=100,
            status=WordStatus.LEARNED,
            learned_at=when,
            first_learned_at=when,
        )
    )
    session.commit()


def test_ranks_by_days_with_the_goal_met_then_new_words_then_name(
    user_client: TestClient, session: Session
) -> None:
    steady = friend(session, "asha@example.com", "Asha", 0, daily_goal=2)
    bursty = friend(session, "bo@example.com", "Bo", 40, daily_goal=2)
    tied = friend(session, "cy@example.com", "Cy", 0, daily_goal=2)
    twin = friend(session, "di@example.com", "Di", 0, daily_goal=2)
    for day in range(4):  # met the goal on four days
        answer_on(session, steady, day, 2)
    for day in range(2):  # twice, with far more coins
        answer_on(session, bursty, day, 20)
        answer_on(session, tied, day, 2)
        answer_on(session, twin, day, 2)
    answer_on(session, tied, 2, 1)  # one answer short of the goal: no day
    answer_on(session, tied, 3, 5, chosen=None)  # "I know this" never counts
    learn(session, tied, "word01", MONDAY)
    learn(session, tied, "word02", MONDAY + timedelta(days=1))
    learn(session, twin, "word03", MONDAY - timedelta(days=1))  # last week: not this week's
    for _ in range(3):
        answer(user_client, session)  # today, short of the goal of 10

    rows = board(user_client)

    assert [(r["display_name"], r["goal_days"], r["new_words"], r["me"]) for r in rows] == [
        ("Asha", 4, 0, False),
        ("Cy", 2, 2, False),
        ("Bo", 2, 0, False),
        ("Di", 2, 0, False),
        ("Reader", 0, 0, True),
    ]
    assert "coins_today" not in rows[0]
    assert "email" not in rows[0]


def test_each_day_is_judged_by_the_goal_it_had(user_client: TestClient, session: Session) -> None:
    other = friend(session, "asha@example.com", "Asha", 0, daily_goal=5)
    session.add(GoalChange(user_id=other.id, goal=2, since=MONDAY - timedelta(days=30)))
    session.add(GoalChange(user_id=other.id, goal=5, since=MONDAY + timedelta(days=2)))
    session.commit()
    for day in range(4):
        answer_on(session, other, day, 2)  # enough on Monday and Tuesday only

    rows = {r["display_name"]: r for r in board(user_client)}

    assert rows["Asha"]["goal_days"] == 2


def test_a_first_time_learn_counts_but_a_relearned_word_does_not(
    user_client: TestClient, session: Session
) -> None:
    other = friend(session, "asha@example.com", "Asha", 0)
    learn(session, other, "word01", MONDAY)
    word = session.scalars(select(Word).where(Word.lemma == "word02")).one()
    session.add(  # learned long ago, back to 100 today: learned_at is today, first_learned_at isn't
        UserWord(
            user_id=other.id,
            word_id=word.id,
            score=100,
            status=WordStatus.LEARNED,
            learned_at=NOW,
            first_learned_at=NOW - timedelta(days=60),
        )
    )
    session.commit()

    rows = {r["display_name"]: r for r in board(user_client)}

    assert rows["Asha"]["new_words"] == 1


def test_people_can_hide_from_it(user_client: TestClient, session: Session) -> None:
    hidden = friend(session, "zed@example.com", "Zed", 99, show_on_leaderboard=False)

    assert "Zed" not in [r["display_name"] for r in board(user_client)]
    assert user_client.get(f"/api/profiles/{hidden.id}?tz=UTC").status_code == 404

    switched = user_client.put("/api/auth/me/leaderboard", json={"show": False})
    assert switched.json()["show_on_leaderboard"] is False
    assert [r["me"] for r in board(user_client)] == [True]  # still sees themselves


def test_a_profile_shows_stats_graphs_and_books_never_the_email(
    user_client: TestClient, session: Session
) -> None:
    other = friend(session, "asha@example.com", "Asha", 40)
    for right in (True, True, False):
        answer(user_client, session, right=right)
    me = reader(session)

    own = user_client.get(f"/api/profiles/{me.id}?tz=UTC").json()
    theirs = user_client.get(f"/api/profiles/{other.id}?tz=UTC")

    assert (own["me"], own["answers"], own["right"], own["coins"]) == (True, 3, 2, 5)
    assert len(own["history"]) == 3
    assert len(own["week"]) == 7
    assert [(b["title"], b["author"]) for b in own["books"]] == [("Moby-Dick", None)]
    assert theirs.status_code == 200
    assert theirs.json()["me"] is False
    assert theirs.json()["coins_today"] == 40
    assert "email" not in theirs.json()
    assert user_client.get(f"/api/profiles/{other.id}/avatar").status_code == 404  # no picture
    assert user_client.get("/api/profiles/99999?tz=UTC").status_code == 404


def test_books_can_be_kept_private(user_client: TestClient, session: Session) -> None:
    private = friend(session, "kai@example.com", "Kai", 5, show_books=False)
    me = reader(session)

    theirs = user_client.get(f"/api/profiles/{private.id}?tz=UTC").json()
    switched = user_client.put("/api/auth/me/books-visibility", json={"show": False})
    own = user_client.get(f"/api/profiles/{me.id}?tz=UTC").json()

    assert (theirs["books"], theirs["books_hidden"]) == ([], True)
    assert switched.json()["show_books"] is False
    assert ([b["title"] for b in own["books"]], own["books_hidden"]) == (["Moby-Dick"], False)


def test_book_covers_on_a_profile(user_client: TestClient, session: Session, settings: Any) -> None:
    moby = session.scalars(select(Document)).one()  # from the book fixture
    other = friend(session, "asha@example.com", "Asha", 0)
    session.add(CurrentReading(user_id=other.id, document_id=moby.id, priority=0))
    moby.cover_path = f"covers/{moby.id}.jpg"
    moby.owner_user_id = None  # a built-in classic: its cover may be shown to anyone
    cover = settings.data_dir / moby.cover_path
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"jpeg bytes")
    session.commit()

    listed = user_client.get(f"/api/profiles/{other.id}?tz=UTC").json()["books"]
    response = user_client.get(f"/api/profiles/{other.id}/books/{moby.id}/cover")

    assert [(b["id"], b["has_cover"]) for b in listed] == [(moby.id, True)]
    assert response.status_code == 200
    assert response.content == b"jpeg bytes"
    assert user_client.get(f"/api/profiles/{other.id}/books/99999/cover").status_code == 404
    other.show_books = False
    session.commit()
    assert user_client.get(f"/api/profiles/{other.id}/books/{moby.id}/cover").status_code == 404


def test_covers_of_someones_own_uploads_stay_private(
    user_client: TestClient, session: Session, settings: Any
) -> None:
    other = friend(session, "asha@example.com", "Asha", 0)
    upload = session.scalars(select(Document)).one()  # from the book fixture
    upload.owner_user_id, upload.cover_path = other.id, f"covers/{upload.id}.jpg"
    session.add(CurrentReading(user_id=other.id, document_id=upload.id, priority=0))
    cover = settings.data_dir / upload.cover_path
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"jpeg bytes")
    session.commit()

    listed = user_client.get(f"/api/profiles/{other.id}?tz=UTC").json()["books"]

    assert [(b["title"], b["has_cover"]) for b in listed] == [(upload.title, False)]  # title only
    assert user_client.get(f"/api/profiles/{other.id}/books/{upload.id}/cover").status_code == 404


def test_new_accounts_keep_off_the_board_until_they_choose(
    user_client: TestClient, session: Session
) -> None:
    newcomer = make_user(session, "new@example.com")

    assert newcomer.show_on_leaderboard is False
    assert all(row["user_id"] != newcomer.id for row in board(user_client))
