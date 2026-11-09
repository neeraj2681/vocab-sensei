"""Friends: finding people by exact username or email, requests, and the friends list."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy.orm import Session

from app.core.enums import Gender
from app.db.models import Friendship, User
from app.repositories.friends import FriendRepository


class FriendError(Exception):
    """Base class for problems the API reports to the user."""


class NoSuchUserError(FriendError):
    pass


class Relation(StrEnum):
    NONE = "none"
    REQUESTED = "requested"  # you asked them; waiting
    ASKED_YOU = "asked_you"  # they asked you
    FRIENDS = "friends"


@dataclass(frozen=True)
class Person:
    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    relation: Relation


@dataclass(frozen=True)
class Friends:
    friends: list[Person]
    asked_you: list[Person]  # incoming requests
    requested: list[Person]  # yours, waiting


class FriendService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = FriendRepository(session)

    def search(self, viewer_id: int, query: str) -> list[Person]:
        """Exact matches only (email or username), so nobody can browse everyone's names or email
        addresses. Found whether or not they show on the leaderboard: friends need a way in."""
        if len(query.strip()) < 2:
            return []
        return [
            self._person(viewer_id, user) for user in self._repo.find(query) if user.id != viewer_id
        ]

    def request(self, viewer_id: int, user_id: int, now: datetime) -> Person:
        """Asks to be friends (or accepts, if they already asked)."""
        user = self._repo.user(user_id)
        if user is None or user.id == viewer_id or not user.is_active:
            raise NoSuchUserError("No such user")
        existing = self._repo.between(viewer_id, user_id)
        if existing is None:
            self._repo.add(Friendship(requester_id=viewer_id, addressee_id=user_id, created_at=now))
        elif existing.accepted_at is None and existing.addressee_id == viewer_id:
            existing.accepted_at = now
        self._session.commit()
        return self._person(viewer_id, user)

    def accept(self, viewer_id: int, user_id: int, now: datetime) -> None:
        existing = self._repo.between(viewer_id, user_id)
        if existing is None or existing.addressee_id != viewer_id:
            raise NoSuchUserError("No request from them")
        existing.accepted_at = existing.accepted_at or now
        self._session.commit()

    def remove(self, viewer_id: int, user_id: int) -> None:
        """Declines their request, cancels yours, or ends the friendship."""
        existing = self._repo.between(viewer_id, user_id)
        if existing is not None:
            self._repo.delete(existing)
            self._session.commit()

    def overview(self, viewer_id: int) -> Friends:
        friends, asked_you, requested = [], [], []
        for f in self._repo.of(viewer_id):
            other_id = f.addressee_id if f.requester_id == viewer_id else f.requester_id
            other = self._repo.user(other_id)
            if other is None:
                continue
            person = self._person(viewer_id, other)
            if person.relation is Relation.FRIENDS:
                friends.append(person)
            elif person.relation is Relation.ASKED_YOU:
                asked_you.append(person)
            else:
                requested.append(person)
        friends.sort(key=lambda p: p.display_name.lower())
        return Friends(friends, asked_you, requested)

    def friend_ids(self, viewer_id: int) -> set[int]:
        return self._repo.friend_ids(viewer_id)

    def _person(self, viewer_id: int, user: User) -> Person:
        f = self._repo.between(viewer_id, user.id)
        if f is None:
            relation = Relation.NONE
        elif f.accepted_at is not None:
            relation = Relation.FRIENDS
        elif f.requester_id == viewer_id:
            relation = Relation.REQUESTED
        else:
            relation = Relation.ASKED_YOU
        return Person(user.id, user.display_name, user.gender, user.has_avatar, relation)
