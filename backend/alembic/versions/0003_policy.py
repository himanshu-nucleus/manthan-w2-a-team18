"""policy settings, line policy flags, DUPLICATE status and the local category

The default policy row is not inserted here: the app inserts it at startup (or on
first read) when it is missing, and never overwrites the finance head's changes.

Revision ID: 0003_policy
Revises: 0002_claims
Create Date: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_policy"
down_revision = "0002_claims"
branch_labels = None
depends_on = None

OLD_STATUSES = "'DRAFT', 'SUBMITTED'"
NEW_STATUSES = "'DRAFT', 'SUBMITTED', 'DUPLICATE'"
OLD_CATEGORIES = "'meal', 'hotel', 'cab', 'airfare', 'other'"
NEW_CATEGORIES = "'meal', 'hotel', 'local', 'cab', 'airfare', 'other'"


def _money(name: str) -> sa.Column:
    return sa.Column(name, sa.Numeric(12, 2), nullable=False)


def _replace_checks(statuses: str, categories: str) -> None:
    op.drop_constraint("ck_claims_status", "claims", type_="check")
    op.create_check_constraint("ck_claims_status", "claims", f"status IN ({statuses})")
    op.drop_constraint("ck_claim_lines_category", "claim_lines", type_="check")
    op.create_check_constraint(
        "ck_claim_lines_category",
        "claim_lines",
        f"category IS NULL OR category IN ({categories})",
    )


def upgrade() -> None:
    op.create_table(
        "policy_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        _money("receipt_required_above"),
        _money("meal_daily_limit"),
        _money("hotel_tier1_nightly_limit"),
        _money("hotel_other_nightly_limit"),
        _money("local_trip_limit"),
        sa.Column(
            "tier1_cities",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "updated_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("id = 1", name="ck_policy_settings_single_row"),
        sa.CheckConstraint(
            "receipt_required_above >= 0", name="ck_policy_settings_receipt_threshold"
        ),
        sa.CheckConstraint("meal_daily_limit > 0", name="ck_policy_settings_meal_limit"),
        sa.CheckConstraint(
            "hotel_tier1_nightly_limit > 0", name="ck_policy_settings_hotel_tier1_limit"
        ),
        sa.CheckConstraint(
            "hotel_other_nightly_limit > 0", name="ck_policy_settings_hotel_other_limit"
        ),
        sa.CheckConstraint("local_trip_limit > 0", name="ck_policy_settings_local_limit"),
    )

    op.add_column(
        "claim_lines",
        sa.Column(
            "policy_flags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    _replace_checks(NEW_STATUSES, NEW_CATEGORIES)


def downgrade() -> None:
    # Fails if any DUPLICATE claim or local line exists - fix the data first.
    _replace_checks(OLD_STATUSES, OLD_CATEGORIES)
    op.drop_column("claim_lines", "policy_flags")
    op.drop_table("policy_settings")
