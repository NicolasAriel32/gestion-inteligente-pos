"""Pruebas del actualizador sin Windows: el sistema operativo se simula con FakeSystem."""
import base64
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gip_updater import package
from gip_updater.auth import AuthError, Limiter, check_technician, hash_technician
from gip_updater.engine import Paths, UpdateError, Updater

TECH = 'clave-de-tecnico-larga'
OWNER_PW = 'Owner-password-1234'


def b64(key):
    return base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


def make_installer(tmp_path, version, fail=False):
    installer = tmp_path / f'setup-{version}.exe'
    installer.write_text(json.dumps({'version': version, 'fail': fail}))
    return installer


def make_package(tmp_path, key, version, **kw):
    out = tmp_path / f'{version}.gipupdate'
    return package.create_package(make_installer(tmp_path, version, **kw), version, key, out, 'notas')


# --- paquete -------------------------------------------------------------------------

def test_paquete_valido_se_abre_y_entrega_el_instalador(tmp_path, key):
    manifest = package.open_package(make_package(tmp_path, key, '0.6.0'), key.public_key(), tmp_path / 'out')
    assert manifest.version == '0.6.0'
    assert json.loads((tmp_path / 'out' / 'installer.exe').read_text())['version'] == '0.6.0'


def rewrite(path, replace):
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    members.update(replace)
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in members.items():
            z.writestr(name, data)


