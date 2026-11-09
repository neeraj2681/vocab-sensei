"""Gives readers who never took the placement check a word level from their past answers (the
first answer to each word, right or wrong, and the words they marked as known).

    uv run python -m app.commands.estimate_levels

Readers with a level already, or too few answers, are left as they are. Safe to run again.
"""

import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_dictionary
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import SessionLocal
from app.services.placement import PlacementService

logger = logging.getLogger(__name__)


def estimate(session_factory: Callable[[], Session], settings: Settings) -> int:
    """How many readers got a level."""
    given = 0
    with session_factory() as session:
        service = PlacementService(session, get_dictionary(settings))
        for user in session.scalars(select(User).where(User.vocab_level.is_(None))):
            level = service.estimate_from_history(user.id)
            if level is not None:
                user.vocab_level = level
                given += 1
                logger.info("user %s: level %s", user.id, level)
        session.commit()
    return given


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"{estimate(SessionLocal, get_settings())} readers got a word level")


if __name__ == "__main__":
    main()
