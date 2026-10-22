"""Casos de uso F2. Ninguna decisión de permisos depende del navegador."""

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Protocol

from app.domain.identity import IdentityError, Passwords, User


# Puerto de persistencia: implementación transaccional en infrastructure.identity.
class Transaction(Protocol):
    def initialized(self) -> bool: ...
    def bootstrap(self) -> dict[str, Any] | None: ...
    def consume_setup(self) -> None: ...
    def add_session(
        self, previous: str, token_hash: str, user_id: int, now: int, expires: int
    ) -> None: ...
    def revoke(self, token_hash: str) -> None: ...
    def employee(self, employee_id: int) -> User | None: ...
    def disable(self, employee_id: int) -> None: ...
    def user_by_name(self, username: str) -> dict[str, Any] | None: ...
    def add_user(self, username: str, password_hash: str, role: str) -> User: ...
    def user(self, row: dict[str, Any]) -> User: ...
    def audit(self, actor: User, action: str, target: int | None = None) -> None: ...
    def session_user(self, token_hash: str, now: int) -> User: ...
    def employees(self) -> list[User]: ...


class Store(Protocol):
    def transaction(self, write: bool = False) -> AbstractContextManager[Transaction]: ...


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return digest("pos-csrf:" + token)


class IdentityService:
    session_seconds = 8 * 60 * 60

    def __init__(
        self,
        store: Store,
        passwords: Passwords,
        dummy_hash: str,
        clock: Callable[[], float] = time.time,
    ):
        self.store = store
        self.passwords = passwords
        self.dummy_hash = dummy_hash
        self.clock = clock

    def initialized(self) -> bool:
        with self.store.transaction() as tx:
            return tx.initialized()

    def setup(self, username: str, password: str, token: str) -> User:
        # Hash fuera del bloqueo de escritura, que debe ser breve.
        encoded = self.passwords.hash(password)
        with self.store.transaction(write=True) as tx:
            if tx.initialized():
                raise IdentityError(409, "La inicialización ya fue completada")
            bootstrap = tx.bootstrap()
            if (
                bootstrap is None
                or bootstrap["completed"]
                or bootstrap["expires_at"] <= int(self.clock())
                or not hmac.compare_digest(bootstrap["token_hash"] or "", digest(token))
            ):
                raise IdentityError(403, "Secreto de inicialización no válido o vencido")
            user = tx.add_user(username, encoded, "ADMIN")
            tx.consume_setup()
            tx.audit(user, "ADMIN_INITIALIZED")
            return user

    def login(self, username: str, password: str, previous: str) -> tuple[User, str]:
        with self.store.transaction() as tx:
            candidate = tx.user_by_name(username)
        valid = self.passwords.verify(
            candidate["password_hash"] if candidate else self.dummy_hash, password
        )
        if not valid or candidate is None or not candidate["is_active"]:
            raise IdentityError(401, "Usuario o contraseña incorrectos")
        token = secrets.token_urlsafe(32)
        with self.store.transaction(write=True) as tx:
            # Revalidar después del hash para respetar una desactivación concurrente.
            current = tx.user_by_name(username)
            if current is None or not current["is_active"]:
                raise IdentityError(401, "Usuario o contraseña incorrectos")
            user = tx.user(current)
            tx.add_session(
                digest(previous),
                digest(token),
                user.id,
                int(self.clock()),
                int(self.clock()) + self.session_seconds,
            )
            tx.audit(user, "LOGIN")
        return user, token

    def me(self, token: str) -> User:
        with self.store.transaction() as tx:
            return tx.session_user(digest(token), int(self.clock()))

    def logout(self, token: str) -> None:
        with self.store.transaction(write=True) as tx:
            actor = tx.session_user(digest(token), int(self.clock()))
            tx.revoke(digest(token))
            tx.audit(actor, "LOGOUT")

    def _admin(self, tx: Transaction, token: str) -> User:
        actor = tx.session_user(digest(token), int(self.clock()))
        if actor.role != "ADMIN":
            raise IdentityError(403, "Se requiere rol ADMIN")
        return actor

    def employees(self, token: str) -> list[User]:
        with self.store.transaction() as tx:
            self._admin(tx, token)
            return tx.employees()

    def create_employee(self, token: str, username: str, password: str) -> User:
        # Evitar el coste Argon2 a un usuario sin permiso.
        with self.store.transaction() as tx:
            self._admin(tx, token)
        encoded = self.passwords.hash(password)
        with self.store.transaction(write=True) as tx:
            actor = self._admin(tx, token)
            if tx.user_by_name(username):
                raise IdentityError(409, "El nombre de usuario ya existe")
            user = tx.add_user(username, encoded, "EMPLOYEE")
            tx.audit(actor, "EMPLOYEE_CREATED", user.id)
            return user

    def deactivate(self, token: str, employee_id: int) -> User:
        with self.store.transaction(write=True) as tx:
            actor = self._admin(tx, token)
            employee = tx.employee(employee_id)
            if employee is None:
                raise IdentityError(404, "Empleado inexistente")
            if employee.is_active:
                tx.disable(employee_id)
                tx.audit(actor, "EMPLOYEE_DISABLED", employee_id)
            return User(employee.id, employee.username, "EMPLOYEE", False)
