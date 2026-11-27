"""Request validation edge cases that used to escape as 500s instead of 422s."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Role, User
from app.schemas.claim import ClaimLineIn, ClaimWrite
from app.schemas.user import UserCreate
from app.security import hash_password

OPTIONAL_LINE_TEXT = ["vendor", "description", "city", "receipt_number"]


@pytest.mark.parametrize("field", OPTIONAL_LINE_TEXT)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_optional_line_text_accepts_null_and_blank_as_none(field: str, value: str | None) -> None:
    line = ClaimLineIn(**{field: value})

    assert getattr(line, field) is None


def test_claim_title_accepts_null() -> None:
    assert ClaimWrite(title=None).title is None


def test_line_text_is_trimmed() -> None:
    assert ClaimLineIn(vendor="  Ola  ").vendor == "Ola"


def test_line_text_over_its_limit_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        ClaimLineIn(vendor="x" * 201)


def test_claim_title_over_its_limit_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        ClaimWrite(title="x" * 201)


def test_username_may_be_a_work_email() -> None:
    user = UserCreate(
        username="priya.nair+ops@expenseflow.example",
        full_name="Priya Nair",
        role="line_manager",
        password="password1",
    )

    assert user.username == "priya.nair+ops@expenseflow.example"


@pytest.mark.parametrize("username", ["has space", "semi;colon", "ab"])
def test_username_with_spaces_symbols_or_too_short_is_refused(username: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(username=username, full_name="X", role="employee", password="password1")


def test_saving_a_draft_with_null_and_blank_optional_fields_returns_201(
    client: TestClient, db_session: Session
) -> None:
    db_session.add(
        User(
            username="emp.null",
            full_name="Emp Null",
            role=Role.EMPLOYEE.value,
            password_hash=hash_password("password1"),
        )
    )
    db_session.flush()
    token = client.post(
        "/api/v1/auth/login", json={"username": "emp.null", "password": "password1"}
    ).json()["access_token"]
    line = {"category": "cab", "amount": "120", "vendor": "", "description": None, "city": None}

    response = client.post(
        "/api/v1/claims",
        json={"action": "draft", "title": None, "lines": [line]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["lines"][0]["vendor"] is None
