"""Credenciales efímeras y SOAP sintético: no equivalen a homologación autenticada."""
import base64
import io
import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.domain.fiscal import validate_cuit
from app.domain.identity import IdentityError
from app.infrastructure.arca import ArcaGateway
from app.infrastructure.arca_credentials import CredentialFiles, certificate, private_key, utc
from app.infrastructure.arca_soap import (
    ENDPOINTS,
    MAX_XML,
    SOAP,
    WSAA,
    WSFE,
    NoRedirect,
    SoapTransport,
    dummy_result,
    parse_xml,
    points_result,
    ticket_result,
)
from tests.conftest import PASSWORD, initialize, login

KEY_PASSWORD = 'Local-test-only-secret-42'
CUIT = '20123456786'


@pytest.fixture
def material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic homologation test')])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return (cert.public_bytes(serialization.Encoding.PEM), key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def configured(root, material):
    files = CredentialFiles(root)
    files.configure(CUIT, *material, '', KEY_PASSWORD, time.time())
    return files


def points():
    return parse_xml(f'<FEParamGetPtosVentaResult xmlns="{WSFE}"><ResultGet><PtoVenta><Nro>1</Nro><EmisionTipo>CAE</EmisionTipo><Bloqueado>N</Bloqueado><FchBaja/></PtoVenta></ResultGet></FEParamGetPtosVentaResult>'.encode())


def ticket(now):
    return parse_xml(f'<loginTicketResponse><header><generationTime>{utc(now - 5)}</generationTime><expirationTime>{utc(now + 43200)}</expirationTime></header><credentials><token>synthetic-token</token><sign>synthetic-sign</sign></credentials></loginTicketResponse>'.encode())


def test_cuit_checksum():
    assert validate_cuit(CUIT) == CUIT
    for value in ('20123456789', '00000000000', '20-12345678-6', '２０１２３４５６７８６', '123'):
        with pytest.raises(IdentityError):
            validate_cuit(value)


def test_encrypted_atomic_credentials_and_safe_metadata(tmp_path, material):
    files = configured(tmp_path, material)
    raw = files.configuration.read_text()
    assert KEY_PASSWORD not in raw and 'BEGIN PRIVATE KEY' not in raw
    assert 'BEGIN ENCRYPTED PRIVATE KEY' in raw
    public = files.status(time.time())
    assert public['configured'] and public['key_encrypted']
    assert not public['production_enabled'] and not public['emission_enabled']
    assert 'encrypted_key' not in public and 'certificate' not in public
    if os.name != 'nt':
        assert files.configuration.stat().st_mode & 0o777 == 0o600
        assert files.directory.stat().st_mode & 0o777 == 0o700
    data, cert = files.load(time.time())
    with pytest.raises(IdentityError, match='clave privada'):
        private_key(data['encrypted_key'].encode(), 'wrong password', cert)
    assert private_key(data['encrypted_key'].encode(), KEY_PASSWORD, cert)
    original = raw
    with pytest.raises(IdentityError):
        files.configure(CUIT, material[0], b'bad-key', '', KEY_PASSWORD, time.time())
    assert files.configuration.read_text() == original
    with pytest.raises(IdentityError, match='vigente'):
        certificate(material[0], time.time() + 2 * 86400)


def test_reject_mismatched_key(tmp_path, material):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    with pytest.raises(IdentityError, match='no corresponde'):
        configured(tmp_path, (material[0], pem))
    assert not CredentialFiles(tmp_path).configuration.exists()


def test_invalid_or_redirected_configuration_does_not_block_local_status(tmp_path):
    files = CredentialFiles(tmp_path)
    assert not files.status(time.time())['configured']
    files.write(files.configuration, {'unexpected': 'no secrets reflected'})
    assert files.status(time.time())['configuration_error']
    if os.name != 'nt':
        files.configuration.chmod(0o644)
        with pytest.raises(IdentityError, match='privados'):
            files.read(files.configuration)
        files.configuration.unlink()
        outside = tmp_path / 'outside'
        outside.write_text('private')
        files.configuration.symlink_to(outside)
        assert files.status(time.time())['configuration_error']
        with pytest.raises(IdentityError, match='enlaces'):
            files.write(files.configuration, {})
        assert outside.read_text() == 'private'


