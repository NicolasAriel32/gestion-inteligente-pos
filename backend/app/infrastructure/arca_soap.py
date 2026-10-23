"""SOAP acotado a consultas de homologación. Nunca recibe un endpoint del usuario."""
import re
import ssl
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from xml.etree import ElementTree as ET

from app.domain.identity import IdentityError

SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
WSFE = 'http://ar.gov.afip.dif.FEV1/'
WSAA = 'http://wsaa.view.sua.dvadac.desein.afip.gov'
ENDPOINTS = {
    'loginCms': ('https://wsaahomo.afip.gov.ar/ws/services/LoginCms', '', WSAA),
    'FEDummy': ('https://wswhomo.afip.gov.ar/wsfev1/service.asmx', WSFE + 'FEDummy', WSFE),
    'FEParamGetPtosVenta': ('https://wswhomo.afip.gov.ar/wsfev1/service.asmx', WSFE + 'FEParamGetPtosVenta', WSFE),
}
MAX_XML = 1024 * 1024


def protocol_error() -> IdentityError:
    return IdentityError(502, 'ARCA devolvió una respuesta no verificable. Revisá el servicio de homologación.')


def parse_xml(data: bytes) -> ET.Element:
    try:
        # Rechazar UTF-16/NUL antes de buscar DTD: evita eludir el filtro de entidades.
        text = data.decode('utf-8-sig')
        if len(data) > MAX_XML or '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError
        root = ET.fromstring(text)
        pending = [(root, 0)]
        count = 0
        while pending:
            node, depth = pending.pop()
            count += 1
            if count > 10000 or depth > 32:
                raise ValueError
            pending.extend((child, depth + 1) for child in node)
        return root
    except (ValueError, ET.ParseError, UnicodeError, RecursionError) as from_exc:
        raise protocol_error() from from_exc


def field(node: ET.Element, name: str, namespace: str = '', maximum: int = 65536) -> str:
    matches = node.findall(f'{{{namespace}}}{name}' if namespace else name)
    if len(matches) != 1 or list(matches[0]):
        raise protocol_error()
    value = matches[0].text or ''
    if not value or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise protocol_error()
    return value


