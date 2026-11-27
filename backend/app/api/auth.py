"""Login and current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.models import User
from app.schemas.user import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class InvalidCredentials(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "The username or password is incorrect."


@router.post("/login", response_model=LoginResponse, summary="Log in with username and password")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == body.username.lower()))
    # Same error for unknown user, wrong password and inactive user: no account probing.
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise InvalidCredentials()
    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=get_settings().access_token_ttl_seconds,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut, summary="The logged-in user")
def me(user: User = Depends(get_current_user)) -> User:
    return user
