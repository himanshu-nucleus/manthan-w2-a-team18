"""Claims API reads and receipt files: list, detail, history, upload and download.
Submission and policy outcomes are covered in test_claims_policy.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role, User
from app.services import attachments
from tests.helpers import API, PNG_BYTES, add_user, line, login, submit_claim

CLAIMS = f"{API}/claims"


@pytest.fixture(autouse=True)
def upload_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(attachments, "upload_root", lambda: tmp_path)


@pytest.fixture
def org(db_session: Session) -> dict[str, User]:
    head = add_user(db_session, "head", Role.FINANCE_HEAD)
    manager = add_user(db_session, "manager", Role.LINE_MANAGER, manager=head)
    return {
        "head": head,
        "manager": manager,
        "emp": add_user(db_session, "emp", Role.EMPLOYEE, manager=manager),
        "emp2": add_user(db_session, "emp2", Role.EMPLOYEE, manager=manager),
    }


def _draft(client: TestClient, username: str) -> int:
    response = client.post(
        CLAIMS, json={"lines": [line("meal", "200")]}, headers=login(client, username)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- list, detail, history ---------------------------------------------------------


def test_employee_lists_only_their_own_claims(client: TestClient, org: dict[str, User]) -> None:
    own = _draft(client, "emp")
    _draft(client, "emp2")

    response = client.get(CLAIMS, headers=login(client, "emp"))

    assert response.status_code == 200
    assert [c["id"] for c in response.json()["items"]] == [own]


def test_another_employees_claim_is_not_found(client: TestClient, org: dict[str, User]) -> None:
    claim_id = _draft(client, "emp2")

    response = client.get(f"{CLAIMS}/{claim_id}", headers=login(client, "emp"))

    assert response.status_code == 404


def test_finance_head_reads_any_claim_and_its_history(
    client: TestClient, org: dict[str, User]
) -> None:
    claim_id = submit_claim(client, login(client, "emp"), [line("meal", "300")]).json()["id"]
    headers = login(client, "head")

    detail = client.get(f"{CLAIMS}/{claim_id}", headers=headers)
    history = client.get(f"{CLAIMS}/{claim_id}/audit", headers=headers)

    assert detail.status_code == 200
    assert detail.json()["id"] == claim_id
    assert {"CREATED", "SUBMITTED"} <= {e["action"] for e in history.json()}


def test_listing_claims_without_a_token_is_refused(client: TestClient) -> None:
    assert client.get(CLAIMS).status_code == 401


# --- receipt upload and download -----------------------------------------------------


def test_uploaded_receipt_downloads_with_the_same_bytes(
    client: TestClient, org: dict[str, User]
) -> None:
    headers = login(client, "emp")
    claim_id = _draft(client, "emp")
    uploaded = client.post(
        f"{CLAIMS}/{claim_id}/attachments",
        files={"file": ("receipt.png", PNG_BYTES, "image/png")},
        headers=headers,
    )

    downloaded = client.get(
        f"{CLAIMS}/{claim_id}/attachments/{uploaded.json()['id']}", headers=headers
    )

    assert uploaded.status_code == 201, uploaded.text
    assert downloaded.status_code == 200
    assert downloaded.content == PNG_BYTES


@pytest.mark.parametrize(
    ("content", "content_type", "status_code"),
    [
        (b"plain text", "text/plain", 415),  # type not allowed
        (b"not really a png", "image/png", 415),  # content does not match the type
        (b"", "image/png", 422),  # empty file
    ],
)
def test_invalid_receipt_upload_is_refused(
    client: TestClient,
    org: dict[str, User],
    content: bytes,
    content_type: str,
    status_code: int,
) -> None:
    claim_id = _draft(client, "emp")

    response = client.post(
        f"{CLAIMS}/{claim_id}/attachments",
        files={"file": ("receipt", content, content_type)},
        headers=login(client, "emp"),
    )

    assert response.status_code == status_code


def test_another_employee_cannot_download_a_receipt(
    client: TestClient, org: dict[str, User]
) -> None:
    claim_id = _draft(client, "emp")
    attachment_id = client.post(
        f"{CLAIMS}/{claim_id}/attachments",
        files={"file": ("receipt.png", PNG_BYTES, "image/png")},
        headers=login(client, "emp"),
    ).json()["id"]

    response = client.get(
        f"{CLAIMS}/{claim_id}/attachments/{attachment_id}", headers=login(client, "emp2")
    )

    assert response.status_code == 404
