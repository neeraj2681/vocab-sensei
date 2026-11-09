"""Deletes the files of uploaded books that have already been read (done for new uploads since
they began to be discarded; this clears the ones from before).

    uv run python -m app.commands.discard_uploads

Word lists, chapters, sentences, covers and everyone's progress are untouched. Built-in classics
keep their files. Safe to run again.
"""

import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_dictionary
from app.core.config import Settings, get_settings
from app.core.enums import DocumentStatus
from app.db.models import Document
from app.db.session import SessionLocal
from app.services.documents import DocumentService

logger = logging.getLogger(__name__)


def discard(session_factory: Callable[[], Session], settings: Settings) -> int:
    """How many files were deleted."""
    deleted = 0
    with session_factory() as session:
        service = DocumentService(session, settings, get_dictionary(settings))
        read = (DocumentStatus.READY, DocumentStatus.FAILED)  # not ones still waiting to be read
        for document in session.scalars(select(Document).where(Document.status.in_(read))):
            if service.discard_upload(document):
                deleted += 1
                logger.info("document %s: file deleted", document.id)
    return deleted


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"deleted {discard(SessionLocal, get_settings())} uploaded files")


if __name__ == "__main__":
    main()
