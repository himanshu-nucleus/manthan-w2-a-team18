"""create claims, claim lines, attachments and the append-only audit trail

Revision ID: 0002_claims
Revises: 0001_create_users
Create Date: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_claims"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _user_fk(name: str) -> sa.Column:
    return sa.Column(
        name, sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk("employee_id"),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        _user_fk("created_by"),
        _user_fk("updated_by"),
        sa.CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name="ck_claims_status"),
        sa.CheckConstraint("currency = 'INR'", name="ck_claims_currency"),
    )
    op.create_index("ix_claims_employee_id", "claims", ["employee_id"])
    op.create_index("ix_claims_status", "claims", ["status"])

    op.create_table(
        "claim_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "claim_id",
            sa.Integer(),
            sa.ForeignKey("claims.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        _user_fk("uploaded_by"),
        _timestamp("uploaded_at"),
        sa.UniqueConstraint("stored_path", name="uq_claim_attachments_stored_path"),
    )
    op.create_index("ix_claim_attachments_claim_id", "claim_attachments", ["claim_id"])
    op.create_index("ix_claim_attachments_sha256", "claim_attachments", ["sha256"])

    op.create_table(
        "claim_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "claim_id",
            sa.Integer(),
            sa.ForeignKey("claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("expense_date", sa.Date(), nullable=True),
        sa.Column("vendor", sa.String(200), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("nights", sa.Integer(), nullable=True),
        sa.Column("receipt_number", sa.String(100), nullable=True),
        sa.Column(
            "receipt_id",
            sa.Integer(),
            sa.ForeignKey("claim_attachments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "category IS NULL OR category IN ('meal', 'hotel', 'cab', 'airfare', 'other')",
            name="ck_claim_lines_category",
        ),
        sa.CheckConstraint("amount IS NULL OR amount > 0", name="ck_claim_lines_amount_positive"),
        sa.CheckConstraint("nights IS NULL OR nights > 0", name="ck_claim_lines_nights_positive"),
    )
    op.create_index("ix_claim_lines_claim_id", "claim_lines", ["claim_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        _user_fk("actor_id"),
        _timestamp("created_at"),
    )
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])

    # Append-only: refuse UPDATE and DELETE on the audit trail at the database level.
    op.execute("""
        CREATE FUNCTION audit_events_block_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """)
    op.execute("""
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_changes();
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_block_changes()")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_claim_lines_claim_id", table_name="claim_lines")
    op.drop_table("claim_lines")
    op.drop_index("ix_claim_attachments_sha256", table_name="claim_attachments")
    op.drop_index("ix_claim_attachments_claim_id", table_name="claim_attachments")
    op.drop_table("claim_attachments")
    op.drop_index("ix_claims_status", table_name="claims")
    op.drop_index("ix_claims_employee_id", table_name="claims")
    op.drop_table("claims")
