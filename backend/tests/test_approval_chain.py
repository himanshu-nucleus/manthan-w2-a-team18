"""Approval chain, approver guard rails, delegation, send-back and duplicate claims.

Thresholds come from the default ``approval_thresholds`` setting (auditor step above
25,000, finance head step above 1,00,000) and the auto-approve limit of 500, both inserted
at app startup. Every expense date is a weekday, so WEEKEND_SPEND never routes a claim,
and each employee submits at most one claim per test, so SPLIT_CLAIM never fires.
"""

from __future__ import annotations

from datetime import date, timedelta
from itertools import count
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password
from app.services import attachments

API = "/api/v1"
WEEKDAY = "2026-11-25"  # a Wednesday
RECEIPT_ABOVE = 500
# Smallest byte string accepted as a PNG receipt (the upload checks the signature only).
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"synthetic receipt"

_receipt_numbers = count(1)


# --- helpers -------------------------------------------------------------------


def _add_user(db: Session, username: str, role: Role, manager: User | None = None) -> User:
    """A synthetic user whose password is their username."""
    user = User(
        username=username,
        full_name=username.title(),
        role=role.value,
        password_hash=hash_password(username),
        manager_id=manager.id if manager else None,
    )
    db.add(user)
    db.flush()
    return user


def _login(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        f"{API}/auth/login", json={"username": user.username, "password": user.username}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _line(amount: str, category: str = "airfare", **fields: Any) -> dict[str, Any]:
    return {
        "category": category,
        "amount": amount,
        "expense_date": WEEKDAY,
        "vendor": "Synthetic Travels",
        **fields,
    }


def _create_draft(client: TestClient, headers: dict[str, str], lines: list[dict[str, Any]]) -> int:
    created = client.post(f"{API}/claims", json={"lines": lines}, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _upload_receipt(client: TestClient, headers: dict[str, str], claim_id: int) -> int:
    uploaded = client.post(
        f"{API}/claims/{claim_id}/attachments",
        files={"file": ("receipt.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    return uploaded.json()["id"]


def _submit(
    client: TestClient, headers: dict[str, str], lines: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a draft, upload a receipt for every line above 500 INR, then submit.
    Returns the submitted claim."""
    claim_id = _create_draft(client, headers, lines)
    lines = [dict(item) for item in lines]
    for item in lines:
        if float(item["amount"]) > RECEIPT_ABOVE and "receipt_id" not in item:
            item["receipt_id"] = _upload_receipt(client, headers, claim_id)
            item.setdefault("receipt_number", f"RCPT-{next(_receipt_numbers):05d}")
    response = client.put(
        f"{API}/claims/{claim_id}",
        json={"action": "submit", "lines": lines},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _steps(client: TestClient, headers: dict[str, str], claim_id: int) -> list[dict[str, Any]]:
    response = client.get(f"{API}/claims/{claim_id}/approval-steps", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _current_step(client: TestClient, headers: dict[str, str], claim_id: int) -> dict[str, Any]:
    return next(s for s in _steps(client, headers, claim_id) if s["status"] == "PENDING")


def _approve(
    client: TestClient, headers: dict[str, str], claim_id: int, step_id: int | None = None
) -> Any:
    return client.post(
        f"{API}/claims/{claim_id}/approve",
        json={"step_id": step_id, "comment": "Checked"},
        headers=headers,
    )


def _delegate(
    client: TestClient,
    headers: dict[str, str],
    delegate: User,
    start: date | None = None,
    days: int = 3,
) -> Any:
    start = start or date.today()
    return client.post(
        f"{API}/delegations",
        json={
            "delegate_id": delegate.id,
            "from_date": start.isoformat(),
            "to_date": (start + timedelta(days=days)).isoformat(),
            "reason": "On leave",
        },
        headers=headers,
    )


# --- fixtures ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _receipts_in_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(attachments, "upload_root", lambda: tmp_path)


@pytest.fixture
def org(db_session: Session) -> dict[str, User]:
    """head <- manager <- employee, plus one finance auditor."""
    head = _add_user(db_session, "head1", Role.FINANCE_HEAD)
    manager = _add_user(db_session, "manager1", Role.LINE_MANAGER, head)
    auditor = _add_user(db_session, "auditor1", Role.FINANCE_AUDITOR, head)
    employee = _add_user(db_session, "employee1", Role.EMPLOYEE, manager)
    return {"head": head, "manager": manager, "auditor": auditor, "employee": employee}


# --- 1. approval thresholds -----------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected_roles"),
    [
        ("25000.00", ["line_manager"]),
        ("25000.01", ["line_manager", "finance_auditor"]),
        ("100000.00", ["line_manager", "finance_auditor"]),
        ("100000.01", ["line_manager", "finance_auditor", "finance_head"]),
    ],
    ids=[
        "exactly_25000_gets_no_auditor_step",
        "25000_01_gets_auditor_step",
        "exactly_100000_gets_no_finance_head_step",
        "100000_01_gets_finance_head_step",
    ],
)
def test_approval_chain_adds_steps_only_strictly_above_each_threshold(
    client: TestClient, org: dict[str, User], amount: str, expected_roles: list[str]
) -> None:
    headers = _login(client, org["employee"])

    claim = _submit(client, headers, [_line(amount)])

    assert claim["status"] == "PENDING_APPROVAL"
    steps = _steps(client, headers, claim["id"])
    assert [s["approver_role"] for s in steps] == expected_roles
    assert [s["step_order"] for s in steps] == list(range(1, len(expected_roles) + 1))
    assert steps[0]["assigned_approver_id"] == org["manager"].id
    assert [s["status"] for s in steps] == ["PENDING"] + ["WAITING"] * (len(steps) - 1)


# --- 2. self-approval ----------------------------------------------------------


def test_auditor_cannot_approve_the_auditor_step_of_their_own_claim(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    claimant = _add_user(db_session, "auditor2", Role.FINANCE_AUDITOR, org["manager"])
    claimant_headers = _login(client, claimant)
    claim = _submit(client, claimant_headers, [_line("30000.00")])
    assert _approve(client, _login(client, org["manager"]), claim["id"]).status_code == 200

    response = _approve(client, claimant_headers, claim["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_current_approver"
    other = _approve(client, _login(client, org["auditor"]), claim["id"])
    assert other.status_code == 200
    assert other.json()["status"] == "APPROVED"


def test_employee_cannot_approve_their_own_claim(client: TestClient, org: dict[str, User]) -> None:
    headers = _login(client, org["employee"])
    claim = _submit(client, headers, [_line("400.00", "meal"), _line("400.00", "other")])

    response = _approve(client, headers, claim["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_current_approver"


# --- 3. one person per step -----------------------------------------------------


def test_finance_head_who_approved_as_manager_cannot_approve_the_finance_head_step(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    second_head = _add_user(db_session, "head2", Role.FINANCE_HEAD)
    claimant = _add_user(db_session, "employee2", Role.EMPLOYEE, org["head"])
    claim = _submit(client, _login(client, claimant), [_line("150000.00")])
    head_headers = _login(client, org["head"])
    assert _approve(client, head_headers, claim["id"]).status_code == 200
    assert _approve(client, _login(client, org["auditor"]), claim["id"]).status_code == 200

    response = _approve(client, head_headers, claim["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_current_approver"
    final = _approve(client, _login(client, second_head), claim["id"])
    assert final.status_code == 200
    assert final.json()["status"] == "APPROVED"


# --- 4. delegation ---------------------------------------------------------------


def test_delegating_to_a_lower_role_is_refused(client: TestClient, org: dict[str, User]) -> None:
    response = _delegate(client, _login(client, org["auditor"]), org["manager"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "delegation_invalid"


def test_delegating_to_yourself_is_refused(client: TestClient, org: dict[str, User]) -> None:
    response = _delegate(client, _login(client, org["manager"]), org["manager"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "delegation_invalid"


def test_employee_cannot_delegate(client: TestClient, org: dict[str, User]) -> None:
    response = _delegate(client, _login(client, org["employee"]), org["manager"])

    assert response.status_code == 403


def test_overlapping_delegation_from_the_same_person_is_refused(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    other_manager = _add_user(db_session, "manager2", Role.LINE_MANAGER)
    headers = _login(client, org["manager"])
    assert _delegate(client, headers, other_manager, days=3).status_code == 201

    response = _delegate(
        client, headers, org["auditor"], start=date.today() + timedelta(days=2), days=3
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "delegation_invalid"


def test_delegating_to_someone_who_has_delegated_away_is_refused(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    other_manager = _add_user(db_session, "manager2", Role.LINE_MANAGER)
    assert _delegate(client, _login(client, other_manager), org["auditor"]).status_code == 201

    response = _delegate(client, _login(client, org["manager"]), other_manager)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "delegation_invalid"


def test_delegating_away_while_holding_someone_elses_delegation_is_refused(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    other_manager = _add_user(db_session, "manager2", Role.LINE_MANAGER)
    assert _delegate(client, _login(client, org["manager"]), other_manager).status_code == 201

    response = _delegate(client, _login(client, other_manager), org["auditor"])

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "delegation_invalid"
    assert "standing in for another approver" in error["message"]


def test_delegate_approves_on_behalf_of_the_manager_and_the_step_and_audit_record_it(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    delegate = _add_user(db_session, "manager2", Role.LINE_MANAGER)
    assert _delegate(client, _login(client, org["manager"]), delegate).status_code == 201
    employee_headers = _login(client, org["employee"])
    claim = _submit(client, employee_headers, [_line("400.00", "meal"), _line("400.00", "other")])

    delegate_headers = _login(client, delegate)
    pending = client.get(f"{API}/approvals/pending", headers=delegate_headers).json()
    assert [item["claim"]["id"] for item in pending["items"]] == [claim["id"]]
    assert pending["items"][0]["on_behalf_of_id"] == org["manager"].id

    response = _approve(client, delegate_headers, claim["id"])

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    step = _steps(client, employee_headers, claim["id"])[0]
    assert step["status"] == "APPROVED"
    assert step["acted_by_id"] == delegate.id
    assert step["on_behalf_of_id"] == org["manager"].id
    audit = client.get(f"{API}/claims/{claim['id']}/audit", headers=employee_headers).json()
    step_event = next(e for e in audit if e["action"] == "STEP_APPROVED")
    assert step_event["actor_id"] == delegate.id
    assert step_event["changes"]["acted_by"]["new"] == "manager2 on behalf of manager1"


def test_user_without_a_delegation_cannot_approve_another_managers_step(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    stranger = _add_user(db_session, "manager2", Role.LINE_MANAGER)
    claim = _submit(
        client,
        _login(client, org["employee"]),
        [_line("400.00", "meal"), _line("400.00", "other")],
    )

    response = _approve(client, _login(client, stranger), claim["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_current_approver"


# --- 5. stale step_id (double click) --------------------------------------------


def test_approving_the_same_step_twice_is_refused_with_409(
    client: TestClient, org: dict[str, User]
) -> None:
    claim = _submit(client, _login(client, org["employee"]), [_line("30000.00")])
    manager_headers = _login(client, org["manager"])
    step_id = _current_step(client, manager_headers, claim["id"])["id"]
    assert _approve(client, manager_headers, claim["id"], step_id).status_code == 200

    response = _approve(client, manager_headers, claim["id"], step_id)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "step_already_decided"
    assert error["details"]["current_step_id"] != step_id


def test_approving_again_after_the_last_step_is_refused_with_409(
    client: TestClient, org: dict[str, User]
) -> None:
    claim = _submit(
        client,
        _login(client, org["employee"]),
        [_line("400.00", "meal"), _line("400.00", "other")],
    )
    manager_headers = _login(client, org["manager"])
    step_id = _current_step(client, manager_headers, claim["id"])["id"]
    assert _approve(client, manager_headers, claim["id"], step_id).status_code == 200

    response = _approve(client, manager_headers, claim["id"], step_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "claim_not_pending"


# --- 6. send back and resubmit ----------------------------------------------------


def test_resubmitting_after_send_back_restarts_the_chain_at_step_one(
    client: TestClient, org: dict[str, User]
) -> None:
    employee_headers = _login(client, org["employee"])
    claim = _submit(client, employee_headers, [_line("30000.00")])
    assert _approve(client, _login(client, org["manager"]), claim["id"]).status_code == 200

    sent_back = client.post(
        f"{API}/claims/{claim['id']}/send-back",
        json={"comment": "Please attach the boarding pass details"},
        headers=_login(client, org["auditor"]),
    )
    assert sent_back.status_code == 200
    assert sent_back.json()["status"] == "CLARIFICATION_REQUESTED"

    edited = claim["lines"][0]
    resubmitted = client.put(
        f"{API}/claims/{claim['id']}",
        json={
            "action": "submit",
            "lines": [
                _line(
                    "29000.00",
                    receipt_id=edited["receipt_id"],
                    receipt_number=edited["receipt_number"],
                    description="Boarding pass PNR SYN123",
                )
            ],
        },
        headers=employee_headers,
    )

    assert resubmitted.status_code == 200, resubmitted.text
    body = resubmitted.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["submission_round"] == 2
    steps = _steps(client, employee_headers, claim["id"])
    round_two = [s for s in steps if s["round"] == 2]
    round_one = [s for s in steps if s["round"] == 1]
    assert [(s["step_order"], s["approver_role"], s["status"]) for s in round_two] == [
        (1, "line_manager", "PENDING"),
        (2, "finance_auditor", "WAITING"),
    ]
    assert [s["status"] for s in round_one] == ["APPROVED", "SENT_BACK"]
    assert steps[0]["round"] == 2


def test_send_back_without_a_comment_is_refused(client: TestClient, org: dict[str, User]) -> None:
    claim = _submit(
        client,
        _login(client, org["employee"]),
        [_line("400.00", "meal"), _line("400.00", "other")],
    )

    response = client.post(
        f"{API}/claims/{claim['id']}/send-back",
        json={},
        headers=_login(client, org["manager"]),
    )

    assert response.status_code == 422


# --- 7. auto-approve boundary -----------------------------------------------------


def test_clean_claim_of_exactly_500_is_auto_approved(
    client: TestClient, org: dict[str, User]
) -> None:
    headers = _login(client, org["employee"])

    claim = _submit(client, headers, [_line("500.00", "other")])

    assert claim["status"] == "AUTO_APPROVED"
    assert _steps(client, headers, claim["id"]) == []


def test_clean_claim_of_500_01_is_routed_for_approval(
    client: TestClient, org: dict[str, User]
) -> None:
    headers = _login(client, org["employee"])

    claim = _submit(client, headers, [_line("250.00", "other"), _line("250.01", "meal")])

    assert claim["status"] == "PENDING_APPROVAL"
    results = client.get(f"{API}/claims/{claim['id']}/policy-results", headers=headers).json()
    assert [f["rule_codes"] for f in results["claim_level"]] == [["AUTO_APPROVE_LIMIT"]]
    assert [s["approver_role"] for s in _steps(client, headers, claim["id"])] == ["line_manager"]


# --- 8. duplicate across employees -----------------------------------------------


def test_same_vendor_amount_and_receipt_number_from_another_employee_is_marked_duplicate(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    second_employee = _add_user(db_session, "employee2", Role.EMPLOYEE, org["manager"])
    duplicate_line = _line("1200.00", vendor="Synthetic Hotels", receipt_number="INV-7781")
    first = _submit(client, _login(client, org["employee"]), [duplicate_line])
    assert first["status"] == "PENDING_APPROVAL"

    headers = _login(client, second_employee)
    second = _submit(client, headers, [duplicate_line])

    assert second["status"] == "DUPLICATE"
    assert _steps(client, headers, second["id"]) == []
    results = client.get(f"{API}/claims/{second['id']}/policy-results", headers=headers).json()
    assert "DUPLICATE_RECEIPT_NUMBER" in results["lines"][0]["rule_codes"]
