"""Policy rules and settings as configuration, and the stored result of each evaluation.

Limits live in ``policy_rules.params`` and ``policy_settings``; changing one is a
data change (``PUT /policy-rules/{code}``), never a code change.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class PolicyOutcome(StrEnum):
    """Ordered by severity: the most severe outcome of all findings wins."""

    AUTO_APPROVE = "AUTO_APPROVE"
    ROUTE_FOR_APPROVAL = "ROUTE_FOR_APPROVAL"
    AUTO_REJECT = "AUTO_REJECT"
    # Same vendor + amount + receipt number as an earlier line: the claim becomes
    # DUPLICATE, which is final and gets no approval chain.
    MARK_DUPLICATE = "MARK_DUPLICATE"

    @property
    def severity(self) -> int:
        return _SEVERITY[self]


_SEVERITY = {
    PolicyOutcome.AUTO_APPROVE: 0,
    PolicyOutcome.ROUTE_FOR_APPROVAL: 1,
    PolicyOutcome.AUTO_REJECT: 2,
    PolicyOutcome.MARK_DUPLICATE: 3,
}

BREACH_OUTCOMES = ("ROUTE_FOR_APPROVAL", "AUTO_REJECT", "MARK_DUPLICATE")


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    __table_args__ = (
        CheckConstraint(
            "outcome_on_breach IN ('ROUTE_FOR_APPROVAL', 'AUTO_REJECT', 'MARK_DUPLICATE')",
            name="ck_policy_rules_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Expense category the rule is limited to; NULL means every line.
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    outcome_on_breach: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    reason_template: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class PolicySetting(Base):
    """Named settings that are not per-rule: tier-1 cities, approval thresholds,
    the auto-approve ceiling."""

    __tablename__ = "policy_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONType, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ClaimPolicyResult(Base):
    """One row per line (or one claim-level row, ``line_position`` NULL) per submission.

    Rows are kept for every round, so an earlier decision stays explainable after
    the claim is edited or a rule limit changes (``rule_snapshot`` holds the values used).
    """

    __tablename__ = "claim_policy_results"
    __table_args__ = (Index("ix_claim_policy_results_claim_round", "claim_id", "round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    line_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_codes: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    reasons: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
