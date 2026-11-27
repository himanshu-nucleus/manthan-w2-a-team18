"""Policy settings: defaults at startup, reading, and finance-head-only changes."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import create_app
from app.models import POLICY_ROW_ID, AuditEvent, PolicySettings, Role, User
from tests.helpers import API, add_user, login

POLICY = f"{API}/policy"


@pytest.fixture
def head(db_session: Session) -> User:
    return add_user(db_session, "head", Role.FINANCE_HEAD)


@pytest.fixture
def head_headers(client: TestClient, head: User) -> dict[str, str]:
    return login(client, "head")


def test_default_policy_is_inserted_at_startup(client: TestClient, db_session: Session) -> None:
    policy = db_session.get(PolicySettings, POLICY_ROW_ID)

    assert policy is not None
    assert str(policy.receipt_required_above) == "500.00"
    assert str(policy.meal_daily_limit) == "1500.00"
    assert str(policy.hotel_tier1_nightly_limit) == "6000.00"
    assert str(policy.hotel_other_nightly_limit) == "4000.00"
    assert str(policy.local_trip_limit) == "2000.00"
    assert "Mumbai" in policy.tier1_cities


def test_startup_does_not_overwrite_a_changed_policy(
    client: TestClient, db_session: Session
) -> None:
    db_session.get(PolicySettings, POLICY_ROW_ID).meal_daily_limit = 2500
    db_session.flush()

    restarted = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    restarted.dependency_overrides[get_db] = override_get_db
    with TestClient(restarted):
        pass

    assert str(db_session.get(PolicySettings, POLICY_ROW_ID).meal_daily_limit) == "2500.00"


@pytest.mark.parametrize("role", list(Role))
def test_every_logged_in_role_can_read_the_policy(
    client: TestClient, db_session: Session, role: Role
) -> None:
    add_user(db_session, "reader", role)

    response = client.get(POLICY, headers=login(client, "reader"))

    assert response.status_code == 200
    body = response.json()
    assert body["meal_daily_limit"] == "1500.00"
    assert body["hotel_tier1_nightly_limit"] == "6000.00"
    assert body["local_trip_limit"] == "2000.00"


def test_reading_the_policy_without_a_token_is_refused(client: TestClient) -> None:
    assert client.get(POLICY).status_code == 401


def test_finance_head_can_change_one_limit_and_others_stay(
    client: TestClient, head: User, head_headers: dict[str, str]
) -> None:
    response = client.patch(POLICY, json={"meal_daily_limit": "2000"}, headers=head_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meal_daily_limit"] == "2000.00"
    assert body["hotel_other_nightly_limit"] == "4000.00"
    assert body["updated_by"] == head.id


def test_finance_head_can_replace_the_tier1_city_list_trimmed_and_deduplicated(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    response = client.patch(
        POLICY, json={"tier1_cities": [" Mumbai ", "mumbai", "Indore"]}, headers=head_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["tier1_cities"] == ["Mumbai", "Indore"]


@pytest.mark.parametrize("role", [Role.EMPLOYEE, Role.LINE_MANAGER, Role.FINANCE_AUDITOR])
def test_non_finance_head_cannot_change_the_policy(
    client: TestClient, db_session: Session, role: Role
) -> None:
    add_user(db_session, "someone", role)

    response = client.patch(
        POLICY, json={"meal_daily_limit": "99999"}, headers=login(client, "someone")
    )

    assert response.status_code == 403
    assert db_session.get(PolicySettings, POLICY_ROW_ID).meal_daily_limit == 1500


@pytest.mark.parametrize(
    "body",
    [
        {"meal_daily_limit": "0"},
        {"hotel_tier1_nightly_limit": "-1"},
        {"receipt_required_above": "-0.01"},
        {"local_trip_limit": None},
        {"local_trip_limit": "12.345"},
        {"tier1_cities": ["  "]},
        {"unknown_limit": "100"},
    ],
)
def test_invalid_policy_change_is_refused(
    client: TestClient, head_headers: dict[str, str], body: dict[str, object]
) -> None:
    response = client.patch(POLICY, json=body, headers=head_headers)

    assert response.status_code == 422, response.text


def test_receipt_threshold_may_be_set_to_zero(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    response = client.patch(POLICY, json={"receipt_required_above": "0"}, headers=head_headers)

    assert response.status_code == 200
    assert response.json()["receipt_required_above"] == "0.00"


def test_policy_change_is_written_to_the_audit_trail(
    client: TestClient, db_session: Session, head: User, head_headers: dict[str, str]
) -> None:
    client.patch(POLICY, json={"local_trip_limit": "2500"}, headers=head_headers)

    event = db_session.scalar(select(AuditEvent).where(AuditEvent.entity_type == "policy"))
    assert event is not None
    assert event.actor_id == head.id
    assert event.changes == {"local_trip_limit": {"old": "2000.00", "new": "2500.00"}}


def test_policy_change_to_the_same_value_writes_no_audit_event(
    client: TestClient, db_session: Session, head_headers: dict[str, str]
) -> None:
    client.patch(POLICY, json={"local_trip_limit": "2000.00"}, headers=head_headers)

    assert db_session.scalar(select(AuditEvent).where(AuditEvent.entity_type == "policy")) is None
