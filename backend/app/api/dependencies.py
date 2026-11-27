"""Request dependencies: who is calling, and are they allowed to."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import Role, User
from app.security import read_access_token

# auto_error=False so a missing header goes through our own error envelope.
bearer_scheme = HTTPBearer(auto_error=False)


class NotAuthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "not_authenticated"
    message = "A valid bearer token is required."


class PermissionDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Your role is not allowed to do this."


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to an active user, re-read from the database.

    Re-reading means a deactivated user or a changed role takes effect at once,
    not when the token expires.
    """
    if credentials is None:
        raise NotAuthenticated()
    payload = read_access_token(credentials.credentials)
    if payload is None:
        raise NotAuthenticated("The token is invalid or has expired.")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise NotAuthenticated("The token is invalid or has expired.")
    return user


def require_role(*roles: Role) -> Callable[..., User]:
    """Dependency factory: allow only users holding one of ``roles``."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDenied()
        return user

    return dependency
