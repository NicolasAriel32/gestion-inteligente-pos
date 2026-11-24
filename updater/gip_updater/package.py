"""Paquetes .gipupdate e índice de versiones firmados con Ed25519.

Un paquete es un ZIP con exactamente tres miembros, sin nombres repetidos:
  manifest.json  datos de la versión (producto, versión, hash y tamaño del instalador, key_id)
  manifest.sig   firma Ed25519 (base64) de los bytes exactos de manifest.json
  installer.exe  instalador Inno Setup de esa versión

Rotación de claves: el actualizador confía en un ANILLO de claves públicas
(`public_keys` en trust.json). Cada manifiesto declara con qué clave se firmó (`key_id`
= primeros 16 hex del SHA-256 de la clave pública) y solo se acepta si esa clave está en
el anillo. Ver updater/README.md, "Claves de firma".
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .storage import file_sha256

PRODUCT = 'gestion-inteligente-pos'
FORMAT = 1
MEMBERS = ['installer.exe', 'manifest.json', 'manifest.sig']
MAX_INSTALLER = 400 * 1024 * 1024
MAX_MANIFEST = 8192
VERSION = re.compile(r'^(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})$')
KEY_ID = re.compile(r'^[0-9a-f]{16}$')


class PackageError(Exception):
    """Mensaje apto para mostrar al usuario; nunca incluye secretos."""


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION.match(value or '') if isinstance(value, str) else None
    if not match:
        raise PackageError(f'Versión inválida: {value!r}')
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


# --- claves --------------------------------------------------------------------------

def raw_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(key: Ed25519PublicKey) -> str:
    return hashlib.sha256(raw_public(key)).hexdigest()[:16]


def public_key(encoded: str) -> Ed25519PublicKey:
    try:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded, validate=True))
    except (ValueError, TypeError) as exc:
        raise PackageError('Una clave pública del actualizador es inválida') from exc


@dataclass(frozen=True)
class Keyring:
    keys: dict[str, Ed25519PublicKey]

    @classmethod
    def from_trust(cls, trust: dict) -> Keyring:
        encoded = trust.get('public_keys')
        if encoded is None and trust.get('public_key'):
            encoded = [trust['public_key']]  # trust.json de la primera iteración
        if not isinstance(encoded, list) or not encoded or not all(isinstance(item, str) for item in encoded):
            raise PackageError('El actualizador no tiene claves públicas configuradas')
        keys = {key_id(key): key for key in map(public_key, encoded)}
        return cls(keys)

    @classmethod
    def of(cls, *keys: Ed25519PublicKey) -> Keyring:
        return cls({key_id(key): key for key in keys})

    def verify(self, data: bytes, signature: bytes, declared: object) -> None:
        key = self.keys.get(declared) if isinstance(declared, str) and KEY_ID.match(declared) else None
        if key is None:
            raise PackageError('Firmado con una clave que este actualizador no reconoce')
        try:
            key.verify(base64.b64decode(signature.strip(), validate=True), data)
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise PackageError('Firma inválida: el archivo no fue publicado por el técnico o fue modificado') from exc


def sign(key: Ed25519PrivateKey, data: bytes) -> bytes:
    return base64.b64encode(key.sign(data))


def declared_key(data: bytes) -> object:
    """key_id declarado, leído SOLO para elegir la clave; el resto se valida tras la firma."""
    try:
        raw = json.loads(data)
        return raw.get('key_id') if isinstance(raw, dict) else None
    except ValueError:
        return None


# --- manifiesto ------------------------------------------------------------------------

@dataclass(frozen=True)
class Manifest:
    version: str
    installer_sha256: str
    installer_size: int
    created_at_utc: str
    notes: str
    key_id: str


def parse_manifest(data: bytes) -> Manifest:
    try:
        raw = json.loads(data)
        if not isinstance(raw, dict) or raw.get('format') != FORMAT or raw.get('product') != PRODUCT:
            raise ValueError('producto o formato')
        digest, size = raw['installer_sha256'], raw['installer_size']
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('hash')
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_INSTALLER:
            raise ValueError('tamaño')
        datetime.fromisoformat(raw['created_at_utc'])
        notes = raw.get('notes', '')
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError('notas')
        if not isinstance(raw.get('key_id'), str) or not KEY_ID.match(raw['key_id']):
            raise ValueError('clave')
        parse_version(raw['version'])
        return Manifest(raw['version'], digest, size, raw['created_at_utc'], notes, raw['key_id'])
    except (ValueError, KeyError, TypeError, PackageError) as exc:
        raise PackageError('El paquete no corresponde a Gestión Inteligente POS o está dañado') from exc


def build_manifest(installer: Path, version: str, signer: Ed25519PublicKey, notes: str = '') -> bytes:
    parse_version(version)
    return json.dumps({
        'format': FORMAT, 'product': PRODUCT, 'version': version,
        'installer_sha256': file_sha256(installer), 'installer_size': installer.stat().st_size,
        'created_at_utc': datetime.now().astimezone().isoformat(), 'notes': notes, 'key_id': key_id(signer),
    }, ensure_ascii=False, indent=2).encode('utf-8')


def create_package(installer: Path, version: str, key: Ed25519PrivateKey, output: Path, notes: str = '') -> Path:
    manifest = build_manifest(installer, version, key.public_key(), notes)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', manifest)
        archive.writestr('manifest.sig', sign(key, manifest))
        archive.write(installer, 'installer.exe')
    return output


def open_package(path: Path, keyring: Keyring, destination: Path) -> Manifest:
    """Verifica estructura, firma y hash; deja el instalador en destination/installer.exe."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise PackageError('El paquete tiene archivos repetidos')
            if sorted(names) != MEMBERS:
                raise PackageError('El paquete tiene archivos inesperados')
            by_name = {info.filename: info for info in infos}
            if by_name['manifest.json'].file_size > MAX_MANIFEST or by_name['manifest.sig'].file_size > 512:
                raise PackageError('El paquete está dañado')
            manifest_bytes = archive.read('manifest.json')
            keyring.verify(manifest_bytes, archive.read('manifest.sig'), declared_key(manifest_bytes))
            manifest = parse_manifest(manifest_bytes)
            info = by_name['installer.exe']
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


