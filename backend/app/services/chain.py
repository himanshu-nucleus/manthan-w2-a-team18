"""Building a claim's approval chain, and deciding who may act on its current step.

Chain (thresholds from the ``approval_thresholds`` setting, compared with ``>``):
  1. the claimant's manager          always
  2. any finance auditor             total > finance_auditor threshold
  3. any finance head                total > finance_head threshold

Guard rails:
* the claimant can never act on any step of their own claim, directly or as a delegate;
* one person (or anyone acting on their behalf) acts on at most one step per round;
* a claimant with no usable manager falls back to the finance heads;
* if a step has nobody eligible, submit fails with 409 instead of skipping the step;
* delegation is followed one hop only.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import status
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import ApprovalStep, Claim, Delegation, Role, StepStatus, User
from app.policy.rules import PolicyConfig

APPROVER_ROLES = (Role.LINE_MANAGER, Role.FINANCE_AUDITOR, Role.FINANCE_HEAD)
ROLE_RANK = {
    Role.EMPLOYEE: 0,
    Role.LINE_MANAGER: 1,
    Role.FINANCE_AUDITOR: 2,
    Role.FINANCE_HEAD: 3,
}


class NoEligibleApprover(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "no_eligible_approver"
    message = "Nobody other than the claimant is available to approve a step of this claim."


class NotCurrentApprover(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "not_current_approver"
    message = "You are not the approver of this claim's current step."


def build_chain(db: Session, claim: Claim, config: PolicyConfig) -> list[ApprovalStep]:
    claimant = db.get(User, claim.employee_id)
    assert claimant is not None
    plan: list[tuple[str, int | None]] = []  # (approver_role, assigned person or None = pool)

    manager = db.get(User, claimant.manager_id) if claimant.manager_id else None
    if manager is not None and manager.is_active and manager.id != claimant.id:
        plan.append((Role.LINE_MANAGER.value, manager.id))
    else:
        plan.append((Role.FINANCE_HEAD.value, None))

    thresholds = config.approval_thresholds
    for role in (Role.FINANCE_AUDITOR, Role.FINANCE_HEAD):
        limit = thresholds.get(role.value)
        if limit is not None and claim.total_amount > limit:
            plan.append((role.value, None))

    _check_every_step_has_someone(db, claimant, plan)

    steps = [
        ApprovalStep(
            claim_id=claim.id,
            round=claim.submission_round,
            step_order=order,
            approver_role=role,
            assigned_approver_id=person,
            status=StepStatus.PENDING.value if order == 1 else StepStatus.WAITING.value,
        )
        for order, (role, person) in enumerate(plan, start=1)
    ]
    db.add_all(steps)
    return steps


def _check_every_step_has_someone(
    db: Session, claimant: User, plan: list[tuple[str, int | None]]
) -> None:
    named = {person for _, person in plan if person is not None}
    pool_needs = Counter(role for role, person in plan if person is None)
    for role, needed in pool_needs.items():
        available = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == role,
                User.is_active,
                User.id != claimant.id,
                User.id.not_in(named) if named else true(),
            )
        )
        if (available or 0) < needed:
            raise NoEligibleApprover(details={"role": role, "needed": needed})


def current_step(db: Session, claim: Claim) -> ApprovalStep | None:
    return db.scalar(
        select(ApprovalStep).where(
            ApprovalStep.claim_id == claim.id,
            ApprovalStep.round == claim.submission_round,
            ApprovalStep.status == StepStatus.PENDING.value,
        )
    )


def active_delegators(db: Session, delegate_id: int, on: date) -> list[User]:
    """People who have delegated to ``delegate_id`` for ``on`` (one hop only)."""
    return list(
        db.scalars(
            select(User)
            .join(Delegation, Delegation.delegator_id == User.id)
            .where(
                Delegation.delegate_id == delegate_id,
                Delegation.active,
                Delegation.from_date <= on,
                Delegation.to_date >= on,
                User.is_active,
            )
        )
    )


def acting_for(db: Session, user: User, claim: Claim, step: ApprovalStep, on: date) -> int | None:
    """Check ``user`` may act on ``step``. Returns the id of the person they act on
    behalf of (None when acting in their own right); raises 403 otherwise, and every
    refusal is audited as ACCESS_DENIED."""
    try:
        return _acting_for(db, user, claim, step, on)
    except NotCurrentApprover as exc:
        from app.services import access  # local: access imports nothing from chain

        access.deny(
            db,
            user,
            reason=exc.message,
            entity_type="approval_step",
            entity_id=step.id,
            claim_id=claim.id,
        )
        raise


def _acting_for(db: Session, user: User, claim: Claim, step: ApprovalStep, on: date) -> int | None:
    if user.id == claim.employee_id:
        raise NotCurrentApprover("You cannot act on your own claim.")

    already = set(
        db.scalars(
            select(ApprovalStep.acted_by_id).where(
                ApprovalStep.claim_id == claim.id,
                ApprovalStep.round == step.round,
                ApprovalStep.id != step.id,
                ApprovalStep.acted_by_id.is_not(None),
            )
        )
    ) | set(
        db.scalars(
            select(ApprovalStep.on_behalf_of_id).where(
                ApprovalStep.claim_id == claim.id,
                ApprovalStep.round == step.round,
                ApprovalStep.id != step.id,
                ApprovalStep.on_behalf_of_id.is_not(None),
            )
        )
    )
    if user.id in already:
        raise NotCurrentApprover("You already acted on an earlier step of this claim.")

    if step.assigned_approver_id is not None:
        if user.id == step.assigned_approver_id:
            return None
        for delegator in active_delegators(db, user.id, on):
            if delegator.id == step.assigned_approver_id:
                return delegator.id
    else:
        if user.role == step.approver_role:
            return None
        for delegator in active_delegators(db, user.id, on):
            if (
                delegator.role == step.approver_role
                and delegator.id != claim.employee_id
                and delegator.id not in already
            ):
                return delegator.id
    raise NotCurrentApprover()
