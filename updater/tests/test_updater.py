"""Pruebas del actualizador sin Windows: el sistema operativo se simula con FakeSystem.

Claves Ed25519 y contraseñas: SIEMPRE descartables, generadas en cada prueba.
Un "corte de luz" se simula con Crash (BaseException): el motor no lo atrapa, igual que
un proceso matado, y el journal queda en disco con la fase en curso.
"""
import base64
import importlib.util
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gip_updater import package
from gip_updater.auth import HASHER, AuthError, Limiter, check_technician, hash_technician
from gip_updater.engine import Paths, System, UpdateError, Updater
from gip_updater.locks import LockBusy, pos_instance_lock, updater_mutex
from gip_updater.storage import file_sha256, tree_manifest

TECH = 'clave-de-tecnico-descartable'
OWNER_PW = 'Owner-password-1234'
GATE = Path(__file__).resolve().parents[2] / 'backend' / 'app' / 'update_gate.py'


class Crash(BaseException):
    """Simula corte de luz / proceso matado: no lo atrapa `except Exception`."""


def b64(key):
    return base64.b64encode(package.raw_public(key.public_key())).decode()


def gate():
    spec = importlib.util.spec_from_file_location('update_gate', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


def make_installer(tmp_path, version, fail=False):
    installer = tmp_path / f'setup-{version}-{fail}.exe'
    installer.write_text(json.dumps({'version': version, 'fail': fail}))
    return installer


def make_package(tmp_path, key, version, **kw):
    return package.create_package(make_installer(tmp_path, version, **kw), version, key, tmp_path / f'{version}.gipupdate')


def rewrite(path, replace, extra=()):
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    members.update(replace)
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in [*members.items(), *extra]:
            z.writestr(name, data)


# --- paquete y claves ------------------------------------------------------------------------

def test_paquete_valido_se_abre(tmp_path, key):
    manifest = package.open_package(make_package(tmp_path, key, '0.6.0'), package.Keyring.of(key.public_key()), tmp_path / 'o')
    assert manifest.version == '0.6.0' and manifest.key_id == package.key_id(key.public_key())


def test_instalador_modificado_se_rechaza(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    with zipfile.ZipFile(path) as z:
        original = z.read('installer.exe')
    rewrite(path, {'installer.exe': original.replace(b'0.6.0', b'6.6.6')})
    with pytest.raises(package.PackageError, match='hash'):
        package.open_package(path, package.Keyring.of(key.public_key()), tmp_path / 'o')
    assert not (tmp_path / 'o' / 'installer.exe').exists()


def test_manifiesto_modificado_rompe_la_firma(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    with zipfile.ZipFile(path) as z:
        manifest = z.read('manifest.json')
    rewrite(path, {'manifest.json': manifest.replace(b'0.6.0', b'9.9.9')})
    with pytest.raises(package.PackageError, match='Firma'):
        package.open_package(path, package.Keyring.of(key.public_key()), tmp_path / 'o')


def test_clave_desconocida_y_firma_cruzada_se_rechazan(tmp_path, key):
    other = Ed25519PrivateKey.generate()
    with pytest.raises(package.PackageError, match='no reconoce'):
        package.open_package(make_package(tmp_path, other, '0.6.0'), package.Keyring.of(key.public_key()), tmp_path / 'o')
    # Firmado por "other" pero declarando el key_id de una clave confiable
    path = make_package(tmp_path, other, '0.6.1')
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('manifest.json'))
    manifest['key_id'] = package.key_id(key.public_key())
    forged = json.dumps(manifest).encode()
    rewrite(path, {'manifest.json': forged, 'manifest.sig': package.sign(other, forged)})
    with pytest.raises(package.PackageError, match='Firma'):
        package.open_package(path, package.Keyring.of(key.public_key()), tmp_path / 'o')


def test_nombres_duplicados_en_el_zip_se_rechazan(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    with pytest.warns(UserWarning):  # zipfile avisa "Duplicate name"
        rewrite(path, {}, extra=[('installer.exe', b'MALICIOSO')])
    with pytest.raises(package.PackageError, match='repetidos'):
        package.open_package(path, package.Keyring.of(key.public_key()), tmp_path / 'o')


def test_archivo_extra_se_rechaza(tmp_path, key):
    path = make_package(tmp_path, key, '0.6.0')
    rewrite(path, {'virus.dll': b'x'})
    with pytest.raises(package.PackageError, match='inesperados'):
        package.open_package(path, package.Keyring.of(key.public_key()), tmp_path / 'o')


def test_rotacion_clave_de_respaldo_y_trust_viejo(tmp_path, key):
    backup = Ed25519PrivateKey.generate()
    ring = package.Keyring.from_trust({'public_keys': [b64(key), b64(backup)]})
    assert package.open_package(make_package(tmp_path, backup, '0.7.0'), ring, tmp_path / 'o').version == '0.7.0'
    old_format = package.Keyring.from_trust({'public_key': b64(key)})
    assert package.open_package(make_package(tmp_path, key, '0.7.1'), old_format, tmp_path / 'p').version == '0.7.1'
    with pytest.raises(package.PackageError):
        package.Keyring.from_trust({'public_keys': []})


def test_indice_firmado(tmp_path, key):
    manifest = package.parse_manifest(package.build_manifest(make_installer(tmp_path, '0.7.0'), '0.7.0', key.public_key()))
    index = package.build_index(manifest, 'https://example.com/p.gipupdate', 'a' * 64)
    ring = package.Keyring.of(key.public_key())
    assert package.parse_index(index, package.sign(key, index), ring).version == '0.7.0'
    with pytest.raises(package.PackageError):
        package.parse_index(index.replace(b'example.com', b'evil.example'), package.sign(key, index), ring)


# --- autorización ------------------------------------------------------------------------------

def test_bloqueo_tras_5_fallos_y_desbloqueo(tmp_path):
    now = [1000.0]
    limiter = Limiter(tmp_path / 'i.json', 'técnico', clock=lambda: now[0])
    encoded = hash_technician(TECH)
    for _ in range(5):
        with pytest.raises(AuthError, match='incorrecta'):
            check_technician(encoded, 'equivocada-equivocada', limiter)
    with pytest.raises(AuthError, match='Esperá'):
        check_technician(encoded, TECH, limiter)
    now[0] += 16 * 60
    check_technician(encoded, TECH, limiter)


def test_contadores_separados_tecnico_correcto_no_reinicia_al_dueno(setup):
    """Hallazgo Codex P2: antes, acertar la clave del técnico reiniciaba el contador común."""
    _paths, build = setup
    updater, _, _ = build()
    for _ in range(5):
        with pytest.raises(UpdateError, match='dueño'):
            updater.authorize(TECH, 'contraseña-incorrecta')
    with pytest.raises(UpdateError, match='Esperá'):
        updater.authorize(TECH, OWNER_PW)  # el dueño quedó bloqueado aunque ahora acierte


def test_contador_danado_falla_cerrado(tmp_path):
    limiter = Limiter(tmp_path / 'i.json', 'técnico')
    (tmp_path / 'i.json').write_text('{no es json')
    with pytest.raises(AuthError, match='Esperá'):
        limiter.check()


# --- motor con sistema simulado ------------------------------------------------------------------

def make_db(path: Path, marker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, role TEXT, is_active INTEGER)')
        db.execute("INSERT INTO users VALUES (1, 'owner', ?, 'ADMIN', 1)", (HASHER.hash(OWNER_PW),))
        db.execute('CREATE TABLE sales (id INTEGER PRIMARY KEY, total_cents INTEGER)')
        db.executemany('INSERT INTO sales(total_cents) VALUES (?)', [(i * 100,) for i in range(1, 51)])
        db.execute('CREATE TABLE marker (value TEXT)')
        db.execute('INSERT INTO marker VALUES (?)', (marker,))
        db.commit()


def marker(path: Path) -> str:
    with closing(sqlite3.connect(path)) as db:
        return db.execute('SELECT value FROM marker').fetchone()[0]


class FakeProcess:
    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        self.code = 0 if self.code is None else self.code
        return self.code

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


class FakeSystem(System):
    """Reemplaza Windows; conserva locked_file y pos_lock reales (flock en Linux)."""

    def __init__(self, paths, migrate_ok=True, start_ok=True, crash_at=None):
        super().__init__(paths)
        self.migrate_ok, self.start_ok, self.crash_at = migrate_ok, start_ok, crash_at
        self.running = False
        self.calls = []
        self.envs = []

    def run(self, args, stdin=None, timeout=900, env=None):
        program = Path(args[0])
        if program.name == 'installer.exe':
            self.calls.append('install')
            if self.crash_at == 'install':  # corte a mitad de la instalación
                self.paths.exe.write_text('A MEDIO INSTALAR')
                raise Crash
            data = json.loads(program.read_text())
            self.paths.app_dir.mkdir(parents=True, exist_ok=True)
            self.paths.exe.write_text(data['version'])
            (self.paths.app_dir / 'nuevo.dll').write_text('nuevo')
            return (1, '') if data['fail'] else (0, '')
        if args[1] == '--version':
            return 0, self.paths.exe.read_text() + '\n'
        if args[1] == '--prepare-stdin':
            self.calls.append('prepare')
            self.envs.append(env)
            assert stdin == OWNER_PW + '\n'
            with closing(sqlite3.connect(self.paths.database)) as db:
                db.execute("UPDATE marker SET value='MIGRADA'")
                db.execute('CREATE TABLE IF NOT EXISTS nueva (x)')
                db.commit()
            self.paths.database.with_name('pos.db-wal').write_bytes(b'WAL DE LA VERSION NUEVA')
            if self.crash_at == 'migrate':
                raise Crash
            return (0, 'Preparación completada.') if self.migrate_ok else (1, 'Contraseña ADMIN incorrecta')
        raise AssertionError(args)

    def start_pos(self, env):
        self.calls.append('start')
        self.envs.append(env)
        if self.crash_at == 'check':
            raise Crash
        self.running = self.start_ok
        return FakeProcess(None if self.start_ok else 1)

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
    (paths.app_dir / '_internal').mkdir()
    (paths.app_dir / '_internal' / 'lib.pyd').write_bytes(b'\x00' * 1000)
    make_db(paths.database, 'ORIGINAL')
    trust = {'public_keys': [b64(key)], 'technician_hash': hash_technician(TECH), 'index_url': 'https://x'}

    def build(**kw):
        system = FakeSystem(paths, **kw)
        steps = []
        updater = Updater(trust, paths, system, report=lambda step, msg: steps.append(step))
        return updater, system, steps
    return paths, build


def original_hashes(paths):
    return tree_manifest(paths.app_dir), file_sha256(paths.database)


def assert_restored(paths, before):
    app, db = before
    assert tree_manifest(paths.app_dir) == app
    assert file_sha256(paths.database) == db and marker(paths.database) == 'ORIGINAL'
    assert not paths.database.with_name('pos.db-wal').exists()  # WAL nuevo eliminado
    assert not paths.journal.exists()
    assert not list(paths.app_dir.parent.glob('*.restaurando')) and not list(paths.app_dir.parent.glob('*.descartado-*'))


def test_actualizacion_exitosa(setup, tmp_path, key):
    paths, build = setup
    updater, system, steps = build()
    system.running = True
    assert updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW) == '0.6.0'
    assert system.calls == ['login', 'shutdown', 'install', 'prepare', 'start', 'login', 'shutdown']
    assert [s for s in steps if s] == [3, 4, 5, 6, 6, 7, 8]
    assert marker(paths.database) == 'MIGRADA'
    assert json.loads(paths.state.read_text())['installed_version'] == '0.6.0'
    assert not paths.journal.exists() and not list(paths.updates.glob('.*.tmp'))
    # Traspaso controlado: misma clave para migrar y comprobar, 64 hex
    tokens = {env['GIP_MAINTENANCE_TOKEN'] for env in system.envs}
    assert len(tokens) == 1 and len(tokens.pop()) == 64
    snapshots = list(paths.rollback.iterdir())
    assert len(snapshots) == 1 and (snapshots[0] / 'snapshot.json').exists()
    log = paths.log.read_text(encoding='utf-8')
    assert 'Éxito' in log and OWNER_PW not in log and TECH not in log


def test_la_copia_anterior_solo_se_borra_tras_el_exito(setup, tmp_path, key):
    paths, build = setup
    updater, _, _ = build()
    updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    first = next(paths.rollback.iterdir()).name
    failing, _, _ = build(migrate_ok=False)
    with pytest.raises(UpdateError):
        failing.update(make_package(tmp_path, key, '0.7.0'), TECH, OWNER_PW)
    assert (paths.rollback / first / 'snapshot.json').exists()  # la falla no borró la copia previa
    updater.update(make_package(tmp_path, key, '0.7.1'), TECH, OWNER_PW)
    remaining = [p.name for p in paths.rollback.iterdir()]
    assert len(remaining) == 1 and first not in remaining


@pytest.mark.parametrize('kwargs, fail, message', [
    ({'migrate_ok': False}, False, 'migración'),
    ({}, True, 'instalador'),
    ({'start_ok': False}, False, 'no arrancó'),
])
def test_error_restaura_programa_y_datos(setup, tmp_path, key, kwargs, fail, message):
    paths, build = setup
    before = original_hashes(paths)
    updater, _, _ = build(**kwargs)
    with pytest.raises(UpdateError, match=f'{message}.*Se restauraron la versión 0.5.1'):
        updater.update(make_package(tmp_path, key, '0.6.0', fail=fail), TECH, OWNER_PW)
    assert_restored(paths, before)
    assert not paths.state.exists()


@pytest.mark.parametrize('crash_at, expected', [
    ('install', 'installing'), ('migrate', 'migrating'), ('check', 'checking'),
])
def test_corte_de_luz_deja_journal_bloquea_el_pos_y_se_recupera(setup, tmp_path, key, crash_at, expected):
    paths, build = setup
    before = original_hashes(paths)
    updater, _, _ = build(crash_at=crash_at)
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    journal = json.loads(paths.journal.read_text(encoding='utf-8'))
    assert journal['phase'] == expected
    # El POS no arranca (ni aun con un token viejo de otra fase)
    assert gate().maintenance_block(paths.database) is not None
    # Al reabrir, no deja actualizar: obliga a recuperar
    fresh, _, _ = build()
    assert fresh.pending()['phase'] == expected
    with pytest.raises(UpdateError, match='recuperala primero'):
        fresh.update(make_package(tmp_path, key, '0.6.1'), TECH, OWNER_PW)
    assert 'restauraron' in fresh.recover(technician=TECH)
    assert_restored(paths, before)
    assert gate().maintenance_block(paths.database) is None


def test_corte_durante_el_respaldo_no_toca_nada(setup, tmp_path, key):
    paths, build = setup
    before = original_hashes(paths)

    def crash(step, message):
        if step == 5:
            raise Crash
    updater, _, _ = build()
    updater.report = crash
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert json.loads(paths.journal.read_text())['phase'] == 'snapshotting'
    fresh, system, _ = build()
    assert 'antes de modificar' in fresh.recover(owner_password=OWNER_PW)
    assert original_hashes(paths) == before and not paths.journal.exists() and system.calls == []


def test_corte_al_confirmar_completa_la_version_nueva(setup, tmp_path, key, monkeypatch):
    paths, build = setup
    updater, _, _ = build()
    monkeypatch.setattr(updater, 'write_state', lambda version: (_ for _ in ()).throw(Crash()))
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    fresh, _, _ = build()
    assert 'ya estaba instalada' in fresh.recover(technician=TECH)
    assert paths.exe.read_text() == '0.6.0' and marker(paths.database) == 'MIGRADA'
    assert json.loads(paths.state.read_text())['installed_version'] == '0.6.0'


def test_recuperacion_idempotente_tras_corte_durante_la_restauracion(setup, tmp_path, key, monkeypatch):
    paths, build = setup
    before = original_hashes(paths)
    updater, _, _ = build(crash_at='migrate')
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    fresh, _, _ = build()
    from gip_updater import engine
    real_replace, calls = engine.os.replace, []

    def flaky(src, dst):
        # Corte en el peor momento: la carpeta actual ya se apartó y la restaurada aún no está
        if str(src).endswith('POS.restaurando') and not calls:
            calls.append(src)
            assert not paths.app_dir.exists()
            raise Crash
        return real_replace(src, dst)
    monkeypatch.setattr(engine.os, 'replace', flaky)
    with pytest.raises(Crash):
        fresh.recover(technician=TECH)
    monkeypatch.setattr(engine.os, 'replace', real_replace)
    assert json.loads(paths.journal.read_text())['phase'] == 'restoring'
    again, _, _ = build()
    again.recover(technician=TECH)
    assert_restored(paths, before)
    again2, _, _ = build()
    assert again2.recover(technician=TECH) == 'No hay actualizaciones interrumpidas.'


def test_recuperacion_con_contrasena_del_dueno_usa_la_copia_verificada(setup, tmp_path, key):
    paths, build = setup
    updater, _, _ = build(crash_at='migrate')
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    paths.database.write_bytes(b'BASE ROTA A MEDIO MIGRAR')  # la base actual no sirve para validar
    fresh, _, _ = build()
    with pytest.raises(UpdateError, match='incorrecta'):
        fresh.recover(owner_password='otra-cosa')
    assert 'restauraron' in fresh.recover(owner_password=OWNER_PW)
    assert marker(paths.database) == 'ORIGINAL'


def test_copia_danada_no_se_restaura_y_no_toca_nada(setup, tmp_path, key):
    paths, build = setup
    updater, _, _ = build(crash_at='migrate')
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    snapshot = next(paths.rollback.iterdir())
    (snapshot / 'app' / 'viejo.dll').write_text('alterado')
    current = original_hashes(paths)
    fresh, _, _ = build()
    with pytest.raises(UpdateError, match='hashes'):
        fresh.recover(technician=TECH)
    assert original_hashes(paths) == current and paths.journal.exists()


def test_instalador_cambiado_tras_verificar_no_se_ejecuta(setup, tmp_path, key):
    paths, build = setup
    before = original_hashes(paths)
    updater, system, _ = build()

    def tamper(step, message):
        if step == 5:
            (paths.updates / 'tmp' / 'verificado' / 'installer.exe').write_text('{"version": "6.6.6", "fail": false}')
    updater.report = tamper
    with pytest.raises(UpdateError, match='cambió después de verificarlo'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert 'install' not in system.calls
    assert_restored(paths, before)


def test_autorizacion_revalidada_en_el_motor(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    system.running = True
    with pytest.raises(UpdateError, match='técnico'):
        updater.update(make_package(tmp_path, key, '0.6.0'), 'clave-incorrecta-xxxxx', OWNER_PW)
    with pytest.raises(UpdateError, match='dueño'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, 'mal')
    assert system.calls == [] and not paths.journal.exists()


def test_un_solo_actualizador_a_la_vez(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    with updater_mutex(paths.data_root), pytest.raises(UpdateError, match='otro actualizador'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert system.calls == []


def test_pos_que_no_suelta_su_bloqueo_frena_sin_cambios(setup, tmp_path, key):
    paths, build = setup
    before = original_hashes(paths)
    updater, system, _ = build()
    # POS "colgado" con su instancia tomada
    with pos_instance_lock(paths.data_root), pytest.raises(UpdateError, match='sigue abierto'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert original_hashes(paths) == before and not paths.journal.exists() and 'install' not in system.calls


def test_bloqueo_de_instancia_se_mantiene_durante_el_respaldo(setup, tmp_path, key):
    paths, build = setup
    updater, _, _ = build()
    seen = []

    def probe(step, message):
        if step == 5:
            with pytest.raises(LockBusy):
                pos_instance_lock(paths.data_root).acquire()
            seen.append(True)
    updater.report = probe
    updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert seen == [True]


def test_state_danado_frena_y_escritura_atomica(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    paths.state.parent.mkdir(parents=True, exist_ok=True)
    paths.state.write_text('{"installed_version": "0.9.0"')
    with pytest.raises(UpdateError, match='state.json está dañado'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    paths.state.write_text(json.dumps({'installed_version': '0.9.0', 'highest_installed': 'x', 'updated_at': ''}))
    with pytest.raises(UpdateError, match='dañado'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert system.calls == []


def test_journal_danado_exige_revision(setup, tmp_path, key):
    paths, build = setup
    paths.journal.parent.mkdir(parents=True, exist_ok=True)
    paths.journal.write_text('basura')
    updater, _, _ = build()
    with pytest.raises(UpdateError, match='revisión manual'):
        updater.pending()
    assert gate().maintenance_block(paths.database) is not None  # el POS también falla cerrado


def test_no_permite_volver_atras(setup, tmp_path, key):
    paths, build = setup
    updater, _system, _ = build()
    for version in ('0.5.1', '0.4.9'):
        with pytest.raises(UpdateError, match='no es posterior'):
            updater.update(make_package(tmp_path, key, version), TECH, OWNER_PW)
    updater.update(make_package(tmp_path, key, '0.7.0'), TECH, OWNER_PW)
    paths.exe.unlink()
    state = json.loads(paths.state.read_text())
    paths.state.write_text(json.dumps({**state, 'installed_version': '0.5.0'}))
    with pytest.raises(UpdateError, match='ya instalada antes'):
        updater.verify(make_package(tmp_path, key, '0.6.0'))


def test_paquete_trucho_no_toca_nada(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    with pytest.raises(UpdateError, match='no reconoce'):
        updater.update(make_package(tmp_path, Ed25519PrivateKey.generate(), '0.9.0'), TECH, OWNER_PW)
    assert system.calls == [] and not paths.rollback.exists()


def test_restauracion_interrumpida_del_pos_frena(setup, tmp_path, key):
    paths, build = setup
    updater, system, _ = build()
    paths.restore_journal.parent.mkdir(parents=True)
    paths.restore_journal.write_text('{}')
    with pytest.raises(UpdateError, match='restauración interrumpida'):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    assert system.calls == []


def test_gate_del_pos_solo_deja_pasar_el_traspaso_correcto(tmp_path, monkeypatch):
    module = gate()
    database = tmp_path / 'root' / 'data' / 'pos.db'
    journal = tmp_path / 'root' / 'updates' / 'update-journal.json'
    assert module.maintenance_block(database) is None
    journal.parent.mkdir(parents=True)
    token = 'a' * 64
    for phase, allowed in [('installing', False), ('snapshot_ok', False), ('migrating', True), ('checking', True)]:
        journal.write_text(json.dumps({'phase': phase, 'handoff_token': token}))
        monkeypatch.setenv('GIP_MAINTENANCE_TOKEN', token)
        assert (module.maintenance_block(database) is None) is allowed
    monkeypatch.setenv('GIP_MAINTENANCE_TOKEN', 'b' * 64)
    assert module.maintenance_block(database) is not None
    monkeypatch.delenv('GIP_MAINTENANCE_TOKEN')
    assert module.maintenance_block(database) is not None
