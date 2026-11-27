"""Claim rules: ownership, draft vs submit, validation, policy and the audit trail.

Access rule: an employee sees only their own claims; every other role sees all
claims. Only the owner may change a claim, and only while it is DRAFT or
CLARIFICATION_REQUESTED. A claim the caller may not see is reported as not found,
so ids cannot be probed.

Submit (and resubmit) runs, in one transaction: full validation -> SUBMITTED ->
policy engine -> AUTO_APPROVED | AUTO_REJECTED | PENDING_APPROVAL with a new chain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    EDITABLE_STATUSES,
    AuditAction,
    AuditEvent,
    Claim,
    ClaimAttachment,
    ClaimLine,
    ClaimPolicyResult,
    ClaimStatus,
    ExpenseCategory,
    PolicyOutcome,
    Role,
    User,
)
from app.policy import engine
from app.schemas.claim import ClaimWrite
from app.services import audit, chain

ENTITY_TYPE = "claim"

CENTS = Decimal("0.01")

LINE_FIELDS = (
    "category",
    "amount",
    "expense_date",
    "vendor",
    "description",
    "city",
    "nights",
    "receipt_number",
    "receipt_id",
)


class ClaimNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "claim_not_found"
    message = "Claim not found."


class NotClaimOwner(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Only the employee who owns this claim can change it."


class ClaimNotEditable(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "claim_not_editable"
    message = "Only a DRAFT or CLARIFICATION_REQUESTED claim can be changed."


class ClaimInvalid(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    message = "The claim is not valid."

    def __init__(self, errors: list[dict[str, str]], message: str | None = None) -> None:
        super().__init__(message, details={"fields": errors})


# --- access ------------------------------------------------------------------


def sees_all_claims(user: User) -> bool:
    return user.role != Role.EMPLOYEE


def get_visible_claim(db: Session, user: User, claim_id: int, *, lock: bool = False) -> Claim:
    query = select(Claim).where(Claim.id == claim_id)
    if lock:
        query = query.with_for_update()
    claim = db.scalar(query)
    if claim is None or (not sees_all_claims(user) and claim.employee_id != user.id):
        raise ClaimNotFound()
    return claim


def get_editable_claim(db: Session, user: User, claim_id: int) -> Claim:
    """The caller's own editable claim, row-locked for the rest of the transaction."""
    claim = get_visible_claim(db, user, claim_id, lock=True)
    if claim.employee_id != user.id:
        raise NotClaimOwner()
    if claim.status not in EDITABLE_STATUSES:
        raise ClaimNotEditable(details={"status": claim.status})
    return claim


# --- reads -------------------------------------------------------------------


