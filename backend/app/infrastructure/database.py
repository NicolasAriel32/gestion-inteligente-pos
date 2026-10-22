import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

def get_db_path() -> Path:
    local = os.getenv("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".local" / "share"
    return root / "GestionInteligentePOS" / "data" / "pos.db"

def build_engine(path: Path | None = None):
    path = path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 5})
    @event.listens_for(engine, "connect")
    def sqlite_config(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    return engine
