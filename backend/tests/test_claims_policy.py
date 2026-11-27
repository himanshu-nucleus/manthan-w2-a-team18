"""Policy rules applied when a claim is submitted: receipts, limits and duplicates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditAction, AuditEvent, Role
from app.services import attachments
from tests.helpers import API, add_user, line, login, submit_claim


@pytest.fixture(autouse=True)
def upload_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(attachments, "upload_root", lambda: tmp_path)


@pytest.fixture
def employee(client: TestClient, db_session: Session) -> dict[str, str]:
    add_user(db_session, "emp", Role.EMPLOYEE)
    return login(client, "emp")


@pytest.fixture
def other_employee(client: TestClient, db_session: Session) -> dict[str, str]:
    add_user(db_session, "emp2", Role.EMPLOYEE)
    return login(client, "emp2")


@pytest.fixture
def head(client: TestClient, db_session: Session) -> dict[str, str]:
    add_user(db_session, "head", Role.FINANCE_HEAD)
    return login(client, "head")


def submitted(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    return response.json()


def flags(claim: dict[str, Any]) -> list[list[str]]:
    return [item["policy_flags"] for item in claim["lines"]]


# --- receipts ----------------------------------------------------------------


def test_line_above_500_in_claim_above_500_without_receipt_is_refused(
    client: TestClient, employee: dict[str, str]
) -> None:
    response = submit_claim(client, employee, [line("other", "600")])

    assert response.status_code == 422
    fields = {item["field"] for item in response.json()["error"]["details"]["fields"]}
    assert fields == {"lines.0.receipt_number", "lines.0.receipt_id"}


def test_line_of_exactly_500_needs_no_receipt(client: TestClient, employee: dict[str, str]) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "500.00")]))

    assert claim["status"] == "SUBMITTED"


def test_small_lines_need_no_receipt_even_when_the_total_is_above_500(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "300"), line("other", "300")]))

    assert claim["status"] == "SUBMITTED"
    assert claim["total_amount"] == "600.00"


def test_line_above_500_with_receipt_number_and_upload_is_submitted(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "600", receipt=True)]))

    assert claim["status"] == "SUBMITTED"
    assert claim["lines"][0]["receipt_id"] == claim["attachments"][0]["id"]
    assert len(claim["attachments"][0]["sha256"]) == 64


def test_raised_receipt_threshold_applies_to_the_next_submit(
    client: TestClient, employee: dict[str, str], head: dict[str, str]
) -> None:
    client.patch(f"{API}/policy", json={"receipt_required_above": "1000"}, headers=head)

    claim = submitted(submit_claim(client, employee, [line("other", "600")]))

    assert claim["status"] == "SUBMITTED"


# --- meal --------------------------------------------------------------------


def test_meal_at_the_daily_limit_is_not_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("meal", "1500", receipt=True)]))

    assert flags(claim) == [[]]


def test_meal_above_the_daily_limit_is_flagged_but_submitted(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("meal", "1500.01", receipt=True)]))

    assert claim["status"] == "SUBMITTED"
    assert flags(claim) == [
        ["meal: 1500.01 spent on 2026-11-20 exceeds the daily limit of 1500.00 INR"]
    ]


def test_meals_on_the_same_day_are_summed_and_all_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(
        submit_claim(
            client,
            employee,
            [line("meal", "1000", receipt=True), line("meal", "501", receipt=True)],
        )
    )

    assert all(item for item in flags(claim))


def test_meals_on_different_days_are_not_summed(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(
        submit_claim(
            client,
            employee,
            [
                line("meal", "1000", receipt=True),
                line("meal", "1000", receipt=True, expense_date="2026-11-21"),
            ],
        )
    )

    assert flags(claim) == [[], []]


def test_meal_limit_counts_the_employees_other_submitted_claims(
    client: TestClient, employee: dict[str, str]
) -> None:
    submitted(submit_claim(client, employee, [line("meal", "1000", receipt=True)]))

    claim = submitted(submit_claim(client, employee, [line("meal", "501", receipt=True)]))

    assert flags(claim) == [
        ["meal: 1501.00 spent on 2026-11-20 exceeds the daily limit of 1500.00 INR"]
    ]


def test_meal_limit_ignores_drafts_and_other_employees(
    client: TestClient, employee: dict[str, str], other_employee: dict[str, str]
) -> None:
    client.post(f"{API}/claims", json={"lines": [line("meal", "1400")]}, headers=employee)
    submitted(submit_claim(client, other_employee, [line("meal", "1400", receipt=True)]))

    claim = submitted(submit_claim(client, employee, [line("meal", "1000", receipt=True)]))

    assert flags(claim) == [[]]


def test_raised_meal_limit_applies_to_the_next_submit(
    client: TestClient, employee: dict[str, str], head: dict[str, str]
) -> None:
    client.patch(f"{API}/policy", json={"meal_daily_limit": "2000"}, headers=head)

    claim = submitted(submit_claim(client, employee, [line("meal", "1800", receipt=True)]))

    assert flags(claim) == [[]]


# --- hotel -------------------------------------------------------------------


def hotel(amount: str, city: str, nights: int = 2) -> dict[str, Any]:
    return line("hotel", amount, city=city, nights=nights, receipt=True)


@pytest.mark.parametrize("city", ["Mumbai", "  mumbai "])
def test_tier1_hotel_at_6000_per_night_is_not_flagged(
    client: TestClient, employee: dict[str, str], city: str
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("12000", city)]))

    assert flags(claim) == [[]]


def test_tier1_hotel_above_6000_per_night_is_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("12000.01", "Mumbai")]))

    assert flags(claim) == [
        [
            "hotel: 12000.01 for 2 night(s) in Mumbai exceeds 12000.00 INR "
            "(6000.00 per night, tier-1 city)"
        ]
    ]


def test_other_city_hotel_at_4000_per_night_is_not_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("8000", "Indore")]))

    assert flags(claim) == [[]]


def test_other_city_hotel_above_4000_per_night_is_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("8000.01", "Indore")]))

    assert flags(claim) == [
        [
            "hotel: 8000.01 for 2 night(s) in Indore exceeds 8000.00 INR "
            "(4000.00 per night, non-tier-1 city)"
        ]
    ]


def test_city_added_to_tier1_list_gets_the_tier1_limit(
    client: TestClient, employee: dict[str, str], head: dict[str, str]
) -> None:
    client.patch(f"{API}/policy", json={"tier1_cities": ["Indore"]}, headers=head)

    claim = submitted(submit_claim(client, employee, [hotel("9000", "Indore")]))

    assert flags(claim) == [[]]


# --- local conveyance --------------------------------------------------------


def test_local_trip_at_2000_is_not_flagged(client: TestClient, employee: dict[str, str]) -> None:
    claim = submitted(submit_claim(client, employee, [line("local", "2000", receipt=True)]))

    assert flags(claim) == [[]]


def test_local_trip_above_2000_is_flagged(client: TestClient, employee: dict[str, str]) -> None:
    claim = submitted(submit_claim(client, employee, [line("local", "2000.01", receipt=True)]))

    assert flags(claim) == [["local: 2000.01 exceeds the per-trip limit of 2000.00 INR"]]


def test_categories_without_a_limit_are_never_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(
        submit_claim(
            client,
            employee,
            [line("cab", "9000", receipt=True), line("other", "9000", receipt=True)],
        )
    )

    assert flags(claim) == [[], []]


def test_draft_lines_carry_no_policy_flags(client: TestClient, employee: dict[str, str]) -> None:
    response = client.post(
        f"{API}/claims", json={"lines": [line("meal", "5000")]}, headers=employee
    )

    assert response.status_code == 201
    assert flags(response.json()) == [[]]


# --- duplicates --------------------------------------------------------------


def receipt_line(vendor: str, amount: str, receipt_number: str) -> dict[str, Any]:
    return line("other", amount, vendor=vendor, receipt_number=receipt_number, receipt=True)


def test_same_vendor_amount_and_receipt_number_marks_the_claim_duplicate(
    client: TestClient,
    db_session: Session,
    employee: dict[str, str],
    other_employee: dict[str, str],
) -> None:
    original = submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))

    claim = submitted(
        submit_claim(client, other_employee, [receipt_line("cafe a", "600.00", "r-1")])
    )

    assert claim["status"] == "DUPLICATE"
    event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_id == claim["id"], AuditEvent.action == AuditAction.SUBMITTED
        )
    )
    assert event.changes["duplicate_of"]["new"] == {
        "line": 0,
        "claim_id": original["id"],
        "claim_line_position": 1,
    }


@pytest.mark.parametrize(
    ("vendor", "amount", "receipt_number"),
    [("Cafe B", "600", "R-1"), ("Cafe A", "601", "R-1"), ("Cafe A", "600", "R-2")],
)
def test_a_different_vendor_amount_or_receipt_number_is_not_a_duplicate(
    client: TestClient,
    employee: dict[str, str],
    vendor: str,
    amount: str,
    receipt_number: str,
) -> None:
    submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))

    claim = submitted(
        submit_claim(client, employee, [receipt_line(vendor, amount, receipt_number)])
    )

    assert claim["status"] == "SUBMITTED"


def test_a_matching_draft_does_not_make_a_duplicate(
    client: TestClient, employee: dict[str, str]
) -> None:
    client.post(
        f"{API}/claims",
        json={"lines": [line("other", "600", vendor="Cafe A", receipt_number="R-1")]},
        headers=employee,
    )

    claim = submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))

    assert claim["status"] == "SUBMITTED"


def test_a_duplicate_claim_cannot_be_edited(client: TestClient, employee: dict[str, str]) -> None:
    submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))
    duplicate = submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))

    response = client.put(
        f"{API}/claims/{duplicate['id']}", json={"action": "draft"}, headers=employee
    )

    assert response.status_code == 409
