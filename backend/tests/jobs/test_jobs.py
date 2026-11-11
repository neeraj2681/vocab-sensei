import io
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_job_queue
from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus
from app.db.models import Document
from app.jobs import tasks
from app.jobs.queue import BackgroundJobQueue, CeleryJobQueue
from app.services import gutenberg as gutenberg_service
from app.services.documents import DocumentService
from tests.api.test_documents import epub_bytes, upload
from tests.conftest import FakeDictionary, make_user


def _queue(settings: Settings, session_factory: sessionmaker[Session]) -> object:
    return get_job_queue(settings, BackgroundTasks(), session_factory, lambda: FakeDictionary())


def test_without_a_broker_uploads_process_in_the_api(
    settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    assert settings.jobs.broker_url is None
    assert isinstance(_queue(settings, session_factory), BackgroundJobQueue)


def test_with_a_broker_uploads_go_to_celery(
    user_client: TestClient,
    settings: Settings,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.jobs.broker_url = "redis://x:6379/1"
    assert isinstance(_queue(settings, session_factory), CeleryJobQueue)
    calls: list[int] = []
    monkeypatch.setattr(
        tasks.process_document, "delay", lambda document_id: calls.append(document_id)
    )

    created = upload(user_client, epub_bytes(tmp_path))

    assert calls == [created["id"]]
    assert created["status"] == "uploaded"  # nothing processed it in the API


def test_the_task_processes_the_book(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    dictionary: FakeDictionary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "_dictionary", lambda: dictionary)
    user = make_user(session)
    document = DocumentService(session, settings, lambda: dictionary).create(
        user.id, "moby.epub", io.BytesIO(epub_bytes(tmp_path))
    )

    tasks.process_document.run(document.id)

    session.expire_all()
    assert session.get(Document, document.id).status == DocumentStatus.READY  # type: ignore[union-attr]


def _gutenberg_book(session: Session) -> Document:
    document = Document(
        owner_user_id=None,
        title="Moby",
        original_filename="gutenberg-2701.epub",
        file_path="library/gutenberg-2701.epub",
        format=DocumentFormat.EPUB,
        status=DocumentStatus.UPLOADED,
        gutenberg_id=2701,
    )
    session.add(document)
    session.commit()
    return document


def test_the_gutenberg_task_downloads_and_processes(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    dictionary: FakeDictionary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "_dictionary", lambda: dictionary)
    book = epub_bytes(tmp_path)
    urls: list[str] = []

    def fake_download(url: str, path: Path) -> None:
        urls.append(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(book)

    monkeypatch.setattr(gutenberg_service, "download", fake_download)
    document = _gutenberg_book(session)

    tasks.fetch_gutenberg_book.run(document.id)

    session.expire_all()
    assert urls == ["https://www.gutenberg.org/ebooks/2701.epub3.images"]
    assert (settings.data_dir / "library" / "gutenberg-2701.epub").exists()
    assert session.get(Document, document.id).status == DocumentStatus.READY  # type: ignore[union-attr]


def test_a_failed_gutenberg_download_is_stored_on_the_book(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    dictionary: FakeDictionary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "_dictionary", lambda: dictionary)

    def broken_download(url: str, path: Path) -> None:
        raise OSError("offline")

    monkeypatch.setattr(gutenberg_service, "download", broken_download)
    document = _gutenberg_book(session)

    tasks.fetch_gutenberg_book.run(document.id)

    session.expire_all()
    stored = session.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.FAILED
    assert stored.error == "Couldn't download this book from Project Gutenberg. Try again later."


def test_the_celery_queue_sends_gutenberg_books_to_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        tasks.fetch_gutenberg_book, "delay", lambda document_id: calls.append(document_id)
    )

    CeleryJobQueue().fetch_gutenberg_book(7)

    assert calls == [7]
