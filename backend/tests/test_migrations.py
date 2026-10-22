"""Migraciones en una base aislada: baseline, upgrade aditivo y reaplicación."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_baseline_persists_and_identity_upgrade_is_additive(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "LOCALAPPDATA": str(tmp_path)}
    command = [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade"]
    path = tmp_path / "GestionInteligentePOS" / "data" / "pos.db"
    for revision in ("0001_empty_baseline", "0001_empty_baseline", "head", "head"):
        subprocess.run(
            command + [revision], cwd=backend, env=env, check=True, capture_output=True, text=True
        )
        expected = "0002_identity" if revision == "head" else revision
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (expected,)
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            tables = {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if revision == "0001_empty_baseline":
                assert tables == {"alembic_version"}
            else:
                assert tables == {"alembic_version", "users", "sessions", "bootstrap", "audit_log"}
