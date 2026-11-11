import io
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_job_queue
from app.core.config import Settings
from app.core.enums import DocumentStatus
from app.db.models import Document
from app.jobs import tasks
from app.jobs.queue import BackgroundJobQueue, CeleryJobQueue
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
