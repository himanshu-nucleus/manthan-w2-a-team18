"""Approver actions (approve, reject, send back), the pending queue, comments and chain view.

Concurrency: every action locks the claim row and re-reads the current step, so a
double click or two approvers at once cannot decide a step twice. ``step_id`` in the
request makes a retry safe: if that step is no longer the current one, 409.
Claim and step rows also carry a version column (optimistic lock).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.errors import AppError
from app.models import (
    ApprovalStep,
    AuditAction,
    Claim,
    ClaimComment,
    ClaimStatus,
    StepStatus,
    User,
)
from app.services import audit, chain, claims


class ClaimNotPending(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "claim_not_pending"
    message = "This claim is not waiting for an approval decision."


class StepAlreadyDecided(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "step_already_decided"
    message = "That approval step has already been decided."


def _actor_label(db: Session, user: User, on_behalf_of: int | None) -> str:
    if on_behalf_of is None:
        return user.username
    original = db.get(User, on_behalf_of)
    return f"{user.username} on behalf of {original.username if original else on_behalf_of}"


def _load_current(
    db: Session, user: User, claim_id: int, step_id: int | None
) -> tuple[Claim, ApprovalStep, int | None]:
    claim = claims.get_visible_claim(db, user, claim_id, lock=True)
    if claim.status != ClaimStatus.PENDING_APPROVAL:
        raise ClaimNotPending(details={"status": claim.status})
    step = chain.current_step(db, claim)
    if step is None:
        raise ClaimNotPending()
    if step_id is not None and step_id != step.id:
        raise StepAlreadyDecided(details={"current_step_id": step.id})
    on_behalf_of = chain.acting_for(db, user, claim, step, date.today())
    return claim, step, on_behalf_of


def _close_step(
    step: ApprovalStep,
    user: User,
    on_behalf_of: int | None,
    new_status: StepStatus,
    comment: str | None,
) -> None:
    step.status = new_status.value
    step.acted_by_id = user.id
    step.on_behalf_of_id = on_behalf_of
    step.acted_at = datetime.now(UTC)
    step.comment = comment


def _cancel_waiting(db: Session, claim: Claim) -> None:
    for waiting in db.scalars(
        select(ApprovalStep).where(
            ApprovalStep.claim_id == claim.id,
            ApprovalStep.round == claim.submission_round,
            ApprovalStep.status == StepStatus.WAITING.value,
        )
    ):
        waiting.status = StepStatus.CANCELLED.value


def _add_comment(db: Session, claim: Claim, user: User, body: str | None) -> None:
    if body:
        db.add(ClaimComment(claim_id=claim.id, author_id=user.id, body=body))


def _step_changes(
    db: Session, step: ApprovalStep, user: User, on_behalf_of: int | None, comment: str | None
) -> dict[str, Any]:
    return {
        f"approval_steps.{step.step_order}.status": {
            "old": StepStatus.PENDING.value,
            "new": step.status,
        },
        "acted_by": {"old": None, "new": _actor_label(db, user, on_behalf_of)},
        "acted_by_id": {"old": None, "new": user.id},
        "on_behalf_of_id": {"old": None, "new": on_behalf_of},
        "comment": {"old": None, "new": comment},
    }


def approve(
    db: Session, user: User, claim_id: int, *, step_id: int | None, comment: str | None
) -> Claim:
    claim, step, on_behalf_of = _load_current(db, user, claim_id, step_id)
    _close_step(step, user, on_behalf_of, StepStatus.APPROVED, comment)
    _add_comment(db, claim, user, comment)
    audit.record(
        db,
        entity_type=claims.ENTITY_TYPE,
        entity_id=claim.id,
        action=AuditAction.STEP_APPROVED,
        changes=_step_changes(db, step, user, on_behalf_of, comment),
        actor_id=user.id,
    )

    following = db.scalar(
        select(ApprovalStep)
        .where(
            ApprovalStep.claim_id == claim.id,
            ApprovalStep.round == claim.submission_round,
            ApprovalStep.status == StepStatus.WAITING.value,
        )
        .order_by(ApprovalStep.step_order)
    )
    if following is not None:
        following.status = StepStatus.PENDING.value
    else:
        claim.status = ClaimStatus.APPROVED.value
        audit.record(
            db,
            entity_type=claims.ENTITY_TYPE,
            entity_id=claim.id,
            action=AuditAction.APPROVED,
            changes={
                "status": {
                    "old": ClaimStatus.PENDING_APPROVAL.value,
                    "new": ClaimStatus.APPROVED.value,
                }
            },
            actor_id=user.id,
        )
    claim.updated_by = user.id
    db.commit()
    db.refresh(claim)
    return claim


def _finish(
    db: Session,
    user: User,
    claim_id: int,
    *,
    step_id: int | None,
    comment: str,
    step_status: StepStatus,
    claim_status: ClaimStatus,
    action: AuditAction,
) -> Claim:
    claim, step, on_behalf_of = _load_current(db, user, claim_id, step_id)
    _close_step(step, user, on_behalf_of, step_status, comment)
    _cancel_waiting(db, claim)
    _add_comment(db, claim, user, comment)
    claim.status = claim_status.value
    claim.updated_by = user.id
    audit.record(
        db,
        entity_type=claims.ENTITY_TYPE,
        entity_id=claim.id,
        action=action,
        changes={
            **_step_changes(db, step, user, on_behalf_of, comment),
            "status": {"old": ClaimStatus.PENDING_APPROVAL.value, "new": claim_status.value},
        },
        actor_id=user.id,
    )
    db.commit()
    db.refresh(claim)
    return claim


def reject(db: Session, user: User, claim_id: int, *, step_id: int | None, comment: str) -> Claim:
    return _finish(
        db,
        user,
        claim_id,
        step_id=step_id,
        comment=comment,
        step_status=StepStatus.REJECTED,
        claim_status=ClaimStatus.REJECTED,
        action=AuditAction.REJECTED,
    )


def send_back(
    db: Session, user: User, claim_id: int, *, step_id: int | None, comment: str
) -> Claim:
    return _finish(
        db,
        user,
        claim_id,
        step_id=step_id,
        comment=comment,
        step_status=StepStatus.SENT_BACK,
        claim_status=ClaimStatus.CLARIFICATION_REQUESTED,
        action=AuditAction.SENT_BACK,
    )


# --- reads ---------------------------------------------------------------------


def approval_steps(db: Session, user: User, claim_id: int) -> list[ApprovalStep]:
    """Every round's steps, latest round first."""
    claims.get_visible_claim(db, user, claim_id)
    return list(
        db.scalars(
            select(ApprovalStep)
            .where(ApprovalStep.claim_id == claim_id)
            .order_by(ApprovalStep.round.desc(), ApprovalStep.step_order)
        )
    )


