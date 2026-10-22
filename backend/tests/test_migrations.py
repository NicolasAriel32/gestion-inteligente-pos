"""La revisión debe persistir al cerrar la conexión de Alembic."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_baseline_persists_and_can_be_reapplied(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "LOCALAPPDATA": str(tmp_path)}
    command = [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"]
    for _ in range(2):
        subprocess.run(command, cwd=backend, env=env, check=True, capture_output=True, text=True)
        with sqlite3.connect(tmp_path / "GestionInteligentePOS" / "data" / "pos.db") as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchall() == [
                ("0001_empty_baseline",)
            ]
            assert db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall() == [("alembic_version",)]
