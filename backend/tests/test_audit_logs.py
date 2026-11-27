"""Audit trail search and hash-chain verification (GET /audit-logs, GET /audit-logs/verify)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role, User
from app.services import attachments
from tests.helpers import API, add_user, line, login, submit_claim

AUDIT = f"{API}/audit-logs"


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
        "emp": add_user(db_session, "emp", Role.EMPLOYEE, manager=manager),
    }


def test_auditor_can_search_the_audit_trail_of_one_claim(
    client: TestClient, org: dict[str, User]
) -> None:
    claim_id = submit_claim(client, login(client, "emp"), [line("meal", "300")]).json()["id"]

    response = client.get(AUDIT, params={"claimId": claim_id}, headers=login(client, "auditor"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 2
    assert {item["claim_id"] for item in body["items"]} == {claim_id}
    assert {"CREATED", "SUBMITTED"} <= {item["action"] for item in body["items"]}


def test_employee_cannot_search_the_audit_trail(client: TestClient, org: dict[str, User]) -> None:
    response = client.get(AUDIT, headers=login(client, "emp"))

    assert response.status_code == 403


def test_finance_head_verifies_an_untouched_chain_as_valid(
    client: TestClient, org: dict[str, User]
) -> None:
    submit_claim(client, login(client, "emp"), [line("meal", "300")])

    response = client.get(f"{AUDIT}/verify", headers=login(client, "head"))

    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True
    assert response.json()["checked"] > 0


def test_only_the_finance_head_can_verify_the_chain(
    client: TestClient, org: dict[str, User]
) -> None:
    response = client.get(f"{AUDIT}/verify", headers=login(client, "auditor"))

    assert response.status_code == 403
