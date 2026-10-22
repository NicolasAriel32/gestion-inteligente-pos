import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import prepare_setup
from app.infrastructure.database import get_db_path
from app.main import create_app

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "Valid-test-password-42"


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    backend = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
    )
    return get_db_path()


@pytest.fixture
def client(database):
    with TestClient(
        create_app(database), base_url="http://127.0.0.1", headers={"origin": ORIGIN}
    ) as client:
        yield client


@pytest.fixture
def setup_token(database):
    return prepare_setup(database).read_text()


def initialize(client, token, username="owner"):
    return client.post(
        "/api/auth/setup",
        json={
            "username": username,
            "password": PASSWORD,
            "setup_token": token,
        },
    )


def login(client, username="owner", password=PASSWORD):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["csrf_token"]


@pytest.fixture
def admin(client, setup_token):
    assert initialize(client, setup_token).status_code == 201
    csrf = login(client)
    return client, csrf
