"""payout batches, PAID status, claim approval/payment dates, user department

Revision ID: 0005_payouts
Revises: 0004_policy_decisions
Create Date: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_payouts"
down_revision = "0004_policy_decisions"
branch_labels = None
depends_on = None

OLD_STATUSES = (
    "'DRAFT', 'SUBMITTED', 'AUTO_APPROVED', 'AUTO_REJECTED', 'PENDING_APPROVAL', "
    "'APPROVED', 'REJECTED', 'CLARIFICATION_REQUESTED', 'DUPLICATE'"
)
NEW_STATUSES = OLD_STATUSES + ", 'PAID'"


def _user_fk(name: str) -> sa.Column:
    return sa.Column(
        name, sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


def upgrade() -> None:
    op.add_column("users", sa.Column("department", sa.String(100), nullable=True))

    op.create_table(
        "payout_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_reference", sa.String(32), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(100), nullable=False),
        sa.Column("export_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_exported_at", sa.DateTime(timezone=True), nullable=True),
        _user_fk("created_by"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("batch_reference", name="uq_payout_batches_reference"),
        sa.CheckConstraint("status IN ('CREATED', 'EXPORTED')", name="ck_payout_batches_status"),
        sa.CheckConstraint("claim_count > 0", name="ck_payout_batches_not_empty"),
        sa.CheckConstraint("total_amount > 0", name="ck_payout_batches_total_positive"),
        sa.CheckConstraint("to_date >= from_date", name="ck_payout_batches_dates"),
    )

    op.create_table(
        "payout_batch_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Integer(),
            sa.ForeignKey("payout_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "claim_id",
            sa.Integer(),
            sa.ForeignKey("claims.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        _user_fk("employee_id"),
        sa.Column("transaction_reference", sa.String(48), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("employee_code", sa.String(32), nullable=False),
        sa.Column("beneficiary_name", sa.String(120), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("claim_code", sa.String(32), nullable=False),
        sa.Column("narration", sa.String(140), nullable=False),
        # A claim can be in one batch only: the database refuses a second payment.
        sa.UniqueConstraint("claim_id", name="uq_payout_batch_items_claim"),
        sa.UniqueConstraint("transaction_reference", name="uq_payout_batch_items_txn_ref"),
        sa.CheckConstraint("amount > 0", name="ck_payout_batch_items_amount_positive"),
    )
    op.create_index("ix_payout_batch_items_batch_id", "payout_batch_items", ["batch_id"])

    op.drop_constraint("ck_claims_status", "claims", type_="check")
    op.create_check_constraint("ck_claims_status", "claims", f"status IN ({NEW_STATUSES})")
    op.add_column("claims", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("claims", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "claims",
        sa.Column(
            "payout_batch_id",
            sa.Integer(),
            sa.ForeignKey("payout_batches.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_claims_approved_at", "claims", ["approved_at"])
    op.create_index("ix_claims_payout_batch_id", "claims", ["payout_batch_id"])

    # Approval date for claims approved before this column existed.
    op.execute(
        "UPDATE claims SET approved_at = policy_evaluated_at "
        "WHERE status = 'AUTO_APPROVED' AND approved_at IS NULL"
    )
    op.execute("""
        UPDATE claims c SET approved_at = (
            SELECT max(s.acted_at) FROM approval_steps s
            WHERE s.claim_id = c.id AND s.round = c.submission_round AND s.status = 'APPROVED'
        )
        WHERE c.status = 'APPROVED' AND c.approved_at IS NULL
        """)


def downgrade() -> None:
    op.drop_index("ix_claims_payout_batch_id", table_name="claims")
    op.drop_index("ix_claims_approved_at", table_name="claims")
    op.drop_column("claims", "payout_batch_id")
    op.drop_column("claims", "paid_at")
    op.drop_column("claims", "approved_at")
    op.execute("UPDATE claims SET status = 'APPROVED' WHERE status = 'PAID'")
    op.drop_constraint("ck_claims_status", "claims", type_="check")
    op.create_check_constraint("ck_claims_status", "claims", f"status IN ({OLD_STATUSES})")
    op.drop_index("ix_payout_batch_items_batch_id", table_name="payout_batch_items")
    op.drop_table("payout_batch_items")
    op.drop_table("payout_batches")
    op.drop_column("users", "department")
