"""Identidad local: migración aditiva, sin tablas comerciales."""

from alembic import op

revision = "0002_identity"
down_revision = "0001_empty_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in (
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN','EMPLOYEE')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at TEXT NOT NULL)""",
        "CREATE UNIQUE INDEX one_admin ON users(role) WHERE role='ADMIN'",
        """CREATE TABLE bootstrap (
            id INTEGER PRIMARY KEY CHECK(id=1), token_hash TEXT,
            expires_at INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0
            CHECK(completed IN (0,1)))""",
        """CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at INTEGER NOT NULL)""",
        "CREATE INDEX sessions_user ON sessions(user_id)",
        """CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY, actor_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL, entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL REFERENCES users(id),
            event_data TEXT NOT NULL DEFAULT '{}', created_at_utc TEXT NOT NULL)""",
    ):
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("F2 no admite downgrade destructivo de identidad y auditoría")
