"""The Shop: what's on sale, buying (Sundays only) and using what's in the inventory."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import ShopPurchase, User
from app.quiz.shop import DOUBLE_COINS_FOR, MAX_OWNED, PRICES, Item, Window, shop_window
from app.repositories.quiz import QuizRepository


class ShopError(Exception):
    """Base class for problems the API reports to the user."""


class ShopClosedError(ShopError):
    pass


class LimitReachedError(ShopError):
    pass


class NotEnoughCoinsError(ShopError):
    pass


class NothingToUseError(ShopError):
    pass


@dataclass(frozen=True)
class Stock:
    item: Item
    price: int
    owned: int  # in the inventory now
    max_owned: int


@dataclass(frozen=True)
class ShopState:
    window: Window
    coins: int
    stock: list[Stock]
    double_coins_until: datetime | None


class ShopService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = QuizRepository(session)

    def state(self, user_id: int, now: datetime, tz: ZoneInfo) -> ShopState:
        user = self._user(user_id)
        return ShopState(
            window=shop_window(now.astimezone(tz)),
            coins=self._repo.total_points(user.id),
            stock=[
                Stock(item, PRICES[item], len(self._repo.unused(user.id, item)), MAX_OWNED[item])
                for item in Item
            ],
            double_coins_until=(
                user.double_coins_until
                if user.double_coins_until and user.double_coins_until > now
                else None
            ),
        )

    def buy(self, user_id: int, item: Item, now: datetime, tz: ZoneInfo) -> None:
        state = self.state(user_id, now, tz)
        if not state.window.open:
            raise ShopClosedError("The Shop is open on Sundays")
        stock = next(s for s in state.stock if s.item is item)
        if stock.owned >= stock.max_owned:
            raise LimitReachedError(f"You can keep at most {stock.max_owned} of these")
        if state.coins < stock.price:
            raise NotEnoughCoinsError("Not enough coins yet")
        self._session.add(
            ShopPurchase(user_id=user_id, item=item, coins=stock.price, bought_at=now)
        )
        self._session.commit()

    def use_double_coins(self, user_id: int, now: datetime) -> datetime:
        """Starts half an hour of double coins (added on, if some are still running)."""
        user = self._user(user_id)
        unused = self._repo.unused(user.id, Item.DOUBLE_COINS)
        if not unused:
            raise NothingToUseError("No double coins in your inventory")
        unused[0].used_at = now
        running = user.double_coins_until
        start = running if running and running > now else now
        user.double_coins_until = start + DOUBLE_COINS_FOR
        self._session.commit()
        return user.double_coins_until

    def _user(self, user_id: int) -> User:
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        return user
