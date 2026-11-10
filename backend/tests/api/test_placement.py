from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import UserWord, Word
from app.quiz.placement import BANDS, PSEUDOWORDS
from app.services import placement as placement_service
from tests.api.test_quiz import Clock, add_book, add_word, answer, clock, reader  # noqa: F401
from tests.conftest import FakeDictionary

EASY = [f"easy{i}" for i in range(6)]  # Zipf 3.8: common
HARD = [f"hard{i}" for i in range(6)]  # Zipf 1.8: rare


@pytest.fixture
def mixed_book(user_client: TestClient, session: Session) -> None:
    for lemma in EASY:
        add_word(session, lemma, zipf=3.8)
    for lemma in HARD:
        add_word(session, lemma, zipf=1.8)
    add_book(session, reader(session), [w for pair in zip(EASY, HARD, strict=True) for w in pair])


@pytest.fixture
def candidates(monkeypatch: pytest.MonkeyPatch, dictionary: FakeDictionary) -> None:
    """Check words without the real word list; the made-up ones aren't in the dictionary."""
    dictionary.unknown |= set(PSEUDOWORDS)
    found = {band: tuple(f"band{band}w{i}" for i in range(5)) for band in BANDS}
    monkeypatch.setattr(placement_service, "_found", found)


def set_level(user_client: TestClient, known_down_to: float) -> dict[str, Any]:
    answers = [
        {"word": word, "known": float(word.split("w")[0].removeprefix("band")) >= known_down_to}
        for band in BANDS
        for word in (f"band{band}w0", f"band{band}w1")
    ]
    answers += [{"word": fake, "known": False} for fake in PSEUDOWORDS[:4]]
    response = user_client.put("/api/placement", json={"answers": answers})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.usefixtures("candidates")
def test_a_check_has_twenty_words(user_client: TestClient) -> None:
    words = user_client.get("/api/placement").json()["words"]

    assert len(words) == 20
    assert sum(word in PSEUDOWORDS for word in words) == 4


@pytest.mark.usefixtures("candidates")
def test_answers_set_the_level(user_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        placement_service,
        "zipf_frequency",
        lambda word, _lang: float(word.split("w")[0].removeprefix("band")),
    )
    assert user_client.get("/api/placement/level").json() == {"level": None, "name": None}

    saved = set_level(user_client, known_down_to=3.0)

    assert 2.5 < saved["level"] <= 3.0
    assert saved["name"] == "Advanced"
    assert user_client.get("/api/auth/me").json()["vocab_level"] == saved["level"]
    assert user_client.put("/api/placement", json={"answers": []}).status_code == 422


@pytest.mark.usefixtures("mixed_book", "clock")
def test_probably_known_words_are_kept_out_of_the_quiz(
    user_client: TestClient, session: Session
) -> None:
    reader(session).vocab_level = 2.5  # words more common than 3.0 are probably known
    session.commit()

    asked = {answer(user_client, session)["word"] for _ in range(6)}
    easy = user_client.get("/api/placement/probably-known").json()

    assert asked <= set(HARD)
    assert sorted(w["word"] for w in easy) == EASY
    assert easy[0]["meaning"] == f"meaning of {easy[0]['word']}"
    assert easy[0]["book"] == "Moby-Dick"


@pytest.mark.usefixtures("mixed_book")
def test_a_probably_known_word_can_be_learned(user_client: TestClient, session: Session) -> None:
    reader(session).vocab_level = 2.5
    session.commit()

    response = user_client.post("/api/quiz/words/easy0/learn")

    assert response.status_code == 204, response.text
    word = session.scalars(select(Word).where(Word.lemma == "easy0")).one()
    progress = session.get(UserWord, (reader(session).id, word.id))
    assert progress is not None
    assert (progress.status, progress.score) == (WordStatus.LEARNING, 0)
    left = {w["word"] for w in user_client.get("/api/placement/probably-known").json()}
    assert "easy0" not in left


@pytest.mark.usefixtures("mixed_book", "clock")
def test_without_a_level_very_common_words_are_kept_aside(
    user_client: TestClient, session: Session
) -> None:
    asked = {answer(user_client, session)["word"] for _ in range(6)}
    easy = user_client.get("/api/placement/probably-known").json()

    assert asked == set(HARD)  # Zipf 1.8
    assert sorted(w["word"] for w in easy) == EASY  # Zipf 3.8: over the default cutoff (3.5)


@pytest.mark.usefixtures("candidates", "mixed_book")
def test_taking_the_check_sets_aside_easy_words_with_little_progress(
    user_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        placement_service,
        "zipf_frequency",
        lambda word, _lang: float(word.split("w")[0].removeprefix("band")),
    )
    user_id = reader(session).id
    words = {w.lemma: w.id for w in session.scalars(select(Word))}
    progress = {  # word: (status, score) before the check
        "easy0": (WordStatus.LEARNING, 10),  # easy, barely started: set aside
        "easy1": (WordStatus.LEARNING, 29),  # easy, just under the line: set aside
        "easy2": (WordStatus.LEARNING, 30),  # easy, real progress: stays
        "easy3": (WordStatus.LEARNED, 100),  # learned: stays
        "hard0": (WordStatus.LEARNING, 5),  # rare: stays
    }
    for lemma, (state, score) in progress.items():
        session.add(UserWord(user_id=user_id, word_id=words[lemma], status=state, score=score))
    session.commit()

    saved = set_level(user_client, known_down_to=3.0)  # level ~2.75: easy above ~3.25

    assert saved["set_aside"] == 2
    session.expire_all()
    after = {
        lemma: (p.status, p.score)
        for lemma in progress
        if (p := session.get(UserWord, (user_id, words[lemma])))
    }
    assert after["easy0"] == after["easy1"] == (WordStatus.NEW, 0)
    assert {k: after[k] for k in ("easy2", "easy3", "hard0")} == {
        k: progress[k] for k in ("easy2", "easy3", "hard0")
    }
    easy = {w["word"] for w in user_client.get("/api/placement/probably-known").json()}
    assert {"easy0", "easy1"} <= easy
    assert not easy & {"easy2", "easy3", "hard0"}


@pytest.mark.usefixtures("mixed_book", "clock")
def test_past_answers_give_a_level(user_client: TestClient, session: Session) -> None:
    service = placement_service.PlacementService(session, lambda: None)  # type: ignore[arg-type,return-value]
    assert service.estimate_from_history(reader(session).id) is None  # too few answers

    for _ in range(12):
        answer(user_client, session)
    for lemma in [f"known{i}" for i in range(40)]:
        word = add_word(session, lemma, zipf=3.5)
        session.add(UserWord(user_id=reader(session).id, word_id=word.id, status=WordStatus.KNOWN))
    session.commit()

    level = service.estimate_from_history(reader(session).id)
    assert level is not None
    assert level <= 3.5
