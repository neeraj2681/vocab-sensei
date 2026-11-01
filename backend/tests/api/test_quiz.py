from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_dictionary
from app.api.quiz import get_now
from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech, QuestionType, WordStatus
from app.db.models import (
    Chapter,
    ChapterWord,
    CurrentReading,
    Definition,
    Document,
    DocumentWord,
    Question,
    User,
    UserWord,
    Word,
)
from app.dictionary.types import DictionaryUnavailableError
from tests.conftest import FakeDictionary, log_in, make_user

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
LEMMAS = [f"word{i:02d}" for i in range(20)]


class Clock:
    def __init__(self) -> None:
        self.now = NOW


@pytest.fixture
def clock(user_client: TestClient) -> Iterator[Clock]:
    clock = Clock()
    app = user_client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_now] = lambda: clock.now
    yield clock


def reader(session: Session) -> User:
    return session.scalars(select(User).where(User.email == "reader@example.com")).one()


def add_word(session: Session, lemma: str, pos: str = "noun", zipf: float = 3.0) -> Word:
    word = Word(
        lemma=lemma,
        zipf_frequency=zipf,
        definitions=[Definition(pos=pos, text=f"meaning of {lemma}", source="test", sense_rank=0)],
    )
    session.add(word)
    session.flush()
    return word


def add_book_word(
    session: Session, document: Document, word: Word, chapter: Chapter, position: int
) -> None:
    """The word in the book (first appearance) and in that chapter, as processing stores them."""
    sentence, form = f"A sentence with {word.lemma}.", word.lemma
    for row in (
        DocumentWord(document_id=document.id, chapter_id=chapter.id, occurrences=1),
        ChapterWord(document_id=document.id, chapter_id=chapter.id),
    ):
        row.word_id, row.first_position, row.pos = word.id, position, PartOfSpeech.NOUN
        row.context_sentence, row.context_form = sentence, form
        session.add(row)


def add_book(session: Session, user: User, lemmas: list[str], *, reading: bool = True) -> Document:
    """A ready book whose first chapter uses `lemmas` in order, optionally being read."""
    document = Document(
        owner_user_id=user.id,
        title="Moby-Dick",
        original_filename="moby.epub",
        file_path="uploads/1/moby.epub",
        format=DocumentFormat.EPUB,
        status=DocumentStatus.READY,
        chapters=[Chapter(index=0, title="Loomings")],
    )
    session.add(document)
    session.flush()
    for position, lemma in enumerate(lemmas):
        word = session.scalars(select(Word).where(Word.lemma == lemma)).first() or add_word(
            session, lemma
        )
        add_book_word(session, document, word, document.chapters[0], position)
    if reading:
        session.add(CurrentReading(user_id=user.id, document_id=document.id))
    session.commit()
    return document


@pytest.fixture
def book(user_client: TestClient, session: Session) -> Document:
    return add_book(session, reader(session), LEMMAS)