def instant(value: str) -> float:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.timestamp()
    except (ValueError, OverflowError) as exc:
        raise protocol_error() from exc


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SoapTransport:
    def __init__(self):
        self.opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoRedirect())

    def call(self, operation: str, arguments: dict[str, str] | None = None) -> ET.Element:
        endpoint, action, namespace = ENDPOINTS[operation]
        envelope = ET.Element(f'{{{SOAP}}}Envelope')
        body = ET.SubElement(envelope, f'{{{SOAP}}}Body')
        method = ET.SubElement(body, f'{{{namespace}}}{operation}')
        parent = ET.SubElement(method, f'{{{namespace}}}Auth') if operation == 'FEParamGetPtosVenta' else method
        for name, value in (arguments or {}).items():
            ET.SubElement(parent, f'{{{namespace}}}{name}').text = value
        request = Request(endpoint, ET.tostring(envelope, encoding='utf-8', xml_declaration=True),
                          headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': f'"{action}"'}, method='POST')
        try:
            try:
                response = self.opener.open(request, timeout=10)
            except HTTPError as exc:
                if exc.code != 500:
                    raise
                response = exc  # SOAP Fault usa HTTP 500; no reflejar su texto.
            with response:
                deadline = time.monotonic() + 15
                chunks, size = [], 0
                while True:
                    # read1 retorna lo disponible: read(n) puede esperar n bytes
                    # indefinidamente si un servidor gotea datos sin agotar el timeout.
                    chunk = getattr(response, 'read1', response.read)(16384)
                    size += len(chunk)
                    if size > MAX_XML or time.monotonic() > deadline:
                        raise protocol_error()
                    if not chunk:
                        break
                    chunks.append(chunk)
            root = parse_xml(b''.join(chunks))
        except (URLError, OSError, TimeoutError) as exc:
            raise IdentityError(503, 'No se pudo conectar con ARCA homologación. Comprobá internet y volvé a intentar; el POS local sigue disponible.') from exc
        if root.tag != f'{{{SOAP}}}Envelope':
            raise protocol_error()
        bodies = root.findall(f'{{{SOAP}}}Body')
        if len(bodies) != 1 or len(bodies[0]) != 1:
            raise protocol_error()
        result = bodies[0][0]
        if result.tag == f'{{{SOAP}}}Fault':
            # Solo códigos conocidos, mensajes propios; faultstring podría contener secretos.
            code = result.findtext('faultcode', '').rsplit(':', 1)[-1]
            messages = {
                'coe.alreadyAuthenticated': 'WSAA ya tiene un ticket vigente. Conservá el cache local y esperá su vencimiento antes de solicitar otro.',
                'cms.cert.expired': 'Certificado vencido. Renovalo en homologación.',
                'coe.notAuthorized': 'Certificado sin autorización para wsfe. Revisá la asociación en WSASS.',
                'xml.generationTime.invalid': 'Revisá fecha, hora y zona horaria de la PC antes de reintentar.',
            }
            raise IdentityError(502, messages.get(code, 'ARCA rechazó la consulta de homologación. Revisá certificado, reloj y asociación al servicio wsfe en WSASS.'))
        if result.tag != f'{{{namespace}}}{operation}Response':
            raise protocol_error()
        if operation == 'loginCms':
            return parse_xml(field(result, 'loginCmsReturn', WSAA).encode('utf-8'))
        children = result.findall(f'{{{namespace}}}{operation}Result')
        if len(children) != 1:
            raise protocol_error()
        return children[0]


def dummy_result(node: ET.Element) -> dict:
    result = {name: field(node, xml, WSFE, 2) for name, xml in (
        ('application', 'AppServer'), ('database', 'DbServer'), ('authentication', 'AuthServer'))}
    if any(value not in {'OK', 'NO'} for value in result.values()):
        raise protocol_error()
    return {'environment': 'homologation', 'healthy': all(value == 'OK' for value in result.values()), **result}


def points_result(node: ET.Element) -> list[dict]:
    if node.findall(f'{{{WSFE}}}Errors/{{{WSFE}}}Err'):
        raise IdentityError(502, 'ARCA rechazó la consulta de puntos de venta. Revisá CUIT representado, certificado y permisos en homologación.')
    result = node.find(f'{{{WSFE}}}ResultGet')
    if result is None:
        raise protocol_error()
    points, seen = [], set()
    for item in result:
        number = field(item, 'Nro', WSFE, 5)
        if item.tag != f'{{{WSFE}}}PtoVenta' or not re.fullmatch(r'[0-9]{1,5}', number) or not 1 <= int(number) <= 99999 or int(number) in seen:
            raise protocol_error()
        seen.add(int(number))
        blocked = field(item, 'Bloqueado', WSFE, 1)
        if blocked not in {'S', 'N'}:
            raise protocol_error()
        # FchBaja puede ser vacío (punto vigente).
        date = item.findtext(f'{{{WSFE}}}FchBaja', '')
        if date and not re.fullmatch(r'[0-9]{8}', date):
            raise protocol_error()
        points.append({'number': int(number), 'emission_type': field(item, 'EmisionTipo', WSFE, 30), 'blocked': blocked == 'S', 'disabled_date': date or None})
    return points


def ticket_result(node: ET.Element, now: float) -> dict:
    if node.tag != 'loginTicketResponse':
        raise protocol_error()
    header, credentials = node.find('header'), node.find('credentials')
    if header is None or credentials is None:
        raise protocol_error()
    expires = instant(field(header, 'expirationTime', maximum=50))
    generated = instant(field(header, 'generationTime', maximum=50))
    if not generated <= now + 300 or not now + 120 < expires <= now + 86400:
        raise protocol_error()
    return {'expires': expires, 'token': field(credentials, 'token'), 'sign': field(credentials, 'sign')}
