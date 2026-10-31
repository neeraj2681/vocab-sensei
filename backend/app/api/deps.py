"""Shared FastAPI dependencies. Tests override get_email_sender, get_dictionary and get_session."""

import logging
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.email import Email, EmailSender, SmtpEmailSender
from app.db.models import User
from app.db.session import get_session
from app.dictionary.types import Dictionary
from app.dictionary.wordnet import WordNetDictionary
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_email_sender(settings: SettingsDep) -> EmailSender:
    return SmtpEmailSender(settings.email)


class BackgroundEmailSender:
    """Sends emails after the response, so a slow or failing mail server never breaks a request.

    It also keeps response times the same whether or not an email goes out, which would otherwise
    hint at which addresses have accounts.
    """

    def __init__(self, sender: EmailSender, tasks: BackgroundTasks) -> None:
        self._sender = sender
        self._tasks = tasks

    def send(self, email: Email) -> None:
        self._tasks.add_task(_send_and_log_failures, self._sender, email)


def _send_and_log_failures(sender: EmailSender, email: Email) -> None:
    try:
        sender.send(email)
    except Exception:
        logger.exception("couldn't send the %r email", email.subject)


DictionaryLoader = Callable[[], Dictionary]


@lru_cache
def _wordnet(data_dir: Path, lexicon: str, senses_per_pos: int) -> Dictionary:
    return WordNetDictionary(data_dir, lexicon, senses_per_pos)  # errors aren't cached: retried


def get_dictionary(settings: SettingsDep) -> DictionaryLoader:
    """Loads the dictionary on first use, so endpoints that don't need it work without it."""
    config = settings.dictionary
    return lambda: _wordnet(settings.dictionary_dir, config.lexicon, config.senses_per_pos)


def get_auth_service(
    session: Annotated[Session, Depends(get_session)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    background: BackgroundTasks,
    settings: SettingsDep,
) -> AuthService:
    return AuthService(session, BackgroundEmailSender(email_sender, background), settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_session_token(request: Request, settings: SettingsDep) -> str | None:
    return request.cookies.get(settings.auth.cookie_name)


def get_current_user(
    auth: AuthServiceDep, token: Annotated[str | None, Depends(get_session_token)]
) -> User:
    user = auth.user_for_session(token) if token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
