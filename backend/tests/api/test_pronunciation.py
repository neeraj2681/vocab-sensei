from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_speech
from app.core.config import Settings
from app.core.speech import AudioError
from app.db.models import UserWord, Word
from tests.api.test_quiz import book, clock, only_word_in_progress, reader  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("book", "clock")


class FakeRecognizer:
    """Hears whatever the test says it heard; b"noise" isn't audio."""

    def __init__(self) -> None:
        self.heard = ""
        self.hints: list[str] = []

    def transcribe(self, audio: bytes, hint: str) -> str:
        if audio == b"noise":
            raise AudioError("That recording couldn't be read")
        self.hints.append(hint)
        return self.heard


@pytest.fixture
def ears(user_client: TestClient) -> FakeRecognizer:
    fake = FakeRecognizer()
    app = user_client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_speech] = lambda: fake
    return fake


def recording(data: bytes = b"webm bytes") -> dict[str, Any]:
    return {"audio": ("say.webm", data, "audio/webm")}


def test_practice_says_whether_the_word_was_said(
    user_client: TestClient, ears: FakeRecognizer
) -> None:
    ears.heard = "Laguubrious."
    right = user_client.post("/api/pronunciation", data={"word": "lugubrious"}, files=recording())
    ears.heard = "Banana."
    wrong = user_client.post("/api/pronunciation", data={"word": "lugubrious"}, files=recording())

    assert right.json() == {"heard": "Laguubrious.", "correct": True}
    assert wrong.json() == {"heard": "Banana.", "correct": False}
    assert ears.hints == ["lugubrious", "lugubrious"]  # the recogniser is told the word


def test_unreadable_or_huge_recordings_are_refused(
    user_client: TestClient, ears: FakeRecognizer, settings: Settings
) -> None:
    noise = user_client.post("/api/pronunciation", data={"word": "x"}, files=recording(b"noise"))
    settings.speech.max_audio_bytes = 10
    huge = user_client.post("/api/pronunciation", data={"word": "x"}, files=recording(b"x" * 11))

    assert noise.status_code == 422
    assert huge.status_code == 413


def well_known(session: Session, lemma: str) -> None:
    only_word_in_progress(session, lemma)
    word = session.scalars(select(Word).where(Word.lemma == lemma)).one()
    progress = session.get(UserWord, (reader(session).id, word.id))
    assert progress is not None
    progress.score = 80  # well known: speaking questions may come
    session.commit()


def test_a_speaking_question_is_scored_by_what_was_heard(
    user_client: TestClient, session: Session, ears: FakeRecognizer, settings: Settings
) -> None:
    settings.speech.say_word_share = 1.0
    well_known(session, "word00")

    asked = user_client.get("/api/quiz/question?speaking=true").json()
    ears.heard = "word zero zero"  # not it
    wrong = user_client.post(f"/api/quiz/questions/{asked['id']}/speak?tz=UTC", files=recording())

    assert (asked["type"], asked["prompt"]) == ("say_word", "word00")
    assert (wrong.json()["correct"], wrong.json()["heard"]) == (False, "word zero zero")
    assert wrong.json()["word_score"] < 80  # scored like a wrong answer


def test_no_speaking_questions_unless_the_screen_can_record(
    user_client: TestClient, session: Session, settings: Settings
) -> None:
    settings.speech.say_word_share = 1.0
    well_known(session, "word00")

    asked = user_client.get("/api/quiz/question").json()

    assert asked["type"] != "say_word"


def test_a_speaking_question_can_be_skipped(
    user_client: TestClient, session: Session, settings: Settings
) -> None:
    settings.speech.say_word_share = 1.0
    well_known(session, "word00")
    asked = user_client.get("/api/quiz/question?speaking=true").json()

    assert user_client.post(f"/api/quiz/questions/{asked['id']}/skip").status_code == 204

    settings.speech.say_word_share = 0.0
    assert user_client.get("/api/quiz/question?speaking=true").json()["type"] != "say_word"


def test_a_normal_question_cant_be_spoken(user_client: TestClient, ears: FakeRecognizer) -> None:
    asked = user_client.get("/api/quiz/question").json()

    response = user_client.post(f"/api/quiz/questions/{asked['id']}/speak", files=recording())

    assert response.status_code == 422
