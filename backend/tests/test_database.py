from sqlalchemy import text
from app.infrastructure.database import build_engine

def test_sqlite_pragmas(tmp_path):
    engine = build_engine(tmp_path / "pos.db")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
    finally:
        engine.dispose()
