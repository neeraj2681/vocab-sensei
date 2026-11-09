"""What people change about themselves: name (once, for now), gender and picture."""

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Gender
from app.core.images import square_avatar
from app.core.newsletter import NewsletterList, NoNewsletterList
from app.db.models import User
from app.quiz.shop import Item
from app.repositories.quiz import QuizRepository

MAX_AVATAR_BYTES = 5 * 1024 * 1024


class ProfileError(Exception):
    pass


class NameAlreadyChangedError(ProfileError):
    pass


class ProfileService:
    def __init__(
        self, session: Session, settings: Settings, newsletter: NewsletterList | None = None
    ) -> None:
        self._session = session
        self._settings = settings
        self._newsletter = newsletter or NoNewsletterList()

    def change_name(self, user: User, name: str, now: datetime) -> None:
        """The first change is free; after it, each change uses a name change bought in the Shop."""
        name = name.strip()
        if not name:
            raise ProfileError("Enter a name")
        if name == user.display_name:
            return
        if user.name_changed_at is not None:
            bought = QuizRepository(self._session).unused(user.id, Item.NAME_CHANGE)
            if not bought:
                raise NameAlreadyChangedError("You've already used your one name change")
            bought[0].used_at = now
        user.display_name, user.name_changed_at = name, now
        self._session.commit()

    def set_gender(self, user: User, gender: Gender) -> None:
        user.gender = gender
        self._session.commit()

    def set_on_leaderboard(self, user: User, show: bool) -> None:
        user.show_on_leaderboard = show
        self._session.commit()

    def set_show_books(self, user: User, show: bool) -> None:
        user.show_books = show
        self._session.commit()

    def set_newsletter(self, user: User, subscribe: bool, now: datetime) -> None:
        """Brevo's list follows at once for a verified address, otherwise when it gets verified."""
        if subscribe == user.newsletter:
            return
        user.newsletter_since = now if subscribe else None
        self._session.commit()
        if not subscribe:
            self._newsletter.remove(user.email)
        elif user.email_verified_at is not None:
            self._newsletter.add(user.email, user.display_name)

    def set_avatar(self, user: User, data: bytes) -> None:
        if len(data) > MAX_AVATAR_BYTES:
            raise ProfileError("Pick a picture under 5 MB")
        picture = square_avatar(data)  # raises NotAnImageError
        relative = Path("avatars", f"{user.id}.jpg")
        path = self._settings.data_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(picture)
        user.avatar_path = relative.as_posix()
        self._session.commit()

    def remove_avatar(self, user: User) -> None:
        if user.avatar_path:
            (self._settings.data_dir / user.avatar_path).unlink(missing_ok=True)
        user.avatar_path = None
        self._session.commit()

    def avatar_file(self, user: User) -> Path | None:
        if not user.avatar_path:
            return None
        path = self._settings.data_dir / user.avatar_path
        return path if path.is_file() else None