def list_claims(
    db: Session, user: User, *, status_filter: ClaimStatus | None, limit: int, offset: int
) -> tuple[list[Claim], int]:
    conditions = []
    if not sees_all_claims(user):
        conditions.append(Claim.employee_id == user.id)
    if status_filter is not None:
        conditions.append(Claim.status == status_filter.value)

    total = db.scalar(select(func.count()).select_from(Claim).where(*conditions)) or 0
    query = (
        select(Claim)
        .where(*conditions)
        .order_by(Claim.updated_at.desc(), Claim.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(query)), total


def claim_history(db: Session, user: User, claim_id: int) -> list[AuditEvent]:
    get_visible_claim(db, user, claim_id)
    return audit.history(db, entity_type=ENTITY_TYPE, entity_id=claim_id)


def policy_results(db: Session, user: User, claim_id: int) -> tuple[Claim, list[ClaimPolicyResult]]:
    """Results of the latest policy run (empty before the first submit)."""
    claim = get_visible_claim(db, user, claim_id)
    rows = db.scalars(
        select(ClaimPolicyResult)
        .where(
            ClaimPolicyResult.claim_id == claim.id,
            ClaimPolicyResult.round == claim.submission_round,
        )
        .order_by(ClaimPolicyResult.line_position.is_(None), ClaimPolicyResult.line_position)
    )
    return claim, list(rows)


# --- writes ------------------------------------------------------------------


def create_claim(db: Session, user: User, body: ClaimWrite) -> Claim:
    claim = Claim(
        employee_id=user.id,
        status=ClaimStatus.DRAFT.value,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(claim)
    db.flush()  # assigns claim.id, needed by the receipt check and the audit row

    _apply(db, claim, body)
    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=claim.id,
        action=AuditAction.CREATED,
        changes=audit.diff({}, _snapshot(claim)),
        actor_id=user.id,
    )
    if body.action == "submit":
        _submit(db, claim, user)

    db.commit()
    db.refresh(claim)
    return claim


def update_claim(db: Session, user: User, claim_id: int, body: ClaimWrite) -> Claim:
    claim = get_editable_claim(db, user, claim_id)
    before = _snapshot(claim)

    _apply(db, claim, body)
    changes = audit.diff(before, _snapshot(claim))
    if changes:
        claim.updated_by = user.id
        audit.record(
            db,
            entity_type=ENTITY_TYPE,
            entity_id=claim.id,
            action=AuditAction.UPDATED,
            changes=changes,
            actor_id=user.id,
        )
    if body.action == "submit":
        _submit(db, claim, user)

    db.commit()
    db.refresh(claim)
    return claim


def submit_claim(db: Session, user: User, claim_id: int) -> Claim:
    """Submit (or resubmit after a send-back) the claim exactly as it is saved."""
    claim = get_editable_claim(db, user, claim_id)
    _submit(db, claim, user)
    db.commit()
    db.refresh(claim)
    return claim


# --- internals ---------------------------------------------------------------


def _apply(db: Session, claim: Claim, body: ClaimWrite) -> None:
    """Replace the claim's content with ``body``. Checks shape only, not completeness."""
    _check_receipts_belong_to_claim(db, claim, body)

    claim.title = body.title
    claim.currency = body.currency
    claim.lines.clear()
    db.flush()  # delete the old lines before positions are reused
    for position, line in enumerate(body.lines, start=1):
        values = line.model_dump(include=set(LINE_FIELDS))
        if values["amount"] is not None:
            values["amount"] = _money(values["amount"])
        claim.lines.append(ClaimLine(position=position, **values))
    claim.total_amount = _money(
        sum((line.amount for line in claim.lines if line.amount is not None), Decimal("0"))
    )


def _money(value: Decimal) -> Decimal:
    """Two decimal places, so 600 and 600.00 compare equal in the audit diff."""
    return value.quantize(CENTS)


def _check_receipts_belong_to_claim(db: Session, claim: Claim, body: ClaimWrite) -> None:
    wanted = {line.receipt_id for line in body.lines if line.receipt_id is not None}
    if not wanted:
        return
    owned = set(
        db.scalars(
            select(ClaimAttachment.id).where(
                ClaimAttachment.claim_id == claim.id, ClaimAttachment.id.in_(wanted)
            )
        )
    )
    errors = [
        {
            "field": f"lines.{index}.receipt_id",
            "message": "receipt_id must be a receipt uploaded to this claim",
        }
        for index, line in enumerate(body.lines)
        if line.receipt_id is not None and line.receipt_id not in owned
    ]
    if errors:
        raise ClaimInvalid(errors)


def _submit(db: Session, claim: Claim, user: User) -> None:
    errors = _submission_errors(db, claim)
    if errors:
        raise ClaimInvalid(errors, "The claim cannot be submitted until these fields are fixed.")

    previous = claim.status
    claim.submission_round += 1
    claim.status = ClaimStatus.SUBMITTED.value
    claim.submitted_at = datetime.now(UTC)
    claim.updated_by = user.id
    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=claim.id,
        action=(
            AuditAction.RESUBMITTED
            if previous == ClaimStatus.CLARIFICATION_REQUESTED
            else AuditAction.SUBMITTED
        ),
        changes={
            "status": {"old": previous, "new": ClaimStatus.SUBMITTED.value},
            "submitted_at": {"old": None, "new": audit.json_safe(claim.submitted_at)},
            "submission_round": {"old": claim.submission_round - 1, "new": claim.submission_round},
        },
        actor_id=user.id,
    )
    db.flush()
    _apply_policy(db, claim, user)


