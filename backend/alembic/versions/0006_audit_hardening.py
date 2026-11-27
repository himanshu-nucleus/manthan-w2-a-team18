"""audit trail hardening: claim id, actor role, SYSTEM actor, request context, hash chain

Revision ID: 0006_audit_hardening
Revises: 0005_payouts
Create Date: 2026-11-27

Only adds columns, indexes and a trigger. Existing audit rows are never rewritten
(the append-only trigger from 0002 would refuse it anyway): they keep NULL in the new
columns, and the hash chain starts with the first row written after this migration.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_audit_hardening"
down_revision = "0005_payouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # actor_id NULL = SYSTEM (policy engine, chain building, startup defaults, failed login).
    op.alter_column("audit_events", "actor_id", existing_type=sa.Integer(), nullable=True)
    # entity_id NULL for entities keyed by name (policy settings).
    op.alter_column("audit_events", "entity_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("audit_events", sa.Column("claim_id", sa.Integer(), nullable=True))
    op.add_column("audit_events", sa.Column("actor_role", sa.String(32), nullable=True))
    op.add_column(
        "audit_events",
        sa.Column(
            "on_behalf_of_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("audit_events", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("audit_events", sa.Column("ip_address", sa.String(64), nullable=True))
    op.add_column("audit_events", sa.Column("request_id", sa.String(64), nullable=True))
    op.add_column("audit_events", sa.Column("prev_hash", sa.String(64), nullable=True))
    op.add_column("audit_events", sa.Column("hash", sa.String(64), nullable=True))

    # No foreign key on claim_id on purpose: audit history must outlive any claim row.
    op.create_index("ix_audit_events_claim_id", "audit_events", ["claim_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    # Row triggers do not fire on TRUNCATE; block it with a statement-level trigger.
    op.execute("""
        CREATE TRIGGER audit_events_no_truncate
        BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION audit_events_block_changes();
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_claim_id", table_name="audit_events")
    for column in (
        "hash",
        "prev_hash",
        "request_id",
        "ip_address",
        "comment",
        "on_behalf_of_id",
        "actor_role",
        "claim_id",
    ):
        op.drop_column("audit_events", column)
    # Rows written as SYSTEM or for settings cannot satisfy NOT NULL again; leave nullable.
