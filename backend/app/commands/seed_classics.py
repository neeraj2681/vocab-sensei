"""Adds the built-in classics: downloads each EPUB from Project Gutenberg once and processes it.

    uv run python -m app.commands.seed_classics

Safe to run again: books already ready are skipped, failed ones are retried. The Docker image runs
it in the background on every start.
"""

import logging
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.api.deps import DictionaryLoader, get_dictionary
from app.core.config import Settings, get_settings
from app.core.enums import DocumentFormat, DocumentStatus
from app.db.models import Document
from app.db.session import SessionLocal
from app.repositories.documents import DocumentRepository
from app.services.documents import DocumentService
from app.services.library import CLASSICS, Classic

logger = logging.getLogger(__name__)

Download = Callable[[str, Path], None]


def download(url: str, path: Path) -> None:
    """Fetches `url` to `path`, retrying a few times (Gutenberg can be slow)."""
    request = urllib.request.Request(url, headers={"User-Agent": "vocab-sensei (book seeding)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".part")
            partial.write_bytes(data)
            partial.rename(path)  # never leave a half-written book behind
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def seed(
    session_factory: Callable[[], Session],
    settings: Settings,
    dictionary: DictionaryLoader,
    fetch: Download = download,
) -> list[str]:
    """Makes sure every classic is ready; returns the titles that were added this time."""
    added = []
    for classic in CLASSICS:
        with session_factory() as session:
            if _seed_one(session, settings, dictionary, fetch, classic):
                added.append(classic.title)
    return added


def _seed_one(
    session: Session,
    settings: Settings,
    dictionary: DictionaryLoader,
    fetch: Download,
    classic: Classic,
) -> bool:
    documents = DocumentRepository(session)
    existing = documents.classic_by_filename(classic.filename)
    if existing is not None and existing.status == DocumentStatus.READY:
        return False
    relative = Path("library", classic.filename)
    path = settings.data_dir / relative
    if not path.exists():
        logger.info("downloading %s", classic.title)
        try:
            fetch(classic.url, path)
        except OSError:
            logger.exception("couldn't download %s; will retry next time", classic.title)
            return False
    if existing is None:
        existing = documents.add(
            Document(
                owner_user_id=None,
                title=classic.title,
                original_filename=classic.filename,
                file_path=relative.as_posix(),
                format=DocumentFormat.EPUB,
                status=DocumentStatus.UPLOADED,
            )
        )
        session.commit()
    logger.info("processing %s", classic.title)
    DocumentService(session, settings, dictionary).process(existing.id)
    return existing.status == DocumentStatus.READY


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    added = seed(SessionLocal, settings, get_dictionary(settings))
    logger.info("classics ready; added this run: %s", ", ".join(added) or "none")


if __name__ == "__main__":
    main()
