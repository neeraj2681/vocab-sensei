from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.quiz import Now
from app.core.enums import Gender
from app.db.session import get_session
from app.services.friends import FriendService, NoSuchUserError, Person, Relation

router = APIRouter(prefix="/friends", tags=["friends"])


def get_friend_service(session: Annotated[Session, Depends(get_session)]) -> FriendService:
    return FriendService(session)


FriendServiceDep = Annotated[FriendService, Depends(get_friend_service)]


class PersonResponse(BaseModel):
    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    relation: Relation


def person(p: Person) -> PersonResponse:
    return PersonResponse(
        user_id=p.user_id,
        display_name=p.display_name,
        gender=p.gender,
        has_avatar=p.has_avatar,
        relation=p.relation,
    )


class FriendsResponse(BaseModel):
    friends: list[PersonResponse]
    asked_you: list[PersonResponse]  # requests waiting for you
    requested: list[PersonResponse]  # your requests, waiting for them


@router.get("")
def overview(user: CurrentUser, friends: FriendServiceDep) -> FriendsResponse:
    o = friends.overview(user.id)
    return FriendsResponse(
        friends=[person(p) for p in o.friends],
        asked_you=[person(p) for p in o.asked_you],
        requested=[person(p) for p in o.requested],
    )


@router.get("/search")
def search(
    user: CurrentUser,
    friends: FriendServiceDep,
    q: Annotated[str, Query(max_length=320, description="an exact username or email")],
) -> list[PersonResponse]:
    """People whose username or email is exactly `q`."""
    return [person(p) for p in friends.search(user.id, q)]


@router.post("/{user_id}")
def request(user_id: int, user: CurrentUser, friends: FriendServiceDep, now: Now) -> PersonResponse:
    """Sends a friend request (or accepts theirs)."""
    try:
        return person(friends.request(user.id, user_id, now))
    except NoSuchUserError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None


@router.post("/{user_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept(user_id: int, user: CurrentUser, friends: FriendServiceDep, now: Now) -> None:
    try:
        friends.accept(user.id, user_id, now)
    except NoSuchUserError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(user_id: int, user: CurrentUser, friends: FriendServiceDep) -> None:
    """Declines their request, cancels yours, or ends the friendship."""
    friends.remove(user.id, user_id)
