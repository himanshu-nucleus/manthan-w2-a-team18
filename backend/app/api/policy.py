"""Expense policy settings: everyone may read them, only the finance head may change them."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import PolicySettings, Role, User
from app.schemas.errors import error_responses
from app.schemas.policy import PolicyOut, PolicyUpdate
from app.services import policy

router = APIRouter(prefix="/policy", tags=["policy"])

finance_head_only = require_role(Role.FINANCE_HEAD)


@router.get(
    "",
    response_model=PolicyOut,
    summary="Current expense policy limits and tier-1 cities (any logged-in user)",
    responses=error_responses(401),
)
def get_policy(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PolicySettings:
    settings = policy.get_policy(db)
    db.commit()  # keeps the default row if this read had to create it
    return settings


@router.patch(
    "",
    response_model=PolicyOut,
    summary="Change one or more policy limits or the tier-1 city list (finance_head only)",
    responses=error_responses(401, 403, 422),
)
def update_policy(
    body: PolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_head_only),
) -> PolicySettings:
    """Send only the fields to change. Limits must be above 0; the receipt threshold may
    be 0. Applies to claims submitted from now on; the change is written to the audit
    trail (`entity_type` = `policy`)."""
    return policy.update_policy(db, user, body)
