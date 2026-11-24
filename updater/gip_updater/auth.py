"""Doble autorización: clave del técnico (Argon2id embebido) + contraseña ADMIN del dueño.

Cada credencial tiene su PROPIO contador de fallos: acertar una no reinicia la otra.
"""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from .storage import CorruptStateError, atomic_write_json, read_json_strict

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
    """Bloqueo temporal tras fallos seguidos de UNA credencial. Archivo atómico; si está
    dañado se trata como bloqueado (falla cerrado). Es editable por el usuario de Windows:
    frena intentos casuales en la caja, no a quien controla la cuenta (auditoría H-01)."""
    path: Path
    label: str
    clock: Callable[[], float] = time.time

    def _read(self) -> dict:
        try:
            return read_json_strict(self.path, {'failures': int, 'locked_until': (int, float)}) or {'failures': 0, 'locked_until': 0}
        except CorruptStateError:
            return {'failures': 0, 'locked_until': self.clock() + LOCK_SECONDS, 'corrupt': True}

    def check(self) -> None:
        data = self._read()
        if data.get('corrupt'):
            atomic_write_json(self.path, {'failures': 0, 'locked_until': data['locked_until']})
        if data['locked_until'] > self.clock():
            minutes = int((data['locked_until'] - self.clock()) // 60) + 1
            raise AuthError(f'Demasiados intentos fallidos de {self.label}. Esperá {minutes} min.')

    def failed(self) -> None:
        failures = self._read()['failures'] + 1
        if failures >= MAX_FAILURES:
            atomic_write_json(self.path, {'failures': 0, 'locked_until': self.clock() + LOCK_SECONDS})
        else:
            atomic_write_json(self.path, {'failures': failures, 'locked_until': 0})

    def succeeded(self) -> None:
        atomic_write_json(self.path, {'failures': 0, 'locked_until': 0})


def check_technician(encoded: str, password: str, limiter: Limiter) -> None:
    limiter.check()
    if not isinstance(encoded, str) or not encoded.startswith('$argon2id$'):
        raise AuthError('Este actualizador no tiene clave de técnico configurada')
    if not _verify(encoded, password):
        limiter.failed()
        raise AuthError('Clave del técnico incorrecta')
    limiter.succeeded()


def _read_owner(database: Path) -> tuple[str, str] | None:
    if not database.is_file() or not database.stat().st_size:
        return None
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            return db.execute("SELECT username, password_hash FROM users WHERE role='ADMIN' AND is_active=1").fetchone()
    except sqlite3.Error as exc:
        if 'no such table' in str(exc):
            return None  # base creada pero sin inicializar
        raise AuthError('No se pudo leer la base del POS para validar al dueño') from exc


def owner_username(database: Path) -> str | None:
    row = _read_owner(database)
    return row[0] if row else None


def check_owner(database: Path, password: str, limiter: Limiter) -> str | None:
    """Devuelve el usuario ADMIN validado, o None si la base aún no tiene ADMIN."""
    limiter.check()
    row = _read_owner(database)
    if row is None:
        return None
    if not _verify(row[1], password):
        limiter.failed()
        raise AuthError('Contraseña del dueño (ADMIN) incorrecta')
    limiter.succeeded()
    return row[0]