def question(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/quiz/question")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def correct_index(session: Session, question_id: int) -> int:
    found = session.get(Question, question_id)
    assert found is not None
    return found.correct_index


def answer(
    client: TestClient, session: Session, *, right: bool = True, tz: str = "UTC"
) -> dict[str, Any]:
    asked = question(client)
    right_index = correct_index(session, asked["id"])
    chosen = right_index if right else (right_index + 1) % len(asked["options"])
    response = client.post(
        f"/api/quiz/questions/{asked['id']}/answer?tz={tz}", json={"chosen_index": chosen}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.usefixtures("book", "clock")
class TestAsking:
    def test_asks_the_first_word_of_the_learning_list(self, user_client: TestClient) -> None:
        asked = question(user_client)

        assert (asked["type"], asked["prompt"]) == ("definition_mcq", "word00")
        assert len(asked["options"]) == 4
        assert "meaning of word00" in asked["options"]
        assert "correct_index" not in asked  # only revealed after answering

    def test_the_same_question_stays_until_it_is_answered(self, user_client: TestClient) -> None:
        first = question(user_client)

        assert question(user_client) == first

    def test_wrong_options_are_other_words_meanings(self, user_client: TestClient) -> None:
        options = question(user_client)["options"]

        assert len(set(options)) == 4
        assert all(o.startswith("meaning of word") for o in options)

    def test_the_quiz_never_ends(self, user_client: TestClient, session: Session) -> None:
        asked = [answer(user_client, session)["word"] for _ in range(30)]

        assert len(asked) == 30  # more answers than words: it just keeps going

    def test_a_word_is_not_asked_again_within_ten_questions(
        self, user_client: TestClient, session: Session
    ) -> None:
        words = [answer(user_client, session, right=False)["word"] for _ in range(25)]

        for i in range(len(words)):
            assert words[i] not in words[i + 1 : i + 11]


def test_without_current_reads_there_is_nothing_to_ask(
    user_client: TestClient, session: Session
) -> None:
    add_book(session, reader(session), LEMMAS, reading=False)

    response = user_client.get("/api/quiz/question")

    assert response.status_code == 409
    assert response.json()["detail"] == "Start reading a book to get questions"


@pytest.mark.usefixtures("book", "clock")
class TestAnswering:
    def test_a_right_answer_adds_five(self, user_client: TestClient, session: Session) -> None:
        result = answer(user_client, session)

        assert result["correct"] is True
        assert result["points"] == 5
        assert result["score_delta"] == 5
        assert result["counted"] is True
        assert result["word_score"] == 5
        assert result["word_status"] == "learning"
        assert result["context_sentence"] == "A sentence with word00."
        assert result["stats"] == {"total": 5, "today": 1, "daily_goal": 10, "streak": 0}

    def test_a_wrong_answer_always_takes_ten_from_the_total(
        self, user_client: TestClient, session: Session
    ) -> None:
        answer(user_client, session)
        answer(user_client, session)

        result = answer(user_client, session, right=False)  # a new word, its score stays at 0

        assert (result["points"], result["stats"]["total"]) == (-10, 0)
        assert (result["score_delta"], result["word_score"]) == (0, 0)

    def test_the_total_never_drops_below_zero(
        self, user_client: TestClient, session: Session
    ) -> None:
        answer(user_client, session)  # total 5

        result = answer(user_client, session, right=False)

        assert (result["points"], result["stats"]["total"]) == (-5, 0)

    def test_a_wrong_answer_takes_ten_from_a_words_score(
        self, user_client: TestClient, session: Session
    ) -> None:
        word = session.scalars(select(Word).where(Word.lemma == "word01")).one()
        session.add(
            UserWord(user_id=reader(session).id, word_id=word.id, score=30, status="learning")
        )
        session.commit()
        while (result := answer(user_client, session, right=False))["word"] != "word01":
            pass

        assert (result["score_delta"], result["word_score"]) == (-10, 20)

    def test_the_answer_reveals_the_correct_option(
        self, user_client: TestClient, session: Session
    ) -> None:
        asked = question(user_client)

        result = answer(user_client, session, right=False)

        assert asked["options"][result["correct_index"]] == "meaning of word00"

    def test_lifetime_points_add_up(self, user_client: TestClient, session: Session) -> None:
        for right in (True, True, False, True):
            result = answer(user_client, session, right=right)

        assert result["stats"]["total"] == 5  # 5, 10, 0, 5

    def test_a_question_can_only_be_answered_once(
        self, user_client: TestClient, session: Session
    ) -> None:
        asked = question(user_client)
        url = f"/api/quiz/questions/{asked['id']}/answer"
        user_client.post(url, json={"chosen_index": 0})

        assert user_client.post(url, json={"chosen_index": 0}).status_code == 409

    def test_choice_must_be_one_of_the_options(self, user_client: TestClient) -> None:
        asked = question(user_client)

        response = user_client.post(
            f"/api/quiz/questions/{asked['id']}/answer", json={"chosen_index": 4}
        )

        assert response.status_code == 422

    def test_other_users_questions_are_hidden(
        self, user_client: TestClient, session: Session
    ) -> None:
        asked = question(user_client)
        log_in(user_client, make_user(session, "other@example.com").email)

        response = user_client.post(
            f"/api/quiz/questions/{asked['id']}/answer", json={"chosen_index": 0}
        )

        assert response.status_code == 404


def test_repeats_sooner_than_ten_questions_do_not_score(
    user_client: TestClient, session: Session, clock: Clock
) -> None:
    add_book(session, reader(session), LEMMAS[:5])  # fewer words than the spacing

    results = [answer(user_client, session) for _ in range(7)]

    assert [r["counted"] for r in results] == [True] * 5 + [False] * 2
    assert [(r["score_delta"], r["points"]) for r in results[5:]] == [(0, 0), (0, 0)]
    assert results[-1]["stats"]["total"] == 25


@pytest.mark.usefixtures("book", "clock")
def test_i_know_this_retires_the_word(user_client: TestClient, session: Session) -> None:
    asked = question(user_client)

    response = user_client.post(f"/api/quiz/questions/{asked['id']}/know")

    assert response.status_code == 204
    assert question(user_client)["prompt"] != asked["prompt"]
    word = session.scalars(select(Word).where(Word.lemma == asked["prompt"])).one()
    progress = session.get(UserWord, (reader(session).id, word.id))
    assert progress is not None
    assert progress.status == WordStatus.KNOWN
    words = [answer(user_client, session)["word"] for _ in range(25)]
    assert asked["prompt"] not in words


def test_synonyms_are_never_wrong_options(
    user_client: TestClient, session: Session, dictionary: FakeDictionary, clock: Clock
) -> None:
    add_book(session, reader(session), LEMMAS[:8])
    dictionary.synonym_sets["word00"] = frozenset(LEMMAS[1:5])

    options = question(user_client)["options"]

    assert not {f"meaning of {lemma}" for lemma in LEMMAS[1:5]} & set(options)


def test_wrong_options_share_the_words_part_of_speech(
    user_client: TestClient, session: Session, clock: Clock
) -> None:
    for lemma in ["verb1", "verb2", "verb3", "verb4"]:
        add_word(session, lemma, pos="verb")
    add_book(session, reader(session), LEMMAS[:4])

    options = question(user_client)["options"]

    assert all(o.startswith("meaning of word") for o in options)


def test_learned_words_come_back_for_review_once_their_score_decays(
    user_client: TestClient, session: Session, clock: Clock
) -> None:
    add_book(session, reader(session), LEMMAS, reading=False)  # nothing new to learn
    word = session.scalars(select(Word).where(Word.lemma == "word07")).one()
    session.add(
        UserWord(
            user_id=reader(session).id,
            word_id=word.id,
            score=100,
            status=WordStatus.LEARNED,
            learned_at=NOW - timedelta(weeks=3),
        )
    )
    session.commit()

    result = answer(user_client, session)

    assert result["word"] == "word07"
    assert result["score_delta"] == 5  # 85 after three weeks of decay, now 90
    assert result["points"] == 5
    assert result["word_score"] == 90


def only_word_in_progress(session: Session, lemma: str) -> None:
    """Every word of the reader's books is known except `lemma`, which is at 40."""
    user = reader(session)
    for word in session.scalars(select(Word)):
        if lemma == word.lemma:
            status, score = WordStatus.LEARNING, 40
        else:
            status, score = WordStatus.KNOWN, 0
        session.add(
            UserWord(
                user_id=user.id,
                word_id=word.id,
                score=score,
                status=status,
                last_reviewed_at=NOW - timedelta(days=1),
            )
        )
    session.commit()


def test_words_in_progress_pause_while_their_book_is_not_being_read(
    user_client: TestClient, session: Session, clock: Clock
) -> None:
    moby = add_book(session, reader(session), LEMMAS, reading=False)
    only_word_in_progress(session, "word03")

    paused = user_client.get("/api/quiz/question")

    assert paused.status_code == 409  # word03 is paused, nothing else to ask
    session.add(CurrentReading(user_id=reader(session).id, document_id=moby.id))
    session.commit()
    assert answer(user_client, session)["word"] == "word03"  # back once the book is read again


def test_words_in_progress_stay_if_another_current_read_uses_them(
    user_client: TestClient, session: Session, clock: Clock
) -> None:
    add_book(session, reader(session), LEMMAS, reading=False)  # stopped
    add_book(session, reader(session), ["word03"], reading=True)  # also uses word03
    only_word_in_progress(session, "word03")

    assert answer(user_client, session)["word"] == "word03"
    assert user_client.get("/api/quiz/words").json()[0]["progress"] == 45  # progress kept


@pytest.mark.usefixtures("book")
class TestStats:
    def test_streak_counts_days_that_met_the_goal(
        self, user_client: TestClient, session: Session, clock: Clock
    ) -> None:
        for day in range(3):
            clock.now = NOW + timedelta(days=day)
            for _ in range(10):
                result = answer(user_client, session)

        assert result["stats"]["streak"] == 3
        assert result["stats"]["today"] == 10

    def test_today_depends_on_the_users_time_zone(
        self, user_client: TestClient, session: Session, clock: Clock
    ) -> None:
        clock.now = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)  # already the 31st in Kolkata
        answer(user_client, session)
        clock.now = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)

        utc = user_client.get("/api/quiz/stats?tz=UTC").json()
        kolkata = user_client.get("/api/quiz/stats?tz=Asia/Kolkata").json()

        assert (utc["today"], kolkata["today"]) == (1, 1)
        clock.now = datetime(2026, 10, 31, 1, 0, tzinfo=UTC)
        assert user_client.get("/api/quiz/stats?tz=UTC").json()["today"] == 0
        assert user_client.get("/api/quiz/stats?tz=Asia/Kolkata").json()["today"] == 1

    def test_old_time_zone_names_work(self, user_client: TestClient, clock: Clock) -> None:
        # Phones report legacy names; slim Docker images don't ship them, the tzdata package does.
        for name in ("Asia/Calcutta", "US/Eastern"):
            assert user_client.get(f"/api/quiz/stats?tz={name}").status_code == 200

    def test_unknown_time_zones_count_days_in_utc(
        self, user_client: TestClient, session: Session, clock: Clock
    ) -> None:
        result = answer(user_client, session, tz="Mars/Olympus")  # answering still works

        assert result["stats"]["today"] == 1

    def test_the_daily_goal_is_each_users_own(
        self, user_client: TestClient, session: Session, clock: Clock
    ) -> None:
        for _ in range(10):
            answer(user_client, session)

        response = user_client.put("/api/quiz/goal?tz=UTC", json={"daily_goal": 20})

        assert response.status_code == 200, response.text
        assert (response.json()["today"], response.json()["daily_goal"]) == (10, 20)
        assert response.json()["streak"] == 0  # today now needs 20
        assert user_client.get("/api/quiz/stats?tz=UTC").json()["daily_goal"] == 20
        lowered = user_client.put("/api/quiz/goal?tz=UTC", json={"daily_goal": 5}).json()
        assert (lowered["daily_goal"], lowered["streak"]) == (5, 1)

    def test_raising_the_goal_keeps_the_streak_already_earned(
        self, user_client: TestClient, session: Session, clock: Clock
    ) -> None:
        for days in (2, 1):  # the goal is 10 so far
            clock.now = NOW - timedelta(days=days)
            for _ in range(10):
                answer(user_client, session)
        clock.now = NOW

        stats = user_client.put("/api/quiz/goal?tz=UTC", json={"daily_goal": 30}).json()

        assert (stats["daily_goal"], stats["streak"]) == (30, 2)  # yesterday's 10 still counts

    @pytest.mark.parametrize("goal", [0, 201])
    def test_goals_must_be_sensible(self, user_client: TestClient, goal: int) -> None:
        assert user_client.put("/api/quiz/goal", json={"daily_goal": goal}).status_code == 422

    def test_history_has_the_running_total_after_every_answer(
        self, user_client: TestClient, session: Session, clock: Clock
    ) -> None:
        for right in (True, True, False):
            answer(user_client, session, right=right)
        asked = question(user_client)
        user_client.post(f"/api/quiz/questions/{asked['id']}/know")  # not part of the graph

        history = user_client.get("/api/quiz/history").json()

        assert [(p["number"], p["total"], p["correct"]) for p in history] == [
            (1, 5, True),
            (2, 10, True),
            (3, 0, False),
        ]


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/quiz/question").status_code == 401
    assert client.get("/api/quiz/stats").status_code == 401
    assert client.get("/api/quiz/history").status_code == 401


