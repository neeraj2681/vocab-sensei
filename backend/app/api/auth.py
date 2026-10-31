from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.api.deps import AuthServiceDep, CurrentUser, SettingsDep, get_session_token
from app.api.rate_limit import EmailLimit, LoginLimit
from app.services.auth import EmailNotVerifiedError, InvalidCredentialsError, InvalidTokenError

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
