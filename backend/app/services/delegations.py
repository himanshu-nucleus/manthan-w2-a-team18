"""Delegation while an approver is on leave.

Rules: only approver roles may delegate; no self-delegation; the delegate holds the
same or a higher role; dates start today or later; one delegator cannot have two
overlapping delegations; no A -> B -> C chains, from either end: a delegate who is
themselves away in that period is refused, and so is a delegator who is standing in
for someone else in that period. Resolution is one hop only (see ``chain.active_delegators``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import AuditAction, Delegation, Role, User
from app.schemas.approval import DelegationCreate
from app.services import audit
from app.services.chain import APPROVER_ROLES, ROLE_RANK

ENTITY_TYPE = "delegation"


class DelegationInvalid(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "delegation_invalid"
    message = "This delegation is not allowed."


class DelegationNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "delegation_not_found"
    message = "Delegation not found."


class CannotDelegate(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Only line managers, finance auditors and finance heads can delegate approvals."


def _overlapping(db: Session, user_id: int, start: date, end: date) -> Delegation | None:
    return db.scalar(
        select(Delegation).where(
            Delegation.delegator_id == user_id,
            Delegation.active,
            Delegation.from_date <= end,
            Delegation.to_date >= start,
        )
    )


def _covering_for(db: Session, user_id: int, start: date, end: date) -> Delegation | None:
    """An active delegation in which ``user_id`` stands in for someone in this period."""
    return db.scalar(
        select(Delegation).where(
            Delegation.delegate_id == user_id,
            Delegation.active,
            Delegation.from_date <= end,
            Delegation.to_date >= start,
        )
    )


def create(db: Session, user: User, body: DelegationCreate) -> Delegation:
    if user.role not in APPROVER_ROLES:
        raise CannotDelegate()
    if body.delegate_id == user.id:
        raise DelegationInvalid("You cannot delegate to yourself.")
    if body.from_date < date.today():
        raise DelegationInvalid("from_date cannot be in the past.")
    if body.to_date < body.from_date:
        raise DelegationInvalid("to_date must be on or after from_date.")

    delegate = db.get(User, body.delegate_id)
    if delegate is None or not delegate.is_active:
        raise DelegationInvalid("delegate_id does not refer to an active user.")
    if ROLE_RANK[Role(delegate.role)] < ROLE_RANK[Role(user.role)]:
        raise DelegationInvalid(
            "The delegate must have the same or a higher role than you.",
            details={"your_role": user.role, "delegate_role": delegate.role},
        )
    if _overlapping(db, user.id, body.from_date, body.to_date) is not None:
        raise DelegationInvalid("You already have an active delegation in this period.")
    if _overlapping(db, delegate.id, body.from_date, body.to_date) is not None:
        raise DelegationInvalid(
            "The delegate has delegated their own approvals in this period; "
            "delegation chains are not allowed."
        )
    if _covering_for(db, user.id, body.from_date, body.to_date) is not None:
        raise DelegationInvalid(
            "You are standing in for another approver in this period; "
            "delegation chains are not allowed."
        )

    delegation = Delegation(
        delegator_id=user.id,
        delegate_id=delegate.id,
        from_date=body.from_date,
        to_date=body.to_date,
        reason=body.reason,
    )
    db.add(delegation)
    db.flush()
    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=delegation.id,
        action=AuditAction.DELEGATION_CREATED,
        changes={
            "delegator_id": {"old": None, "new": user.id},
            "delegate_id": {"old": None, "new": delegate.id},
            "from_date": {"old": None, "new": body.from_date.isoformat()},
            "to_date": {"old": None, "new": body.to_date.isoformat()},
            "reason": {"old": None, "new": body.reason},
        },
        actor_id=user.id,
    )
    db.commit()
    db.refresh(delegation)
    return delegation


def mine(db: Session, user: User) -> list[Delegation]:
    """Delegations I gave or received, newest first."""
    return list(
        db.scalars(
            select(Delegation)
            .where(or_(Delegation.delegator_id == user.id, Delegation.delegate_id == user.id))
            .order_by(Delegation.created_at.desc(), Delegation.id.desc())
        )
    )


def cancel(db: Session, user: User, delegation_id: int) -> None:
    delegation = db.get(Delegation, delegation_id)
    if delegation is None or delegation.delegator_id != user.id:
        raise DelegationNotFound()
    if not delegation.active:
        return  # already cancelled: idempotent
    delegation.active = False
    delegation.cancelled_at = datetime.now(UTC)
    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=delegation.id,
        action=AuditAction.DELEGATION_CANCELLED,
        changes={"active": {"old": True, "new": False}},
        actor_id=user.id,
    )
    db.commit()
