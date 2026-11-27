"""Login and finance-head user management."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password

API = "/api/v1"


def _add_user(db: Session, username: str, password: str, role: Role) -> User:
    user = User(
        username=username,
        full_name=username.title(),
        role=role.value,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    return user


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def finance_head(db_session: Session) -> User:
    return _add_user(db_session, "admin", "admin", Role.FINANCE_HEAD)


@pytest.fixture
def head_headers(client: TestClient, finance_head: User) -> dict[str, str]:
    return _login(client, "admin", "admin")


def _new_user(role: str, username: str = "asha.k") -> dict[str, object]:
    return {
        "username": username,
        "full_name": "Asha K",
        "email": f"{username}@expenseflow.example",
        "role": role,
        "password": "s3cret-pass",
    }


def test_finance_head_login_with_default_credentials_returns_token(
    client: TestClient, finance_head: User
) -> None:
    response = client.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "finance_head"
    assert "password_hash" not in body["user"]


def test_login_with_wrong_password_is_refused(client: TestClient, finance_head: User) -> None:
    response = client.post(f"{API}/auth/login", json={"username": "admin", "password": "nope"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_with_unknown_username_is_refused(client: TestClient) -> None:
    response = client.post(f"{API}/auth/login", json={"username": "ghost", "password": "admin"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.parametrize("role", list(Role))
def test_every_persona_can_log_in_and_me_returns_same_user(
    client: TestClient, db_session: Session, role: Role
) -> None:
    user = _add_user(db_session, "persona", "password1", role)

    response = client.post(
        f"{API}/auth/login", json={"username": "persona", "password": "password1"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["role"] == role.value
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.id
    assert me.json()["role"] == role.value


def test_inactive_user_login_is_refused(client: TestClient, db_session: Session) -> None:
    user = _add_user(db_session, "leaver", "password1", Role.EMPLOYEE)
    user.is_active = False
    db_session.flush()

    response = client.post(
        f"{API}/auth/login", json={"username": "leaver", "password": "password1"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_returns_the_logged_in_user(client: TestClient, head_headers: dict[str, str]) -> None:
    response = client.get(f"{API}/auth/me", headers=head_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.parametrize("role", ["employee", "line_manager", "finance_auditor"])
def test_finance_head_can_add_user_with_each_persona(
    client: TestClient, head_headers: dict[str, str], role: str
) -> None:
    response = client.post(f"{API}/users", json=_new_user(role), headers=head_headers)

    assert response.status_code == 201, response.text
    assert response.json()["role"] == role


def test_added_user_can_log_in_with_their_password(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    client.post(f"{API}/users", json=_new_user("employee"), headers=head_headers)

    response = client.post(
        f"{API}/auth/login", json={"username": "asha.k", "password": "s3cret-pass"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "employee"


def test_finance_head_cannot_add_another_finance_head(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    response = client.post(f"{API}/users", json=_new_user("finance_head"), headers=head_headers)

    assert response.status_code == 422


def test_duplicate_username_is_refused(client: TestClient, head_headers: dict[str, str]) -> None:
    client.post(f"{API}/users", json=_new_user("employee"), headers=head_headers)

    response = client.post(f"{API}/users", json=_new_user("employee"), headers=head_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"


def test_unknown_manager_id_is_refused(client: TestClient, head_headers: dict[str, str]) -> None:
    payload = _new_user("employee") | {"manager_id": 9999}

    response = client.post(f"{API}/users", json=payload, headers=head_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "manager_not_found"


@pytest.mark.parametrize("role", [Role.EMPLOYEE, Role.LINE_MANAGER, Role.FINANCE_AUDITOR])
def test_non_finance_head_cannot_add_users(
    client: TestClient, db_session: Session, role: Role
) -> None:
    _add_user(db_session, "someone", "password1", role)
    headers = _login(client, "someone", "password1")

    response = client.post(f"{API}/users", json=_new_user("employee"), headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_adding_user_without_token_is_refused(client: TestClient) -> None:
    response = client.post(f"{API}/users", json=_new_user("employee"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_forged_token_is_refused(client: TestClient) -> None:
    response = client.get(f"{API}/users", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_finance_head_can_list_users(client: TestClient, head_headers: dict[str, str]) -> None:
    client.post(f"{API}/users", json=_new_user("line_manager"), headers=head_headers)

    response = client.get(f"{API}/users", headers=head_headers)

    assert response.status_code == 200
    assert [user["username"] for user in response.json()] == ["admin", "asha.k"]


NON_HEAD_ROLES = [Role.EMPLOYEE, Role.LINE_MANAGER, Role.FINANCE_AUDITOR]


@pytest.mark.parametrize("role", NON_HEAD_ROLES)
def test_non_finance_head_can_fetch_own_details(
    client: TestClient, db_session: Session, role: Role
) -> None:
    me = _add_user(db_session, "self.user", "password1", role)
    headers = _login(client, "self.user", "password1")

    response = client.get(f"{API}/users/{me.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == me.id
    assert response.json()["role"] == role.value


@pytest.mark.parametrize("role", NON_HEAD_ROLES)
def test_non_finance_head_cannot_fetch_another_user_is_forbidden(
    client: TestClient, db_session: Session, role: Role
) -> None:
    _add_user(db_session, "self.user", "password1", role)
    other = _add_user(db_session, "other.user", "password1", Role.EMPLOYEE)
    headers = _login(client, "self.user", "password1")

    response = client.get(f"{API}/users/{other.id}", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_employee_cannot_fetch_another_employee_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    _add_user(db_session, "emp.one", "password1", Role.EMPLOYEE)
    colleague = _add_user(db_session, "emp.two", "password1", Role.EMPLOYEE)
    headers = _login(client, "emp.one", "password1")

    response = client.get(f"{API}/users/{colleague.id}", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("role", NON_HEAD_ROLES)
def test_non_finance_head_fetching_unknown_id_is_forbidden_not_found(
    client: TestClient, db_session: Session, role: Role
) -> None:
    _add_user(db_session, "self.user", "password1", role)
    headers = _login(client, "self.user", "password1")

    response = client.get(f"{API}/users/99999", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_finance_head_can_fetch_any_user(
    client: TestClient, db_session: Session, head_headers: dict[str, str]
) -> None:
    other = _add_user(db_session, "emp.one", "password1", Role.EMPLOYEE)

    response = client.get(f"{API}/users/{other.id}", headers=head_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "emp.one"


def test_finance_head_fetching_unknown_user_is_not_found(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    response = client.get(f"{API}/users/99999", headers=head_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"


def test_fetching_user_without_token_is_refused(client: TestClient, finance_head: User) -> None:
    response = client.get(f"{API}/users/{finance_head.id}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_user_whose_username_is_their_work_email_can_be_added_and_log_in(
    client: TestClient, head_headers: dict[str, str]
) -> None:
    body = _new_user("employee") | {"username": "Asha.K@expenseflow.example"}

    created = client.post(f"{API}/users", json=body, headers=head_headers)
    login = client.post(
        f"{API}/auth/login",
        json={"username": "asha.k@expenseflow.example", "password": "s3cret-pass"},
    )

    assert created.status_code == 201, created.text
    assert created.json()["username"] == "asha.k@expenseflow.example"
    assert login.status_code == 200
