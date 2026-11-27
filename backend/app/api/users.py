"""User management - finance head only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.database import get_db
from app.errors import AppError
from app.models import Role, User
from app.schemas.user import UserCreate, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

finance_head_only = require_role(Role.FINANCE_HEAD)


class UserAlreadyExists(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "user_already_exists"
    message = "A user with this username or email already exists."


class ManagerNotFound(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "manager_not_found"
    message = "manager_id does not refer to an active user."


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add an employee, line manager or finance auditor",
)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(finance_head_only),
) -> User:
    username = body.username.lower()
    email = body.email.lower() if body.email else None

    duplicate = select(User.id).where(
        or_(User.username == username, User.email == email) if email else User.username == username
    )
    if db.scalar(duplicate) is not None:
        raise UserAlreadyExists()

    if body.manager_id is not None:
        manager = db.get(User, body.manager_id)
        if manager is None or not manager.is_active:
            raise ManagerNotFound()

    user = User(
        username=username,
        full_name=body.full_name,
        email=email,
        role=body.role,
        manager_id=body.manager_id,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Lost a race with a concurrent insert of the same username/email.
        db.rollback()
        raise UserAlreadyExists() from exc
    db.refresh(user)
    return user


@router.get("", response_model=list[UserOut], summary="List all users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(finance_head_only),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))
