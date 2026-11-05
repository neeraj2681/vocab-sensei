from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Friendship, User


class FriendRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find(self, query: str) -> list[User]:
        """Verified, active users whose username or email is exactly `query` (any case)."""
        q = query.strip().lower()
        return list(
            self._session.scalars(
                select(User)
                .where(
                    User.is_active.is_(True),
                    User.email_verified_at.is_not(None),
                    or_(func.lower(User.display_name) == q, User.email == q),
                )
                .order_by(User.id)
                .limit(20)
            )
        )

    def between(self, a: int, b: int) -> Friendship | None:
        return self._session.scalars(
            select(Friendship).where(
                or_(
                    (Friendship.requester_id == a) & (Friendship.addressee_id == b),
                    (Friendship.requester_id == b) & (Friendship.addressee_id == a),
                )
            )
        ).first()

    def of(self, user_id: int) -> list[Friendship]:
        """Every request and friendship the user is part of."""
        return list(
            self._session.scalars(
                select(Friendship)
                .where(or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id))
                .order_by(Friendship.created_at)
            )
        )

    def friend_ids(self, user_id: int) -> set[int]:
        return {
            f.addressee_id if f.requester_id == user_id else f.requester_id
            for f in self.of(user_id)
            if f.accepted_at is not None
        }

    def user(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def add(self, friendship: Friendship) -> None:
        self._session.add(friendship)

    def delete(self, friendship: Friendship) -> None:
        self._session.delete(friendship)
