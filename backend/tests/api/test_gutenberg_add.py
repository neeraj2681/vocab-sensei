import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import gutenberg
from app.core.config import Settings
from app.jobs.queue import BackgroundJobQueue
from app.services.catalogue import catalogue_path
from tests.conftest import log_in, make_user

SAMPLE = Path(__file__).parent.parent / "services" / "data" / "pg_catalog_sample.csv"


@pytest.fixture(autouse=True)
def catalogue(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    path = catalogue_path(settings.data_dir)
    path.parent.mkdir(parents=True)
    shutil.copy(SAMPLE, path)
    monkeypatch.setattr(gutenberg, "refresh_catalogue", lambda path: None)


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(
        BackgroundJobQueue,
        "fetch_gutenberg_book",
        lambda self, document_id: calls.append(document_id),
    )
    return calls


def test_adding_a_book_returns_202_and_starts_the_fetch(
    user_client: TestClient, fetched: list[int]
) -> None:
    response = user_client.post("/api/library/gutenberg/1342")

    assert response.status_code == 202
    body = response.json()
    assert body["title"] == "Pride and Prejudice"
    assert body["status"] == "uploaded"
    assert body["gutenberg"] is True
    assert fetched == [body["id"]]


def test_a_second_new_book_the_same_day_is_429(user_client: TestClient, fetched: list[int]) -> None:
    user_client.post("/api/library/gutenberg/1342")

    response = user_client.post("/api/library/gutenberg/158")

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "You can add one new book a day. Books other readers have added are always free."
    )
    assert len(fetched) == 1


def test_an_unknown_book_is_404(user_client: TestClient, fetched: list[int]) -> None:
    response = user_client.post("/api/library/gutenberg/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "That book isn't in Project Gutenberg's catalogue"
    assert fetched == []


def test_a_missing_catalogue_is_503(
    user_client: TestClient, settings: Settings, fetched: list[int]
) -> None:
    catalogue_path(settings.data_dir).unlink()

    response = user_client.post("/api/library/gutenberg/1342")

    assert response.status_code == 503


def test_requires_login(client: TestClient) -> None:
    assert client.post("/api/library/gutenberg/1342").status_code == 401


def test_the_shelf_shows_in_classics_only_for_the_reader_who_added_it(
    user_client: TestClient, session: Session, fetched: list[int]
) -> None:
    added = user_client.post("/api/library/gutenberg/1342").json()

    mine = user_client.get("/api/documents/classics").json()
    assert [(d["id"], d["gutenberg"], d["classic"], d["status"]) for d in mine] == [
        (added["id"], True, True, "uploaded")
    ]

    other = make_user(session, "other@example.com")
    log_in(user_client, other.email)
    assert user_client.get("/api/documents/classics").json() == []

    free = user_client.post("/api/library/gutenberg/1342")  # someone else's: free, no fetch
    assert free.status_code == 202
    assert fetched == [added["id"]]


def test_removing_a_book_takes_it_off_the_shelf(
    user_client: TestClient, fetched: list[int]
) -> None:
    added = user_client.post("/api/library/gutenberg/1342").json()

    response = user_client.delete(f"/api/library/gutenberg/{added['id']}/shelf")

    assert response.status_code == 204
    assert user_client.get("/api/documents/classics").json() == []
    assert user_client.get(f"/api/documents/{added['id']}").status_code == 200  # still shared
