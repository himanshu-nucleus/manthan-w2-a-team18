"""ORM models: defaults, database constraints and the append-only audit table."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    EDITABLE_STATUSES,
    PAYABLE_STATUSES,
    AuditAction,
    AuditEvent,
    Claim,
    ClaimStatus,
    Role,
    User,
)
from app.models.audit import AuditImmutable
from app.services import audit
from tests.helpers import add_user


def test_new_user_is_active_and_gets_a_created_at(db_session: Session) -> None:
    user = add_user(db_session, "fresh", Role.EMPLOYEE)
    db_session.refresh(user)

    assert user.is_active is True
    assert user.created_at is not None


@pytest.mark.parametrize(
    "row",
    [
        lambda: User(username="x1", full_name="X", role="superuser", password_hash="h"),
        lambda: Claim(employee_id=None, status="LOST", total_amount=Decimal("1")),
    ],
    ids=["unknown_role", "unknown_claim_status"],
)
def test_values_outside_the_allowed_set_are_refused_by_the_database(
    db_session: Session, row
) -> None:
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(row())
        db_session.flush()


def test_audit_rows_cannot_be_updated(db_session: Session) -> None:
    user = add_user(db_session, "actor", Role.FINANCE_HEAD)
    event = audit.record(
        db_session, entity_type="user", entity_id=user.id, action=AuditAction.CREATED, actor=user
    )
    db_session.flush()

    with pytest.raises(AuditImmutable), db_session.begin_nested():
        event.comment = "tampered"
        db_session.flush()

    with pytest.raises(AuditImmutable), db_session.begin_nested():
        db_session.execute(update(AuditEvent).values(comment="tampered"))


def test_only_approved_claims_are_payable_and_only_drafts_or_send_backs_editable() -> None:
    assert {ClaimStatus.APPROVED, ClaimStatus.AUTO_APPROVED} == PAYABLE_STATUSES
    assert {ClaimStatus.DRAFT, ClaimStatus.CLARIFICATION_REQUESTED} == EDITABLE_STATUSES
