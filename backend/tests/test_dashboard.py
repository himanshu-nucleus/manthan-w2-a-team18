"""GET /dashboard/summary: finance overview built from claims, policy and approval data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Claim, ClaimStatus, Role, User
from app.services import attachments
from tests.helpers import API, add_user, line, login, submit_claim

MONTH = "2026-11"
MID_NOVEMBER = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)
MID_OCTOBER = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)
APPROVED_STATES = {ClaimStatus.APPROVED, ClaimStatus.AUTO_APPROVED, ClaimStatus.PAID}


@pytest.fixture(autouse=True)
def upload_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(attachments, "upload_root", lambda: tmp_path)


@pytest.fixture
def org(db_session: Session) -> dict[str, User]:
    head = add_user(db_session, "head", Role.FINANCE_HEAD)
    auditor = add_user(db_session, "auditor", Role.FINANCE_AUDITOR, manager=head)
    manager = add_user(db_session, "manager", Role.LINE_MANAGER, manager=head)
    return {
        "head": head,
        "auditor": auditor,
        "manager": manager,
        "emp": add_user(db_session, "emp", Role.EMPLOYEE, manager=manager),
        "emp2": add_user(db_session, "emp2", Role.EMPLOYEE, manager=manager),
    }


def submit(client: TestClient, username: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
    response = submit_claim(client, login(client, username), lines)
    assert response.status_code == 200, response.text
    return response.json()


def move(db: Session, claim_id: int, submitted_at: datetime) -> None:
    db.get(Claim, claim_id).submitted_at = submitted_at
    db.flush()


def summary(client: TestClient, username: str = "head", month: str = MONTH) -> Any:
    return client.get(
        f"{API}/dashboard/summary", params={"month": month}, headers=login(client, username)
    )


def add_raw_claim(
    db: Session, owner: User, total: str, status: ClaimStatus, submitted_at: datetime
) -> Claim:
    claim = Claim(
        employee_id=owner.id,
        title=f"Synthetic {total}",
        status=status.value,
        total_amount=Decimal(total),
        submitted_at=submitted_at,
        approved_at=submitted_at if status in APPROVED_STATES else None,
        paid_at=submitted_at if status == ClaimStatus.PAID else None,
        created_by=owner.id,
        updated_by=owner.id,
    )
    db.add(claim)
    db.flush()
    return claim


# --- access ------------------------------------------------------------------


@pytest.mark.parametrize("username", ["head", "auditor"])
def test_finance_roles_can_read_the_dashboard(
    client: TestClient, org: dict[str, User], username: str
) -> None:
    response = summary(client, username)

    assert response.status_code == 200, response.text
    assert response.json()["month"] == MONTH


@pytest.mark.parametrize("username", ["manager", "emp"])
def test_other_roles_cannot_read_the_dashboard(
    client: TestClient, org: dict[str, User], username: str
) -> None:
    assert summary(client, username).status_code == 403


def test_dashboard_without_a_token_is_refused(client: TestClient) -> None:
    assert client.get(f"{API}/dashboard/summary").status_code == 401


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "november"])
def test_a_badly_formed_month_is_refused(
    client: TestClient, org: dict[str, User], month: str
) -> None:
    assert summary(client, month=month).status_code == 422


def test_month_defaults_to_the_current_india_month(
    client: TestClient, org: dict[str, User]
) -> None:
    response = client.get(f"{API}/dashboard/summary", headers=login(client, "head"))

    expected = (datetime.now(UTC) + timedelta(hours=5, minutes=30)).strftime("%Y-%m")
    assert response.json()["month"] == expected


# --- KPIs --------------------------------------------------------------------


def test_claims_and_spend_count_only_this_months_counted_claims(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    this_month = submit(client, "emp", [line("other", "300")])
    routed = submit(client, "emp2", [line("meal", "1600", receipt=True)])
    last_month = submit(client, "emp", [line("other", "200")])
    for claim, when in ((this_month, MID_NOVEMBER), (routed, MID_NOVEMBER)):
        move(db_session, claim["id"], when)
    move(db_session, last_month["id"], MID_OCTOBER)
    draft = client.post(
        f"{API}/claims", json={"lines": [line("other", "999")]}, headers=login(client, "emp")
    )
    assert draft.status_code == 201
    add_raw_claim(db_session, org["emp"], "700", ClaimStatus.REJECTED, MID_NOVEMBER)
    add_raw_claim(db_session, org["emp"], "800", ClaimStatus.DUPLICATE, MID_NOVEMBER)

    kpis = summary(client).json()["kpis"]

    assert kpis["claims"] == {"value": 2, "previous": 1}
    assert kpis["total_spend"] == {"value": "1900.00", "previous": "200.00"}


def test_a_claim_submitted_just_after_india_midnight_counts_in_the_new_month(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    # 31 Oct 19:00 UTC is 1 Nov 00:30 IST.
    add_raw_claim(
        db_session, org["emp"], "450", ClaimStatus.AUTO_APPROVED, datetime(2026, 10, 31, 19, 0)
    )

    kpis = summary(client).json()["kpis"]

    assert kpis["claims"] == {"value": 1, "previous": 0}


def test_policy_violations_count_breached_lines_out_of_all_lines(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    routed = submit(
        client, "emp", [line("meal", "1600", receipt=True), line("other", "100"), line("cab", "50")]
    )
    clean = submit(client, "emp2", [line("other", "100")])
    for claim in (routed, clean):
        move(db_session, claim["id"], MID_NOVEMBER)

    violations = summary(client).json()["kpis"]["policy_violations"]

    assert violations == {"lines": 1, "total_lines": 4, "rate_percent": 25.0, "previous_lines": 0}


def test_ready_for_payout_counts_what_a_payout_batch_could_pay_now(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    add_raw_claim(db_session, org["emp"], "400", ClaimStatus.AUTO_APPROVED, MID_OCTOBER)
    approved = submit(client, "emp2", [line("meal", "1600", receipt=True)])
    response = client.post(
        f"{API}/claims/{approved['id']}/approve",
        json={"step_id": None},
        headers=login(client, "manager"),
    )
    assert response.json()["status"] == "APPROVED", response.text
    add_raw_claim(db_session, org["emp"], "7000", ClaimStatus.PAID, MID_NOVEMBER)
    # APPROVED with no approved chain behind it is not payable.
    add_raw_claim(db_session, org["emp"], "30000", ClaimStatus.APPROVED, MID_NOVEMBER)
    add_raw_claim(db_session, org["emp"], "9000", ClaimStatus.PENDING_APPROVAL, MID_NOVEMBER)

    payout = summary(client).json()["kpis"]["ready_for_payout"]

    assert payout == {"claims": 2, "amount": "2000.00"}


def test_average_approval_time_runs_from_submit_to_the_final_approval(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    claim = submit(client, "emp", [line("meal", "1600", receipt=True)])
    assert claim["status"] == "PENDING_APPROVAL"
    move(db_session, claim["id"], datetime.now(UTC) - timedelta(hours=10))
    approved = client.post(
        f"{API}/claims/{claim['id']}/approve",
        json={"step_id": None, "comment": "ok"},
        headers=login(client, "manager"),
    )
    assert approved.status_code == 200, approved.text

    this_month = (datetime.now(UTC) + timedelta(hours=5, minutes=30)).strftime("%Y-%m")
    approval_time = summary(client, month=this_month).json()["kpis"]["approval_time"]

    assert approval_time["approved_claims"] == 1
    assert approval_time["average_hours"] == pytest.approx(10.0, abs=0.1)


def test_approval_time_is_null_when_nothing_was_approved(
    client: TestClient, org: dict[str, User]
) -> None:
    approval_time = summary(client).json()["kpis"]["approval_time"]

    assert approval_time == {
        "average_hours": None,
        "previous_average_hours": None,
        "approved_claims": 0,
    }


# --- needs action, charts, events ----------------------------------------------


def test_claims_above_the_finance_head_threshold_awaiting_approval_need_action(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    big = add_raw_claim(
        db_session, org["emp"], "142000", ClaimStatus.PENDING_APPROVAL, MID_NOVEMBER
    )
    bigger = add_raw_claim(
        db_session, org["emp2"], "150000", ClaimStatus.PENDING_APPROVAL, MID_NOVEMBER
    )
    add_raw_claim(db_session, org["emp"], "100000", ClaimStatus.PENDING_APPROVAL, MID_NOVEMBER)
    add_raw_claim(db_session, org["emp"], "200000", ClaimStatus.APPROVED, MID_NOVEMBER)

    high_value = summary(client).json()["needs_action"]["high_value_pending"]

    assert high_value["threshold"] == "100000.00"
    assert high_value["count"] == 2
    assert [item["id"] for item in high_value["claims"]] == [bigger.id, big.id]
    assert high_value["claims"][0]["employee_name"] == "Emp2"


def test_my_pending_approvals_matches_the_approval_queue(
    client: TestClient, org: dict[str, User]
) -> None:
    submit(client, "emp", [line("meal", "1600", receipt=True)])
    manager_headers = login(client, "manager")
    queue = client.get(f"{API}/approvals/pending", headers=manager_headers).json()

    for username, expected in (("head", 0), ("auditor", 0)):
        assert summary(client, username).json()["needs_action"]["my_pending_approvals"] == expected
    assert queue["total"] == 1


def test_monthly_spend_covers_january_to_december_of_the_year(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    add_raw_claim(db_session, org["emp"], "400", ClaimStatus.AUTO_APPROVED, MID_OCTOBER)
    add_raw_claim(db_session, org["emp"], "450", ClaimStatus.APPROVED, MID_NOVEMBER)
    add_raw_claim(db_session, org["emp"], "50", ClaimStatus.AUTO_APPROVED, MID_NOVEMBER)
    add_raw_claim(
        db_session, org["emp"], "999", ClaimStatus.AUTO_APPROVED, datetime(2025, 11, 10, tzinfo=UTC)
    )

    monthly = summary(client).json()["monthly_spend"]

    assert [item["month"] for item in monthly] == [f"2026-{m:02d}" for m in range(1, 13)]
    by_month = {item["month"]: (item["claims"], item["amount"]) for item in monthly}
    assert by_month["2026-10"] == (1, "400.00")
    assert by_month["2026-11"] == (2, "500.00")
    assert by_month["2026-01"] == (0, "0.00")


def test_spend_by_category_is_this_months_lines_largest_first(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    first = submit(client, "emp", [line("other", "300"), line("cab", "450")])
    second = submit(client, "emp2", [line("other", "250")])
    for claim in (first, second):
        move(db_session, claim["id"], MID_NOVEMBER)

    body = summary(client).json()

    assert body["spend_by_category"] == [
        {"category": "other", "amount": "550.00"},
        {"category": "cab", "amount": "450.00"},
    ]


def test_spend_by_department_groups_by_the_claimants_department(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    org["emp"].department = "Sales"
    org["manager"].department = "Sales"
    db_session.flush()
    add_raw_claim(db_session, org["emp"], "400", ClaimStatus.AUTO_APPROVED, MID_NOVEMBER)
    add_raw_claim(db_session, org["manager"], "450", ClaimStatus.AUTO_APPROVED, MID_NOVEMBER)
    add_raw_claim(db_session, org["emp2"], "300", ClaimStatus.AUTO_APPROVED, MID_NOVEMBER)
    add_raw_claim(db_session, org["emp2"], "999", ClaimStatus.AUTO_APPROVED, MID_OCTOBER)

    departments = summary(client).json()["spend_by_department"]

    assert departments == [
        {"department": "Sales", "amount": "850.00"},
        {"department": "Unassigned", "amount": "300.00"},
    ]


def test_recent_events_list_finance_actions_newest_first_with_the_actor(
    client: TestClient, org: dict[str, User]
) -> None:
    claim = submit(client, "emp", [line("meal", "1600", receipt=True)])
    client.post(
        f"{API}/claims/{claim['id']}/approve",
        json={"step_id": None},
        headers=login(client, "manager"),
    )
    changed = client.put(
        f"{API}/policy-rules/MEAL_DAILY_LIMIT",
        json={"params": {"limit": "2000"}},
        headers=login(client, "head"),
    )
    assert changed.status_code == 200, changed.text

    events = summary(client).json()["recent_events"]

    actions = [(event["action"], event["actor_name"]) for event in events]
    assert actions[0] == ("POLICY_RULE_UPDATED", "Head")
    assert ("APPROVED", "Manager") in actions
    assert all(event["action"] not in {"CREATED", "SUBMITTED"} for event in events)


def test_active_employees_counts_only_active_employee_users(
    client: TestClient, db_session: Session, org: dict[str, User]
) -> None:
    org["emp2"].is_active = False
    db_session.flush()

    assert summary(client).json()["active_employees"] == 1
