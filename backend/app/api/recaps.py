from datetime import date
from typing import Annotated, Self

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.quiz import Now, TimeZone
from app.db.session import get_session
from app.services.recaps import Period, Recap, RecapService

router = APIRouter(prefix="/recaps", tags=["recaps"])


def get_recap_service(session: Annotated[Session, Depends(get_session)]) -> RecapService:
    return RecapService(session)


RecapServiceDep = Annotated[RecapService, Depends(get_recap_service)]


class RecapResponse(BaseModel):
    period: Period
    first: date  # or the day the user joined, if later
    last: date  # inclusive
    words_learned: int
    coins: int
    answers: int
    right: int
    goal_days: int
    days: int
    best_day: date | None
    best_day_coins: int
    toughest_word: str | None
    favourite_book: str | None
    streak: int  # at the period's end (now, for the current period)
    current: bool  # still running

    @classmethod
    def of(cls, r: Recap) -> Self:
        return cls(
            period=r.period,
            first=r.first,
            last=r.last,
            words_learned=r.words_learned,
            coins=r.coins,
            answers=r.answers,
            right=r.right,
            goal_days=r.goal_days,
            days=r.days,
            best_day=r.best_day[0] if r.best_day else None,
            best_day_coins=r.best_day[1] if r.best_day else 0,
            toughest_word=r.toughest_word[0] if r.toughest_word else None,
            favourite_book=r.favourite_book[0] if r.favourite_book else None,
            streak=r.streak,
            current=r.current,
        )


class RecapsResponse(BaseModel):
    weeks: list[RecapResponse]  # this week and the last 4, newest first (none before joining)
    months: list[RecapResponse]  # this month and the last 3


@router.get("")
def recaps(user: CurrentUser, service: RecapServiceDep, now: Now, tz: TimeZone) -> RecapsResponse:
    weeks, months = service.recent(user.id, now, tz)
    return RecapsResponse(
        weeks=[RecapResponse.of(r) for r in weeks], months=[RecapResponse.of(r) for r in months]
    )
