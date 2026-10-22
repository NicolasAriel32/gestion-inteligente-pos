import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.application.identity import digest
from app.bootstrap import prepare_setup
from app.domain.identity import IdentityError
from app.main import create_app
from tests.conftest import ORIGIN, PASSWORD, initialize, login


def create_employee(client, csrf, username="worker"):
    return client.post(
        "/api/employees",
        headers={"x-csrf-token": csrf},
        json={"username": username, "password": PASSWORD},
    )


def test_setup_requires_local_secret(client):
    assert initialize(client, "x" * 43).status_code == 403
    assert client.get("/api/auth/setup").json() == {"initialized": False}
    assert client.get("/api/auth/me").status_code == 401


def test_setup_once_and_token_consumed(client, setup_token, database):
    response = initialize(client, setup_token)
    assert response.status_code == 201
    assert response.json()["role"] == "ADMIN"
    assert initialize(client, setup_token, "second").status_code == 409
    assert client.get("/api/auth/setup").json() == {"initialized": True}
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT token_hash,completed FROM bootstrap").fetchone() == (None, 1)
        assert db.execute("SELECT COUNT(*) FROM users").fetchone() == (1,)
    with pytest.raises(IdentityError):
        prepare_setup(database, renew=True)


def test_expired_setup_secret(client, setup_token, database):
    with sqlite3.connect(database) as db:
        db.execute("UPDATE bootstrap SET expires_at=0")
    assert initialize(client, setup_token).status_code == 403


def test_secret_renewal_revokes_old_token(client, setup_token, database):
    with pytest.raises(IdentityError):
        prepare_setup(database)
    path = prepare_setup(database, renew=True)
    renewed = path.read_text()
    assert renewed != setup_token
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    assert initialize(client, setup_token).status_code == 403
    assert initialize(client, renewed).status_code == 201


def test_setup_concurrent_one_admin(database, setup_token):
    barrier = Barrier(2)

    def attempt(name):
        with TestClient(
            create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}
        ) as client:
            barrier.wait(timeout=10)
            return initialize(client, setup_token, name).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["owner_one", "owner_two"]))
    assert sorted(results) == [201, 409]
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM users WHERE role='ADMIN'").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone() == (1,)


