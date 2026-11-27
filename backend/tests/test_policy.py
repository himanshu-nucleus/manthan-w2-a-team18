"""Policy rules: defaults at startup, reading, and finance-head-only changes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import create_app
from app.models import AuditAction, AuditEvent, PolicyRule, PolicySetting, Role, User
from app.policy.defaults import DEFAULT_RULES
from tests.helpers import API, add_user, login

RULES = f"{API}/policy-rules"


@pytest.fixture
def head(db_session: Session) -> User:
    return add_user(db_session, "head", Role.FINANCE_HEAD)


@pytest.fixture
def head_headers(client: TestClient, head: User) -> dict[str, str]:
    return login(client, "head")


def rule(db: Session, code: str) -> PolicyRule:
    found = db.scalar(select(PolicyRule).where(PolicyRule.code == code))
    assert found is not None, code
    return found


def by_code(rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["code"]: item for item in rules}


def policy_rule_events(db: Session) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.entity_type == "policy_rule")))


def test_default_policy_is_inserted_at_startup(client: TestClient, db_session: Session) -> None:
    codes = set(db_session.scalars(select(PolicyRule.code)))

    assert codes == {item["code"] for item in DEFAULT_RULES}
    assert rule(db_session, "RECEIPT_MANDATORY").params == {"above": "500"}
    assert rule(db_session, "MEAL_DAILY_LIMIT").params == {"limit": "1500"}
    assert rule(db_session, "HOTEL_NIGHTLY_LIMIT_T1").params["limit"] == "6000"
    assert rule(db_session, "HOTEL_NIGHTLY_LIMIT_OTHER").params["limit"] == "4000"
    assert rule(db_session, "LOCAL_TRIP_LIMIT").params == {"limit": "2000"}
    tier1 = db_session.get(PolicySetting, "tier1_cities")
    assert tier1 is not None
    assert "mumbai" in tier1.value
    auto_approve = db_session.get(PolicySetting, "auto_approve_max_total")
    assert auto_approve is not None
    assert auto_approve.value == "500"


def test_duplicate_receipt_number_is_the_active_duplicate_rule_by_default(
    client: TestClient, db_session: Session
) -> None:
    duplicate = rule(db_session, "DUPLICATE_RECEIPT_NUMBER")

    assert duplicate.active is True
    assert duplicate.outcome_on_breach == "MARK_DUPLICATE"
    assert rule(db_session, "DUPLICATE_LINE").active is False
    assert rule(db_session, "DUPLICATE_RECEIPT_HASH").active is False


def test_cab_has_no_trip_limit_by_default(client: TestClient, db_session: Session) -> None:
    assert rule(db_session, "CAB_TRIP_LIMIT").active is False
    assert rule(db_session, "LOCAL_TRIP_LIMIT").active is True


def test_startup_does_not_overwrite_a_changed_policy(
    client: TestClient, db_session: Session, head_headers: dict[str, str]
) -> None:
    changed = client.put(
        f"{RULES}/MEAL_DAILY_LIMIT", json={"params": {"limit": "2500"}}, headers=head_headers
    )
    assert changed.status_code == 200, changed.text

    restarted = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    restarted.dependency_overrides[get_db] = override_get_db
    with TestClient(restarted):
        pass

    db_session.expire_all()
    assert rule(db_session, "MEAL_DAILY_LIMIT").params == {"limit": "2500"}


@pytest.mark.parametrize("role", list(Role))
def test_every_logged_in_role_can_read_the_policy(
    client: TestClient, db_session: Session, role: Role
) -> None:
    add_user(db_session, "reader", role)

    response = client.get(RULES, headers=login(client, "reader"))

    assert response.status_code == 200
    rules = by_code(response.json())
    assert rules["MEAL_DAILY_LIMIT"]["params"] == {"limit": "1500"}
    assert rules["HOTEL_NIGHTLY_LIMIT_T1"]["params"]["limit"] == "6000"
    assert rules["LOCAL_TRIP_LIMIT"]["params"] == {"limit": "2000"}


def test_reading_the_policy_without_a_token_is_refused(client: TestClient) -> None:
    assert client.get(RULES).status_code == 401


def test_finance_head_can_change_one_limit_and_others_stay(
    client: TestClient, head: User, head_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{RULES}/MEAL_DAILY_LIMIT", json={"params": {"limit": "2000"}}, headers=head_headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["params"] == {"limit": "2000"}
    assert body["updated_by"] == head.id
    rules = by_code(client.get(RULES, headers=head_headers).json())
    assert rules["HOTEL_NIGHTLY_LIMIT_OTHER"]["params"]["limit"] == "4000"


@pytest.mark.parametrize("role", [Role.EMPLOYEE, Role.LINE_MANAGER, Role.FINANCE_AUDITOR])
def test_non_finance_head_cannot_change_the_policy(
    client: TestClient, db_session: Session, role: Role
) -> None:
    add_user(db_session, "someone", role)

    response = client.put(
        f"{RULES}/MEAL_DAILY_LIMIT",
        json={"params": {"limit": "99999"}},
        headers=login(client, "someone"),
    )

    assert response.status_code == 403
    db_session.expire_all()
    assert rule(db_session, "MEAL_DAILY_LIMIT").params == {"limit": "1500"}


@pytest.mark.parametrize(
    ("code", "body"),
    [
        ("MEAL_DAILY_LIMIT", {"params": {"limit": "0"}}),
        ("HOTEL_NIGHTLY_LIMIT_T1", {"params": {"limit": "-1", "city_tier": "tier1"}}),
        ("RECEIPT_MANDATORY", {"params": {"above": "-0.01"}}),
        ("LOCAL_TRIP_LIMIT", {"params": {"limit": None}}),
        ("LOCAL_TRIP_LIMIT", {"params": {"limit": "12.345"}}),
        ("LOCAL_TRIP_LIMIT", {"params": {"limit": "100", "unknown_limit": "100"}}),
        ("LOCAL_TRIP_LIMIT", {"unknown_limit": "100"}),
        ("LOCAL_TRIP_LIMIT", {"reason_template": "Over {nonsense}"}),
    ],
)
def test_invalid_policy_change_is_refused(
    client: TestClient, head_headers: dict[str, str], code: str, body: dict[str, object]
) -> None:
    response = client.put(f"{RULES}/{code}", json=body, headers=head_headers)

    assert response.status_code == 422, response.text


def test_receipt_threshold_may_be_set_to_zero(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{RULES}/RECEIPT_MANDATORY", json={"params": {"above": "0"}}, headers=head_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["params"] == {"above": "0"}


def test_policy_change_is_written_to_the_audit_trail(
    client: TestClient, db_session: Session, head: User, head_headers: dict[str, str]
) -> None:
    client.put(
        f"{RULES}/LOCAL_TRIP_LIMIT", json={"params": {"limit": "2500"}}, headers=head_headers
    )

    events = policy_rule_events(db_session)
    assert len(events) == 1
    event = events[0]
    assert event.action == AuditAction.POLICY_RULE_UPDATED
    assert event.actor_id == head.id
    assert event.entity_id == rule(db_session, "LOCAL_TRIP_LIMIT").id
    assert event.changes["params"] == {"old": {"limit": "2000"}, "new": {"limit": "2500"}}


def test_policy_change_to_the_same_value_writes_no_audit_event(
    client: TestClient, db_session: Session, head_headers: dict[str, str]
) -> None:
    client.put(
        f"{RULES}/LOCAL_TRIP_LIMIT", json={"params": {"limit": "2000"}}, headers=head_headers
    )

    assert policy_rule_events(db_session) == []
