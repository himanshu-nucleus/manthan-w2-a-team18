"""Small helpers shared by the API tests: users, logins, claim submission and policy results."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password

API = "/api/v1"

# A Friday, so the WEEKEND_SPEND rule never fires on a line that keeps the default date.
EXPENSE_DATE = "2026-11-20"

# Smallest byte string accepted as a PNG receipt (the upload checks the signature only).
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"synthetic receipt"


def add_user(db: Session, username: str, role: Role, manager: User | None = None) -> User:
    """A user whose password is their username, optionally reporting to ``manager``."""
    user = User(
        username=username,
        full_name=username.title(),
        role=role.value,
        manager_id=manager.id if manager is not None else None,
        password_hash=hash_password(username),
    )
    db.add(user)
    db.flush()
    return user


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": username})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def line(category: str, amount: str, **fields: Any) -> dict[str, Any]:
    """A complete claim line dated on a weekday. Pass ``receipt=True`` to attach an
    uploaded receipt (and a receipt number, unless one is given) on submit."""
    return {
        "category": category,
        "amount": amount,
        "expense_date": EXPENSE_DATE,
        "vendor": "Synthetic Vendor",
        **fields,
    }


def submit_claim(client: TestClient, headers: dict[str, str], lines: list[dict[str, Any]]) -> Any:
    """Create a draft, upload a receipt for each line marked ``receipt=True``, then submit
    with ``PUT /claims/{id}`` and ``action: submit``.

    Returns the submit response, so callers can assert on 200 or 422.
    """
    plain = [{k: v for k, v in item.items() if k != "receipt"} for item in lines]
    created = client.post(f"{API}/claims", json={"lines": plain}, headers=headers)
    assert created.status_code == 201, created.text
    claim_id = created.json()["id"]

    for index, item in enumerate(lines):
        if item.get("receipt"):
            uploaded = client.post(
                f"{API}/claims/{claim_id}/attachments",
                files={"file": ("receipt.png", PNG_BYTES, "image/png")},
                headers=headers,
            )
            assert uploaded.status_code == 201, uploaded.text
            plain[index]["receipt_id"] = uploaded.json()["id"]
            plain[index].setdefault("receipt_number", f"RCPT-{claim_id}-{index}")

    return client.put(
        f"{API}/claims/{claim_id}",
        json={"action": "submit", "lines": plain},
        headers=headers,
    )


def policy_results(client: TestClient, headers: dict[str, str], claim_id: int) -> dict[str, Any]:
    """``GET /claims/{id}/policy-results`` for the latest policy run."""
    response = client.get(f"{API}/claims/{claim_id}/policy-results", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def line_codes(client: TestClient, headers: dict[str, str], claim_id: int) -> list[list[str]]:
    """Rule codes breached by each line, in line order."""
    return [item["rule_codes"] for item in policy_results(client, headers, claim_id)["lines"]]
