"""Expense claims, their line items and receipt attachments."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClaimStatus(StrEnum):
    """Claim lifecycle.

    DRAFT -> SUBMITTED -> AUTO_APPROVED | AUTO_REJECTED | PENDING_APPROVAL
    PENDING_APPROVAL -> APPROVED | REJECTED | CLARIFICATION_REQUESTED
    CLARIFICATION_REQUESTED -> (edit, resubmit) -> SUBMITTED
    SUBMITTED -> DUPLICATE when a line repeats an earlier line's vendor, amount and
    receipt number; final, no approval chain, not editable.
    SUBMITTED is transient: the policy engine runs in the same transaction.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTO_APPROVED = "AUTO_APPROVED"
    AUTO_REJECTED = "AUTO_REJECTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    DUPLICATE = "DUPLICATE"


# The owner may change a claim only in these states.
EDITABLE_STATUSES = frozenset({ClaimStatus.DRAFT, ClaimStatus.CLARIFICATION_REQUESTED})


class ExpenseCategory(StrEnum):
    MEAL = "meal"
    HOTEL = "hotel"
    LOCAL = "local"  # local conveyance; one line is one trip
    CAB = "cab"
    AIRFARE = "airfare"
    OTHER = "other"


def _in_values(column: str, enum: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum)
    return f"{column} IN ({values})"


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(_in_values("status", ClaimStatus), name="ck_claims_status"),
        CheckConstraint("currency = 'INR'", name="ck_claims_currency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ClaimStatus.DRAFT.value, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Outcome of the latest policy run and how many times the claim has been submitted.
    policy_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    policy_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submission_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optimistic lock: every UPDATE checks and bumps it, so concurrent writes fail.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    lines: Mapped[list[ClaimLine]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="ClaimLine.position",
    )
    attachments: Mapped[list[ClaimAttachment]] = relationship(
        back_populates="claim",
        order_by="ClaimAttachment.id",
    )

    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": version}


class ClaimLine(Base):
    """One expense on a claim. Fields are nullable so a draft can be partial."""

    __tablename__ = "claim_lines"
    __table_args__ = (
        CheckConstraint(
            f"category IS NULL OR {_in_values('category', ExpenseCategory)}",
            name="ck_claim_lines_category",
        ),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_claim_lines_amount_positive"),
        CheckConstraint("nights IS NULL OR nights > 0", name="ck_claim_lines_nights_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expense_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nights: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receipt_id: Mapped[int | None] = mapped_column(
        ForeignKey("claim_attachments.id", ondelete="RESTRICT"), nullable=True
    )

    claim: Mapped[Claim] = relationship(back_populates="lines")


class ClaimAttachment(Base):
    """Metadata for an uploaded receipt; the file itself lives under ``upload_dir``."""

    __tablename__ = "claim_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    claim: Mapped[Claim] = relationship(back_populates="attachments")
