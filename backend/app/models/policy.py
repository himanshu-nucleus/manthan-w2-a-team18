"""Expense policy limits: one row of configuration the finance head can change.

The defaults live in ``app.services.policy`` and are inserted only when the row
is missing; after that the database row is the single source of truth.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

POLICY_ROW_ID = 1


class PolicySettings(Base):
    __tablename__ = "policy_settings"
    __table_args__ = (
        CheckConstraint(f"id = {POLICY_ROW_ID}", name="ck_policy_settings_single_row"),
        CheckConstraint("receipt_required_above >= 0", name="ck_policy_settings_receipt_threshold"),
        CheckConstraint("meal_daily_limit > 0", name="ck_policy_settings_meal_limit"),
        CheckConstraint(
            "hotel_tier1_nightly_limit > 0", name="ck_policy_settings_hotel_tier1_limit"
        ),
        CheckConstraint(
            "hotel_other_nightly_limit > 0", name="ck_policy_settings_hotel_other_limit"
        ),
        CheckConstraint("local_trip_limit > 0", name="ck_policy_settings_local_limit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    receipt_required_above: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    meal_daily_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hotel_tier1_nightly_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hotel_other_nightly_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    local_trip_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tier1_cities: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
