"""User management (finance head) and user lookup (finance head: anyone; others: self)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import PermissionDenied, get_current_user, require_role
from app.database import get_db
from app.errors import AppError
from app.models import Role, User
from app.schemas.errors import error_responses
from app.schemas.user import UserCreate, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

finance_head_only = require_role(Role.FINANCE_HEAD)


class UserAlreadyExists(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "user_already_exists"
    message = "A user with this username or email already exists."


class ManagerNotFound(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "manager_not_found"
    message = "manager_id does not refer to an active user."


class UserNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "user_not_found"
    message = "No user has this id."


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an employee, line manager or finance auditor (finance_head only)",
    responses=error_responses(401, 403, 409, 422),
)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(finance_head_only),
) -> User:
    """`role` must be `employee`, `line_manager` or `finance_auditor` - never `finance_head`.
    `manager_id` (optional) must be an active user. Username and email must be unique."""
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


@router.get(
    "",
    response_model=list[UserOut],
    summary="List all users, oldest first (finance_head only)",
    responses=error_responses(401, 403),
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(finance_head_only),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get one user's details (finance_head: anyone; others: only themselves)",
    responses=error_responses(401, 403, 404, 422),
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Non-heads get 403 for any id but their own, whether or not it exists: no probing."""
    if current_user.role != Role.FINANCE_HEAD and user_id != current_user.id:
        raise PermissionDenied("You may only view your own user record.")
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFound()
    return user
