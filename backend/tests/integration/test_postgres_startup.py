"""Startup against a real PostgreSQL database: Alembic schema + seed.sql + policy defaults.

Opt-in: runs only with RUN_INTEGRATION=1 and DATABASE_URL pointing at a PostgreSQL
database that has had the container's startup steps (``alembic upgrade head``, then
``python -m scripts.seed_db``, as ``scripts/start.py`` runs them). The CI `startup` job
does exactly that. Use a throwaway database: the flow test pays today's approved claims.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import create_app
from app.models import PolicyRule, User
from scripts import seed_db

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_INTEGRATION") != "1"
        or not get_settings().database_url.startswith("postgresql"),
        reason="needs RUN_INTEGRATION=1 and a migrated, seeded PostgreSQL DATABASE_URL",
    ),
]

API = "/api/v1"
DEMO_LOGINS = {
    "admin": "finance_head",
    "manager": "line_manager",
    "auditor": "finance_auditor",
    "employee": "employee",
}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """The real application on the migrated, seeded database (startup adds policy defaults)."""
    with TestClient(create_app()) as test_client:
        yield test_client


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": username})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _last_weekday() -> str:
    day = date.today() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def test_startup_inserts_policy_defaults_and_the_database_is_ready(client: TestClient) -> None:
    with SessionLocal() as db:
        rules = db.scalar(select(func.count()).select_from(PolicyRule))

    assert rules and rules > 0
    assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize(("username", "role"), DEMO_LOGINS.items())
def test_every_seeded_persona_can_log_in(client: TestClient, username: str, role: str) -> None:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": username})

    assert response.status_code == 200, response.text
    assert response.json()["user"]["role"] == role


def test_seeding_again_on_restart_does_not_duplicate_data(client: TestClient) -> None:
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(User))

    seed_db.run()

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == before


def test_claim_to_payout_flow_works_on_postgres(client: TestClient) -> None:
    employee = _login(client, "employee")
    draft = client.post(
        f"{API}/claims",
        json={
            "lines": [
                {
                    "category": "meal",
                    "amount": "300",
                    "expense_date": _last_weekday(),
                    "vendor": "CI Synthetic Cafe",
                }
            ]
        },
        headers=employee,
    )
    assert draft.status_code == 201, draft.text
    submitted = client.post(f"{API}/claims/{draft.json()['id']}/submit", headers=employee)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "AUTO_APPROVED"

    head = _login(client, "admin")
    batch = client.post(f"{API}/payouts/batches", json={"range": "TODAY"}, headers=head)
    assert batch.status_code == 201, batch.text
    exported = client.get(f"{API}/payouts/batches/{batch.json()['id']}/export", headers=head)

    assert exported.status_code == 200
    assert exported.text.startswith("BatchReference,")
