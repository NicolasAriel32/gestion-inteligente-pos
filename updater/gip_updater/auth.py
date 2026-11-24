"""Doble autorización: clave del técnico (Argon2id embebido) + contraseña ADMIN del dueño."""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60
MIN_TECHNICIAN = 16


class AuthError(Exception):
    pass


def hash_technician(password: str) -> str:
    if len(password) < MIN_TECHNICIAN:
        raise AuthError(f'La clave del técnico debe tener al menos {MIN_TECHNICIAN} caracteres')
    return HASHER.hash(password)


def _verify(encoded: str, password: str) -> bool:
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


@dataclass
class Limiter:
    """Bloqueo temporal tras fallos seguidos. Solo frena intentos casuales en la caja:
    el archivo es editable por el usuario de Windows (ver auditoría H-01)."""
    path: Path
    clock: Callable[[], float] = time.time

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding='utf-8')

    def check(self) -> None:
        until = self._read().get('locked_until', 0)
        if isinstance(until, (int, float)) and until > self.clock():
            minutes = int((until - self.clock()) // 60) + 1
            raise AuthError(f'Demasiados intentos fallidos. Esperá {minutes} min.')

    def failed(self) -> None:
        data = self._read()
        failures = int(data.get('failures', 0)) + 1
        data['failures'] = failures
        if failures >= MAX_FAILURES:
            data = {'failures': 0, 'locked_until': self.clock() + LOCK_SECONDS}
        self._write(data)

    def succeeded(self) -> None:
        self._write({'failures': 0, 'locked_until': 0})


def check_technician(encoded: str, password: str, limiter: Limiter) -> None:
    limiter.check()
    if not encoded.startswith('$argon2id$'):
        raise AuthError('Este actualizador no tiene clave de técnico configurada')
    if not _verify(encoded, password):
        limiter.failed()
        raise AuthError('Clave del técnico incorrecta')
    limiter.succeeded()


def owner_username(database: Path) -> str | None:
    if not database.is_file() or not database.stat().st_size:
        return None
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute("SELECT username FROM users WHERE role='ADMIN' AND is_active=1").fetchone()
    return row[0] if row else None


def check_owner(database: Path, password: str, limiter: Limiter) -> str | None:
    """Devuelve el usuario ADMIN validado, o None si la base aún no fue inicializada."""
    limiter.check()
    username = owner_username(database)
    if username is None:
        return None
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        encoded = db.execute('SELECT password_hash FROM users WHERE username=?', (username,)).fetchone()[0]
    if not _verify(encoded, password):
        limiter.failed()
        raise AuthError('Contraseña del dueño (ADMIN) incorrecta')
    limiter.succeeded()
    return username
