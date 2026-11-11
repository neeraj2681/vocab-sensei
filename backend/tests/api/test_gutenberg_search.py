import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import gutenberg
from app.core.config import Settings
from app.services.catalogue import catalogue_path

SAMPLE = Path(__file__).parent.parent / "services" / "data" / "pg_catalog_sample.csv"


@pytest.fixture
def no_refresh(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []
    monkeypatch.setattr(gutenberg, "refresh_catalogue", lambda path: calls.append(path))
    return calls


def test_search_returns_books(
    user_client: TestClient, settings: Settings, no_refresh: list[Path]
) -> None:
    path = catalogue_path(settings.data_dir)
    path.parent.mkdir(parents=True)
    shutil.copy(SAMPLE, path)
    response = user_client.get("/api/library/gutenberg", params={"q": "pride prej"})
    assert response.status_code == 200
    assert response.json() == [
        {"gutenberg_id": 1342, "title": "Pride and Prejudice", "authors": "Austen, Jane, 1775-1817"}
    ]
    assert no_refresh == []  # fresh file: nothing scheduled


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/library/gutenberg", params={"q": "pride"}).status_code == 401


def test_missing_catalogue_is_503_and_schedules_refresh(
    user_client: TestClient, settings: Settings, no_refresh: list[Path]
) -> None:
    response = user_client.get("/api/library/gutenberg", params={"q": "pride"})
    assert response.status_code == 503
    assert (
        response.json()["detail"] == "The book catalogue is being prepared. Try again in a minute."
    )
    assert no_refresh == [catalogue_path(settings.data_dir)]
