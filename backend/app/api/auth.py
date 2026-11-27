"""Login and current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.models import AuditAction, User
from app.schemas.errors import error_responses
from app.schemas.user import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, verify_password
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class InvalidCredentials(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "The username or password is incorrect."


def find_login_user(db: Session, identifier: str) -> User | None:
    """The user whose username or email matches ``identifier``, ignoring case and
    surrounding spaces.

    Usernames may themselves be email addresses, so one value could match one user's
    username and another user's email; the username match wins, so the answer is never
    ambiguous. Both columns are unique, so each side matches at most one user.
    """
    value = identifier.strip().lower()
    if not value:
        return None
    by_username = db.scalar(select(User).where(func.lower(User.username) == value))
    if by_username is not None:
        return by_username
    return db.scalar(select(User).where(func.lower(User.email) == value))


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in with username or email + password; returns a bearer token (public)",
    responses=error_responses(401, 422),
)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """`username` may be the username or the email address, in any letter case. Send the
    returned `access_token` as `Authorization: Bearer <token>` on every other call.
    Unknown user, wrong password and inactive user all return the same 401."""
    user = find_login_user(db, body.username)
    # Same error for unknown user, wrong password and inactive user: no account probing.
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        # Kept even though the request fails; the username typed, never the password.
        audit.record_detached(
            db,
            entity_type="user",
            entity_id=user.id if user else None,
            action=AuditAction.LOGIN_FAILED,
            actor=None,
            changes={"username": {"old": None, "new": body.username.strip().lower()[:254]}},
        )
        raise InvalidCredentials()
    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=get_settings().access_token_ttl_seconds,
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the logged-in user and role (any logged-in user)",
    responses=error_responses(401),
)
def me(user: User = Depends(get_current_user)) -> User:
    """Call on page load to restore the session and pick the role's landing page."""
    return user