# --- índice de versiones (paso 1) --------------------------------------------------------

@dataclass(frozen=True)
class IndexEntry:
    version: str
    package_url: str
    package_sha256: str
    notes: str


def build_index(manifest: Manifest, package_url: str, package_sha256: str) -> bytes:
    if not package_url.startswith('https://'):
        raise PackageError('La URL del paquete debe ser https')
    return json.dumps({
        'format': FORMAT, 'product': PRODUCT, 'version': manifest.version, 'key_id': manifest.key_id,
        'package_url': package_url, 'package_sha256': package_sha256, 'notes': manifest.notes,
    }, ensure_ascii=False, indent=2).encode('utf-8')


def parse_index(data: bytes, signature: bytes, keyring: Keyring) -> IndexEntry:
    if len(data) > MAX_MANIFEST:
        raise PackageError('Índice de versiones demasiado grande')
    keyring.verify(data, signature, declared_key(data))
    try:
        raw = json.loads(data)
        if raw.get('format') != FORMAT or raw.get('product') != PRODUCT:
            raise ValueError
        parse_version(raw['version'])
        if not str(raw['package_url']).startswith('https://') or not re.fullmatch(r'[0-9a-f]{64}', raw['package_sha256']):
            raise ValueError
        return IndexEntry(raw['version'], raw['package_url'], raw['package_sha256'], str(raw.get('notes', ''))[:2000])
    except (ValueError, KeyError, TypeError, AttributeError, PackageError) as exc:
        raise PackageError('El índice de versiones está dañado') from exc
