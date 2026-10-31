from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PushSubscription, Reminder, User


class ReminderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> Reminder | None:
        return self._session.get(Reminder, user_id)

    def enabled(self) -> list[tuple[Reminder, User]]:
        return [
            (reminder, user)
            for reminder, user in self._session.execute(
                select(Reminder, User)
                .join(User, User.id == Reminder.user_id)
                .where(Reminder.enabled.is_(True), User.is_active.is_(True))
            )
        ]

    def subscriptions(self, user_id: int) -> list[PushSubscription]:
        return list(
            self._session.scalars(
                select(PushSubscription).where(PushSubscription.user_id == user_id)
            )
        )

    def subscription(self, endpoint: str) -> PushSubscription | None:
        return self._session.scalars(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        ).first()

    def add(self, item: Reminder | PushSubscription) -> None:
        self._session.add(item)

    def delete(self, item: PushSubscription) -> None:
        self._session.delete(item)
