"""Fills in the meaning each word's sentence uses, for books processed before meanings were stored.

    uv run python -m app.commands.reindex_meanings

Only the meaning rank of each word row changes; word lists, chapters, sentences and everyone's
progress are untouched. Safe to run again: a second run changes nothing.
"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.api.deps import get_dictionary
from app.core.config import Settings, get_settings
from app.db.models import Document
from app.db.session import SessionLocal
from app.repositories.documents import DocumentRepository
from app.services.words import WordService

logger = logging.getLogger(__name__)


def reindex(session_factory: Callable[[], Session], settings: Settings) -> int:
    """Every READY document, one at a time (one session + commit per book); returns rows changed."""
    dictionary = get_dictionary(settings)()  # load the dictionary once, not per book
    with session_factory() as session:
        ids = DocumentRepository(session).ready_ids()
    changed = 0
    for document_id in ids:
        with session_factory() as session:
            document = session.get(Document, document_id)
            if document is None:  # deleted since the list was read
                continue
            count = WordService(session).reindex_meanings(document_id, dictionary)
            session.commit()
        changed += count
        logger.info("%s: %d meanings set", document.title, count)
    return changed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"set {reindex(SessionLocal, get_settings())} meanings")


if __name__ == "__main__":
    main()