def _apply_policy(db: Session, claim: Claim, user: User) -> None:
    """Run the policy engine, store per-line results, and move the claim on."""
    evaluation = engine.evaluate(db, claim)
    evaluated_at = datetime.now(UTC)
    findings = [*evaluation.lines, evaluation.claim_level]

    for finding in findings:
        if finding.line_position is None and not finding.rule_codes:
            continue  # no claim-level findings: no row
        db.add(
            ClaimPolicyResult(
                claim_id=claim.id,
                round=claim.submission_round,
                line_position=finding.line_position,
                outcome=finding.outcome.value,
                rule_codes=finding.rule_codes,
                reasons=finding.reasons,
                rule_snapshot=finding.rule_snapshot,
                evaluated_at=evaluated_at,
            )
        )

    next_status = {
        PolicyOutcome.AUTO_APPROVE: ClaimStatus.AUTO_APPROVED,
        PolicyOutcome.AUTO_REJECT: ClaimStatus.AUTO_REJECTED,
        PolicyOutcome.ROUTE_FOR_APPROVAL: ClaimStatus.PENDING_APPROVAL,
    }[evaluation.outcome]
    claim.policy_outcome = evaluation.outcome.value
    claim.policy_evaluated_at = evaluated_at
    claim.status = next_status.value

    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=claim.id,
        action=AuditAction.POLICY_EVALUATED,
        changes={
            "status": {"old": ClaimStatus.SUBMITTED.value, "new": next_status.value},
            "policy_outcome": {"old": None, "new": evaluation.outcome.value},
            "findings": {
                "old": None,
                "new": [
                    {
                        "line": f.line_position,
                        "outcome": f.outcome.value,
                        "rule_codes": f.rule_codes,
                        "reasons": f.reasons,
                    }
                    for f in findings
                    if f.rule_codes
                ],
            },
        },
        actor_id=user.id,
    )

    if next_status == ClaimStatus.PENDING_APPROVAL:
        steps = chain.build_chain(db, claim, engine.load_config(db))
        db.flush()
        audit.record(
            db,
            entity_type=ENTITY_TYPE,
            entity_id=claim.id,
            action=AuditAction.CHAIN_BUILT,
            changes={
                "approval_steps": {
                    "old": None,
                    "new": [
                        {
                            "step": step.step_order,
                            "role": step.approver_role,
                            "assigned_approver_id": step.assigned_approver_id,
                        }
                        for step in steps
                    ],
                }
            },
            actor_id=user.id,
        )


def _submission_errors(db: Session, claim: Claim) -> list[dict[str, str]]:
    """Full validation, run only on submit. Lists every problem, not just the first.
    The receipt threshold comes from the active RECEIPT_REQUIRED policy rule."""
    errors: list[dict[str, str]] = []
    receipt_above = engine.receipt_required_above(db)

    def missing(field: str, message: str = "is required to submit") -> None:
        errors.append({"field": field, "message": message})

    if not claim.lines:
        missing("lines", "at least one line item is required to submit")

    for index, line in enumerate(claim.lines):
        prefix = f"lines.{index}"
        for field in ("category", "amount", "expense_date", "vendor"):
            if getattr(line, field) is None:
                missing(f"{prefix}.{field}")
        if line.category == ExpenseCategory.HOTEL:
            for field in ("city", "nights"):
                if getattr(line, field) is None:
                    missing(f"{prefix}.{field}", "is required for a hotel line")
        if receipt_above is not None and line.amount is not None and line.amount > receipt_above:
            for field in ("receipt_number", "receipt_id"):
                if getattr(line, field) is None:
                    missing(
                        f"{prefix}.{field}",
                        f"is required when the amount is above {receipt_above} INR",
                    )
    return errors


def _snapshot(claim: Claim) -> dict[str, Any]:
    """Flat, JSON-safe view of the editable content, used to diff for the audit trail."""
    data: dict[str, Any] = {
        "title": claim.title,
        "currency": claim.currency,
        "status": claim.status,
        "total_amount": audit.json_safe(claim.total_amount),
    }
    for index, line in enumerate(claim.lines):
        for field in LINE_FIELDS:
            value = getattr(line, field)
            if value is not None:
                data[f"lines.{index}.{field}"] = audit.json_safe(value)
    return data
