"""Shared FastAPI dependencies. Tests override get_email_sender, get_dictionary and get_session."""

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.email import EmailSender, SmtpEmailSender
from app.db.models import User
from app.db.session import get_session
from app.dictionary.types import Dictionary
from app.dictionary.wordnet import WordNetDictionary
from app.services.auth import AuthService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_email_sender(settings: SettingsDep) -> EmailSender:
    return SmtpEmailSender(settings.email)


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
    settings: SettingsDep,
) -> AuthService:
    return AuthService(session, email_sender, settings)


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
