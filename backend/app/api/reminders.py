from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SettingsDep, get_email_sender
from app.api.quiz import Now
from app.core.config import PushSettings
from app.core.email import EmailSender
from app.core.enums import ReminderChannel
from app.core.push import PushSender, VapidKeys, WebPushSender, load_or_create_keys
from app.db.session import get_session
from app.services.reminders import ReminderError, ReminderService, ReminderView

router = APIRouter(prefix="/reminders", tags=["reminders"])


@lru_cache
def _keys(private_key: str | None, public_key: str | None, data_dir: Path) -> VapidKeys:
    configured = PushSettings(vapid_private_key=private_key, vapid_public_key=public_key)
    return load_or_create_keys(configured, data_dir)


def get_vapid_keys(settings: SettingsDep) -> VapidKeys:
    push = settings.push
    return _keys(push.vapid_private_key, push.vapid_public_key, settings.data_dir)


def get_push_sender(
    settings: SettingsDep, keys: Annotated[VapidKeys, Depends(get_vapid_keys)]
) -> PushSender:
    return WebPushSender(keys, settings.push.subject)


def get_reminder_service(
    session: Annotated[Session, Depends(get_session)],
    settings: SettingsDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    push_sender: Annotated[PushSender, Depends(get_push_sender)],
) -> ReminderService:
    return ReminderService(session, settings, email_sender, push_sender)


RemindersDep = Annotated[ReminderService, Depends(get_reminder_service)]


class ReminderResponse(BaseModel):
    enabled: bool
    time: str  # HH:MM in `timezone`
    timezone: str
    channel: ReminderChannel
    devices: int  # devices with push notifications turned on
    push_public_key: str  # for the browser's pushManager.subscribe()

    @classmethod
    def of(cls, view: ReminderView, keys: VapidKeys) -> "ReminderResponse":
        return cls(
            enabled=view.enabled,
            time=view.time,
            timezone=view.timezone,
            channel=view.channel,
            devices=view.devices,
            push_public_key=keys.public_key,
        )


class ReminderRequest(BaseModel):
    enabled: bool
    time: str = Field(examples=["20:00"])
    timezone: str = Field(examples=["Asia/Kolkata"])
    channel: ReminderChannel


class DeviceKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class DeviceRequest(BaseModel):
    """What the browser's PushSubscription.toJSON() returns."""

    endpoint: str = Field(max_length=1000, pattern=r"^https://")
    keys: DeviceKeys


class EndpointRequest(BaseModel):
    endpoint: str = Field(max_length=1000)


class TestResponse(BaseModel):
    sent: bool


KeysDep = Annotated[VapidKeys, Depends(get_vapid_keys)]


@router.get("")
def get_reminder(user: CurrentUser, reminders: RemindersDep, keys: KeysDep) -> ReminderResponse:
    return ReminderResponse.of(reminders.view(user.id), keys)


@router.put("")
def update_reminder(
    body: ReminderRequest, user: CurrentUser, reminders: RemindersDep, keys: KeysDep
) -> ReminderResponse:
    try:
        view = reminders.update(
            user.id,
            enabled=body.enabled,
            at=body.time,
            timezone=body.timezone,
            channel=body.channel,
        )
    except ReminderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return ReminderResponse.of(view, keys)


@router.post("/devices", status_code=status.HTTP_204_NO_CONTENT)
def add_device(body: DeviceRequest, user: CurrentUser, reminders: RemindersDep) -> None:
    """Turns on push notifications for this browser."""
    reminders.subscribe(user.id, body.endpoint, body.keys.p256dh, body.keys.auth)


@router.delete("/devices", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(body: EndpointRequest, user: CurrentUser, reminders: RemindersDep) -> None:
    reminders.unsubscribe(user.id, body.endpoint)


@router.post("/test")
def send_test(user: CurrentUser, reminders: RemindersDep, now: Now) -> TestResponse:
    """Sends a reminder right now, so you can see what it looks like."""
    return TestResponse(sent=reminders.send_test(user, now))
