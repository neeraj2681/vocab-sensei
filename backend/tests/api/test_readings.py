from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api.test_documents import epub_bytes, upload
from tests.conftest import log_in, make_user


def book(client: TestClient, tmp_path: Path, name: str = "book.epub") -> int:
    document_id = upload(client, epub_bytes(tmp_path, chapters=3), name)["id"]
    assert isinstance(document_id, int)
    return document_id


def start(client: TestClient, document_id: int) -> dict[str, object]:
    response = client.post("/api/readings", json={"document_id": document_id})
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def order(client: TestClient) -> list[object]:
    return [r["document"]["id"] for r in client.get("/api/readings").json()]


def test_starting_a_book_begins_at_its_first_chapter(
    user_client: TestClient, tmp_path: Path
) -> None:
    reading = start(user_client, book(user_client, tmp_path))

    assert reading["priority"] == 0
    assert reading["current_chapter_index"] == 0
    assert reading["current_chapter_title"] == "Chapter 1"
    document = reading["document"]
    assert isinstance(document, dict)
    assert document["title"] == "Moby-Dick"
    assert document["word_count"] > 0


def test_new_reads_go_to_the_end_of_the_list(user_client: TestClient, tmp_path: Path) -> None:
    first, second = book(user_client, tmp_path, "a.epub"), book(user_client, tmp_path, "b.epub")
    start(user_client, first)

    assert start(user_client, second)["priority"] == 1
    assert order(user_client) == [first, second]


def test_a_book_can_only_be_started_once(user_client: TestClient, tmp_path: Path) -> None:
    document_id = book(user_client, tmp_path)
    start(user_client, document_id)

    response = user_client.post("/api/readings", json={"document_id": document_id})

    assert response.status_code == 409


def test_books_that_failed_to_process_cannot_be_started(user_client: TestClient) -> None:
    document_id = upload(user_client, b"not an epub")["id"]

    response = user_client.post("/api/readings", json={"document_id": document_id})

    assert response.status_code == 409
    assert response.json()["detail"] == "This book isn't ready yet"


def test_reordering(user_client: TestClient, tmp_path: Path) -> None:
    ids = [book(user_client, tmp_path, f"{n}.epub") for n in "abc"]
    for document_id in ids:
        start(user_client, document_id)

    response = user_client.put("/api/readings/order", json={"document_ids": ids[::-1]})

    assert response.status_code == 200
    assert [r["priority"] for r in response.json()] == [0, 1, 2]
    assert order(user_client) == ids[::-1]


@pytest.mark.parametrize("change", [lambda ids: ids[:1], lambda ids: [*ids, ids[0]]])
def test_reordering_must_list_every_read_once(
    user_client: TestClient, tmp_path: Path, change: Callable[[list[int]], list[int]]
) -> None:
    ids = [book(user_client, tmp_path, f"{n}.epub") for n in "ab"]
    for document_id in ids:
        start(user_client, document_id)

    response = user_client.put("/api/readings/order", json={"document_ids": change(ids)})

    assert response.status_code == 422
    assert order(user_client) == ids


def test_moving_to_another_chapter(user_client: TestClient, tmp_path: Path) -> None:
    document_id = book(user_client, tmp_path)
    start(user_client, document_id)

    response = user_client.patch(f"/api/readings/{document_id}", json={"current_chapter_index": 2})

    assert response.status_code == 200
    assert response.json()["current_chapter_index"] == 2
    assert response.json()["current_chapter_title"] == "Chapter 3"


@pytest.mark.parametrize("index", [-1, 3])
def test_chapter_must_exist(user_client: TestClient, tmp_path: Path, index: int) -> None:
    document_id = book(user_client, tmp_path)
    start(user_client, document_id)

    response = user_client.patch(
        f"/api/readings/{document_id}", json={"current_chapter_index": index}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "This book has chapters 0 to 2"


def test_stopping_closes_the_gap_in_priorities(user_client: TestClient, tmp_path: Path) -> None:
    ids = [book(user_client, tmp_path, f"{n}.epub") for n in "abc"]
    for document_id in ids:
        start(user_client, document_id)

    assert user_client.delete(f"/api/readings/{ids[0]}").status_code == 204

    readings = user_client.get("/api/readings").json()
    assert [(r["document"]["id"], r["priority"]) for r in readings] == [(ids[1], 0), (ids[2], 1)]


def test_stopping_a_book_you_are_not_reading(user_client: TestClient, tmp_path: Path) -> None:
    response = user_client.delete(f"/api/readings/{book(user_client, tmp_path)}")

    assert response.status_code == 404


def test_deleting_a_book_stops_reading_it(user_client: TestClient, tmp_path: Path) -> None:
    document_id = book(user_client, tmp_path)
    start(user_client, document_id)

    user_client.delete(f"/api/documents/{document_id}")

    assert user_client.get("/api/readings").json() == []


def test_other_users_books_cannot_be_started(
    user_client: TestClient, session: Session, tmp_path: Path
) -> None:
    document_id = book(user_client, tmp_path)
    log_in(user_client, make_user(session, "other@example.com").email)

    response = user_client.post("/api/readings", json={"document_id": document_id})

    assert response.status_code == 404


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/readings").status_code == 401
