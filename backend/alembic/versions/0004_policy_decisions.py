"""policy decisions: DUPLICATE claim status, MARK_DUPLICATE outcome, local category

The team's duplicate rule (same vendor + amount + receipt number) marks the whole
claim DUPLICATE, which is final; local conveyance becomes its own category. The rule
rows themselves are inserted at startup by app/policy/defaults.py, not here.

Revision ID: 0004_policy_decisions
Revises: 0003_policy_and_approvals
Create Date: 2026-11-27
"""

from __future__ import annotations

from alembic import op

revision = "0004_policy_decisions"
down_revision = "0003_policy_and_approvals"
branch_labels = None
depends_on = None

OLD_STATUSES = (
    "'DRAFT', 'SUBMITTED', 'AUTO_APPROVED', 'AUTO_REJECTED', 'PENDING_APPROVAL', "
    "'APPROVED', 'REJECTED', 'CLARIFICATION_REQUESTED'"
)
NEW_STATUSES = f"{OLD_STATUSES}, 'DUPLICATE'"

OLD_CATEGORIES = "'meal', 'hotel', 'cab', 'airfare', 'other'"
NEW_CATEGORIES = "'meal', 'hotel', 'local', 'cab', 'airfare', 'other'"

OLD_OUTCOMES = "'ROUTE_FOR_APPROVAL', 'AUTO_REJECT'"
NEW_OUTCOMES = "'ROUTE_FOR_APPROVAL', 'AUTO_REJECT', 'MARK_DUPLICATE'"


def _replace_checks(statuses: str, categories: str, outcomes: str) -> None:
    op.drop_constraint("ck_claims_status", "claims", type_="check")
    op.create_check_constraint("ck_claims_status", "claims", f"status IN ({statuses})")
    op.drop_constraint("ck_claim_lines_category", "claim_lines", type_="check")
    op.create_check_constraint(
        "ck_claim_lines_category",
        "claim_lines",
        f"category IS NULL OR category IN ({categories})",
    )
    op.drop_constraint("ck_policy_rules_outcome", "policy_rules", type_="check")
    op.create_check_constraint(
        "ck_policy_rules_outcome", "policy_rules", f"outcome_on_breach IN ({outcomes})"
    )


def upgrade() -> None:
    _replace_checks(NEW_STATUSES, NEW_CATEGORIES, NEW_OUTCOMES)


def downgrade() -> None:
    # Fails while any DUPLICATE claim, local line or MARK_DUPLICATE rule exists -
    # fix the data first (synthetic only: docker compose down -v is fine locally).
    _replace_checks(OLD_STATUSES, OLD_CATEGORIES, OLD_OUTCOMES)