@pytest.mark.parametrize('payload', [b'<!DOCTYPE a [<!ENTITY x "secret">]><a>&x;</a>', b'\xff', b'<a>', b'<a/>\x00', ('<a>' * 34 + '</a>' * 34).encode(), b'a' * (MAX_XML + 1), '<a/>'.encode('utf-16')])
def test_xml_rejects_malformed_oversized_entities_and_depth(payload):
    with pytest.raises(IdentityError, match='no verificable'):
        parse_xml(payload)


def test_contracts_and_expiration():
    assert points_result(points()) == [{'number': 1, 'emission_type': 'CAE', 'blocked': False, 'disabled_date': None}]
    now = time.time()
    assert ticket_result(ticket(now), now)['token'] == 'synthetic-token'
    with pytest.raises(IdentityError):
        ticket_result(ticket(now), now + 43200)
    with pytest.raises(IdentityError):
        points_result(parse_xml(f'<Result xmlns="{WSFE}"><Errors><Err><Code>1</Code><Msg>secret</Msg></Err></Errors></Result>'.encode()))
    with pytest.raises(IdentityError):
        dummy_result(parse_xml(b'<FEDummyResult><AppServer>OK</AppServer></FEDummyResult>'))


def test_transport_fixed_endpoints_escaped_soap_faults_and_network_errors():
    transport = SoapTransport()
    payload = f'<s:Envelope xmlns:s="{SOAP}"><s:Body><loginCmsResponse xmlns="{WSAA}"><loginCmsReturn>&lt;loginTicketResponse/&gt;</loginCmsReturn></loginCmsResponse></s:Body></s:Envelope>'.encode()
    transport.opener = Mock()
    transport.opener.open.return_value = io.BytesIO(payload)
    assert transport.call('loginCms', {'in0': 'cms+<>&'}).tag == 'loginTicketResponse'
    request = transport.opener.open.call_args.args[0]
    assert request.full_url == ENDPOINTS['loginCms'][0]
    assert parse_xml(request.data).find(f'.//{{{WSAA}}}in0').text == 'cms+<>&'
    assert request.get_header('Soapaction') == '""'
    assert NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test') is None
    fault = f'<s:Envelope xmlns:s="{SOAP}"><s:Body><s:Fault><faultcode>ns:coe.notAuthorized</faultcode><faultstring>PRIVATE SECRET</faultstring></s:Fault></s:Body></s:Envelope>'.encode()
    transport.opener.open.side_effect = HTTPError(request.full_url, 500, 'error', {}, io.BytesIO(fault))
    with pytest.raises(IdentityError, match='sin autorización') as error:
        transport.call('FEDummy')
    assert 'PRIVATE SECRET' not in str(error.value)
    transport.opener.open.side_effect = URLError('private TLS details')
    with pytest.raises(IdentityError, match='POS local sigue') as error:
        transport.call('FEDummy')
    assert 'TLS details' not in str(error.value)
    transport.opener.open.side_effect = None
    transport.opener.open.return_value = io.BytesIO(b'a' * (MAX_XML + 1))
    with pytest.raises(IdentityError):
        transport.call('FEDummy')


def test_signed_cms_and_durable_bound_ticket(tmp_path, material):
    files = configured(tmp_path, material)
    now = time.time()
    transport = Mock()
    transport.call.side_effect = lambda operation, arguments: ticket(now) if operation == 'loginCms' else points()
    gateway = ArcaGateway(files, lambda: now, transport)
    result = gateway.access(KEY_PASSWORD)
    assert result['authenticated'] and result['points'][0]['number'] == 1
    assert 'token' not in json.dumps(result) and 'sign' not in json.dumps(result)
    cms = base64.b64decode(transport.call.call_args_list[0].args[1]['in0'])
    # Verificar la firma, no solo inspeccionar los bytes del constructor.
    verified = subprocess.run(['openssl', 'cms', '-verify', '-noverify', '-inform', 'DER'], input=cms, capture_output=True, check=True)
    request = parse_xml(verified.stdout)
    assert request.findtext('service') == 'wsfe'
    assert request.find('header/source') is None  # CUIT representado puede diferir del firmante.
    gateway = ArcaGateway(files, lambda: now, transport)
    gateway.access(KEY_PASSWORD)
    assert [call.args[0] for call in transport.call.call_args_list].count('loginCms') == 1
    # Misma identidad reconfigurada conserva TA; otra CUIT no lo reutiliza.
    configured(tmp_path, material)
    gateway.access(KEY_PASSWORD)
    assert [call.args[0] for call in transport.call.call_args_list].count('loginCms') == 1
    files.configure('30712345671', *material, '', KEY_PASSWORD, now)
    gateway.access(KEY_PASSWORD)
    assert [call.args[0] for call in transport.call.call_args_list].count('loginCms') == 2
    gateway.lock.acquire()
    try:
        with pytest.raises(IdentityError, match='en curso'):
            gateway.access(KEY_PASSWORD)
    finally:
        gateway.lock.release()


