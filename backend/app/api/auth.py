from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import AuthServiceDep, CurrentUser, SettingsDep, get_session_token
from app.api.rate_limit import EmailLimit, LoginLimit
from app.core.enums import Gender
from app.core.images import NotAnImageError
from app.db.session import get_session
from app.db.types import utcnow
from app.services.auth import (
    EmailInUseError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.services.profile import NameAlreadyChangedError, ProfileError, ProfileService

router = APIRouter(prefix="/auth", tags=["auth"])

Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    display_name: Annotated[str, Field(min_length=1, max_length=100)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(max_length=128)]


class PasswordRequest(BaseModel):
    password: Annotated[str, Field(max_length=128)]


class EmailRequest(BaseModel):
    email: EmailStr


class NameRequest(BaseModel):
    display_name: Annotated[str, Field(min_length=1, max_length=100)]


class GenderRequest(BaseModel):
    gender: Gender


class ChangeEmailRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(max_length=128)]


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(max_length=128)]
    new_password: Password


class TokenRequest(BaseModel):
    token: Annotated[str, Field(max_length=200)]


class ResetPasswordRequest(TokenRequest):
    new_password: Password


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    email_verified_at: datetime | None
    onboarded_at: datetime | None  # None: show the first-run tour
    name_changed_at: datetime | None  # set once the one name change is used
    gender: Gender
    has_avatar: bool  # GET /auth/me/avatar has a picture
    pending_email: str | None  # a new address waiting for its link to be opened


class MessageResponse(BaseModel):
    message: str


CHECK_EMAIL = MessageResponse(message="If that address can receive email, we've sent a link.")


@contextmanager
def invalid_token_as_400() -> Iterator[None]:
    try:
        yield
    except InvalidTokenError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This link is invalid or has expired"
        ) from None


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register(body: RegisterRequest, auth: AuthServiceDep, _: EmailLimit) -> MessageResponse:
    auth.register(body.email, body.password, body.display_name)
    return CHECK_EMAIL


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(body: EmailRequest, auth: AuthServiceDep, _: EmailLimit) -> MessageResponse:
    auth.resend_verification(body.email)
    return CHECK_EMAIL


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(body: TokenRequest, auth: AuthServiceDep) -> None:
    with invalid_token_as_400():
        auth.verify_email(body.token)


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    _: LoginLimit,
    user_agent: Annotated[str | None, Header()] = None,
) -> UserResponse:
    try:
        result = auth.login(body.email, body.password, user_agent)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password") from None
    except EmailNotVerifiedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please verify your email first") from None

    response.set_cookie(
        settings.auth.cookie_name,
        result.session_token,
        expires=result.expires_at,
        httponly=True,  # not readable from JavaScript
        secure=settings.auth.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs, which blocks CSRF
        path="/api",
    )
    return UserResponse.model_validate(result.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    token: Annotated[str | None, Depends(get_session_token)],
) -> None:
    if token:
        auth.logout(token)
    response.delete_cookie(settings.auth.cookie_name, path="/api")


@router.get("/me")
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/me/onboarded", status_code=status.HTTP_204_NO_CONTENT)
def finish_onboarding(user: CurrentUser, auth: AuthServiceDep) -> None:
    """Marks the first-run tour as done (or skipped), so it isn't shown again."""
    auth.finish_onboarding(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: PasswordRequest,
    user: CurrentUser,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    _: LoginLimit,  # the password check must not become a way to guess passwords
) -> None:
    """Deletes your account and everything in it. Asks for the password again."""
    try:
        auth.delete_account(user, body.password)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password") from None
    response.delete_cookie(settings.auth.cookie_name, path="/api")


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: EmailRequest, auth: AuthServiceDep, _: EmailLimit) -> MessageResponse:
    auth.forgot_password(body.email)
    return CHECK_EMAIL


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordRequest, auth: AuthServiceDep, _: LoginLimit) -> None:
    with invalid_token_as_400():
        auth.reset_password(body.token, body.new_password)


def get_profile_service(
    session: Annotated[Session, Depends(get_session)], settings: SettingsDep
) -> ProfileService:
    return ProfileService(session, settings)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


@router.patch("/me/name")
def change_name(body: NameRequest, user: CurrentUser, profile: ProfileServiceDep) -> UserResponse:
    """Changes the display name. Only once for now (more changes will cost coins)."""
    try:
        profile.change_name(user, body.display_name, utcnow())
    except NameAlreadyChangedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except ProfileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return UserResponse.model_validate(user)


@router.put("/me/gender")
def set_gender(body: GenderRequest, user: CurrentUser, profile: ProfileServiceDep) -> UserResponse:
    profile.set_gender(user, body.gender)
    return UserResponse.model_validate(user)


@router.put("/me/avatar")
async def set_avatar(
    file: UploadFile, user: CurrentUser, profile: ProfileServiceDep
) -> UserResponse:
    """A profile picture: any common image, cropped to a square."""
    try:
        profile.set_avatar(user, await file.read())
    except (ProfileError, NotAnImageError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return UserResponse.model_validate(user)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def remove_avatar(user: CurrentUser, profile: ProfileServiceDep) -> None:
    profile.remove_avatar(user)


@router.get("/me/avatar", response_class=FileResponse)
def avatar(user: CurrentUser, profile: ProfileServiceDep) -> FileResponse:
    path = profile.avatar_file(user)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.post("/me/email", status_code=status.HTTP_202_ACCEPTED)
def change_email(
    body: ChangeEmailRequest, user: CurrentUser, auth: AuthServiceDep, _: EmailLimit
) -> MessageResponse:
    """Sends a confirmation link to the new address; the old one stays until it's opened."""
    try:
        auth.change_email(user, body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password") from None
    except EmailInUseError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return MessageResponse(message="Check your new inbox for a confirmation link.")


@router.post("/confirm-email", status_code=status.HTTP_204_NO_CONTENT)
def confirm_email(body: TokenRequest, auth: AuthServiceDep) -> None:
    with invalid_token_as_400():
        auth.confirm_email(body.token)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest, user: CurrentUser, auth: AuthServiceDep, _: LoginLimit
) -> None:
    try:
        auth.change_password(user, body.current_password, body.new_password)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong current password") from None
