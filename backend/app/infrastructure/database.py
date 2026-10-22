import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase

from app.domain.reporting import ZONE


class ExactSum:
    def __init__(self) -> None:
        self.value = 0

    def step(self, value: int) -> None:
        self.value += value

    def finalize(self) -> str:
        return str(self.value)


class Base(DeclarativeBase):
    pass

def get_db_path() -> Path:
    local = os.getenv("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".local" / "share"
    return root / "GestionInteligentePOS" / "data" / "pos.db"

def build_engine(path: Path | None = None) -> Engine:
    path = path or get_db_path()
    path.parent.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o600)
        if path.parent.name == "data" and path.parent.parent.name == "GestionInteligentePOS":
            path.parent.chmod(0o700)
            path.parent.parent.chmod(0o700)
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 5})
    @event.listens_for(engine, "connect")
    def sqlite_config(connection: sqlite3.Connection, _: object) -> None:
        connection.create_function("casefold", 1, str.casefold, deterministic=True)
        connection.create_aggregate("pos_sum", 1, ExactSum)
        connection.create_function("pos_hour", 1, lambda value: datetime.fromisoformat(value).astimezone(ZONE).hour, deterministic=True)
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    return engine
