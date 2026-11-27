"""Payout batches: approved claims grouped for one mock bank file, then marked PAID.

Each item keeps a copy of every value printed in the file (employee code, name,
department, claim code, narration), so downloading the file again later always
produces exactly the same bytes, even after a user is renamed or moved.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
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


class BatchStatus(StrEnum):
    CREATED = "CREATED"  # claims are PAID; file not downloaded yet
    EXPORTED = "EXPORTED"  # file downloaded at least once


class PayoutBatch(Base):
    __tablename__ = "payout_batches"
    __table_args__ = (
        CheckConstraint("status IN ('CREATED', 'EXPORTED')", name="ck_payout_batches_status"),
        CheckConstraint("claim_count > 0", name="ck_payout_batches_not_empty"),
        CheckConstraint("total_amount > 0", name="ck_payout_batches_total_positive"),
        CheckConstraint("to_date >= from_date", name="ck_payout_batches_dates"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date] = mapped_column(Date, nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    file_name: Mapped[str] = mapped_column(String(100), nullable=False)
    export_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_exported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list[PayoutBatchItem]] = relationship(
        back_populates="batch", order_by="PayoutBatchItem.id"
    )


class PayoutBatchItem(Base):
    __tablename__ = "payout_batch_items"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payout_batch_items_amount_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("payout_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Unique: a claim can be paid in one batch only, whatever the service does.
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    transaction_reference: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Values printed in the file, copied when the batch is created.
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    beneficiary_name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claim_code: Mapped[str] = mapped_column(String(32), nullable=False)
    narration: Mapped[str] = mapped_column(String(140), nullable=False)

    batch: Mapped[PayoutBatch] = relationship(back_populates="items")
