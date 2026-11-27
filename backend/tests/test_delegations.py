"""Delegations API: create, list mine and cancel.

The refusal rules (self, lower role, overlap, chains) are covered in test_approval_chain.py.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role, User
from tests.helpers import API, add_user, login

DELEGATIONS = f"{API}/delegations"


@pytest.fixture
def org(db_session: Session) -> dict[str, User]:
    head = add_user(db_session, "head", Role.FINANCE_HEAD)
    return {
        "head": head,
        "manager": add_user(db_session, "manager", Role.LINE_MANAGER, manager=head),
        "manager2": add_user(db_session, "manager2", Role.LINE_MANAGER, manager=head),
    }


def _body(delegate: User, start: date | None = None) -> dict[str, object]:
    start = start or date.today()
    return {
        "delegate_id": delegate.id,
        "from_date": start.isoformat(),
        "to_date": (start + timedelta(days=2)).isoformat(),
        "reason": "On leave",
    }


def test_delegation_is_created_and_listed_for_both_people(
    client: TestClient, org: dict[str, User]
) -> None:
    created = client.post(
        DELEGATIONS, json=_body(org["manager2"]), headers=login(client, "manager")
    )

    assert created.status_code == 201, created.text
    for username in ("manager", "manager2"):
        mine = client.get(f"{DELEGATIONS}/me", headers=login(client, username))
        assert [d["id"] for d in mine.json()] == [created.json()["id"]]


def test_delegator_can_cancel_their_delegation(client: TestClient, org: dict[str, User]) -> None:
    headers = login(client, "manager")
    delegation_id = client.post(DELEGATIONS, json=_body(org["manager2"]), headers=headers).json()[
        "id"
    ]

    response = client.delete(f"{DELEGATIONS}/{delegation_id}", headers=headers)

    assert response.status_code == 204
    mine = client.get(f"{DELEGATIONS}/me", headers=headers).json()
    assert mine[0]["active"] is False


def test_cancelling_someone_elses_delegation_is_not_found(
    client: TestClient, org: dict[str, User]
) -> None:
    delegation_id = client.post(
        DELEGATIONS, json=_body(org["manager2"]), headers=login(client, "manager")
    ).json()["id"]

    response = client.delete(f"{DELEGATIONS}/{delegation_id}", headers=login(client, "manager2"))

    assert response.status_code == 404


def test_delegation_starting_in_the_past_is_refused(
    client: TestClient, org: dict[str, User]
) -> None:
    response = client.post(
        DELEGATIONS,
        json=_body(org["manager2"], start=date.today() - timedelta(days=1)),
        headers=login(client, "manager"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "delegation_invalid"
