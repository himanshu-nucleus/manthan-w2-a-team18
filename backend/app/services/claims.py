"""Claim rules: ownership, draft vs submit, validation and the audit trail.

Access rule: an employee sees only their own claims; every other role sees all
claims. Only the owner may change a claim, and only while it is a DRAFT.
A claim the caller may not see is reported as not found, so ids cannot be probed.
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
    AuditAction,
    AuditEvent,
    Claim,
    ClaimAttachment,
    ClaimLine,
    ClaimStatus,
    ExpenseCategory,
    Role,
    User,
)
from app.schemas.claim import ClaimWrite
from app.services import audit

ENTITY_TYPE = "claim"

# A receipt number and an uploaded receipt are mandatory above this amount (INR).
RECEIPT_REQUIRED_ABOVE = Decimal("500")
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
    message = "Only a DRAFT claim can be changed."


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
    """The caller's own DRAFT claim, row-locked for the rest of the transaction."""
    claim = get_visible_claim(db, user, claim_id, lock=True)
    if claim.employee_id != user.id:
        raise NotClaimOwner()
    if claim.status != ClaimStatus.DRAFT:
        raise ClaimNotEditable()
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
    errors = _submission_errors(claim)
    if errors:
        raise ClaimInvalid(errors, "The claim cannot be submitted until these fields are fixed.")

    claim.status = ClaimStatus.SUBMITTED.value
    claim.submitted_at = datetime.now(UTC)
    claim.updated_by = user.id
    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=claim.id,
        action=AuditAction.SUBMITTED,
        changes={
            "status": {"old": ClaimStatus.DRAFT.value, "new": ClaimStatus.SUBMITTED.value},
            "submitted_at": {"old": None, "new": audit.json_safe(claim.submitted_at)},
        },
        actor_id=user.id,
    )


def _submission_errors(claim: Claim) -> list[dict[str, str]]:
    """Full validation, run only on submit. Lists every problem, not just the first."""
    errors: list[dict[str, str]] = []

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
        if line.amount is not None and line.amount > RECEIPT_REQUIRED_ABOVE:
            for field in ("receipt_number", "receipt_id"):
                if getattr(line, field) is None:
                    missing(
                        f"{prefix}.{field}",
                        f"is required when the amount is above {RECEIPT_REQUIRED_ABOVE} INR",
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