def test_instalador_modificado_se_rechaza(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    with zipfile.ZipFile(path) as z:
        original = z.read('installer.exe')
    rewrite(path, {'installer.exe': original.replace(b'0.6.0', b'6.6.6')})
    with pytest.raises(package.PackageError, match='hash'):
        package.open_package(path, key.public_key(), tmp_path / 'out')
    assert not (tmp_path / 'out' / 'installer.exe').exists()


def test_manifiesto_modificado_rompe_la_firma(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    with zipfile.ZipFile(path) as z:
        manifest = z.read('manifest.json')
    rewrite(path, {'manifest.json': manifest.replace(b'0.6.0', b'9.9.9')})
    with pytest.raises(package.PackageError, match='Firma'):
        package.open_package(path, key.public_key(), tmp_path / 'out')


def test_paquete_firmado_por_otra_clave_se_rechaza(tmp_path, key):
    path = make_package(tmp_path, Ed25519PrivateKey.generate(), '0.6.0')
    with pytest.raises(package.PackageError, match='Firma'):
        package.open_package(path, key.public_key(), tmp_path / 'out')


def test_archivo_extra_en_el_paquete_se_rechaza(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    rewrite(path, {'virus.dll': b'x'})
    with pytest.raises(package.PackageError, match='inesperados'):
        package.open_package(path, key.public_key(), tmp_path / 'out')


def test_indice_de_versiones_firmado(tmp_path, key):
    manifest = package.parse_manifest(package.build_manifest(make_installer(tmp_path, '0.7.0'), '0.7.0'))
    index = package.build_index(manifest, 'https://example.com/p.gipupdate', 'a' * 64)
    entry = package.parse_index(index, package.sign(key, index), key.public_key())
    assert entry.version == '0.7.0'
    forged = index.replace(b'https://example.com', b'https://evil.example')
    with pytest.raises(package.PackageError):
        package.parse_index(forged, package.sign(key, index), key.public_key())
    with pytest.raises(package.PackageError):
        package.build_index(manifest, 'http://inseguro.example/p', 'a' * 64)


# --- autorización ---------------------------------------------------------------------

def test_clave_tecnico_y_bloqueo_tras_5_fallos(tmp_path):
    now = [1000.0]
    limiter = Limiter(tmp_path / 'intentos.json', clock=lambda: now[0])
    encoded = hash_technician(TECH)
    check_technician(encoded, TECH, limiter)
    for _ in range(5):
        with pytest.raises(AuthError, match='incorrecta'):
            check_technician(encoded, 'equivocada-equivocada', limiter)
    with pytest.raises(AuthError, match='Esperá'):
        check_technician(encoded, TECH, limiter)  # bloqueado aunque sea la correcta
    now[0] += 16 * 60
    check_technician(encoded, TECH, limiter)


def test_clave_tecnico_corta_no_se_acepta():
    with pytest.raises(AuthError):
        hash_technician('corta')


# --- motor con sistema simulado ----------------------------------------------------------

class FakeProcess:
    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        self.code = 0
        return 0

    def terminate(self):
        self.code = -1

    kill = terminate


class FakeApi:
    def __init__(self, system):
        self.system = system

    def alive(self):
        return self.system.running

    def login(self, username, password):
        if password != OWNER_PW:
            raise UpdateError('rechazada')
        self.system.calls.append('login')
        return {'role': 'ADMIN', 'username': username}

    def shutdown(self):
        self.system.calls.append('shutdown')
        self.system.running = False


class FakeSystem:
    def __init__(self, paths, migrate_ok=True, start_ok=True):
        self.paths, self.migrate_ok, self.start_ok = paths, migrate_ok, start_ok
        self.running = False
        self.calls = []

    def run(self, args, stdin=None, timeout=900):
        program = Path(args[0])
        if program.name == 'installer.exe':
            self.calls.append('install')
            data = json.loads(program.read_text())
            self.paths.app_dir.mkdir(parents=True, exist_ok=True)
            self.paths.exe.write_text(data['version'])
            (self.paths.app_dir / 'nuevo.dll').write_text('nuevo')
            return (1, '') if data['fail'] else (0, '')
        if args[1] == '--version':
            return 0, self.paths.exe.read_text() + '\n'
        if args[1] == '--prepare-stdin':
            self.calls.append('prepare')
            assert stdin == OWNER_PW + '\n'
            if not self.migrate_ok:
                self.paths.database.write_bytes(b'BASE A MEDIO MIGRAR')
                return 1, 'Contraseña ADMIN incorrecta'
            self.paths.database.write_bytes(b'BASE MIGRADA')
            return 0, 'Preparación completada.'
        raise AssertionError(args)

    def start_pos(self):
        self.calls.append('start')
        process = FakeProcess()
        self.running = self.start_ok
        if not self.start_ok:
            process.code = 1
        return process

    def api(self):
        return FakeApi(self)

    def registry_version(self):
        return None

    def sleep(self, seconds):
        pass


@pytest.fixture
def setup(tmp_path, key):
    paths = Paths(tmp_path / 'data_root', tmp_path / 'Programs' / 'POS')
    paths.app_dir.mkdir(parents=True)
    paths.exe.write_text('0.5.1')
    (paths.app_dir / 'viejo.dll').write_text('viejo')
    paths.database.parent.mkdir(parents=True)
    paths.database.write_bytes(b'BASE ORIGINAL')
    paths.database.with_name('pos.db-wal').write_bytes(b'WAL ORIGINAL')
    trust = {'public_key': b64(key), 'technician_hash': hash_technician(TECH), 'index_url': 'https://x'}

    def build(**kw):
        system = FakeSystem(paths, **kw)
        steps = []
        updater = Updater(trust, paths, system, report=lambda step, msg: steps.append(step))
        return updater, system, steps
    return paths, build


def test_actualizacion_exitosa_sigue_los_7_pasos(setup, tmp_path, key):
    paths, build = setup
    updater, system, steps = build()
    system.running = True  # el POS estaba abierto
    version = updater.update(make_package(tmp_path, key, '0.6.0'), 'owner', OWNER_PW)
    assert version == '0.6.0'
    assert system.calls == ['login', 'shutdown', 'install', 'prepare', 'start', 'login', 'shutdown']
    assert [s for s in steps if s] == [3, 4, 5, 6, 6, 7, 8]
    assert paths.database.read_bytes() == b'BASE MIGRADA'
    assert json.loads(paths.state.read_text())['installed_version'] == '0.6.0'
    assert (paths.rollback / 'data' / 'pos.db').read_bytes() == b'BASE ORIGINAL'
    assert 'Éxito: versión 0.6.0' in paths.log.read_text()
    assert OWNER_PW not in paths.log.read_text()


@pytest.mark.parametrize('kwargs, fail, message', [
    ({'migrate_ok': False}, False, 'migración'),
    ({}, True, 'instalador'),
    ({'start_ok': False}, False, 'no arrancó'),
])
def test_error_restaura_programa_y_datos(setup, tmp_path, key, kwargs, fail, message):
    paths, build = setup
    updater, _, _ = build(**kwargs)
    with pytest.raises(UpdateError, match=f'{message}.*Se restauraron la versión 0.5.1'):
        updater.update(make_package(tmp_path, key, '0.6.0', fail=fail), 'owner', OWNER_PW)
    assert paths.exe.read_text() == '0.5.1'
    assert (paths.app_dir / 'viejo.dll').exists() and not (paths.app_dir / 'nuevo.dll').exists()
    assert paths.database.read_bytes() == b'BASE ORIGINAL'
    assert paths.database.with_name('pos.db-wal').read_bytes() == b'WAL ORIGINAL'
    assert not paths.state.exists()


def test_no_permite_volver_a_una_version_anterior(setup, tmp_path, key):
    _, build = setup
    updater, system, _ = build()
    for version in ('0.5.1', '0.4.9'):
        with pytest.raises(UpdateError, match='no es posterior'):
            updater.update(make_package(tmp_path, key, version), 'owner', OWNER_PW)
    assert system.calls == []


def test_no_permite_reinstalar_version_vieja_aunque_borren_el_exe(setup, tmp_path, key):
    paths, build = setup
    updater, _, _ = build()
    updater.update(make_package(tmp_path, key, '0.7.0'), 'owner', OWNER_PW)
    paths.exe.unlink()
    state = json.loads(paths.state.read_text())
    paths.state.write_text(json.dumps({**state, 'installed_version': '0.5.0'}))
    with pytest.raises(UpdateError, match='ya instalada antes'):
        updater.verify(make_package(tmp_path, key, '0.6.0'))


def test_paquete_trucho_no_toca_nada(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    with pytest.raises(UpdateError, match='Firma'):
        updater.update(make_package(tmp_path, Ed25519PrivateKey.generate(), '0.9.0'), 'owner', OWNER_PW)
    assert system.calls == [] and paths.exe.read_text() == '0.5.1' and not paths.rollback.exists()


def test_restauracion_interrumpida_frena_antes_de_instalar(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    paths.restore_journal.parent.mkdir(parents=True)
    paths.restore_journal.write_text('{}')
    with pytest.raises(UpdateError, match='restauración interrumpida'):
        updater.update(make_package(tmp_path, key, '0.6.0'), 'owner', OWNER_PW)
    assert 'install' not in system.calls
