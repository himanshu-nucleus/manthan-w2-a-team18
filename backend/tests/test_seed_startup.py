"""Startup data: db/seed.sql, which the api container loads on every start, inserts the demo
users idempotently.

The container runs it through psycopg (``scripts/seed_db.py``); here the same file runs
through SQLite on the ORM schema, which is enough to check what it inserts. The real
PostgreSQL run is in tests/integration/.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Role, User
from app.security import verify_password
from scripts import seed_db

DEMO_LOGINS = {
    "admin": Role.FINANCE_HEAD,
    "manager": Role.LINE_MANAGER,
    "auditor": Role.FINANCE_AUDITOR,
    "employee": Role.EMPLOYEE,
}


@pytest.fixture
def seeded(tmp_path) -> Iterator[tuple[Session, sqlite3.Connection]]:
    """A file SQLite database with the ORM schema and db/seed.sql applied once."""
    path = tmp_path / "seed.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    Base.metadata.create_all(engine)
    raw = sqlite3.connect(path)
    raw.executescript(seed_db.SEED_FILE.read_text(encoding="utf-8"))
    with Session(engine) as session:
        yield session, raw
    raw.close()
    engine.dispose()


def test_seed_file_inserts_every_demo_persona_with_a_working_password(
    seeded: tuple[Session, sqlite3.Connection],
) -> None:
    session, _ = seeded

    for username, role in DEMO_LOGINS.items():
        user = session.scalar(select(User).where(User.username == username))
        assert user is not None, username
        assert user.role == role.value
        assert verify_password(username, user.password_hash)


def test_seed_file_links_employees_to_managers_and_sets_departments(
    seeded: tuple[Session, sqlite3.Connection],
) -> None:
    users = {u.username: u for u in seeded[0].scalars(select(User))}

    assert users["employee"].manager_id == users["manager"].id
    assert users["employee1"].manager_id == users["manager1"].id
    assert users["admin"].department == "Finance"
    assert users["employee1"].department == "Engineering"


def test_running_the_seed_again_adds_no_duplicate_rows(
    seeded: tuple[Session, sqlite3.Connection],
) -> None:
    session, raw = seeded
    before = session.scalar(select(func.count()).select_from(User))

    raw.executescript(seed_db.SEED_FILE.read_text(encoding="utf-8"))

    assert session.scalar(select(func.count()).select_from(User)) == before


def test_seed_script_turns_the_sqlalchemy_url_into_a_libpq_url() -> None:
    url = "postgresql+psycopg://manthan:manthan@db:5432/manthan"

    assert seed_db.psycopg_url(url) == "postgresql://manthan:manthan@db:5432/manthan"
