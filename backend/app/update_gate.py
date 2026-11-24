"""Bloqueo de mantenimiento del actualizador externo (ADR-019).

Mientras exista `updates/update-journal.json`, el POS no arranca ni modifica la base,
salvo el proceso que el propio actualizador lanza con el token de traspaso de esa
actualización (variable de entorno, nunca argumento) y solo en las fases que lo
requieren (migración y comprobación). El registro sobrevive a cortes de luz, así que
el bloqueo también; se levanta cuando el actualizador termina o recupera.

Falla cerrado: un registro ilegible también bloquea.
"""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path

ENV_TOKEN = 'GIP_MAINTENANCE_TOKEN'
HANDOFF_PHASES = {'migrating', 'checking'}
BLOCKED = ('Hay una actualización del POS en curso o interrumpida. '
           'Abrí "Actualizador del POS (técnico)" para terminarla o recuperarla.')


def journal_path(db_path: Path) -> Path:
    return db_path.parent.parent / 'updates' / 'update-journal.json'


def maintenance_block(db_path: Path) -> str | None:
    """Devuelve el motivo del bloqueo, o None si el POS puede operar."""
    path = journal_path(db_path)
    if not path.exists():
        return None
    try:
        journal = json.loads(path.read_text(encoding='utf-8'))
        token = journal.get('handoff_token') or ''
        phase = journal.get('phase')
    except (OSError, ValueError, AttributeError):
        return BLOCKED + ' (registro de actualización dañado)'
    supplied = os.environ.get(ENV_TOKEN, '')
    if (phase in HANDOFF_PHASES and isinstance(token, str) and len(token) >= 32
            and supplied and hmac.compare_digest(supplied.encode(), token.encode())):
        return None
    return BLOCKED
