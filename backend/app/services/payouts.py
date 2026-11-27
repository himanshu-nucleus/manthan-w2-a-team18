"""Payout batches: pick every eligible approved claim in a date range, pay it, export a CSV.

Eligible = APPROVED or AUTO_APPROVED, approved (IST day) within the range, not in a
batch, not held for sample audit; for APPROVED, every step of the latest round is
approved. The batch takes every eligible claim; none can be left out.

Creating a batch is one transaction: lock the claims, write the batch and its items,
mark each claim PAID, write the audit trail. Any failure rolls everything back.
Batch creation is also serialised (PostgreSQL advisory lock), so two finance users at
the same moment cannot both pay a claim; the unique ``payout_batch_items.claim_id``
is the last line of defence.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import (
    PAYABLE_STATUSES,
    ApprovalStep,
    AuditAction,
    BatchStatus,
    Claim,
    ClaimStatus,
    PayoutBatch,
    PayoutBatchItem,
    StepStatus,
    User,
)
from app.services import audit
from app.services.claims import ENTITY_TYPE as CLAIM_ENTITY

ENTITY_TYPE = "payout_batch"
CENTS = Decimal("0.01")
CSV_HEADER = (
    "BatchReference",
    "TransactionReference",
    "ValueDate",
    "EmployeeId",
    "BeneficiaryName",
    "Department",
    "ClaimId",
    "Amount",
    "Currency",
    "Narration",
)
# Characters that make a spreadsheet treat a cell as a formula (CSV injection).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# Arbitrary constant key for pg_advisory_xact_lock: one batch creation at a time.
BATCH_LOCK_KEY = 4_270_001


class InvalidDateRange(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_date_range"
    message = "The date range is not valid."


class NoEligibleClaims(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "no_eligible_claims"
    message = "No approved claims in the selected range."


class AmountMismatch(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "claim_amount_mismatch"
    message = "A claim's total does not match the sum of its lines; no batch was created."


class BatchNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "payout_batch_not_found"
    message = "Payout batch not found."


# --- dates -------------------------------------------------------------------------


def business_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def business_today() -> date:
    return datetime.now(business_tz()).date()


def resolve_range(
    range_name: Literal["TODAY"] | None, from_date: date | None, to_date: date | None
) -> tuple[date, date]:
    """Validate the request and return (from, to). 400 with a clear message otherwise."""
    today = business_today()
    if range_name == "TODAY":
        if from_date is not None or to_date is not None:
            raise InvalidDateRange("Send either range=TODAY or fromDate and toDate, not both.")
        return today, today
    if from_date is None or to_date is None:
        raise InvalidDateRange("fromDate and toDate are both required unless range=TODAY.")
    future = [name for name, d in (("fromDate", from_date), ("toDate", to_date)) if d > today]
    if future:
        raise InvalidDateRange(
            f"{' and '.join(future)} cannot be in the future (today is {today.isoformat()}).",
            details={"today": today.isoformat()},
        )
    if from_date > to_date:
        raise InvalidDateRange("fromDate must be on or before toDate.")
    return from_date, to_date


def _bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """[start of from_date, start of the day after to_date) in the business time zone."""
    tz = business_tz()
    return (
        datetime.combine(from_date, time.min, tz),
        datetime.combine(to_date + timedelta(days=1), time.min, tz),
    )


# --- eligibility -------------------------------------------------------------------


def held_for_sample_audit(claim: Claim) -> bool:
    """Hook for the 10% sample audit (not built yet): a claim held for audit must not
    be paid until it is cleared."""
    return False


def payable_amount(claim: Claim) -> Decimal:
    """What the claim pays: the sum of its approved lines. Lines are approved or rejected
    with the whole claim today, so every line of an approved claim counts."""
    return sum((line.amount for line in claim.lines if line.amount is not None), Decimal("0"))


def _fully_approved(db: Session, claim: Claim) -> bool:
    """AUTO_APPROVED has no chain. APPROVED needs every step of its latest round approved."""
    if claim.status == ClaimStatus.AUTO_APPROVED:
        return True
    statuses = list(
        db.scalars(
            select(ApprovalStep.status).where(
                ApprovalStep.claim_id == claim.id,
                ApprovalStep.round == claim.submission_round,
            )
        )
    )
    return bool(statuses) and all(s == StepStatus.APPROVED for s in statuses)


def eligible_claims(
    db: Session, from_date: date, to_date: date, *, lock: bool = False
) -> list[Claim]:
    start, end = _bounds(from_date, to_date)
    query = (
        select(Claim)
        .where(
            Claim.status.in_([s.value for s in PAYABLE_STATUSES]),
            Claim.approved_at.is_not(None),
            Claim.approved_at >= start,
            Claim.approved_at < end,
            Claim.payout_batch_id.is_(None),
            Claim.paid_at.is_(None),
        )
        .order_by(Claim.approved_at, Claim.id)
    )
    if lock:
        query = query.with_for_update()
    claims = [
        claim
        for claim in db.scalars(query)
        if not held_for_sample_audit(claim) and _fully_approved(db, claim)
    ]
    mismatched = [
        {
            "claim_id": c.id,
            "total_amount": str(c.total_amount),
            "sum_of_lines": str(payable_amount(c)),
        }
        for c in claims
        if payable_amount(c).quantize(CENTS) != c.total_amount.quantize(CENTS)
    ]
    if mismatched:
        raise AmountMismatch(details={"claims": mismatched})
    return claims


@dataclass
class Preview:
    from_date: date
    to_date: date
    claims: list[Claim]

    @property
    def total(self) -> Decimal:
        return sum((payable_amount(c) for c in self.claims), Decimal("0")).quantize(CENTS)


def preview(
    db: Session,
    range_name: Literal["TODAY"] | None,
    from_date: date | None,
    to_date: date | None,
) -> Preview:
    start, end = resolve_range(range_name, from_date, to_date)
    return Preview(start, end, eligible_claims(db, start, end))


# --- batch creation ----------------------------------------------------------------


def employee_code(user_id: int) -> str:
    return f"EMP{user_id:04d}"


def claim_code(claim_id: int) -> str:
    return f"CLM-{claim_id:06d}"


def _next_reference(db: Session, value_date: date) -> str:
    prefix = f"PB-{value_date:%Y%m%d}-"
    used = db.scalar(
        select(func.count())
        .select_from(PayoutBatch)
        .where(PayoutBatch.batch_reference.like(f"{prefix}%"))
    )
    return f"{prefix}{(used or 0) + 1:03d}"


def _serialise_batch_creation(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BATCH_LOCK_KEY})


def create_batch(
    db: Session,
    user: User,
    range_name: Literal["TODAY"] | None,
    from_date: date | None,
    to_date: date | None,
) -> PayoutBatch:
    start, end = resolve_range(range_name, from_date, to_date)
    _serialise_batch_creation(db)
    claims = eligible_claims(db, start, end, lock=True)
    if not claims:
        raise NoEligibleClaims(details={"from_date": start.isoformat(), "to_date": end.isoformat()})

    now = datetime.now(UTC)
    value_date = business_today()
    reference = _next_reference(db, value_date)
    amounts = {c.id: payable_amount(c).quantize(CENTS) for c in claims}
    batch = PayoutBatch(
        batch_reference=reference,
        from_date=start,
        to_date=end,
        value_date=value_date,
        claim_count=len(claims),
        total_amount=sum(amounts.values(), Decimal("0")),
        currency="INR",
        status=BatchStatus.CREATED.value,
        file_name=f"payout_{reference}.csv",
        export_count=0,
        created_by=user.id,
    )
    db.add(batch)
    db.flush()

    employees = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_({c.employee_id for c in claims})))
    }
    for number, claim in enumerate(claims, start=1):
        employee = employees[claim.employee_id]
        txn = f"{reference}-{number:04d}"
        db.add(
            PayoutBatchItem(
                batch_id=batch.id,
                claim_id=claim.id,
                employee_id=employee.id,
                transaction_reference=txn,
                amount=amounts[claim.id],
                employee_code=employee_code(employee.id),
                beneficiary_name=employee.full_name,
                department=employee.department,
                claim_code=claim_code(claim.id),
                narration=f"Expense reimbursement {claim_code(claim.id)}",
            )
        )
        previous = claim.status
        claim.status = ClaimStatus.PAID.value
        claim.paid_at = now
        claim.payout_batch_id = batch.id
        claim.updated_by = user.id
        audit.record(
            db,
            entity_type=CLAIM_ENTITY,
            entity_id=claim.id,
            action=AuditAction.PAID,
            changes={
                "status": {"old": previous, "new": ClaimStatus.PAID.value},
                "paid_at": {"old": None, "new": now.isoformat()},
                "payout_batch_reference": {"old": None, "new": reference},
                "transaction_reference": {"old": None, "new": txn},
                "amount": {"old": None, "new": str(amounts[claim.id])},
            },
            actor_id=user.id,
        )

    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=batch.id,
        action=AuditAction.BATCH_CREATED,
        changes={
            "batch_reference": {"old": None, "new": reference},
            "from_date": {"old": None, "new": start.isoformat()},
            "to_date": {"old": None, "new": end.isoformat()},
            "claim_count": {"old": None, "new": batch.claim_count},
            "total_amount": {"old": None, "new": str(batch.total_amount)},
            "claim_ids": {"old": None, "new": [c.id for c in claims]},
        },
        actor_id=user.id,
    )
    db.commit()
    db.refresh(batch)
    return batch


# --- reads and export ----------------------------------------------------------------


def list_batches(db: Session, *, limit: int, offset: int) -> tuple[list[PayoutBatch], int]:
    total = db.scalar(select(func.count()).select_from(PayoutBatch)) or 0
    rows = db.scalars(
        select(PayoutBatch)
        .order_by(PayoutBatch.created_at.desc(), PayoutBatch.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


def get_batch(db: Session, batch_id: int) -> PayoutBatch:
    batch = db.get(PayoutBatch, batch_id)
    if batch is None:
        raise BatchNotFound()
    return batch


def _cell(value: object) -> str:
    text_value = "" if value is None else str(value)
    if text_value.startswith(FORMULA_PREFIXES):
        return "'" + text_value
    return text_value


def _money(value: Decimal) -> str:
    return f"{value.quantize(CENTS):.2f}"  # 12450.00: two decimals, no separators


def render_csv(batch: PayoutBatch) -> bytes:
    """The bank file, built only from the saved batch and items: always the same bytes."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADER)
    value_date = f"{batch.value_date:%d-%m-%Y}"
    for item in batch.items:
        writer.writerow(
            [
                _cell(batch.batch_reference),
                _cell(item.transaction_reference),
                _cell(value_date),
                _cell(item.employee_code),
                _cell(item.beneficiary_name),
                _cell(item.department),
                _cell(item.claim_code),
                _money(item.amount),
                _cell(batch.currency),
                _cell(item.narration),
            ]
        )
    writer.writerow(["TRAILER", batch.claim_count, _money(batch.total_amount)])
    return buffer.getvalue().encode("utf-8")


def export_batch(db: Session, user: User, batch_id: int) -> tuple[PayoutBatch, bytes]:
    batch = db.scalar(select(PayoutBatch).where(PayoutBatch.id == batch_id).with_for_update())
    if batch is None:
        raise BatchNotFound()
    content = render_csv(batch)
    now = datetime.now(UTC)
    previous_status = batch.status
    batch.export_count += 1
    batch.status = BatchStatus.EXPORTED.value
    if batch.first_exported_at is None:
        batch.first_exported_at = now
    audit.record(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=batch.id,
        action=AuditAction.BATCH_EXPORTED,
        changes={
            "file_name": {"old": None, "new": batch.file_name},
            "export_count": {"old": batch.export_count - 1, "new": batch.export_count},
            "status": {"old": previous_status, "new": batch.status},
            "bytes": {"old": None, "new": len(content)},
        },
        actor_id=user.id,
    )
    db.commit()
    return batch, content
