from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.quiz import Now, QuizServiceDep, TimeZone
from app.db.session import get_session
from app.quiz.shop import Item
from app.services.shop import (
    LimitReachedError,
    NotEnoughCoinsError,
    NothingToUseError,
    ShopClosedError,
    ShopService,
    ShopState,
)

router = APIRouter(prefix="/shop", tags=["shop"])


def get_shop_service(session: Annotated[Session, Depends(get_session)]) -> ShopService:
    return ShopService(session)


ShopServiceDep = Annotated[ShopService, Depends(get_shop_service)]


class StockResponse(BaseModel):
    item: Item
    price: int
    owned: int
    max_owned: int


class ShopResponse(BaseModel):
    open: bool  # open all of Sunday
    opens_at: datetime  # this Sunday's start if open, else next Sunday's
    closes_at: datetime
    coins: int  # to spend
    stock: list[StockResponse]
    double_coins_until: datetime | None  # double coins running until then

    @classmethod
    def of(cls, state: ShopState) -> Self:
        return cls(
            open=state.window.open,
            opens_at=state.window.opens_at,
            closes_at=state.window.closes_at,
            coins=state.coins,
            stock=[
                StockResponse(item=s.item, price=s.price, owned=s.owned, max_owned=s.max_owned)
                for s in state.stock
            ],
            double_coins_until=state.double_coins_until,
        )


@router.get("")
def shop(
    user: CurrentUser, shop: ShopServiceDep, quiz: QuizServiceDep, now: Now, tz: TimeZone
) -> ShopResponse:
    """What's on sale, what's in the inventory, and when the Shop opens or closes."""
    quiz.apply_streak_freezes(user.id, now, tz)  # so the inventory count is current
    return ShopResponse.of(shop.state(user.id, now, tz))


@router.post("/buy/{item}")
def buy(
    item: Item, user: CurrentUser, shop: ShopServiceDep, now: Now, tz: TimeZone
) -> ShopResponse:
    try:
        shop.buy(user.id, item, now, tz)
    except ShopClosedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except (LimitReachedError, NotEnoughCoinsError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return ShopResponse.of(shop.state(user.id, now, tz))


@router.post("/use/double_coins")
def use_double_coins(
    user: CurrentUser, shop: ShopServiceDep, now: Now, tz: TimeZone
) -> ShopResponse:
    """Starts 30 minutes of double coins on right answers (any day, not just Sundays)."""
    try:
        shop.use_double_coins(user.id, now)
    except NothingToUseError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return ShopResponse.of(shop.state(user.id, now, tz))
