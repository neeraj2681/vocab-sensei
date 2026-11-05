"""Daily reminders: a nudge at the user's chosen time on days the daily goal isn't met yet.

`send_due` runs every minute (see app.main). A reminder goes out at most once per local day: on
or after the chosen time, unless the user already answered enough questions today. Push goes to
every device the user enabled; a device that unsubscribed is forgotten. Email uses the normal
mail settings.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from threading import Event
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.email import Email, EmailSender
from app.core.push import PushError, PushSender, PushTarget, SubscriptionGoneError
from app.db.models import PushSubscription, Reminder, User
from app.repositories.quiz import QuizRepository
from app.repositories.reminders import ReminderRepository
from app.services.quiz import Stats, quiz_stats
from app.services.recaps import Period, RecapService, months_before, recap_text, weeks_before

logger = logging.getLogger(__name__)

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ReminderError(Exception):
    """A request the API rejects with the message as the reason."""


@dataclass(frozen=True)
class ReminderView:
    enabled: bool
    time: str
    timezone: str
    push: bool  # notifications on this person's devices
    email: bool
    devices: int  # devices with push turned on


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ReminderError(f"Unknown time zone {name!r}") from None


def message(stats: Stats) -> str:
    left = max(stats.daily_goal - stats.today, 0)
    progress = f"{stats.today}/{stats.daily_goal} today"
    if stats.streak > 0:
        return f"{progress}: {left} more answers keep your 🔥 {stats.streak}-day streak."
    return f"{progress}: {left} more answers reach today's goal."


class ReminderService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        email_sender: EmailSender,
        push_sender: PushSender,
    ) -> None:
        self._session = session
        self._settings = settings
        self._email = email_sender
        self._push = push_sender
        self._repo = ReminderRepository(session)
        self._quiz = QuizRepository(session)

    # Settings

    def view(self, user_id: int) -> ReminderView:
        reminder = self._repo.get(user_id) or Reminder(
            user_id=user_id,
            enabled=False,
            time="20:00",
            timezone="UTC",
            push=True,
            email=False,
        )
        return ReminderView(
            enabled=reminder.enabled,
            time=reminder.time,
            timezone=reminder.timezone,
            push=reminder.push,
            email=reminder.email,
            devices=len(self._repo.subscriptions(user_id)),
        )

    def update(
        self, user_id: int, *, enabled: bool, at: str, timezone: str, push: bool, email: bool
    ) -> ReminderView:
        if not _TIME.match(at):
            raise ReminderError("Use a time like 20:00")
        if enabled and not (push or email):
            raise ReminderError("Choose notifications, email or both")
        zone(timezone)
        reminder = self._repo.get(user_id)
        if reminder is None:
            reminder = Reminder(user_id=user_id)
            self._repo.add(reminder)
        changed_time = reminder.time != at or reminder.timezone != timezone
        reminder.enabled, reminder.time, reminder.timezone = enabled, at, timezone
        reminder.push, reminder.email = push, email
        if changed_time:
            reminder.last_sent_on = None  # a new time may still fire today
        self._session.commit()
        return self.view(user_id)

    def subscribe(self, user_id: int, endpoint: str, p256dh: str, auth: str) -> None:
        existing = self._repo.subscription(endpoint)
        if existing is not None:  # the same browser again, perhaps for another account
            existing.user_id, existing.p256dh, existing.auth = user_id, p256dh, auth
        else:
            self._repo.add(
                PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
            )
        self._session.commit()

    def unsubscribe(self, user_id: int, endpoint: str) -> None:
        existing = self._repo.subscription(endpoint)
        if existing is not None and existing.user_id == user_id:
            self._repo.delete(existing)
            self._session.commit()

    # Sending

    def send_test(self, user: User, now: datetime) -> bool:
        """Sends one reminder now, whatever the time and goal. True if anything went out."""
        view = self.view(user.id)
        stats = quiz_stats(self._quiz, user, now, zone(view.timezone))
        return self._send(user, stats, push=view.push, email=view.email)

    def send_due(self, now: datetime) -> int:
        """Sends every reminder that is due; returns how many went out."""
        sent = 0
        for reminder, user in self._repo.enabled():
            try:
                tz = zone(reminder.timezone)
            except ReminderError:
                continue
            local = now.astimezone(tz)
            hour, minute = (int(part) for part in reminder.time.split(":"))
            if reminder.last_sent_on == local.date() or local.time() < time(hour, minute):
                continue
            reminder.last_sent_on = local.date()  # checked today, sent or not
            stats = quiz_stats(self._quiz, user, now, tz)
            due = stats.today < stats.daily_goal
            if due and self._send(user, stats, push=reminder.push, email=reminder.email):
                sent += 1
            self._session.commit()
        return sent

    def send_recaps(self, now: datetime) -> int:
        """Emails last week's recap on Mondays and last month's on the 1st, at the reminder time,
        to people with email reminders on. Returns how many went out."""
        sent = 0
        for reminder, user in self._repo.enabled():
            if not reminder.email:
                continue
            try:
                tz = zone(reminder.timezone)
            except ReminderError:
                continue
            local = now.astimezone(tz)
            today = local.date()
            hour, minute = (int(part) for part in reminder.time.split(":"))
            if reminder.last_recap_on == today or local.time() < time(hour, minute):
                continue
            recaps = RecapService(self._session)
            parts = []
            if today.weekday() == 0:
                first, last = weeks_before(today, 1)[0]
                parts.append(recap_text(recaps.recap(user.id, Period.WEEK, first, last, now, tz)))
            if today.day == 1:
                first, last = months_before(today, 1)[0]
                parts.append(recap_text(recaps.recap(user.id, Period.MONTH, first, last, now, tz)))
            reminder.last_recap_on = today
            if parts and self._send_recap_email(user, "\n\n".join(parts)):
                sent += 1
            self._session.commit()
        return sent

    def _send_recap_email(self, user: User, text: str) -> bool:
        link = f"{self._settings.email.app_base_url}/me"
        try:
            self._email.send(
                Email(
                    to=user.email,
                    subject="Your Vocab Sensei recap",
                    body=f"Hi {user.display_name},\n\n{text}\n\nSee more: {link}\n\n"
                    "(These come with email reminders; change them in Me → Settings.)",
                )
            )
        except Exception:
            logger.exception("recap email failed")
            return False
        return True

    def _send(self, user: User, stats: Stats, *, push: bool, email: bool) -> bool:
        """Sends on every chosen channel; True if any reached the person."""
        text = message(stats)
        emailed = self._send_email(user, text) if email else False
        pushed = self._send_push(user, text) if push else False
        return emailed or pushed

    def _send_email(self, user: User, text: str) -> bool:
        link = f"{self._settings.email.app_base_url}/quiz"
        try:
            self._email.send(
                Email(
                    to=user.email,
                    subject="Your daily Vocab Sensei words",
                    body=f"Hi {user.display_name},\n\n{text}\n\nPlay now: {link}\n\n"
                    "(Change or turn off reminders in Me → Settings.)",
                )
            )
        except Exception:
            logger.exception("reminder email failed")
            return False
        return True

    def _send_push(self, user: User, text: str) -> bool:
        delivered = False
        payload = {"title": "Vocab Sensei", "body": text, "url": "/quiz"}
        for subscription in self._repo.subscriptions(user.id):
            target = PushTarget(subscription.endpoint, subscription.p256dh, subscription.auth)
            try:
                self._push.send(target, payload)
                delivered = True
            except SubscriptionGoneError:
                self._repo.delete(subscription)
            except PushError:
                logger.exception("push reminder failed")
        self._session.commit()
        return delivered


def run_scheduler(
    stop: Event,
    session_factory: Callable[[], Session],
    settings: Settings,
    email_sender: EmailSender,
    push_sender: PushSender,
) -> None:
    """Checks for due reminders every `check_seconds` until `stop` is set (a background thread)."""
    while not stop.wait(settings.reminders.check_seconds):
        try:
            with session_factory() as session:
                service = ReminderService(session, settings, email_sender, push_sender)
                now = datetime.now(ZoneInfo("UTC"))
                sent = service.send_due(now)
                service.send_recaps(now)
            if sent:
                logger.info("sent %d reminders", sent)
        except Exception:
            logger.exception("reminder check failed")
