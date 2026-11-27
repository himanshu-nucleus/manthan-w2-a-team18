"""policy rules as configuration, policy results, approval chain, delegations, comments

Revision ID: 0003_policy_and_approvals
Revises: 0002_claims
Create Date: 2026-11-27

Rule and setting rows are data, not schema: they are inserted by backend/db/seed.sql.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_policy_and_approvals"
down_revision = "0002_claims"
branch_labels = None
depends_on = None

NEW_STATUSES = (
    "'DRAFT', 'SUBMITTED', 'AUTO_APPROVED', 'AUTO_REJECTED', 'PENDING_APPROVAL', "
    "'APPROVED', 'REJECTED', 'CLARIFICATION_REQUESTED'"
)


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _user_fk(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name, sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=nullable
    )


def _claim_fk() -> sa.Column:
    return sa.Column(
        "claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )


def _json(name: str, default: str) -> sa.Column:
    return sa.Column(
        name, postgresql.JSONB(), nullable=False, server_default=sa.text(f"'{default}'::jsonb")
    )


def upgrade() -> None:
    # --- claims: new states, policy outcome, submission round, optimistic lock ---
    op.drop_constraint("ck_claims_status", "claims", type_="check")
    op.create_check_constraint("ck_claims_status", "claims", f"status IN ({NEW_STATUSES})")
    op.add_column("claims", sa.Column("policy_outcome", sa.String(32), nullable=True))
    op.add_column(
        "claims", sa.Column("policy_evaluated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "claims",
        sa.Column("submission_round", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("claims", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # --- policy configuration ---
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("rule_type", sa.String(64), nullable=False),
        _json("params", "{}"),
        sa.Column("outcome_on_breach", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason_template", sa.String(500), nullable=False),
        _now("updated_at"),
        _user_fk("updated_by", nullable=True),
        sa.UniqueConstraint("code", name="uq_policy_rules_code"),
        sa.CheckConstraint(
            "outcome_on_breach IN ('ROUTE_FOR_APPROVAL', 'AUTO_REJECT')",
            name="ck_policy_rules_outcome",
        ),
    )
    op.create_table(
        "policy_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        _now("updated_at"),
    )
    op.create_table(
        "claim_policy_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        _claim_fk(),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("line_position", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        _json("rule_codes", "[]"),
        _json("reasons", "[]"),
        _json("rule_snapshot", "{}"),
        _now("evaluated_at"),
    )
    op.create_index(
        "ix_claim_policy_results_claim_round", "claim_policy_results", ["claim_id", "round"]
    )

    # --- approval chain ---
    op.create_table(
        "approval_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        _claim_fk(),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_role", sa.String(32), nullable=False),
        _user_fk("assigned_approver_id", nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        _user_fk("acted_by_id", nullable=True),
        _user_fk("on_behalf_of_id", nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        _now("created_at"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status IN ('WAITING', 'PENDING', 'APPROVED', 'REJECTED', 'SENT_BACK', 'CANCELLED')",
            name="ck_approval_steps_status",
        ),
    )
    op.create_index("ix_approval_steps_claim_round", "approval_steps", ["claim_id", "round"])
    op.create_index("ix_approval_steps_status", "approval_steps", ["status"])

    op.create_table(
        "delegations",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk("delegator_id"),
        _user_fk("delegate_id"),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _now("created_at"),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("delegator_id <> delegate_id", name="ck_delegations_not_self"),
        sa.CheckConstraint("to_date >= from_date", name="ck_delegations_dates"),
    )
    op.create_index("ix_delegations_delegate", "delegations", ["delegate_id", "active"])
    op.create_index("ix_delegations_delegator", "delegations", ["delegator_id", "active"])

    op.create_table(
        "claim_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        _claim_fk(),
        _user_fk("author_id"),
        sa.Column("body", sa.Text(), nullable=False),
        _now("created_at"),
    )
    op.create_index("ix_claim_comments_claim_id", "claim_comments", ["claim_id"])


def downgrade() -> None:
    op.drop_index("ix_claim_comments_claim_id", table_name="claim_comments")
    op.drop_table("claim_comments")
    op.drop_index("ix_delegations_delegator", table_name="delegations")
    op.drop_index("ix_delegations_delegate", table_name="delegations")
    op.drop_table("delegations")
    op.drop_index("ix_approval_steps_status", table_name="approval_steps")
    op.drop_index("ix_approval_steps_claim_round", table_name="approval_steps")
    op.drop_table("approval_steps")
    op.drop_index("ix_claim_policy_results_claim_round", table_name="claim_policy_results")
    op.drop_table("claim_policy_results")
    op.drop_table("policy_settings")
    op.drop_table("policy_rules")
    op.drop_column("claims", "version")
    op.drop_column("claims", "submission_round")
    op.drop_column("claims", "policy_evaluated_at")
    op.drop_column("claims", "policy_outcome")
    op.drop_constraint("ck_claims_status", "claims", type_="check")
    op.create_check_constraint("ck_claims_status", "claims", "status IN ('DRAFT', 'SUBMITTED')")
