"""Policy rules applied when a claim is submitted: receipts, limits and duplicates.

A breach is observed through ``GET /claims/{id}/policy-results``: each line lists the
rule codes it breached. Every line is dated on a weekday, so WEEKEND_SPEND stays quiet,
and each test keeps its claims well under the 25,000 SPLIT_CLAIM threshold.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PolicySetting, Role, User
from app.services import attachments
from tests.helpers import API, add_user, line, line_codes, login, policy_results, submit_claim

RULES = f"{API}/policy-rules"
LIMIT_CODES = {
    "MEAL_DAILY_LIMIT",
    "HOTEL_NIGHTLY_LIMIT_T1",
    "HOTEL_NIGHTLY_LIMIT_OTHER",
    "LOCAL_TRIP_LIMIT",
    "CAB_TRIP_LIMIT",
}


@pytest.fixture(autouse=True)
def upload_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(attachments, "upload_root", lambda: tmp_path)


@pytest.fixture
def manager(db_session: Session) -> User:
    return add_user(db_session, "mgr", Role.LINE_MANAGER)


@pytest.fixture
def employee(client: TestClient, db_session: Session, manager: User) -> dict[str, str]:
    add_user(db_session, "emp", Role.EMPLOYEE, manager=manager)
    return login(client, "emp")


@pytest.fixture
def other_employee(client: TestClient, db_session: Session, manager: User) -> dict[str, str]:
    add_user(db_session, "emp2", Role.EMPLOYEE, manager=manager)
    return login(client, "emp2")


@pytest.fixture
def head(client: TestClient, db_session: Session) -> dict[str, str]:
    add_user(db_session, "head", Role.FINANCE_HEAD)
    return login(client, "head")


def submitted(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    return response.json()


def change_rule(client: TestClient, head: dict[str, str], code: str, params: dict) -> None:
    response = client.put(f"{RULES}/{code}", json={"params": params}, headers=head)
    assert response.status_code == 200, response.text


# --- receipts ----------------------------------------------------------------


def test_line_above_500_in_claim_above_500_without_receipt_is_refused(
    client: TestClient, employee: dict[str, str]
) -> None:
    response = submit_claim(client, employee, [line("other", "600")])

    assert response.status_code == 422
    fields = {item["field"] for item in response.json()["error"]["details"]["fields"]}
    assert fields == {"lines.0.receipt_number", "lines.0.receipt_id"}


def test_line_of_exactly_500_needs_no_receipt_and_is_auto_approved(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "500.00")]))

    assert claim["status"] == "AUTO_APPROVED"
    assert "RECEIPT_MANDATORY" not in line_codes(client, employee, claim["id"])[0]


def test_small_lines_need_no_receipt_even_when_the_total_is_above_500(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "300"), line("other", "300")]))

    assert claim["status"] == "PENDING_APPROVAL"
    assert claim["total_amount"] == "600.00"
    assert all(
        "RECEIPT_MANDATORY" not in codes for codes in line_codes(client, employee, claim["id"])
    )


def test_clean_claim_above_500_is_routed_for_approval_not_auto_approved(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "500.01", receipt=True)]))

    assert claim["status"] == "PENDING_APPROVAL"
    results = policy_results(client, employee, claim["id"])
    assert [item["rule_codes"] for item in results["claim_level"]] == [["AUTO_APPROVE_LIMIT"]]


def test_line_above_500_with_receipt_number_and_upload_is_submitted(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("other", "600", receipt=True)]))

    assert claim["status"] == "PENDING_APPROVAL"
    assert claim["lines"][0]["receipt_id"] == claim["attachments"][0]["id"]
    assert len(claim["attachments"][0]["sha256"]) == 64
    assert "RECEIPT_MANDATORY" not in line_codes(client, employee, claim["id"])[0]


def test_raised_receipt_threshold_applies_to_the_next_submit(
    client: TestClient, employee: dict[str, str], head: dict[str, str]
) -> None:
    change_rule(client, head, "RECEIPT_MANDATORY", {"above": "1000"})

    claim = submitted(submit_claim(client, employee, [line("other", "600")]))

    assert claim["status"] == "PENDING_APPROVAL"
    assert "RECEIPT_MANDATORY" not in line_codes(client, employee, claim["id"])[0]


def test_receipt_threshold_of_zero_refuses_a_small_line_without_receipt(
    client: TestClient, employee: dict[str, str], head: dict[str, str]
) -> None:
    change_rule(client, head, "RECEIPT_MANDATORY", {"above": "0"})

    response = submit_claim(client, employee, [line("other", "100")])

    assert response.status_code == 422


# --- meal --------------------------------------------------------------------


def test_meal_at_the_daily_limit_is_not_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("meal", "1500", receipt=True)]))

    assert "MEAL_DAILY_LIMIT" not in line_codes(client, employee, claim["id"])[0]


def test_meal_above_the_daily_limit_is_routed_for_approval(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("meal", "1500.01", receipt=True)]))

    assert claim["status"] == "PENDING_APPROVAL"
    finding = policy_results(client, employee, claim["id"])["lines"][0]
    assert "MEAL_DAILY_LIMIT" in finding["rule_codes"]
    assert finding["outcome"] == "ROUTE_FOR_APPROVAL"
    assert (
        "Meal spend 1,500.01 INR on 20-Nov-2026 exceeds daily limit of 1,500.00 INR"
        in finding["reasons"]
    )


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

    assert all("MEAL_DAILY_LIMIT" in codes for codes in line_codes(client, employee, claim["id"]))


def test_meals_on_different_days_are_not_summed(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(
        submit_claim(
            client,
            employee,
            [
                line("meal", "1000", receipt=True),
                line("meal", "1000", receipt=True, expense_date="2026-11-19"),
            ],
        )
    )

    assert all(
        "MEAL_DAILY_LIMIT" not in codes for codes in line_codes(client, employee, claim["id"])
    )


def test_meal_limit_counts_the_employees_other_submitted_claims(
    client: TestClient, employee: dict[str, str]
) -> None:
    submitted(submit_claim(client, employee, [line("meal", "1000", receipt=True)]))

    claim = submitted(submit_claim(client, employee, [line("meal", "501", receipt=True)]))

    finding = policy_results(client, employee, claim["id"])["lines"][0]
    assert "MEAL_DAILY_LIMIT" in finding["rule_codes"]
    assert (
        "Meal spend 1,501.00 INR on 20-Nov-2026 exceeds daily limit of 1,500.00 INR"
        in finding["reasons"]
    )


def test_meal_limit_ignores_drafts_and_other_employees(
    client: TestClient, employee: dict[str, str], other_employee: dict[str, str]
) -> None:
    client.post(f"{API}/claims", json={"lines": [line("meal", "1400")]}, headers=employee)
    submitted(submit_claim(client, other_employee, [line("meal", "1400", receipt=True)]))

    claim = submitted(submit_claim(client, employee, [line("meal", "1000", receipt=True)]))

    assert "MEAL_DAILY_LIMIT" not in line_codes(client, employee, claim["id"])[0]


def test_raised_meal_limit_applies_to_the_next_submit(
    client: TestClient, employee: dict[str, str], head: dict[str, str]
) -> None:
    change_rule(client, head, "MEAL_DAILY_LIMIT", {"limit": "2000"})

    claim = submitted(submit_claim(client, employee, [line("meal", "1800", receipt=True)]))

    assert "MEAL_DAILY_LIMIT" not in line_codes(client, employee, claim["id"])[0]


# --- hotel -------------------------------------------------------------------


def hotel(amount: str, city: str, nights: int = 2) -> dict[str, Any]:
    return line("hotel", amount, city=city, nights=nights, receipt=True)


@pytest.mark.parametrize("city", ["Mumbai", "  mumbai "])
def test_tier1_hotel_at_6000_per_night_is_not_flagged(
    client: TestClient, employee: dict[str, str], city: str
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("12000", city)]))

    codes = line_codes(client, employee, claim["id"])[0]
    assert "HOTEL_NIGHTLY_LIMIT_T1" not in codes
    assert "HOTEL_NIGHTLY_LIMIT_OTHER" not in codes


def test_tier1_hotel_above_6000_per_night_is_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("12000.01", "Mumbai")]))

    assert claim["status"] == "PENDING_APPROVAL"
    assert "HOTEL_NIGHTLY_LIMIT_T1" in line_codes(client, employee, claim["id"])[0]


def test_other_city_hotel_at_4000_per_night_is_not_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("8000", "Indore")]))

    assert "HOTEL_NIGHTLY_LIMIT_OTHER" not in line_codes(client, employee, claim["id"])[0]


def test_other_city_hotel_above_4000_per_night_is_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [hotel("8000.02", "Indore")]))

    finding = policy_results(client, employee, claim["id"])["lines"][0]
    assert finding["rule_codes"] == ["HOTEL_NIGHTLY_LIMIT_OTHER"]
    assert finding["reasons"] == [
        "Hotel 4,000.01 INR per night in Indore exceeds limit of 4,000.00 INR "
        "for non-tier-1 cities"
    ]


def test_city_added_to_tier1_list_gets_the_tier1_limit(
    client: TestClient, db_session: Session, employee: dict[str, str]
) -> None:
    setting = db_session.get(PolicySetting, "tier1_cities")
    assert setting is not None
    setting.value = [*setting.value, "indore"]
    db_session.flush()

    claim = submitted(submit_claim(client, employee, [hotel("9000", "Indore")]))

    codes = line_codes(client, employee, claim["id"])[0]
    assert "HOTEL_NIGHTLY_LIMIT_OTHER" not in codes
    assert "HOTEL_NIGHTLY_LIMIT_T1" not in codes


# --- local conveyance --------------------------------------------------------


def test_local_trip_at_2000_is_not_flagged(client: TestClient, employee: dict[str, str]) -> None:
    claim = submitted(submit_claim(client, employee, [line("local", "2000", receipt=True)]))

    assert "LOCAL_TRIP_LIMIT" not in line_codes(client, employee, claim["id"])[0]


def test_local_trip_above_2000_is_routed_for_approval(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(submit_claim(client, employee, [line("local", "2000.01", receipt=True)]))

    assert claim["status"] == "PENDING_APPROVAL"
    finding = policy_results(client, employee, claim["id"])["lines"][0]
    assert "LOCAL_TRIP_LIMIT" in finding["rule_codes"]
    assert (
        "Local conveyance 2,000.01 INR on 20-Nov-2026 exceeds per-trip limit of 2,000.00 INR"
        in finding["reasons"]
    )


def test_categories_without_a_limit_are_never_flagged(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(
        submit_claim(
            client,
            employee,
            [
                line("cab", "9000", receipt=True),
                line("airfare", "9000", receipt=True),
                line("other", "6000", receipt=True),
            ],
        )
    )

    for codes in line_codes(client, employee, claim["id"]):
        assert LIMIT_CODES.isdisjoint(codes)


def test_draft_lines_carry_no_policy_results(client: TestClient, employee: dict[str, str]) -> None:
    response = client.post(
        f"{API}/claims", json={"lines": [line("meal", "5000")]}, headers=employee
    )

    assert response.status_code == 201
    results = policy_results(client, employee, response.json()["id"])
    assert results["round"] == 0
    assert results["outcome"] is None
    assert results["lines"] == []
    assert results["claim_level"] == []


# --- duplicates --------------------------------------------------------------


def receipt_line(vendor: str, amount: str, receipt_number: str) -> dict[str, Any]:
    return line("other", amount, vendor=vendor, receipt_number=receipt_number, receipt=True)


def test_same_vendor_amount_and_receipt_number_marks_the_claim_duplicate(
    client: TestClient, employee: dict[str, str], other_employee: dict[str, str]
) -> None:
    original = submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))

    claim = submitted(
        submit_claim(client, other_employee, [receipt_line(" cafe  a ", "600.00", "r-1")])
    )

    assert claim["status"] == "DUPLICATE"
    finding = policy_results(client, other_employee, claim["id"])["lines"][0]
    assert finding["outcome"] == "MARK_DUPLICATE"
    assert "DUPLICATE_RECEIPT_NUMBER" in finding["rule_codes"]
    assert (
        f"Duplicate: same vendor, amount and receipt number as line 1 of claim #{original['id']}"
        in finding["reasons"]
    )


def test_two_matching_lines_in_one_claim_mark_it_duplicate(
    client: TestClient, employee: dict[str, str]
) -> None:
    claim = submitted(
        submit_claim(
            client,
            employee,
            [receipt_line("Cafe A", "600", "R-1"), receipt_line("Cafe A", "600", "R-1")],
        )
    )

    assert claim["status"] == "DUPLICATE"
    codes = line_codes(client, employee, claim["id"])
    assert "DUPLICATE_RECEIPT_NUMBER" not in codes[0]
    assert "DUPLICATE_RECEIPT_NUMBER" in codes[1]


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

    assert claim["status"] == "PENDING_APPROVAL"
    assert "DUPLICATE_RECEIPT_NUMBER" not in line_codes(client, employee, claim["id"])[0]


def test_a_matching_draft_does_not_make_a_duplicate(
    client: TestClient, employee: dict[str, str]
) -> None:
    client.post(
        f"{API}/claims",
        json={"lines": [line("other", "600", vendor="Cafe A", receipt_number="R-1")]},
        headers=employee,
    )

    claim = submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))

    assert claim["status"] == "PENDING_APPROVAL"


def test_a_duplicate_claim_cannot_be_edited(client: TestClient, employee: dict[str, str]) -> None:
    submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))
    duplicate = submitted(submit_claim(client, employee, [receipt_line("Cafe A", "600", "R-1")]))
    assert duplicate["status"] == "DUPLICATE"

    response = client.put(
        f"{API}/claims/{duplicate['id']}", json={"action": "draft"}, headers=employee
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "claim_not_editable"
