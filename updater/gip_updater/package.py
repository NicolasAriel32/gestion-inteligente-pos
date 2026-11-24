"""Paquetes .gipupdate e índice de versiones firmados con Ed25519.

Un paquete es un ZIP con exactamente tres miembros:
  manifest.json  datos de la versión (producto, versión, hash y tamaño del instalador)
  manifest.sig   firma Ed25519 (base64) de los bytes exactos de manifest.json
  installer.exe  instalador Inno Setup de esa versión

El índice latest.json (consulta de versiones) se firma igual, en latest.json.sig.
La firma se verifica ANTES de confiar en cualquier dato; el hash del instalador se
compara después, leyendo por bloques para no cargar cientos de MiB en memoria.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

PRODUCT = 'gestion-inteligente-pos'
FORMAT = 1
MEMBERS = ['installer.exe', 'manifest.json', 'manifest.sig']
MAX_INSTALLER = 400 * 1024 * 1024
MAX_MANIFEST = 8192
VERSION = re.compile(r'^(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})$')


class PackageError(Exception):
    """Mensaje apto para mostrar al usuario; nunca incluye secretos."""


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION.match(value or '')
    if not match:
        raise PackageError(f'Versión inválida: {value!r}')
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def public_key(encoded: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(encoded, validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise PackageError('La clave pública del actualizador es inválida') from exc


def sign(key: Ed25519PrivateKey, data: bytes) -> bytes:
    return base64.b64encode(key.sign(data))


def verify_signature(key: Ed25519PublicKey, data: bytes, signature: bytes) -> None:
    try:
        key.verify(base64.b64decode(signature.strip(), validate=True), data)
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise PackageError('Firma inválida: el archivo no fue publicado por el técnico o fue modificado') from exc


@dataclass(frozen=True)
class Manifest:
    version: str
    installer_sha256: str
    installer_size: int
    created_at_utc: str
    notes: str


def parse_manifest(data: bytes) -> Manifest:
    try:
        raw = json.loads(data)
        if not isinstance(raw, dict) or raw.get('format') != FORMAT or raw.get('product') != PRODUCT:
            raise ValueError('producto o formato')
        digest = raw['installer_sha256']
        size = raw['installer_size']
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('hash')
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_INSTALLER:
            raise ValueError('tamaño')
        datetime.fromisoformat(raw['created_at_utc'])
        notes = raw.get('notes', '')
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError('notas')
        parse_version(raw['version'])
        return Manifest(raw['version'], digest, size, raw['created_at_utc'], notes)
    except (ValueError, KeyError, TypeError) as exc:
        raise PackageError('El paquete no corresponde a Gestión Inteligente POS o está dañado') from exc


def build_manifest(installer: Path, version: str, notes: str = '') -> bytes:
    parse_version(version)
    digest = hashlib.sha256()
    with installer.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return json.dumps({
        'format': FORMAT, 'product': PRODUCT, 'version': version,
        'installer_sha256': digest.hexdigest(), 'installer_size': installer.stat().st_size,
        'created_at_utc': datetime.now().astimezone().isoformat(), 'notes': notes,
    }, ensure_ascii=False, indent=2).encode('utf-8')


def create_package(installer: Path, version: str, key: Ed25519PrivateKey, output: Path, notes: str = '') -> Path:
    manifest = build_manifest(installer, version, notes)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', manifest)
        archive.writestr('manifest.sig', sign(key, manifest))
        archive.write(installer, 'installer.exe')
    return output


def open_package(path: Path, key: Ed25519PublicKey, destination: Path) -> Manifest:
    """Verifica firma, estructura y hash; deja el instalador en destination/installer.exe."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = {info.filename: info for info in archive.infolist()}
            if sorted(infos) != MEMBERS:
                raise PackageError('El paquete tiene archivos inesperados')
            if infos['manifest.json'].file_size > MAX_MANIFEST or infos['manifest.sig'].file_size > 512:
                raise PackageError('El paquete está dañado')
            manifest_bytes = archive.read('manifest.json')
            verify_signature(key, manifest_bytes, archive.read('manifest.sig'))
            manifest = parse_manifest(manifest_bytes)
            info = infos['installer.exe']
            if info.file_size != manifest.installer_size:
                raise PackageError('El tamaño del instalador no coincide con el firmado')
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / 'installer.exe'
            digest = hashlib.sha256()
            written = 0
            with archive.open(info) as source, target.open('wb') as sink:
                for block in iter(lambda: source.read(1 << 20), b''):
                    written += len(block)
                    if written > manifest.installer_size:
                        raise PackageError('El instalador supera el tamaño firmado')
                    digest.update(block)
                    sink.write(block)
            if written != manifest.installer_size or digest.hexdigest() != manifest.installer_sha256:
                target.unlink(missing_ok=True)
                raise PackageError('El instalador no coincide con el hash firmado')
            return manifest
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise PackageError('No se pudo leer el paquete; puede estar dañado') from exc


# --- Índice de versiones (paso 1: consultar versiones disponibles) -----------------

def build_index(manifest: Manifest, package_url: str, package_sha256: str) -> bytes:
    if not package_url.startswith('https://'):
        raise PackageError('La URL del paquete debe ser https')
    return json.dumps({
        'format': FORMAT, 'product': PRODUCT, 'version': manifest.version,
        'package_url': package_url, 'package_sha256': package_sha256, 'notes': manifest.notes,
    }, ensure_ascii=False, indent=2).encode('utf-8')


@dataclass(frozen=True)
class IndexEntry:
    version: str
    package_url: str
    package_sha256: str
    notes: str


def parse_index(data: bytes, signature: bytes, key: Ed25519PublicKey) -> IndexEntry:
    if len(data) > MAX_MANIFEST:
        raise PackageError('Índice de versiones demasiado grande')
    verify_signature(key, data, signature)
    try:
        raw = json.loads(data)
        if raw.get('format') != FORMAT or raw.get('product') != PRODUCT:
            raise ValueError
        parse_version(raw['version'])
        if not str(raw['package_url']).startswith('https://') or not re.fullmatch(r'[0-9a-f]{64}', raw['package_sha256']):
            raise ValueError
        return IndexEntry(raw['version'], raw['package_url'], raw['package_sha256'], str(raw.get('notes', ''))[:2000])
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise PackageError('El índice de versiones está dañado') from exc


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=False)
