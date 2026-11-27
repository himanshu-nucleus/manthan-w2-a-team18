"""Policy rules: list (any logged-in user) and change (finance head only, audited)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import PolicyRule, Role, User
from app.schemas.errors import error_responses
from app.schemas.policy import PolicyRuleOut, PolicyRuleUpdate
from app.services import policy_rules

router = APIRouter(prefix="/policy-rules", tags=["policy"])

finance_head_only = require_role(Role.FINANCE_HEAD)


@router.get(
    "",
    response_model=list[PolicyRuleOut],
    summary="List active policy rules (any logged-in user; finance_head may include inactive)",
    responses=error_responses(401, 422),
)
def list_policy_rules(
    include_inactive: bool = Query(
        default=False, description="finance_head only; ignored for other roles."
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PolicyRule]:
    return policy_rules.list_rules(
        db, include_inactive=include_inactive and user.role == Role.FINANCE_HEAD
    )


@router.put(
    "/{code}",
    response_model=PolicyRuleOut,
    summary="Change a rule's params, outcome, template or active flag (finance_head only)",
    responses=error_responses(401, 403, 404, 422),
)
def update_policy_rule(
    code: str,
    body: PolicyRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_head_only),
) -> PolicyRule:
    return policy_rules.update_rule(db, user, code, body)
