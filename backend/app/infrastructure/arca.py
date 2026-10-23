"""WSAA + WSFEv1: autenticación y consultas explícitas, únicamente homologación."""
import base64
import secrets
import threading
import time
from collections.abc import Callable
from typing import Protocol
from xml.etree import ElementTree as ET

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7

from app.domain.identity import IdentityError
from app.infrastructure.arca_credentials import CredentialFiles, private_key, utc
from app.infrastructure.arca_soap import SoapTransport, dummy_result, points_result, ticket_result


class SoapPort(Protocol):
    def call(self, operation: str, arguments: dict[str, str] | None = None) -> ET.Element: ...


class ArcaGateway:
    def __init__(self, files: CredentialFiles, clock: Callable[[], float] = time.time, transport: SoapPort | None = None):
        self.files, self.clock = files, clock
        # Construcción perezosa: ni contexto TLS ni llamadas remotas al arrancar.
        self.transport = transport
        self.lock = threading.Lock()

    def call(self, operation: str, arguments: dict[str, str] | None = None) -> ET.Element:
        return (self.transport or SoapTransport()).call(operation, arguments)

    def status(self) -> dict:
        return self.files.status(self.clock())

    def connection(self) -> dict:
        return dummy_result(self.call('FEDummy'))

    def ticket(self, data: dict, cert: x509.Certificate, key: rsa.RSAPrivateKey) -> dict:
        now = self.clock()
        binding = {'environment': 'homologation', 'service': 'wsfe', 'cuit': data['cuit'],
                   'fingerprint': cert.fingerprint(hashes.SHA256()).hex()}
        if self.files.cache.exists():
            cached = self.files.read(self.files.cache)
            if (all(cached.get(name) == value for name, value in binding.items())
                    and isinstance(cached.get('expires'), (int, float)) and now + 120 < cached['expires'] <= now + 86400
                    and all(isinstance(cached.get(name), str) and 0 < len(cached[name]) <= 16384 for name in ('token', 'sign'))):
                return cached
        request = ET.Element('loginTicketRequest', version='1.0')
        header = ET.SubElement(request, 'header')
        for name, value in {'uniqueId': str(secrets.randbits(32)), 'generationTime': utc(now - 300), 'expirationTime': utc(now + 300)}.items():
            ET.SubElement(header, name).text = value
        ET.SubElement(request, 'service').text = 'wsfe'
        cms = pkcs7.PKCS7SignatureBuilder().set_data(ET.tostring(request, encoding='utf-8', xml_declaration=True)).add_signer(cert, key, hashes.SHA256()).sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
        result = ticket_result(self.call('loginCms', {'in0': base64.b64encode(cms).decode('ascii')}), now)
        self.files.write(self.files.cache, {**binding, **result})
        return result

    def access(self, password: str) -> dict:
        # No cola de firmas/reintentos automáticos; el administrador decide reintentar.
        if not self.lock.acquire(blocking=False):
            raise IdentityError(409, 'Ya hay una consulta ARCA en curso')
        try:
            data, cert = self.files.load(self.clock())
            # Verificar posesión incluso con TA cacheado. No guardar contraseña en memoria persistente.
            key = private_key(data['encrypted_key'].encode('ascii'), password, cert)
            ticket = self.ticket(data, cert, key)
            points = points_result(self.call('FEParamGetPtosVenta', {'Token': ticket['token'], 'Sign': ticket['sign'], 'Cuit': data['cuit']}))
            return {'environment': 'homologation', 'authenticated': True, 'ticket_expires_at': utc(ticket['expires']), 'points': points}
        except OSError as exc:
            raise IdentityError(503, 'No se pudieron leer o guardar las credenciales fiscales en el perfil local') from exc
        finally:
            self.lock.release()