def test_cookie_and_session_storage(admin, database):
    client, _ = admin
    # Nueva sesión debe rotar la anterior.
    old = client.cookies.get("pos_session")
    response = client.post("/api/auth/login", json={"username": "OWNER", "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
    assert "Max-Age=28800" in cookie and "Domain=" not in cookie
    new = client.cookies.get("pos_session")
    assert old != new
    assert client.get("/api/auth/me").json()["user"]["username"] == "owner"
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT token_hash FROM sessions").fetchall() == [(digest(new),)]
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
        assert stored.startswith("$argon2id$v=19$m=65536,t=3,p=1$")
        assert PASSWORD not in stored


@pytest.mark.parametrize(
    "username,password", [("owner", "wrong-password-12"), ("unknown", PASSWORD)]
)
def test_bad_credentials(admin, username, password):
    client, _ = admin
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Usuario o contraseña incorrectos"}


def test_logout_revokes_replayed_cookie(admin):
    client, csrf = admin
    old = client.cookies.get("pos_session")
    assert (
        client.post("/api/auth/logout", json={}, headers={"x-csrf-token": csrf}).status_code == 204
    )
    assert client.cookies.get("pos_session") is None
    assert client.get("/api/auth/me", headers={"cookie": f"pos_session={old}"}).status_code == 401


def test_absolute_expiry(admin):
    client, _ = admin
    now = time.time()
    client.app.state.identity.clock = lambda: now + 28801
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/employees").status_code == 401


@pytest.mark.parametrize(
    "path,method,payload",
    [
        ("/api/employees", "post", {"username": "worker", "password": PASSWORD}),
        ("/api/employees/1", "patch", {"is_active": False}),
        ("/api/auth/logout", "post", {}),
    ],
)
def test_missing_or_forged_csrf(admin, path, method, payload):
    client, _ = admin
    for headers in ({}, {"x-csrf-token": "forged"}):
        assert getattr(client, method)(path, json=payload, headers=headers).status_code == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://127.0.0.1:9999"])
def test_untrusted_origin(client, origin):
    assert (
        client.post(
            "/api/auth/login",
            headers={"origin": origin},
            json={"username": "owner", "password": PASSWORD},
        ).status_code
        == 403
    )
    assert client.get("/api/auth/setup", headers={"origin": origin}).status_code == 403


def test_missing_origin_and_non_json(client):
    client.headers.pop("origin")
    assert client.post("/api/auth/login", json={}).status_code == 403
    assert (
        client.post(
            "/api/auth/setup", headers={"origin": ORIGIN}, content="username=owner"
        ).status_code
        == 415
    )


def test_invalid_host(client):
    assert client.get("/api/auth/setup", headers={"host": "evil.example"}).status_code == 400


def test_employees_require_admin_and_ignore_client_role(admin, database):
    client, csrf = admin
    employee = create_employee(client, csrf).json()
    assert employee["role"] == "EMPLOYEE"
    assert create_employee(client, csrf).status_code == 409
    client.post("/api/auth/logout", json={}, headers={"x-csrf-token": csrf})
    worker_csrf = login(client, "worker")
    assert client.get("/api/employees").status_code == 403
    assert create_employee(client, worker_csrf, "worker2").status_code == 403
    assert (
        client.patch(
            f"/api/employees/{employee['id']}",
            json={"is_active": False},
            headers={"x-csrf-token": worker_csrf},
        ).status_code
        == 403
    )
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone() == (2,)


def test_deactivation_revokes_all_sessions_and_blocks_login(admin, database):
    client, csrf = admin
    employee = create_employee(client, csrf).json()
    with TestClient(
        create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}
    ) as worker:
        login(worker, "worker")
        assert worker.get("/api/auth/me").status_code == 200
        response = client.patch(
            f"/api/employees/{employee['id']}",
            json={"is_active": False},
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 200 and response.json()["is_active"] is False
        assert worker.get("/api/auth/me").status_code == 401
        assert (
            worker.post(
                "/api/auth/login", json={"username": "worker", "password": PASSWORD}
            ).status_code
            == 401
        )
    assert (
        client.patch(
            "/api/employees/1", json={"is_active": False}, headers={"x-csrf-token": csrf}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/employees/999", json={"is_active": False}, headers={"x-csrf-token": csrf}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/employees/{employee['id']}",
            json={"is_active": True},
            headers={"x-csrf-token": csrf},
        ).status_code
        == 422
    )


def test_injected_role_and_validation_never_reflect_secrets(admin):
    client, csrf = admin
    response = client.post(
        "/api/employees",
        headers={"x-csrf-token": csrf},
        json={"username": "worker", "password": PASSWORD, "role": "ADMIN"},
    )
    assert response.status_code == 422 and PASSWORD not in response.text
    response = client.post("/api/auth/login", json={"username": "bad!", "password": "shortsecret"})
    assert response.status_code == 422 and "shortsecret" not in response.text
    assert "input" not in response.text


def test_audit_is_attributable_and_contains_no_secrets(admin, database, setup_token):
    client, csrf = admin
    raw = client.cookies.get("pos_session")
    employee = create_employee(client, csrf).json()
    client.patch(
        f"/api/employees/{employee['id']}",
        json={"is_active": False},
        headers={"x-csrf-token": csrf},
    )
    client.post("/api/auth/logout", json={}, headers={"x-csrf-token": csrf})
    with sqlite3.connect(database) as db:
        rows = db.execute(
            "SELECT actor_id,action,entity_id,created_at_utc FROM audit_log"
        ).fetchall()
        assert [row[1] for row in rows] == [
            "ADMIN_INITIALIZED",
            "LOGIN",
            "EMPLOYEE_CREATED",
            "EMPLOYEE_DISABLED",
            "LOGOUT",
        ]
        assert all(row[0] == 1 and row[3].endswith("+00:00") for row in rows)
        contents = repr(rows)
        assert all(secret not in contents for secret in [PASSWORD, raw, digest(raw), setup_token])


def test_restart_preserves_users_and_sessions(admin, database):
    client, _ = admin
    cookie = client.cookies.get("pos_session")
    with TestClient(create_app(database), base_url="http://127.0.0.1") as restarted:
        response = restarted.get("/api/auth/me", headers={"cookie": f"pos_session={cookie}"})
        assert response.status_code == 200 and response.json()["user"]["role"] == "ADMIN"
        assert restarted.get("/api/auth/setup").json()["initialized"] is True


def test_audit_failure_rolls_back_user_creation(admin):
    client, csrf = admin
    engine = client.app.state.identity.store.engine
    with engine.begin() as connection:
        connection.execute(
            text("""CREATE TRIGGER reject_audit BEFORE INSERT ON audit_log
            WHEN NEW.action='EMPLOYEE_CREATED' BEGIN SELECT RAISE(ABORT, 'test rollback'); END""")
        )
    with pytest.raises(IntegrityError):
        create_employee(client, csrf)
    assert client.get("/api/employees").json() == []


def test_setup_audit_failure_keeps_initialization_available(client, setup_token, database):
    engine = client.app.state.identity.store.engine
    with engine.begin() as connection:
        connection.execute(
            text("""CREATE TRIGGER fail_setup BEFORE INSERT ON audit_log
            BEGIN SELECT RAISE(ABORT, 'test setup rollback'); END""")
        )
    with pytest.raises(IntegrityError):
        initialize(client, setup_token)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone() == (0,)
        assert db.execute("SELECT completed FROM bootstrap").fetchone() == (0,)
        db.execute("DROP TRIGGER fail_setup")
    assert initialize(client, setup_token).status_code == 201


def test_db_permissions_are_private_after_migration(database):
    if os.name != "nt":
        assert database.stat().st_mode & 0o777 == 0o600
        assert database.parent.stat().st_mode & 0o777 == 0o700
        assert database.parent.parent.stat().st_mode & 0o777 == 0o700


def test_unauthenticated_employees_api(client):
    assert client.get("/api/employees").status_code == 401
    # Incluso si se calcula el CSRF para cookie vacía, no existe una sesión válida.
    response = create_employee(client, digest("pos-csrf:"))
    assert response.status_code == 401


def test_deactivation_during_login_is_rechecked(admin, database):
    from threading import Event

    client, csrf = admin
    employee = create_employee(client, csrf).json()
    verified, resume = Event(), Event()
    with TestClient(
        create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}
    ) as worker:
        passwords = worker.app.state.identity.passwords
        real_verify = passwords.verify

        def paused_verify(encoded, password):
            valid = real_verify(encoded, password)
            verified.set()
            assert resume.wait(timeout=10)
            return valid

        passwords.verify = paused_verify
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                worker.post, "/api/auth/login", json={"username": "worker", "password": PASSWORD}
            )
            try:
                assert verified.wait(timeout=10)
                assert (
                    client.patch(
                        f"/api/employees/{employee['id']}",
                        json={"is_active": False},
                        headers={"x-csrf-token": csrf},
                    ).status_code
                    == 200
                )
            finally:
                resume.set()
            assert future.result(timeout=10).status_code == 401
        assert worker.get("/api/auth/me").status_code == 401
