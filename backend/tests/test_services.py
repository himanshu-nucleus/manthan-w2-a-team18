"""Service-layer units without HTTP: payout date ranges and CSV, audit hash chain, passwords
and tokens."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import AuditAction, PayoutBatch, PayoutBatchItem, Role
from app.security import (
    create_access_token,
    hash_password,
    read_access_token,
    verify_password,
)
from app.services import audit, payouts
from tests.helpers import add_user

# --- payouts -------------------------------------------------------------------------


def test_today_range_resolves_to_the_business_day() -> None:
    today = payouts.business_today()

    assert payouts.resolve_range("TODAY", None, None) == (today, today)


@pytest.mark.parametrize(
    ("from_date", "to_date"),
    [
        (None, date(2026, 11, 1)),  # from missing
        (date(2026, 11, 5), date(2026, 11, 1)),  # from after to
        (date(2026, 11, 1), date.today() + timedelta(days=2)),  # to in the future
    ],
)
def test_invalid_payout_range_raises(from_date: date | None, to_date: date) -> None:
    with pytest.raises(payouts.InvalidDateRange):
        payouts.resolve_range(None, from_date, to_date)


def test_csv_neutralises_spreadsheet_formulas_and_ends_with_a_trailer() -> None:
    batch = PayoutBatch(
        batch_reference="PB-20261127-001",
        value_date=date(2026, 11, 27),
        claim_count=1,
        total_amount=Decimal("1250.5"),
        currency="INR",
    )
    batch.items = [
        PayoutBatchItem(
            transaction_reference="PB-20261127-001-0001",
            employee_code="EMP0007",
            beneficiary_name="=HYPERLINK(1)",
            department=None,
            claim_code="CLM-000001",
            amount=Decimal("1250.5"),
            narration="Expense reimbursement CLM-000001",
        )
    ]

    rows = payouts.render_csv(batch).decode("utf-8").strip().split("\r\n")

    assert "'=HYPERLINK(1)" in rows[1]
    assert ",1250.50," in rows[1]
    assert rows[-1] == "TRAILER,1,1250.50"


# --- audit hash chain ------------------------------------------------------------------


def test_editing_an_audit_row_behind_the_orm_breaks_the_chain(db_session: Session) -> None:
    actor = add_user(db_session, "actor", Role.FINANCE_HEAD)
    first = audit.record(
        db_session, entity_type="user", entity_id=1, action=AuditAction.CREATED, actor=actor
    )
    audit.record(
        db_session, entity_type="user", entity_id=2, action=AuditAction.CREATED, actor=actor
    )
    db_session.flush()
    assert audit.verify_chain(db_session).valid is True

    db_session.connection().exec_driver_sql(
        f"UPDATE audit_events SET comment = 'tampered' WHERE id = {first.id}"
    )
    db_session.expire_all()
    report = audit.verify_chain(db_session)

    assert report.valid is False
    assert report.first_broken_id == first.id


# --- passwords and tokens -------------------------------------------------------------


def test_password_hash_verifies_only_the_right_password() -> None:
    stored = hash_password("s3cret-pass")

    assert verify_password("s3cret-pass", stored) is True
    assert verify_password("wrong-pass", stored) is False
    assert verify_password("s3cret-pass", "not-a-hash") is False


def test_access_token_round_trips_and_a_forged_one_is_rejected() -> None:
    token = create_access_token(42, Role.EMPLOYEE.value)

    assert read_access_token(token) == {"sub": 42, "role": "employee"}
    assert read_access_token(token + "x") is None
