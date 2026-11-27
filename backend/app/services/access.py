"""Who may see which claim: the single rule every claim endpoint goes through.

* employee        -> only their own claims
* line_manager    -> their own claims, their direct reports' claims, and any claim
                     whose approval chain names them (assigned, acted, on behalf of) or
                     names someone who has delegated to them today
* finance_auditor, finance_head -> every claim

Lists use ``visibility_condition`` inside the SQL query (never filter in memory).
Single claims use ``get_visible_claim``: a claim the caller may not see answers 404,
exactly like a claim that does not exist, so ids cannot be probed. When the claim
does exist, an ACCESS_DENIED audit row is written in its own transaction.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import status
from sqlalchemy import ColumnElement, exists, or_, select, true
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import ApprovalStep, AuditAction, Claim, Delegation, Role, User
from app.request_context import request_path_var
from app.services import audit

SEES_ALL_ROLES = frozenset({Role.FINANCE_AUDITOR, Role.FINANCE_HEAD})


class ClaimNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "claim_not_found"
    message = "Claim not found."


def sees_all_claims(user: User) -> bool:
    return user.role in SEES_ALL_ROLES


def visibility_condition(user: User, on: date | None = None) -> ColumnElement[bool]:
    """SQL condition on ``Claim`` for the claims ``user`` may see."""
    if sees_all_claims(user):
        return true()
    own = Claim.employee_id == user.id
    if user.role != Role.LINE_MANAGER:
        return own
    on = on or date.today()
    reports = Claim.employee_id.in_(select(User.id).where(User.manager_id == user.id))
    delegators = select(Delegation.delegator_id).where(
        Delegation.delegate_id == user.id,
        Delegation.active,
        Delegation.from_date <= on,
        Delegation.to_date >= on,
    )
    in_chain = exists().where(
        ApprovalStep.claim_id == Claim.id,
        or_(
            ApprovalStep.assigned_approver_id == user.id,
            ApprovalStep.acted_by_id == user.id,
            ApprovalStep.on_behalf_of_id == user.id,
            ApprovalStep.assigned_approver_id.in_(delegators),
        ),
    )
    return or_(own, reports, in_chain)


def deny(
    db: Session,
    user: User | None,
    *,
    reason: str,
    entity_type: str,
    entity_id: int | None = None,
    claim_id: int | None = None,
    **details: Any,
) -> None:
    """Write an ACCESS_DENIED row that survives the request's rollback."""
    audit.record_detached(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        claim_id=claim_id,
        action=AuditAction.ACCESS_DENIED,
        actor=user,
        changes={"request": request_path_var.get(), "reason": reason, **details},
    )


def get_visible_claim(db: Session, user: User, claim_id: int, *, lock: bool = False) -> Claim:
    query = select(Claim).where(Claim.id == claim_id, visibility_condition(user))
    if lock:
        query = query.with_for_update()
    claim = db.scalar(query)
    if claim is None:
        if db.scalar(select(Claim.id).where(Claim.id == claim_id)) is not None:
            deny(
                db,
                user,
                reason="claim belongs to someone the caller may not see",
                entity_type="claim",
                entity_id=claim_id,
            )
        raise ClaimNotFound()
    return claim