def test_too_few_words_for_four_options(user_client: TestClient, session: Session) -> None:
    add_book(session, reader(session), LEMMAS[:3])

    response = user_client.get("/api/quiz/question")

    assert response.status_code == 409
    assert "enough words" in response.json()["detail"]


@pytest.mark.usefixtures("book")
def test_missing_dictionary(user_client: TestClient) -> None:
    def unavailable() -> FakeDictionary:
        raise DictionaryUnavailableError("not installed")

    app = user_client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_dictionary] = lambda: unavailable

    response = user_client.get("/api/quiz/question")

    assert response.status_code == 503


@pytest.mark.usefixtures("book", "clock")
def test_i_know_this_needs_an_open_question_of_your_own(
    user_client: TestClient, session: Session
) -> None:
    asked = question(user_client)
    know = f"/api/quiz/questions/{asked['id']}/know"
    assert user_client.post(know).status_code == 204

    assert user_client.post(know).status_code == 409
    assert user_client.post("/api/quiz/questions/999/know").status_code == 404


@pytest.mark.usefixtures("book", "clock")
class TestQuestionTypes:
    @pytest.fixture
    def forced(self, monkeypatch: pytest.MonkeyPatch) -> Callable[[QuestionType], None]:
        def force(kind: QuestionType) -> None:
            monkeypatch.setattr(
                "app.services.quiz.choose_question_type", lambda *args, **kwargs: kind
            )

        return force

    def test_reverse_shows_a_meaning_and_hides_the_word(
        self, user_client: TestClient, session: Session, forced: Callable[[QuestionType], None]
    ) -> None:
        forced(QuestionType.REVERSE)

        asked = question(user_client)

        assert (asked["type"], asked["prompt"]) == ("reverse", "meaning of word00")
        assert "word00" in asked["options"]
        result = answer(user_client, session)
        assert (result["word"], result["meaning"]) == ("word00", "meaning of word00")

    def test_fill_in_blanks_the_book_sentence(
        self, user_client: TestClient, session: Session, forced: Callable[[QuestionType], None]
    ) -> None:
        forced(QuestionType.FILL_IN_BLANK)

        asked = question(user_client)

        assert (asked["type"], asked["prompt"]) == ("fill_in_blank", "A sentence with _____.")
        assert "word00" in asked["options"]
        result = answer(user_client, session)
        assert result["context_sentence"] == "A sentence with word00."

    def test_without_the_sentence_form_it_asks_the_meaning(
        self, user_client: TestClient, session: Session, forced: Callable[[QuestionType], None]
    ) -> None:
        forced(QuestionType.FILL_IN_BLANK)
        session.execute(text("UPDATE chapter_words SET context_form = NULL"))
        session.commit()

        assert question(user_client)["type"] == "definition_mcq"

    def test_well_known_words_get_harder_formats(
        self, user_client: TestClient, session: Session
    ) -> None:
        user = reader(session)
        for word in session.scalars(select(Word)):
            session.add(UserWord(user_id=user.id, word_id=word.id, score=80, status="learning"))
        session.commit()

        kinds = {question_type(user_client, session) for _ in range(30)}

        assert kinds == {"definition_mcq", "reverse", "fill_in_blank"}