def pending_for(
    db: Session, user: User, *, limit: int, offset: int
) -> tuple[list[tuple[ApprovalStep, Claim, int | None]], int]:
    """Current steps ``user`` may act on: assigned to them, open to their role, or
    delegated to them today. Oldest submission first."""
    today = date.today()
    delegators = chain.active_delegators(db, user.id, today)
    delegator_ids = [d.id for d in delegators]
    delegator_roles = sorted({d.role for d in delegators})

    other = aliased(ApprovalStep)
    already_acted = exists().where(
        other.claim_id == ApprovalStep.claim_id,
        other.round == ApprovalStep.round,
        or_(other.acted_by_id == user.id, other.on_behalf_of_id == user.id),
    )
    mine = or_(
        ApprovalStep.assigned_approver_id == user.id,
        and_(ApprovalStep.assigned_approver_id.is_(None), ApprovalStep.approver_role == user.role),
        ApprovalStep.assigned_approver_id.in_(delegator_ids),
        and_(
            ApprovalStep.assigned_approver_id.is_(None),
            ApprovalStep.approver_role.in_(delegator_roles),
        ),
    )
    conditions = (
        ApprovalStep.status == StepStatus.PENDING.value,
        ApprovalStep.round == Claim.submission_round,
        Claim.status == ClaimStatus.PENDING_APPROVAL.value,
        Claim.employee_id != user.id,
        mine,
        ~already_acted,
    )
    base = select(ApprovalStep, Claim).join(Claim, Claim.id == ApprovalStep.claim_id)
    total = db.scalar(
        select(func.count())
        .select_from(ApprovalStep)
        .join(Claim, Claim.id == ApprovalStep.claim_id)
        .where(*conditions)
    )
    rows = db.execute(
        base.where(*conditions).order_by(Claim.submitted_at, Claim.id).limit(limit).offset(offset)
    ).all()

    items = []
    for step, claim in rows:
        own_right = step.assigned_approver_id == user.id or (
            step.assigned_approver_id is None and step.approver_role == user.role
        )
        if own_right:
            via = None
        elif step.assigned_approver_id in delegator_ids:
            via = step.assigned_approver_id
        else:
            via = next((d.id for d in delegators if d.role == step.approver_role), None)
        items.append((step, claim, via))
    return items, total or 0


# --- comments --------------------------------------------------------------------


def add_comment(db: Session, user: User, claim_id: int, body: str) -> ClaimComment:
    claim = claims.get_visible_claim(db, user, claim_id)
    comment = ClaimComment(claim_id=claim.id, author_id=user.id, body=body)
    db.add(comment)
    db.flush()
    audit.record(
        db,
        entity_type=claims.ENTITY_TYPE,
        entity_id=claim.id,
        action=AuditAction.COMMENTED,
        changes={f"comments.{comment.id}": {"old": None, "new": body}},
        actor_id=user.id,
    )
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, user: User, claim_id: int) -> list[ClaimComment]:
    claims.get_visible_claim(db, user, claim_id)
    return list(
        db.scalars(
            select(ClaimComment)
            .where(ClaimComment.claim_id == claim_id)
            .order_by(ClaimComment.created_at, ClaimComment.id)
        )
    )
