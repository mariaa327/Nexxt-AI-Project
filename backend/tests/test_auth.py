"""Login, session tokens, per-user databases and isolation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import security
from app.core.database import DatabaseRouter
from app.models import client as m
from app.models.directory import User
from app.services.provisioning import provision
from tests.conftest import DEMO_PASSWORD, FakeClock, auth_headers

H = dict[str, str]

DATA_ENDPOINTS = [
    ("GET", "/api/dashboard"),
    ("POST", "/api/agent/analyze"),
    ("POST", "/api/agent/reset"),
    ("GET", "/api/auth/me"),
]


def test_login_returns_token_and_user(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "Andrei ", "password": DEMO_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {"username": "andrei", "display_name": "Andrei Popescu"}
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert me.json()["username"] == "andrei"


@pytest.mark.parametrize(
    ("username", "password"), [("andrei", "wrong"), ("nobody", DEMO_PASSWORD)]
)
def test_bad_credentials_get_one_generic_error(
    client: TestClient, username: str, password: str
) -> None:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."


@pytest.mark.parametrize(("method", "path"), DATA_ENDPOINTS)
def test_data_endpoints_require_login(
    client: TestClient, method: str, path: str
) -> None:
    assert client.request(method, path).status_code == 401
    bad = {"Authorization": "Bearer 1.9999999999.forged"}
    assert client.request(method, path, headers=bad).status_code == 401


def test_tampered_and_expired_tokens_are_rejected() -> None:
    token = security.issue_token(1, now=1_000_000)
    assert security.read_token(token, now=1_000_001) == 1
    user_id, expires, signature = token.split(".")
    assert security.read_token(f"2.{expires}.{signature}", now=1_000_001) is None
    assert (
        security.read_token(f"{user_id}.{int(expires) + 1}.{signature}", now=1_000_001)
        is None
    )
    assert security.read_token(token, now=int(expires) + 1) is None
    assert security.read_token("garbage", now=1_000_001) is None


def test_passwords_are_hashed(db_router: DatabaseRouter) -> None:
    with db_router.directory_session() as directory:
        user = directory.scalars(select(User).where(User.username == "andrei")).one()
    assert DEMO_PASSWORD not in user.password_hash
    assert security.verify_password(DEMO_PASSWORD, user.password_hash)
    assert not security.verify_password("wrong", user.password_hash)


@pytest.mark.parametrize(
    ("username", "name", "recommended", "no_action", "source"),
    [
        ("andrei", "Andrei Popescu", "credit_card", False, "scheduled"),
        ("maria", "Maria Ionescu", None, True, "scheduled"),
        ("ioana", "Ioana Dumitrescu", "savings", False, "scheduled"),
        ("mihai", "Mihai Stan", "savings", False, "scheduled"),
        ("elena", "Elena Radu", "overdraft", False, "scheduled"),
        ("radu", "Radu Marin", "credit_card", False, "recurring_history"),
    ],
)
def test_each_user_sees_their_own_situation(
    client: TestClient,
    username: str,
    name: str,
    recommended: str | None,
    no_action: bool,
    source: str,
) -> None:
    body = client.get("/api/dashboard", headers=auth_headers(client, username)).json()

    assert body["customer_name"] == name
    assert body["recommended_option_id"] == recommended
    assert body["no_action_needed"] is no_action
    assert body["payments_source"] == source


def test_demo_users_listed_in_edge_case_order(client: TestClient) -> None:
    users = client.get("/api/auth/demo-users").json()

    assert [u["username"] for u in users] == [
        "andrei",
        "maria",
        "ioana",
        "mihai",
        "elena",
        "radu",
    ]
    assert all(u["caption"] and "password" not in u for u in users)


def test_execution_is_saved_and_isolated(
    client: TestClient, clock: FakeClock, db_router: DatabaseRouter, andrei: H
) -> None:
    maria = auth_headers(client, "maria")
    challenge_id = client.post(
        "/api/agent/execute/initiate", json={"option_id": "credit_card"}, headers=andrei
    ).json()["challenge_id"]
    clock.advance(3)

    # Maria cannot see or use Andrei's verification.
    assert (
        client.get(f"/api/agent/challenges/{challenge_id}", headers=maria).status_code
        == 404
    )
    stolen = client.post(
        "/api/agent/execute", json={"challenge_id": challenge_id}, headers=maria
    )
    assert stolen.status_code == 404

    done = client.post(
        "/api/agent/execute", json={"challenge_id": challenge_id}, headers=andrei
    )
    assert done.status_code == 200

    # Saved in Andrei's database: a fresh login still sees it.
    again = auth_headers(client, "andrei")
    assert (
        client.get("/api/dashboard", headers=again).json()["no_action_needed"] is True
    )
    with db_router.session("client_andrei") as session:
        card = session.get(m.Account, "ACC-CREDIT-002")
        enel = session.get(m.ScheduledPayment, "SCH-11-05-01")
    assert str(card.available_balance) == "7531.60"
    assert enel.account_id == "ACC-CREDIT-002"
    # Maria's database is untouched.
    with db_router.session("client_maria") as session:
        assert (
            str(session.get(m.Account, "ACC-CREDIT-002").available_balance) == "8150.00"
        )


def test_history_only_payment_rerouting_is_saved(
    client: TestClient, clock: FakeClock, db_router: DatabaseRouter
) -> None:
    radu = auth_headers(client, "radu")
    challenge_id = client.post(
        "/api/agent/execute/initiate", json={"option_id": "credit_card"}, headers=radu
    ).json()["challenge_id"]
    clock.advance(3)
    client.post("/api/agent/execute", json={"challenge_id": challenge_id}, headers=radu)

    assert client.get("/api/dashboard", headers=radu).json()["no_action_needed"] is True


def test_reset_restores_seed(
    client: TestClient, clock: FakeClock, db_router: DatabaseRouter, andrei: H
) -> None:
    challenge_id = client.post(
        "/api/agent/execute/initiate", json={"option_id": "savings"}, headers=andrei
    ).json()["challenge_id"]
    clock.advance(3)
    client.post(
        "/api/agent/execute", json={"challenge_id": challenge_id}, headers=andrei
    )

    reset = client.post("/api/agent/reset", headers=andrei).json()

    assert reset["recommended_option_id"] == "credit_card"
    with db_router.session("client_andrei") as session:
        savings = session.get(m.Account, "ACC-SAVINGS-003")
    assert str(savings.available_balance) == "12000.00"
    assert str(savings.accrued_interest) == "12.40"


def test_provisioning_is_idempotent(db_router: DatabaseRouter) -> None:
    provision(db_router)
    with db_router.directory_session() as directory:
        assert directory.scalar(select(func.count()).select_from(User)) == 6
    with db_router.session("client_andrei") as session:
        assert session.scalar(select(func.count()).select_from(m.Transaction)) == 37
        assert session.scalar(select(func.count()).select_from(m.Customer)) == 1
