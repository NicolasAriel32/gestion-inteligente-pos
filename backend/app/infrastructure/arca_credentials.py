"""Custodia local independiente del respaldo comercial; sin red ni secretos en errores."""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.domain.fiscal import validate_cuit
from app.domain.identity import IdentityError
from app.infrastructure.backups import atomic_json

MAX_CREDENTIAL = 65536


def local_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CREDENTIAL:
        raise IdentityError(422, 'Archivo de credenciales inválido o mayor a 64 KiB')
    with path.open('rb') as stream:
        data = stream.read(MAX_CREDENTIAL + 1)
    if len(data) > MAX_CREDENTIAL:
        raise IdentityError(422, 'Archivo de credenciales demasiado grande')
    return data


def certificate(pem: bytes, now: float) -> x509.Certificate:
    try:
        cert = x509.load_pem_x509_certificate(pem)
        public = cert.public_key()
        if not isinstance(public, rsa.RSAPublicKey) or public.key_size < 2048:
            raise ValueError
        if not cert.not_valid_before_utc.timestamp() <= now < cert.not_valid_after_utc.timestamp():
            raise IdentityError(422, 'El certificado no está vigente. Revisá su vencimiento y el reloj de la PC.')
        return cert
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise IdentityError(422, 'Certificado PEM RSA inválido (mínimo 2048 bits)') from exc


def private_key(pem: bytes, password: str, cert: x509.Certificate) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(pem, password.encode('utf-8') if password else None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.public_key().public_numbers() != cert.public_key().public_numbers():
            raise ValueError
        return key
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise IdentityError(422, 'No se pudo abrir la clave privada o no corresponde al certificado. Revisá la contraseña local.') from exc


class CredentialFiles:
    def __init__(self, root: Path):
        self.directory = root / 'config' / 'fiscal'
        self.configuration = self.directory / 'homologation.json'
        self.cache = self.directory / 'wsaa-ticket.json'

    def checked(self, path: Path) -> None:
        # No seguir enlaces/reparse points en la custodia fiscal.
        for entry in (self.directory.parent, self.directory, path):
            if entry.is_symlink() or (entry.exists() and getattr(entry.stat(), 'st_file_attributes', 0) & 0x400):
                raise IdentityError(422, 'La configuración fiscal no admite enlaces ni redirecciones locales')
        if os.name != 'nt' and path.exists() and path.stat().st_mode & 0o077:
            raise IdentityError(422, 'La configuración fiscal requiere permisos privados del usuario')

    def write(self, path: Path, data: dict) -> None:
        self.checked(path)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != 'nt':
            self.directory.chmod(0o700)
        # Windows hereda la ACL del perfil local del usuario. La clave siempre se cifra.
        atomic_json(path, data)

    def read(self, path: Path) -> dict:
        self.checked(path)
        try:
            data = json.loads(local_bytes(path))
            if not isinstance(data, dict):
                raise TypeError
            return data
        except (ValueError, TypeError, UnicodeError) as exc:
            raise IdentityError(422, 'Configuración fiscal local inválida. Volvé a configurarla con ADMIN.') from exc

    def configure(self, cuit: str, cert_pem: bytes, key_pem: bytes, source_password: str, storage_password: str, now: float) -> dict:
        cuit = validate_cuit(cuit)
        if not 12 <= len(storage_password) <= 128:
            raise IdentityError(422, 'La contraseña local de la clave debe tener entre 12 y 128 caracteres')
        if len(cert_pem) > MAX_CREDENTIAL or len(key_pem) > MAX_CREDENTIAL:
            raise IdentityError(422, 'Credenciales demasiado grandes')
        cert = certificate(cert_pem, now)
        key = private_key(key_pem, source_password, cert)
        # Reencriptar incluso si la fuente no estaba cifrada; nunca guardar texto plano.
        encrypted = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.BestAvailableEncryption(storage_password.encode('utf-8')))
        self.write(self.configuration, {'version': 1, 'environment': 'homologation', 'cuit': cuit,
                                       'certificate': cert.public_bytes(serialization.Encoding.PEM).decode('ascii'),
                                       'encrypted_key': encrypted.decode('ascii')})
        # El cache se liga al fingerprint/CUIT. No borrarlo: reconfigurar la misma identidad
        # conserva un TA aún vigente y evita coe.alreadyAuthenticated tras reiniciar.
        return self.metadata(now)

    def load(self, now: float) -> tuple[dict, x509.Certificate]:
        data = self.read(self.configuration)
        try:
            if data['version'] != 1 or data['environment'] != 'homologation':
                raise ValueError
            validate_cuit(data['cuit'])
            cert = certificate(data['certificate'].encode('ascii'), now)
            if not data['encrypted_key'].startswith('-----BEGIN ENCRYPTED PRIVATE KEY-----'):
                raise ValueError
            return data, cert
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise IdentityError(422, 'Configuración fiscal local inválida. Volvé a configurarla con ADMIN.') from exc

    def metadata(self, now: float) -> dict:
        data, cert = self.load(now)
        return {'cuit': data['cuit'], 'certificate_fingerprint': cert.fingerprint(hashes.SHA256()).hex(),
                'certificate_expires_at': cert.not_valid_after_utc.isoformat(), 'key_encrypted': True}

    def status(self, now: float) -> dict:
        base = {'environment': 'homologation', 'emission_enabled': False, 'production_enabled': False,
                'configured': False, 'configuration_error': None, 'cuit': None,
                'certificate_fingerprint': None, 'certificate_expires_at': None, 'key_encrypted': False}
        try:
            self.checked(self.configuration)
            if not self.configuration.exists():
                return base
            return {**base, **self.metadata(now), 'configured': True}
        except (IdentityError, OSError):
            return {**base, 'configuration_error': 'La configuración fiscal requiere revisión local por ADMIN; el POS sigue disponible.'}


def utc(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat()
