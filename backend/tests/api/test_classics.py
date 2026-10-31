from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.commands import seed_classics
from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech
from app.db.models import Chapter, Document, DocumentWord, Word
from app.services.library import CLASSICS
from tests.api.test_quiz import LEMMAS, add_word, answer
from tests.conftest import FakeDictionary
from tests.extraction.epub_builder import Chapter as EpubChapter
from tests.extraction.epub_builder import EpubSpec, build_epub

PRIDE = "gutenberg-1342.epub"


def add_classic(
    session: Session, title: str = "Pride and Prejudice", filename: str = PRIDE
) -> Document:
    document = Document(
        owner_user_id=None,
        title=title,
        original_filename=filename,
        file_path=f"library/{filename}",
        format=DocumentFormat.EPUB,
        status=DocumentStatus.READY,
        chapters=[Chapter(index=0, title="Chapter 1")],
    )
    session.add(document)
    session.flush()
    for position, lemma in enumerate(LEMMAS):
        word = session.scalars(select(Word).where(Word.lemma == lemma)).first() or add_word(
            session, lemma
        )
        session.add(
            DocumentWord(
                document_id=document.id,
                word_id=word.id,
                chapter_id=document.chapters[0].id,
                first_position=position,
                context_sentence=f"A sentence with {lemma}.",
                context_form=lemma,
                pos=PartOfSpeech.NOUN,
            )
        )
    session.commit()
    return document


@pytest.fixture
def classic(user_client: TestClient, session: Session) -> Document:
    return add_classic(session)


def test_classics_are_listed_for_everyone(user_client: TestClient, classic: Document) -> None:
    classics = user_client.get("/api/documents/classics").json()

    assert [(c["title"], c["classic"], c["word_count"]) for c in classics] == [
        ("Pride and Prejudice", True, 20)
    ]
    assert user_client.get("/api/documents").json() == []  # "My books" holds uploads only


def test_anyone_can_read_a_classic_but_nobody_can_delete_it(
    user_client: TestClient, classic: Document
) -> None:
    assert user_client.get(f"/api/documents/{classic.id}").json()["classic"] is True
    assert len(user_client.get(f"/api/documents/{classic.id}/words").json()) == 20
    assert user_client.get(f"/api/documents/{classic.id}/readiness").status_code == 200

    response = user_client.delete(f"/api/documents/{classic.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Built-in classics can't be deleted"


def test_new_users_start_on_the_default_classic(user_client: TestClient, classic: Document) -> None:
    readings = user_client.get("/api/readings").json()

    assert [(r["document"]["title"], r["current_chapter_index"]) for r in readings] == [
        ("Pride and Prejudice", 0)
    ]


def test_the_quiz_works_before_any_upload(
    user_client: TestClient, session: Session, classic: Document
) -> None:
    result = answer(user_client, session)  # no reads yet: the classic is started on the way

    assert result["word"] == "word00"
    assert result["context_sentence"] == "A sentence with word00."


def test_users_who_stopped_reading_are_not_restarted(
    user_client: TestClient, session: Session, classic: Document
) -> None:
    answer(user_client, session)
    user_client.delete(f"/api/readings/{classic.id}")

    assert user_client.get("/api/readings").json() == []


def test_no_classics_seeded_means_no_automatic_start(user_client: TestClient) -> None:
    assert user_client.get("/api/readings").json() == []
    assert user_client.get("/api/quiz/question").status_code == 409


def test_words_of_a_classic_can_be_sorted(user_client: TestClient, classic: Document) -> None:
    user_client.get("/api/readings")  # starts the classic
    word_id = user_client.get(f"/api/documents/{classic.id}/sort?limit=1").json()["words"][0][
        "word_id"
    ]

    response = user_client.put(f"/api/words/{word_id}/sort", json={"choice": "known"})

    assert response.status_code == 200


def test_a_backup_reattaches_to_a_classic_by_title(
    user_client: TestClient, classic: Document
) -> None:
    backup = {
        "exported_at": "2026-10-30T12:00:00Z",
        "readings": [{"title": "Pride and Prejudice", "priority": 0, "chapter_index": 0}],
    }

    summary = user_client.post("/api/backup", json=backup).json()

    assert (summary["readings_added"], summary["books_missing"]) == (1, [])


# Seeding


def fake_download(tmp_path: Path) -> tuple[list[str], seed_classics.Download]:
    calls: list[str] = []
    spec = EpubSpec(
        [
            EpubChapter(
                "c1.xhtml",
                "<p>Chapter 1. It is a truth universally acknowledged that a lugubrious tune"
                " played while the perfunctory nod was obsequious and quite lugubrious.</p>",
                toc_title="Chapter 1",
            )
        ],
        title="Pride and Prejudice",
        author="Jane Austen",
    )
    source = build_epub(tmp_path / "source.epub", spec)

    def fetch(url: str, path: Path) -> None:
        calls.append(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.read_bytes())

    return calls, fetch


def test_seeding_downloads_and_processes_every_classic_once(
    session_factory: sessionmaker[Session], settings: Settings, tmp_path: Path
) -> None:
    calls, fetch = fake_download(tmp_path)
    dictionary = FakeDictionary()

    added = seed_classics.seed(session_factory, settings, lambda: dictionary, fetch)
    again = seed_classics.seed(session_factory, settings, lambda: dictionary, fetch)

    assert added == [c.title for c in CLASSICS]
    assert again == []
    assert len(calls) == len(CLASSICS)  # each book downloaded once
    assert calls[2] == "https://www.gutenberg.org/ebooks/1342.epub3.images"
    with session_factory() as session:
        books = session.scalars(select(Document)).all()
    assert {b.owner_user_id for b in books} == {None}
    assert {b.status for b in books} == {DocumentStatus.READY}


def test_a_failed_download_is_retried_next_time(
    session_factory: sessionmaker[Session],
    settings: Settings,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, fetch = fake_download(tmp_path)

    def offline(url: str, path: Path) -> None:
        raise OSError("network is down")

    dictionary = FakeDictionary()

    assert seed_classics.seed(session_factory, settings, lambda: dictionary, offline) == []
    assert "couldn't download" in caplog.text
    assert len(seed_classics.seed(session_factory, settings, lambda: dictionary, fetch)) == 8


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_download_retries_and_writes_the_whole_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts: list[str] = []

    def urlopen(request: object, timeout: float) -> FakeResponse:
        attempts.append("try")
        if len(attempts) == 1:
            raise OSError("connection reset")
        return FakeResponse(b"EPUB bytes")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    target = tmp_path / "library" / "gutenberg-11.epub"

    seed_classics.download("https://www.gutenberg.org/ebooks/11.epub3.images", target)

    assert target.read_bytes() == b"EPUB bytes"
    assert len(attempts) == 2
    assert not target.with_suffix(".part").exists()


def test_download_gives_up_after_three_tries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def urlopen(request: object, timeout: float) -> FakeResponse:
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    with pytest.raises(OSError):
        seed_classics.download("https://example.com/x.epub", tmp_path / "x.epub")
