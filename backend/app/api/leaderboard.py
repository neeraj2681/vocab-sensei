from datetime import date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SettingsDep
from app.api.quiz import Now, TimeZone
from app.core.enums import Gender
from app.db.session import get_session
from app.services.leaderboard import LeaderboardService, ProfileNotFoundError, PublicProfile

router = APIRouter(tags=["leaderboard"])


def get_leaderboard_service(
    session: Annotated[Session, Depends(get_session)], settings: SettingsDep
) -> LeaderboardService:
    return LeaderboardService(session, settings)


LeaderboardServiceDep = Annotated[LeaderboardService, Depends(get_leaderboard_service)]


class RowResponse(BaseModel):
    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    coins_today: int
    me: bool


class DayPoints(BaseModel):
    date: date
    answers: int
    met: bool
    points: int


class HistoryPointResponse(BaseModel):
    number: int
    total: int
    correct: bool
    answered_at: datetime


class BookResponse(BaseModel):
    title: str
    author: str | None


class ProfileResponse(BaseModel):
    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    me: bool
    coins: int
    coins_today: int
    streak: int
    words_learned: int
    answers: int
    right: int
    week: list[DayPoints]
    history: list[HistoryPointResponse]
    books: list[BookResponse]

    @classmethod
    def of(cls, p: PublicProfile) -> Self:
        return cls(
            user_id=p.user_id,
            display_name=p.display_name,
            gender=p.gender,
            has_avatar=p.has_avatar,
            me=p.me,
            coins=p.coins,
            coins_today=p.coins_today,
            streak=p.streak,
            words_learned=p.words_learned,
            answers=p.answers,
            right=p.right,
            week=[
                DayPoints(date=d.date, answers=d.answers, met=d.met, points=d.points)
                for d in p.week
            ],
            history=[
                HistoryPointResponse(
                    number=h.number, total=h.total, correct=h.correct, answered_at=h.answered_at
                )
                for h in p.history
            ],
            books=[BookResponse(title=b.title, author=b.author) for b in p.books],
        )


@router.get("/leaderboard")
def leaderboard(
    user: CurrentUser, board: LeaderboardServiceDep, now: Now, tz: TimeZone
) -> list[RowResponse]:
    """Everyone on the leaderboard, by coins earned today (in the viewer's time zone)."""
    return [
        RowResponse(
            user_id=r.user_id,
            display_name=r.display_name,
            gender=r.gender,
            has_avatar=r.has_avatar,
            coins_today=r.coins_today,
            me=r.me,
        )
        for r in board.today(user.id, now, tz)
    ]


@router.get("/profiles/{user_id}")
def profile(
    user_id: int, user: CurrentUser, board: LeaderboardServiceDep, now: Now, tz: TimeZone
) -> ProfileResponse:
    """A user's public profile (anyone on the leaderboard, or yourself)."""
    try:
        return ProfileResponse.of(board.profile(user.id, user_id, now, tz))
    except ProfileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None


@router.get("/profiles/{user_id}/avatar", response_class=FileResponse)
def avatar(user_id: int, user: CurrentUser, board: LeaderboardServiceDep) -> FileResponse:
    try:
        path = board.avatar(user.id, user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
