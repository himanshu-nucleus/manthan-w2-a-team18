"""Payout batches: eligible-claims preview, batch creation, listing, detail and CSV export."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Claim, ClaimStatus, Role, User
from app.services import attachments, payouts
from tests.helpers import API, add_user, line, login, submit_claim

PAYOUTS = f"{API}/payouts"


@pytest.fixture(autouse=True)
def upload_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(attachments, "upload_root", lambda: tmp_path)


@pytest.fixture
def org(db_session: Session) -> dict[str, User]:
    head = add_user(db_session, "head", Role.FINANCE_HEAD)
    manager = add_user(db_session, "manager", Role.LINE_MANAGER, manager=head)
    return {
        "head": head,
        "auditor": add_user(db_session, "auditor", Role.FINANCE_AUDITOR, manager=head),
        "manager": manager,
        "emp": add_user(db_session, "emp", Role.EMPLOYEE, manager=manager),
    }


@pytest.fixture
def approved_claim(client: TestClient, org: dict[str, User]) -> int:
    """A clean 300 INR meal claim: auto-approved today, so payable with range=TODAY."""
    response = submit_claim(client, login(client, "emp"), [line("meal", "300")])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ClaimStatus.AUTO_APPROVED
    return response.json()["id"]


def test_preview_lists_todays_approved_claims_and_their_total(
    client: TestClient, approved_claim: int
) -> None:
    response = client.get(
        f"{PAYOUTS}/eligible-claims", params={"range": "TODAY"}, headers=login(client, "auditor")
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [c["claim_id"] for c in body["claims"]] == [approved_claim]
    assert body["claim_count"] == 1
    assert body["total_amount"] == "300.00"


@pytest.mark.parametrize(
    "params",
    [
        {"range": "TODAY", "fromDate": "2026-11-01", "toDate": "2026-11-02"},  # both forms
        {"fromDate": "2026-11-01"},  # toDate missing
        {"fromDate": "2026-11-05", "toDate": "2026-11-01"},  # from after to
    ],
    ids=["today_and_dates_together", "to_date_missing", "from_after_to"],
)
def test_preview_with_an_invalid_date_range_is_refused_with_400(
    client: TestClient, org: dict[str, User], params: dict[str, str]
) -> None:
    response = client.get(
        f"{PAYOUTS}/eligible-claims", params=params, headers=login(client, "head")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"


@pytest.mark.parametrize("username", ["emp", "manager"])
def test_non_finance_roles_cannot_use_payouts(
    client: TestClient, org: dict[str, User], username: str
) -> None:
    response = client.get(
        f"{PAYOUTS}/eligible-claims", params={"range": "TODAY"}, headers=login(client, username)
    )

    assert response.status_code == 403


def test_creating_a_batch_pays_the_claim_and_a_second_batch_finds_nothing(
    client: TestClient, db_session: Session, approved_claim: int
) -> None:
    headers = login(client, "head")

    created = client.post(f"{PAYOUTS}/batches", json={"range": "TODAY"}, headers=headers)
    again = client.post(f"{PAYOUTS}/batches", json={"range": "TODAY"}, headers=headers)

    assert created.status_code == 201, created.text
    assert created.json()["claim_count"] == 1
    claim = db_session.get(Claim, approved_claim)
    assert claim.status == ClaimStatus.PAID
    assert claim.payout_batch_id == created.json()["id"]
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "no_eligible_claims"


def test_batches_are_listed_and_an_unknown_batch_is_not_found(
    client: TestClient, approved_claim: int
) -> None:
    headers = login(client, "auditor")
    batch_id = client.post(f"{PAYOUTS}/batches", json={"range": "TODAY"}, headers=headers).json()[
        "id"
    ]

    listed = client.get(f"{PAYOUTS}/batches", headers=headers)
    detail = client.get(f"{PAYOUTS}/batches/{batch_id}", headers=headers)
    missing = client.get(f"{PAYOUTS}/batches/999999", headers=headers)

    assert listed.status_code == 200
    assert [b["id"] for b in listed.json()["items"]] == [batch_id]
    assert detail.status_code == 200
    assert missing.status_code == 404


def test_export_returns_the_bank_csv_and_marks_the_batch_exported(
    client: TestClient, approved_claim: int
) -> None:
    headers = login(client, "head")
    batch = client.post(f"{PAYOUTS}/batches", json={"range": "TODAY"}, headers=headers).json()

    response = client.get(f"{PAYOUTS}/batches/{batch['id']}/export", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = response.text.strip().split("\r\n")
    assert rows[0].split(",") == list(payouts.CSV_HEADER)
    assert rows[-1] == "TRAILER,1,300.00"
    detail = client.get(f"{PAYOUTS}/batches/{batch['id']}", headers=headers).json()
    assert detail["status"] == "EXPORTED"
    assert detail["export_count"] == 1


def test_future_to_date_is_refused(client: TestClient, org: dict[str, User]) -> None:
    tomorrow = payouts.business_today() + timedelta(days=1)
    response = client.post(
        f"{PAYOUTS}/batches",
        json={"fromDate": tomorrow.isoformat(), "toDate": tomorrow.isoformat()},
        headers=login(client, "head"),
    )

    assert response.status_code == 400
