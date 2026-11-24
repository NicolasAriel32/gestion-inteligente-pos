"""Escritura atómica y lectura estricta de JSON, hashes de archivos y árboles."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


class CorruptStateError(Exception):
    """Un archivo de control existe pero no se puede confiar en su contenido."""


def fsync_directory(path: Path) -> None:
    if os.name == 'nt':  # Windows no permite abrir directorios; os.replace ya es durable en NTFS
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Escribe en un temporal del mismo directorio, fsync y reemplaza: nunca queda a medias."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fsync_directory(path.parent)


def atomic_write_json(path: Path, data: dict) -> None:
    atomic_write_bytes(path, json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))


def read_json_strict(path: Path, required: dict[str, type | tuple[type, ...]]) -> dict | None:
    """None si no existe; CorruptStateError si existe y no es válido. Nunca lo ignora."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_bytes().decode('utf-8'))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise CorruptStateError(f'{path.name} está dañado') from exc
    if not isinstance(data, dict):
        raise CorruptStateError(f'{path.name} está dañado')
    for key, kind in required.items():
        if key not in data or not isinstance(data[key], kind) or isinstance(data[key], bool) and kind is not bool:
            raise CorruptStateError(f'{path.name} está dañado: campo {key}')
    return data


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def tree_manifest(root: Path) -> dict[str, str]:
    """Ruta relativa (con /) -> sha256 de cada archivo regular. Rechaza enlaces."""
    result: dict[str, str] = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise OSError(f'Enlace no admitido en {path}')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = file_sha256(path)
    return result


def fsync_tree(root: Path) -> None:
    for path in root.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
    for directory in [root, *(p for p in root.rglob('*') if p.is_dir())]:
        fsync_directory(directory)
