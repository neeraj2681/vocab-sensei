"""Project Gutenberg's catalogue: download it weekly and search English books by title or author."""

import csv
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

CATALOGUE_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
MAX_AGE = timedelta(days=7)

_TOKEN = re.compile(r"[a-z0-9]+")


class CatalogueUnavailableError(Exception):
    """The catalogue file has not been downloaded yet."""


@dataclass(frozen=True)
class CatalogueBook:
    gutenberg_id: int
    title: str
    authors: str


def catalogue_path(data_dir: Path) -> Path:
    return data_dir / "gutenberg" / "pg_catalog.csv"


def download(url: str, path: Path) -> None:
    """Fetches `url` to `path`, retrying a few times (Gutenberg can be slow)."""
    request = urllib.request.Request(url, headers={"User-Agent": "vocab-sensei (catalogue)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".part")
            partial.write_bytes(data)
            partial.rename(path)  # never leave a half-written file behind
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def is_stale(path: Path, now: datetime | None = None) -> bool:
    """True when the file is missing or older than MAX_AGE."""
    if not path.exists():
        return True
    current = now or datetime.now()
    return current - datetime.fromtimestamp(path.stat().st_mtime) > MAX_AGE


def refresh_catalogue(
    path: Path,
    fetch: Callable[[str, Path], None] = download,
    now: datetime | None = None,
) -> bool:
    """Downloads the catalogue if it's missing or older than MAX_AGE; True if it downloaded.

    Writes to a .part file first and renames, so a half-written file is never read."""
    if not is_stale(path, now):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    try:
        fetch(CATALOGUE_URL, partial)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return True


@dataclass(frozen=True)
class _Entry:
    book: CatalogueBook
    title_tokens: tuple[str, ...]
    author_tokens: tuple[str, ...]


_cache: dict[tuple[Path, float], list[_Entry]] = {}


def _load(path: Path) -> list[_Entry]:
    try:
        key = (path, path.stat().st_mtime)
    except OSError as error:
        raise CatalogueUnavailableError(str(path)) from error
    if key not in _cache:
        _cache.clear()  # keep only the newest file's books in memory
        entries: list[_Entry] = []
        with path.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                languages = {code.strip() for code in (row.get("Language") or "").split(";")}
                if row.get("Type") != "Text" or "en" not in languages:
                    continue
                try:
                    gutenberg_id = int(row["Text#"])
                except (KeyError, ValueError):
                    continue
                title = " ".join((row.get("Title") or "").split())
                authors = row.get("Authors") or ""
                entries.append(
                    _Entry(
                        CatalogueBook(gutenberg_id, title, authors),
                        tuple(_TOKEN.findall(title.lower())),
                        tuple(_TOKEN.findall(authors.lower())),
                    )
                )
        for stale in [k for k in _cache if k[0] == path]:
            del _cache[stale]
        _cache[key] = entries
    return _cache[key]


def _all_match(tokens: list[str], words: tuple[str, ...]) -> bool:
    return all(any(word.startswith(token) for word in words) for token in tokens)


class Catalogue:
    def __init__(self, path: Path) -> None:
        self._path = path

    def search(self, query: str, limit: int = 20) -> list[CatalogueBook]:
        tokens = _TOKEN.findall(query.lower())
        entries = _load(self._path)
        if not tokens:
            return []
        in_title: list[CatalogueBook] = []
        elsewhere: list[CatalogueBook] = []
        for entry in entries:
            if _all_match(tokens, entry.title_tokens):
                in_title.append(entry.book)
            elif _all_match(tokens, entry.title_tokens + entry.author_tokens):
                elsewhere.append(entry.book)

        def order(book: CatalogueBook) -> tuple[int, int]:
            return (len(book.title), book.gutenberg_id)

        return (sorted(in_title, key=order) + sorted(elsewhere, key=order))[:limit]

    def get(self, gutenberg_id: int) -> CatalogueBook | None:
        for entry in _load(self._path):
            if entry.book.gutenberg_id == gutenberg_id:
                return entry.book
        return None
