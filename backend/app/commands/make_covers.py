"""Adds cover thumbnails to ready books processed before covers existed.

    uv run python -m app.commands.make_covers

Safe to run again: books that already have a cover, or have none to offer, are skipped.
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


def make_covers(session_factory: Callable[[], Session], settings: Settings) -> int:
    """How many books got a cover."""
    with session_factory() as session:
        ids = DocumentRepository(session).ready_ids()
    made = 0
    for document_id in ids:
        with session_factory() as session:
            service = DocumentService(session, settings, get_dictionary(settings))
            if service.add_missing_cover(document_id):
                made += 1
    return made


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("covers added: %d", make_covers(SessionLocal, get_settings()))


if __name__ == "__main__":
    main()