def question_type(client: TestClient, session: Session) -> str:
    kind: str = question(client)["type"]
    answer(client, session)
    return kind


def test_words_lists_answered_words_with_their_progress(
    user_client: TestClient, session: Session, book: Document, clock: Clock
) -> None:
    for _ in range(3):
        answer(user_client, session, right=True)

    response = user_client.get("/api/quiz/words")

    assert response.status_code == 200, response.text
    words = response.json()
    assert len(words) == 3
    assert {(w["progress"], w["learned"], w["book"]) for w in words} == {(5, False, "Moby-Dick")}
    assert all(w["meaning"] == f"meaning of {w['word']}" for w in words)
    assert all(w["sentence"] == f"A sentence with {w['word']}." for w in words)


def test_words_puts_learned_first_and_leaves_out_unanswered_and_known(
    user_client: TestClient, session: Session, book: Document, clock: Clock
) -> None:
    user = reader(session)
    reviewed = NOW - timedelta(days=1)

    def progress(lemma: str, score: int, status: WordStatus, **extra: Any) -> None:
        word = session.scalars(select(Word).where(Word.lemma == lemma)).one()
        session.add(UserWord(user_id=user.id, word_id=word.id, score=score, status=status, **extra))

    progress("word00", 40, WordStatus.LEARNING, last_reviewed_at=reviewed)
    progress("word01", 105, WordStatus.LEARNED, learned_at=reviewed, last_reviewed_at=reviewed)
    progress(  # learned three weeks ago: decayed to 85, so back to learning
        "word02",
        100,
        WordStatus.LEARNED,
        learned_at=NOW - timedelta(weeks=3),
        last_reviewed_at=NOW - timedelta(weeks=3),
    )
    progress("word03", 30, WordStatus.LEARNING)  # "unsure" on triage, never answered
    progress("word04", 0, WordStatus.KNOWN, last_reviewed_at=reviewed)  # "I know this"
    session.commit()

    words = user_client.get("/api/quiz/words").json()

    assert [(w["word"], w["progress"], w["learned"]) for w in words] == [
        ("word01", 100, True),
        ("word02", 85, False),
        ("word00", 40, False),
    ]


def test_words_is_empty_before_any_answer(user_client: TestClient, book: Document) -> None:
    assert user_client.get("/api/quiz/words").json() == []
