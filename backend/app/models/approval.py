"""The approval chain of each claim, delegations while on leave, and claim comments."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StepStatus(StrEnum):
    WAITING = "WAITING"  # a later step, not yet reached
    PENDING = "PENDING"  # the step an approver must act on now
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT_BACK = "SENT_BACK"
    CANCELLED = "CANCELLED"  # closed because an earlier step rejected or sent back


class ApprovalStep(Base):
    """One step of one claim's chain, built at submit and kept for the record.

    ``assigned_approver_id`` set: only that person (or their active delegate) may act.
    ``assigned_approver_id`` NULL: any active user holding ``approver_role`` may act.
    """

    __tablename__ = "approval_steps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('WAITING', 'PENDING', 'APPROVED', 'REJECTED', 'SENT_BACK', 'CANCELLED')",
            name="ck_approval_steps_status",
        ),
        Index("ix_approval_steps_claim_round", "claim_id", "round"),
        Index("ix_approval_steps_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_approver_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    acted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    on_behalf_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": version}


class Delegation(Base):
    __tablename__ = "delegations"
    __table_args__ = (
        CheckConstraint("delegator_id <> delegate_id", name="ck_delegations_not_self"),
        CheckConstraint("to_date >= from_date", name="ck_delegations_dates"),
        Index("ix_delegations_delegate", "delegate_id", "active"),
        Index("ix_delegations_delegator", "delegator_id", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delegator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    delegate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClaimComment(Base):
    __tablename__ = "claim_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
