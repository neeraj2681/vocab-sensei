"""Daily reminders: each user's settings and the devices that accept push notifications."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ReminderChannel
from app.db.base import Base
from app.db.types import UTCDateTime, str_enum, utcnow


class Reminder(Base):
    """A nudge at `time` (in `timezone`) on days the daily goal isn't met yet."""

    __tablename__ = "reminders"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(default=False)
    time: Mapped[str] = mapped_column(String(5), default="20:00")  # HH:MM, local time
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")  # IANA name
    channel: Mapped[ReminderChannel] = mapped_column(
        str_enum(ReminderChannel), default=ReminderChannel.PUSH
    )
    last_sent_on: Mapped[date | None] = mapped_column(Date)  # local date, so once a day at most


class PushSubscription(Base):
    """A browser/device that agreed to receive notifications (Web Push)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True)  # the push service URL
    p256dh: Mapped[str] = mapped_column(String(200))  # the browser's public key
    auth: Mapped[str] = mapped_column(String(100))  # the browser's auth secret
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
