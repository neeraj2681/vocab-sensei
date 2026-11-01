"""Records every chapter each book's words appear in, for books processed before that was stored.

    uv run python -m app.commands.reindex_chapters

Re-reads each ready book from its file; word lists and everyone's progress are untouched. Safe to
run again.
"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.api.deps import get_dictionary
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.repositories.documents import DocumentRepository
from app.services.documents import DocumentService

logger = logging.getLogger(__name__)


def reindex(session_factory: Callable[[], Session], settings: Settings) -> tuple[int, int]:
    """(books updated, books skipped)."""
    with session_factory() as session:
        ids = DocumentRepository(session).ready_ids()
    updated = 0
    for document_id in ids:
        with session_factory() as session:
            service = DocumentService(session, settings, get_dictionary(settings))
            if service.reindex_chapters(document_id):
                updated += 1
                logger.info("document %s: chapters recorded", document_id)
    return updated, len(ids) - updated


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    updated, skipped = reindex(SessionLocal, get_settings())
    logger.info("done: %d books updated, %d skipped", updated, skipped)


if __name__ == "__main__":
    main()