def test_api_auth_csrf_safe_secrets_offline_start_and_restore_boundary(client, setup_token, material, monkeypatch):
    assert client.app.state.fiscal.gateway.transport is None  # No red al arrancar.
    assert client.get('/api/fiscal/status').status_code == 401
    initialize(client, setup_token)
    csrf = login(client)
    headers = {'X-CSRF-Token': csrf}
    status = client.get('/api/fiscal/status').json()
    assert status['configured'] is False and status['emission_enabled'] is False
    assert client.post('/api/fiscal/connection', json={}).status_code == 403
    assert client.post('/api/fiscal/access', json={'private_key_password': 'PRIVATE'}, headers=headers).status_code == 422
    files = configured(client.app.state.files.root, material)
    gateway = client.app.state.fiscal.gateway
    transport = Mock()
    transport.call.side_effect = lambda operation, arguments: ticket(time.time()) if operation == 'loginCms' else points()
    gateway.transport = transport
    wrong = client.post('/api/fiscal/access', json={'private_key_password': 'wrong-password-42'}, headers=headers)
    assert wrong.status_code == 422 and 'wrong-password' not in wrong.text
    assert not transport.call.called
    response = client.post('/api/fiscal/access', json={'private_key_password': KEY_PASSWORD}, headers=headers)
    assert response.status_code == 200
    assert 'synthetic-token' not in response.text and KEY_PASSWORD not in response.text
    backup = client.post('/api/backups', json={}, headers=headers).json()
    import zipfile
    with zipfile.ZipFile(client.app.state.files.path(backup['id'])) as archive:
        assert not any('fiscal' in name or 'ticket' in name for name in archive.namelist())
    saved_config = files.configuration.read_bytes()
    restored = client.post('/api/backups/restore', json={'backup_id': backup['id'], 'password': PASSWORD, 'confirmation': 'RESTAURAR'}, headers=headers)
    assert restored.status_code == 200
    assert files.configuration.read_bytes() == saved_config
    assert client.get('/api/fiscal/status').status_code == 401
    csrf = login(client)
    client.post('/api/employees', json={'username': 'worker', 'password': PASSWORD}, headers={'X-CSRF-Token': csrf})
    login(client, 'worker')
    assert client.get('/api/fiscal/status').status_code == 403


def test_configure_cli_offline_authenticated_audited(admin, material, tmp_path, monkeypatch):
    from app.runtime import configure_arca
    client, _ = admin
    cert, key = tmp_path / 'certificate.pem', tmp_path / 'key.pem'
    cert.write_bytes(material[0]); key.write_bytes(material[1])
    values = iter(['owner', 'CONFIGURAR ARCA', CUIT, str(cert), str(key)])
    secrets = iter([PASSWORD, '', KEY_PASSWORD, KEY_PASSWORD])
    monkeypatch.setattr('builtins.input', lambda _: next(values))
    monkeypatch.setattr('getpass.getpass', lambda _: next(secrets))
    configure_arca(client.app.state.files.database)
    assert client.get('/api/fiscal/status').json()['configured']
    from sqlalchemy import text
    with client.app.state.maintenance.store.engine.connect() as connection:
        events = connection.execute(text("SELECT action,event_data FROM audit_events WHERE entity_type='fiscal' ORDER BY id")).fetchall()
    assert [row[0] for row in events] == ['FISCAL_CONFIGURATION_STARTED', 'FISCAL_CONFIGURATION_SAVED']
    assert KEY_PASSWORD not in str(events)
