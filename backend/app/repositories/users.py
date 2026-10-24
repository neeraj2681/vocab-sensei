from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import EmailTokenPurpose
from app.db.models import AuthSession, EmailToken, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalars(select(User).where(User.email == email)).one_or_none()

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user


class AuthSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, auth_session: AuthSession) -> None:
        self._session.add(auth_session)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self._session.scalars(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        ).one_or_none()

    def delete(self, auth_session: AuthSession) -> None:
        self._session.delete(auth_session)

    def delete_all_for_user(self, user_id: int) -> None:
        self._session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


class EmailTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, token: EmailToken) -> None:
        self._session.add(token)

    def get_by_token_hash(self, token_hash: str) -> EmailToken | None:
        return self._session.scalars(
            select(EmailToken).where(EmailToken.token_hash == token_hash)
        ).one_or_none()

    def invalidate_unused(self, user_id: int, purpose: EmailTokenPurpose, now: datetime) -> None:
        """Older links stop working once a new one is sent."""
        for token in self._session.scalars(
            select(EmailToken).where(
                EmailToken.user_id == user_id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
        ):
            token.used_at = now
