import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services.catalogue import (
    Catalogue,
    CatalogueBook,
    CatalogueUnavailableError,
    catalogue_path,
    refresh_catalogue,
)

SAMPLE = Path(__file__).parent / "data" / "pg_catalog_sample.csv"


@pytest.fixture
def catalogue() -> Catalogue:
    return Catalogue(SAMPLE)


def ids(books: list[CatalogueBook]) -> list[int]:
    return [b.gutenberg_id for b in books]


def test_title_search(catalogue: Catalogue) -> None:
    assert 1342 in ids(catalogue.search("pride"))


def test_author_search(catalogue: Catalogue) -> None:
    assert ids(catalogue.search("austen")) == [158, 1342]


def test_prefix_tokens(catalogue: Catalogue) -> None:
    assert ids(catalogue.search("pri prej")) == [1342]


def test_title_matches_rank_first(catalogue: Catalogue) -> None:
    # "jane": 5000 matches by title; 158 and 1342 only by author
    assert ids(catalogue.search("jane")) == [5000, 158, 1342]


def test_french_and_sound_rows_are_dropped(catalogue: Catalogue) -> None:
    assert catalogue.search("misérables") == []
    assert catalogue.search("hugo") == []
    assert 9000 not in ids(catalogue.search("pride"))
    assert catalogue.get(9000) is None


def test_newline_title_and_two_authors(catalogue: Catalogue) -> None:
    assert catalogue.get(345).title == "Dracula Illustrated"  # type: ignore[union-attr]
    assert ids(catalogue.search("pratchett")) == [8800]


def test_empty_query_and_limit(catalogue: Catalogue) -> None:
    assert catalogue.search("  ") == []
    assert len(catalogue.search("jane", limit=1)) == 1


def test_get(catalogue: Catalogue) -> None:
    book = catalogue.get(1342)
    assert book is not None and book.title == "Pride and Prejudice"
    assert catalogue.get(999999) is None


def test_missing_file_raises(tmp_path: Path) -> None:
    missing = Catalogue(tmp_path / "nope.csv")
    with pytest.raises(CatalogueUnavailableError):
        missing.search("pride")
    with pytest.raises(CatalogueUnavailableError):
        missing.get(1)


def fake_fetch(calls: list[str]):  # type: ignore[no-untyped-def]
    def fetch(url: str, path: Path) -> None:
        calls.append(url)
        path.write_bytes(SAMPLE.read_bytes())

    return fetch


def test_refresh_downloads_when_missing_then_not_when_fresh(tmp_path: Path) -> None:
    path = catalogue_path(tmp_path)
    calls: list[str] = []
    assert refresh_catalogue(path, fake_fetch(calls)) is True
    assert path.exists()
    assert refresh_catalogue(path, fake_fetch(calls)) is False
    assert len(calls) == 1
    assert not list(path.parent.glob("*.part"))


def test_refresh_again_when_older_than_a_week(tmp_path: Path) -> None:
    path = catalogue_path(tmp_path)
    calls: list[str] = []
    refresh_catalogue(path, fake_fetch(calls))
    old = (datetime.now() - timedelta(days=8)).timestamp()
    os.utime(path, (old, old))
    assert refresh_catalogue(path, fake_fetch(calls)) is True
    assert len(calls) == 2
    assert not list(path.parent.glob("*.part"))
