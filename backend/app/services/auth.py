"""Sign-up, email verification, login sessions and password reset.

Responses never reveal whether an email address has an account: register, resend-verification and
forgot-password behave the same either way, and the email itself tells the owner what happened.
"""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings
from app.core.email import Email, EmailSender
from app.core.enums import EmailTokenPurpose
from app.db.models import AuthSession, EmailToken, User
from app.db.types import utcnow
from app.repositories.users import AuthSessionRepository, EmailTokenRepository, UserRepository


class AuthError(Exception):
    """Base class for errors the API turns into 4xx responses."""


class InvalidCredentialsError(AuthError):
    pass


class EmailNotVerifiedError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


@dataclass(frozen=True)
class LoginResult:
    user: User
    session_token: str  # raw token for the cookie; only its hash is stored
    expires_at: datetime


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        session: Session,
        email_sender: EmailSender,
        settings: Settings,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._session = session
        self._email = email_sender
        self._settings = settings
        self._now = clock
        self._users = UserRepository(session)
        self._auth_sessions = AuthSessionRepository(session)
        self._tokens = EmailTokenRepository(session)

    # --- sign-up and verification -------------------------------------------------------------

    def register(self, email: str, password: str, display_name: str) -> None:
        email = normalize_email(email)
        if existing := self._users.get_by_email(email):
            self._email.send(self._already_registered_email(existing))
            return

        user = self._users.add(
            User(
                email=email,
                password_hash=security.hash_password(password),
                display_name=display_name.strip(),
                daily_goal=self._settings.quiz.daily_goal,
            )
        )
        email_to_send = self._verification_email(user)
        self._session.commit()  # save first, so every link we send works
        self._email.send(email_to_send)

    def resend_verification(self, email: str) -> None:
        user = self._users.get_by_email(normalize_email(email))
        if user and user.is_active and user.email_verified_at is None:
            email_to_send = self._verification_email(user)
            self._session.commit()
            self._email.send(email_to_send)

    def verify_email(self, token: str) -> None:
        email_token = self._use_token(token, EmailTokenPurpose.VERIFY_EMAIL)
        user = self._users.get(email_token.user_id)
        if user is None:
            raise InvalidTokenError
        if user.email_verified_at is None:
            user.email_verified_at = self._now()
        self._session.commit()

    # --- login sessions -----------------------------------------------------------------------

    def login(self, email: str, password: str, user_agent: str | None) -> LoginResult:
        user = self._users.get_by_email(normalize_email(email))
        if user is None:
            security.verify_password_against_nothing(password)
            raise InvalidCredentialsError
        if not security.verify_password(user.password_hash, password) or not user.is_active:
            raise InvalidCredentialsError
        if user.email_verified_at is None:
            raise EmailNotVerifiedError

        if security.password_needs_rehash(user.password_hash):
            user.password_hash = security.hash_password(password)

        token = security.new_token()
        now = self._now()
        expires_at = now + timedelta(days=self._settings.auth.session_days)
        self._auth_sessions.add(
            AuthSession(
                user_id=user.id,
                token_hash=security.hash_token(token),
                user_agent=(user_agent or "")[:255] or None,
                created_at=now,
                last_used_at=now,
                expires_at=expires_at,
            )
        )
        self._session.commit()
        return LoginResult(user=user, session_token=token, expires_at=expires_at)

    def user_for_session(self, token: str) -> User | None:
        auth_session = self._auth_sessions.get_by_token_hash(security.hash_token(token))
        if auth_session is None:
            return None
        now = self._now()
        if auth_session.expires_at <= now or not auth_session.user.is_active:
            self._auth_sessions.delete(auth_session)
            self._session.commit()
            return None
        if now - auth_session.last_used_at > timedelta(hours=1):  # avoid a write on every request
            auth_session.last_used_at = now
            self._session.commit()
        return auth_session.user

    def logout(self, token: str) -> None:
        if auth_session := self._auth_sessions.get_by_token_hash(security.hash_token(token)):
            self._auth_sessions.delete(auth_session)
            self._session.commit()

    # --- account deletion ---------------------------------------------------------------------

    def delete_account(self, user: User, password: str) -> None:
        """Deletes the user with all their books, uploads, progress and sessions.

        The database removes everything that belongs to the user (foreign keys cascade); shared
        words and definitions stay. The password is asked again so a borrowed session can't do it.
        """
        if not security.verify_password(user.password_hash, password):
            raise InvalidCredentialsError
        uploads = self._settings.data_dir / "uploads" / str(user.id)
        self._users.delete(user)
        self._session.commit()
        shutil.rmtree(uploads, ignore_errors=True)

    # --- password reset -----------------------------------------------------------------------

    def forgot_password(self, email: str) -> None:
        user = self._users.get_by_email(normalize_email(email))
        if user is None or not user.is_active:
            return
        token = self._issue_token(
            user,
            EmailTokenPurpose.RESET_PASSWORD,
            timedelta(minutes=self._settings.auth.reset_password_minutes),
        )
        link = self._link("reset-password", token)
        minutes = self._settings.auth.reset_password_minutes
        self._session.commit()
        self._email.send(
            Email(
                to=user.email,
                subject="Reset your Vocab Sensei password",
                body=f"Someone asked to reset your password. To choose a new one, open:\n\n{link}"
                f"\n\nThe link works once and expires in {minutes} minutes. "
                "If it wasn't you, ignore this email.",
            )
        )

    def reset_password(self, token: str, new_password: str) -> None:
        email_token = self._use_token(token, EmailTokenPurpose.RESET_PASSWORD)
        user = self._users.get(email_token.user_id)
        if user is None:
            raise InvalidTokenError
        user.password_hash = security.hash_password(new_password)
        # The link proves the user owns the address, so it also counts as verifying it.
        user.email_verified_at = user.email_verified_at or self._now()
        self._auth_sessions.delete_all_for_user(user.id)  # log out everywhere
        self._session.commit()

    # --- helpers ------------------------------------------------------------------------------

    def _verification_email(self, user: User) -> Email:
        hours = self._settings.auth.verify_email_hours
        token = self._issue_token(user, EmailTokenPurpose.VERIFY_EMAIL, timedelta(hours=hours))
        return Email(
            to=user.email,
            subject="Verify your Vocab Sensei email",
            body=f"Welcome, {user.display_name}! Confirm your email address by opening:\n\n"
            f"{self._link('verify-email', token)}\n\nThe link expires in {hours} hours.",
        )

    def _issue_token(self, user: User, purpose: EmailTokenPurpose, ttl: timedelta) -> str:
        now = self._now()
        self._tokens.invalidate_unused(user.id, purpose, now)
        token = security.new_token()
        self._tokens.add(
            EmailToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=security.hash_token(token),
                created_at=now,
                expires_at=now + ttl,
            )
        )
        return token

    def _use_token(self, token: str, purpose: EmailTokenPurpose) -> EmailToken:
        email_token = self._tokens.get_by_token_hash(security.hash_token(token))
        now = self._now()
        if (
            email_token is None
            or email_token.purpose is not purpose
            or email_token.used_at is not None
            or email_token.expires_at <= now
        ):
            raise InvalidTokenError
        email_token.used_at = now
        return email_token

    def _link(self, page: str, token: str) -> str:
        return f"{self._settings.email.app_base_url}/{page}?token={token}"

    def _already_registered_email(self, user: User) -> Email:
        return Email(
            to=user.email,
            subject="You already have a Vocab Sensei account",
            body="Someone tried to create a Vocab Sensei account with this email, but you already "
            "have one. You can log in, or reset your password here:\n\n"
            f"{self._settings.email.app_base_url}/forgot-password\n\n"
            "If it wasn't you, you can ignore this email.",
        )
