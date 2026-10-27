from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from tests.conftest import log_in, make_user
from tests.extraction.epub_builder import Chapter, EpubSpec, build_epub

TEXT = (
    " This paragraph is comfortably long enough to count as a real chapter of the book,"
    " not just a heading."
)


def epub_bytes(tmp_path: Path, chapters: int = 2) -> bytes:
    spec = EpubSpec(
        [
            Chapter(f"c{i}.xhtml", f"<p>Chapter {i}.{TEXT}</p>", toc_title=f"Chapter {i}")
            for i in range(1, chapters + 1)
        ]
    )
    return build_epub(tmp_path / "upload.epub", spec).read_bytes()


def upload(client: TestClient, content: bytes, filename: str = "moby.epub") -> dict[str, object]:
    response = client.post("/api/documents", files={"file": (filename, content)})
    assert response.status_code == 202, response.text
    body: dict[str, object] = response.json()
    return body


def test_upload_parses_the_book_into_chapters(user_client: TestClient, tmp_path: Path) -> None:
    created = upload(user_client, epub_bytes(tmp_path))
    assert created["status"] == "uploaded"
    assert created["title"] == "moby"  # file name until the book has been read

    # TestClient runs background tasks before returning, so processing is done here.
    detail = user_client.get(f"/api/documents/{created['id']}").json()

    assert detail["status"] == "ready"
    assert detail["title"] == "Moby-Dick"
    assert detail["author"] == "Herman Melville"
    assert detail["chapter_count"] == 2
    assert detail["chapters"] == [
        {"index": 0, "title": "Chapter 1"},
        {"index": 1, "title": "Chapter 2"},
    ]


def test_file_is_stored_under_the_users_folder(
    user_client: TestClient, tmp_path: Path, settings: Settings
) -> None:
    upload(user_client, epub_bytes(tmp_path))

    stored = list((settings.data_dir / "uploads").glob("*/*.epub"))

    assert len(stored) == 1
    assert stored[0].read_bytes() == epub_bytes(tmp_path)


def test_list_shows_newest_first(user_client: TestClient, tmp_path: Path) -> None:
    first = upload(user_client, epub_bytes(tmp_path), "first.epub")
    second = upload(user_client, epub_bytes(tmp_path), "second.epub")

    ids = [d["id"] for d in user_client.get("/api/documents").json()]

    assert ids == [second["id"], first["id"]]


def test_damaged_file_fails_with_a_reason(user_client: TestClient) -> None:
    created = upload(user_client, b"not really an epub")

    detail = user_client.get(f"/api/documents/{created['id']}").json()

    assert detail["status"] == "failed"
    assert "not a valid EPUB" in detail["error"]
    assert detail["chapters"] == []


def test_unexpected_errors_still_end_as_failed(
    user_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Exploding:
        def parse(self, path: Path) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.documents.get_parser", lambda _format: Exploding())
    created = upload(user_client, epub_bytes(tmp_path))

    detail = user_client.get(f"/api/documents/{created['id']}").json()

    assert detail["status"] == "failed"
    assert detail["error"] == "Something went wrong while reading this file"


@pytest.mark.parametrize("filename", ["notes.docx", "picture.png", "no-extension"])
def test_rejects_unsupported_file_types(user_client: TestClient, filename: str) -> None:
    response = user_client.post("/api/documents", files={"file": (filename, b"data")})

    assert response.status_code == 415


def test_rejects_formats_without_a_parser_yet(user_client: TestClient) -> None:
    response = user_client.post("/api/documents", files={"file": ("book.pdf", b"%PDF-1.7")})

    assert response.status_code == 415
    assert "not supported yet" in response.json()["detail"]


def test_rejects_empty_files(user_client: TestClient) -> None:
    response = user_client.post("/api/documents", files={"file": ("empty.epub", b"")})

    assert response.status_code == 415


def test_rejects_files_over_the_size_limit(
    user_client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    settings.upload.max_bytes = 100

    response = user_client.post("/api/documents", files={"file": ("big.epub", b"x" * 101)})

    assert response.status_code == 413
    assert not list((settings.data_dir / "uploads").glob("*/*"))  # partial file removed


def test_path_in_file_name_is_ignored(
    user_client: TestClient, tmp_path: Path, settings: Settings
) -> None:
    created = upload(user_client, epub_bytes(tmp_path), "../../etc/evil.epub")

    assert created["original_filename"] == "evil.epub"
    assert not (settings.data_dir.parent / "etc").exists()


def test_documents_are_private_to_their_owner(
    user_client: TestClient, session: Session, tmp_path: Path
) -> None:
    created = upload(user_client, epub_bytes(tmp_path))
    log_in(user_client, make_user(session, "other@example.com").email)

    assert user_client.get("/api/documents").json() == []
    assert user_client.get(f"/api/documents/{created['id']}").status_code == 404
    assert user_client.delete(f"/api/documents/{created['id']}").status_code == 404


def test_delete_removes_the_document_and_file(
    user_client: TestClient, tmp_path: Path, settings: Settings
) -> None:
    created = upload(user_client, epub_bytes(tmp_path))

    assert user_client.delete(f"/api/documents/{created['id']}").status_code == 204

    assert user_client.get(f"/api/documents/{created['id']}").status_code == 404
    assert not list((settings.data_dir / "uploads").glob("*/*"))


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/documents").status_code == 401
    assert client.post("/api/documents", files={"file": ("a.epub", b"x")}).status_code == 401
