from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CurrentReading


class ReadingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for(self, user_id: int) -> list[CurrentReading]:
        """The user's current reads, highest priority (0) first."""
        return list(
            self._session.scalars(
                select(CurrentReading)
                .where(CurrentReading.user_id == user_id)
                .order_by(CurrentReading.priority, CurrentReading.started_at)
            )
        )

    def get(self, user_id: int, document_id: int) -> CurrentReading | None:
        return self._session.get(CurrentReading, (user_id, document_id))

    def add(self, reading: CurrentReading) -> None:
        self._session.add(reading)

    def delete(self, reading: CurrentReading) -> None:
        self._session.delete(reading)
