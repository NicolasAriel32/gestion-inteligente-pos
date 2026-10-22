"""Unidad de trabajo SQLite: cada escritura autoriza dentro de BEGIN IMMEDIATE."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import OperationalError

from app.domain.identity import IdentityError, User


class IdentityTransaction:
    def __init__(self, connection: Connection):
        self.connection = connection

    def row(self, sql: str, **params: Any) -> dict[str, Any] | None:
        row = self.connection.execute(text(sql), params).mappings().first()
        return dict(row) if row is not None else None

    def execute(self, sql: str, **params: Any) -> None:
        self.connection.execute(text(sql), params)

    def initialized(self) -> bool:
        return self.row("SELECT id FROM users WHERE role='ADMIN'") is not None

    def bootstrap(self) -> dict[str, Any] | None:
        return self.row("SELECT * FROM bootstrap WHERE id=1")

    def user_by_name(self, username: str) -> dict[str, Any] | None:
        return self.row("SELECT * FROM users WHERE username=:username", username=username)

    @staticmethod
    def user(row: dict[str, Any]) -> User:
        return User(row["id"], row["username"], row["role"], bool(row["is_active"]))

    def add_user(self, username: str, password_hash: str, role: str) -> User:
        self.execute(
            """INSERT INTO users(username,password_hash,role,created_at)
            VALUES (:username,:password_hash,:role,:now)""",
            username=username,
            password_hash=password_hash,
            role=role,
            now=datetime.now(UTC).isoformat(),
        )
        row = self.user_by_name(username)
        assert row is not None
        return self.user(row)

    def audit(self, actor: User, action: str, target: int | None = None) -> None:
        self.execute(
            """INSERT INTO audit_log(actor_id,action,entity_type,entity_id,created_at_utc)
            VALUES (:actor,:action,'users',:target,:now)""",
            actor=actor.id,
            action=action,
            target=target or actor.id,
            now=datetime.now(UTC).isoformat(),
        )

        self.execute(
            """INSERT INTO audit_events(actor_id,action,entity_type,entity_id,created_at_utc)
            VALUES (:actor,:action,'users',:target,:now)""",
            actor=actor.id, action=action, target=target or actor.id,
            now=datetime.now(UTC).isoformat(),
        )

    def session_user(self, token_hash: str, now: int) -> User:
        row = self.row(
            """SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id
            WHERE s.token_hash=:token AND s.expires_at>:now AND u.is_active=1""",
            token=token_hash,
            now=now,
        )
        if row is None:
            raise IdentityError(401, "Sesión no válida o vencida")
        return self.user(row)

    def employees(self) -> list[User]:
        rows = self.connection.execute(
            text("SELECT * FROM users WHERE role='EMPLOYEE' ORDER BY username")
        ).mappings()
        return [self.user(dict(row)) for row in rows]

    def consume_setup(self) -> None:
        self.execute("UPDATE bootstrap SET completed=1, token_hash=NULL WHERE id=1")

    def prepare_setup(self, token_hash: str, expiry: int) -> None:
        self.execute(
            """INSERT INTO bootstrap(id,token_hash,expires_at,completed)
            VALUES(1,:token,:expiry,0) ON CONFLICT(id) DO UPDATE
            SET token_hash=:token, expires_at=:expiry, completed=0""",
            token=token_hash,
            expiry=expiry,
        )

    def add_session(
        self, previous: str, token_hash: str, user_id: int, now: int, expires: int
    ) -> None:
        self.execute(
            "DELETE FROM sessions WHERE token_hash=:token OR expires_at<=:now",
            token=previous,
            now=now,
        )
        self.execute(
            "INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(:t,:u,:e)",
            t=token_hash,
            u=user_id,
            e=expires,
        )

    def revoke(self, token_hash: str) -> None:
        self.execute("DELETE FROM sessions WHERE token_hash=:token", token=token_hash)

    def employee(self, employee_id: int) -> User | None:
        row = self.row("SELECT * FROM users WHERE id=:id AND role='EMPLOYEE'", id=employee_id)
        return self.user(row) if row else None

    def disable(self, employee_id: int) -> None:
        self.execute("UPDATE users SET is_active=0 WHERE id=:id", id=employee_id)
        self.execute("DELETE FROM sessions WHERE user_id=:id", id=employee_id)


class IdentityStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    @contextmanager
    def transaction(self, write: bool = False) -> Iterator[IdentityTransaction]:
        try:
            with self.engine.connect() as connection:
                if write:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    yield IdentityTransaction(connection)
                    if write:
                        connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        except OperationalError as exc:
            raise IdentityError(
                503, "Base local no disponible; comprobá migraciones y reintentá"
            ) from exc
