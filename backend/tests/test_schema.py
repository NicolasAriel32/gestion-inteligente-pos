"""Nunca habilitar endpoints con versión incorrecta o estructura incompleta."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.schema import SchemaCompatibilityError
from app.main import create_app


def assert_startup_refused(path):
    with (
        pytest.raises(SchemaCompatibilityError, match="Esquema local incompatible"),
        TestClient(create_app(path), base_url="http://127.0.0.1"),
    ):
        pytest.fail("La aplicación no debe habilitarse")


def test_empty_database_is_not_automatically_migrated(tmp_path):
    path = tmp_path / "empty.db"
    assert_startup_refused(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


@pytest.mark.parametrize("revision", ["0001_empty_baseline", "future_revision"])
def test_old_or_newer_revision_refused_without_modifying_data(database, revision):
    with sqlite3.connect(database) as db:
        db.execute("UPDATE alembic_version SET version_num=?", (revision,))
    with sqlite3.connect(database) as db:
        before = list(db.iterdump())
    assert_startup_refused(database)
    with sqlite3.connect(database) as db:
        assert list(db.iterdump()) == before


def test_missing_table_refused_even_with_current_revision(database):
    # Únicamente una base temporal de prueba.
    with sqlite3.connect(database) as db:
        db.execute("ALTER TABLE sessions RENAME TO sessions_incomplete")
    assert_startup_refused(database)


def test_missing_column_refused_even_with_current_revision(database):
    with sqlite3.connect(database) as db:
        db.execute("ALTER TABLE audit_log RENAME COLUMN event_data TO unexpected_column")
    assert_startup_refused(database)


def test_migrated_database_starts_and_exposes_health(client):
    assert client.get("/api/health").status_code == 200
