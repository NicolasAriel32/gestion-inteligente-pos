"""Motor del actualizador (ADR-019).

Pasos: 1 consultar · 2 descargar · 3 verificar · 4 cerrar el POS · 5 respaldo verificado ·
6 instalar y migrar · 7 comprobar. Éxito: confirmar. Error: restaurar.

Garantías:
- Un solo actualizador a la vez (mutex propio) y bloqueo de instancia del POS mientras se
  copian o restauran archivos: tenerlo PRUEBA que el POS está cerrado.
- Journal persistente y atómico (`updates/update-journal.json`). Mientras exista, el POS
  no arranca (backend/app/update_gate.py) salvo el traspaso controlado de migración
  y comprobación. Un corte de luz, reinicio o cierre forzado deja el journal: la próxima
  apertura del actualizador obliga a recuperar antes de cualquier otra cosa.
- Respaldo en una carpeta nueva por actualización, con hashes, verificado y con
  `integrity_check` de SQLite; la copia anterior no se borra hasta confirmar la nueva versión.
- Restauración idempotente: verifica la copia antes de tocar nada, arma la carpeta en
  staging y la cambia con renombres; se puede repetir hasta completar.
- state.json atómico y estricto: si está dañado se frena, no se ignora.
- Autorización (técnico + dueño, contadores separados) revalidada dentro del motor
  inmediatamente antes de cerrar el POS; hash del instalador revalidado con el archivo
  bloqueado contra escritura justo antes de ejecutarlo.
"""
from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from . import package
from .auth import AuthError, Limiter, check_owner, check_technician
from .locks import LockBusy, NamedLock, pos_instance_lock, updater_mutex
from .package import IndexEntry, Keyring, Manifest, PackageError
from .storage import CorruptStateError, atomic_write_json, file_sha256, fsync_tree, read_json_strict, tree_manifest

APP_ID = '{F95EAEE3-B79F-4501-9C08-02EF49B75021}_is1'
EXE = 'GestionInteligentePOS.exe'
BASE = 'http://127.0.0.1:8765'
ENV_TOKEN = 'GIP_MAINTENANCE_TOKEN'
MAX_DOWNLOAD = package.MAX_INSTALLER + 1024 * 1024
INSTALLER_ARGS = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL', '/SP-']
DB_FILES = ('pos.db', 'pos.db-wal', 'pos.db-shm')
PHASES = ('snapshotting', 'snapshot_ok', 'installing', 'migrating', 'checking', 'committing', 'restoring')
STATE_FIELDS = {'installed_version': str, 'highest_installed': str, 'updated_at': str}
JOURNAL_FIELDS = {'id': str, 'phase': str, 'from_version': (str, type(None)), 'to_version': str,
                  'handoff_token': str, 'started_at': str, 'updated_at': str}

Report = Callable[[int, str], None]


class UpdateError(Exception):
    pass


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


@dataclass(frozen=True)
class Paths:
    data_root: Path
    app_dir: Path

    @classmethod
    def default(cls) -> Paths:
        local = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share')
        return cls(local / 'GestionInteligentePOS', local / 'Programs' / 'GestionInteligentePOS')

    @property
    def database(self) -> Path:
        return self.data_root / 'data' / 'pos.db'

    @property
    def exe(self) -> Path:
        return self.app_dir / EXE

    @property
    def updates(self) -> Path:
        return self.data_root / 'updates'

    @property
    def rollback(self) -> Path:
        return self.updates / 'rollback'

    @property
    def journal(self) -> Path:
        return self.updates / 'update-journal.json'

    @property
    def state(self) -> Path:
        return self.updates / 'state.json'

    @property
    def log(self) -> Path:
        return self.updates / 'actualizaciones.log'

    @property
    def restore_journal(self) -> Path:
        return self.data_root / 'config' / 'restore-pending.json'


@dataclass(frozen=True)
class Authorization:
    owner: str | None


class LocalApi:
    """Cliente mínimo de la API local del POS (loopback, sin proxy, con cookie y CSRF)."""

    def __init__(self, base: str = BASE):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                  urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = ''

    def request(self, method: str, path: str, body: dict | None = None, timeout: float = 5) -> tuple[int, dict]:
        data = json.dumps(body or {}).encode() if method != 'GET' else None
        headers = {'Origin': BASE, 'Content-Type': 'application/json'}
        if self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                raw = response.read(65536)
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            return exc.code, {}

    def alive(self) -> bool:
        try:
            return self.request('GET', '/api/health', timeout=2)[0] == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def login(self, username: str, password: str) -> dict:
        status, body = self.request('POST', '/api/auth/login', {'username': username, 'password': password}, timeout=15)
        if status != 200:
            raise UpdateError('El POS rechazó la cuenta del dueño')
        self.csrf = body['csrf_token']
        return body['user']

    def shutdown(self) -> None:
        status, _ = self.request('POST', '/api/runtime/shutdown', {})
        if status != 200:
            raise UpdateError('El POS no aceptó el cierre ordenado')


class System:
    """Acciones reales sobre Windows. Los tests la reemplazan por una falsa."""

    def __init__(self, paths: Paths):
        self.paths = paths

    def run(self, args: list[str], stdin: str | None = None, timeout: float = 900,
            env: dict[str, str] | None = None) -> tuple[int, str]:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(args, input=stdin, check=False, capture_output=True, text=True, timeout=timeout,
                                creationflags=flags, env={**os.environ, **(env or {})})
        return result.returncode, (result.stdout + result.stderr)[-2000:]

    def start_pos(self, env: dict[str, str]) -> subprocess.Popen:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        return subprocess.Popen([str(self.paths.exe), '--no-browser'], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=flags, env={**os.environ, **env})

    def api(self) -> LocalApi:
        return LocalApi()

    def pos_lock(self) -> NamedLock:
        return pos_instance_lock(self.paths.data_root)

    @contextmanager
    def locked_file(self, path: Path) -> Iterator[BinaryIO]:
        """Abre para lectura impidiendo que otro proceso lo modifique mientras está abierto."""
        if os.name != 'nt':
            with path.open('rb') as stream:
                yield stream
            return
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        generic_read, share_read, open_existing = 0x80000000, 0x1, 3
        handle = kernel.CreateFileW(str(path), generic_read, share_read, None, open_existing, 0, None)
        if handle in (None, wintypes.HANDLE(-1).value):
            raise OSError(ctypes.get_last_error(), 'No se pudo bloquear el instalador')
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
        with os.fdopen(fd, 'rb') as stream:
            yield stream

    def registry_version(self) -> str | None:
        if os.name != 'nt':
            return None
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf'Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}') as key:
                return str(winreg.QueryValueEx(key, 'DisplayVersion')[0])
        except OSError:
            return None

    def open_url(self, url: str, limit: int) -> bytes:
        if not url.startswith('https://'):
            raise UpdateError('Solo se descargan actualizaciones por https')
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise UpdateError('La descarga supera el tamaño admitido')
        return data

    def download(self, url: str, destination: Path, limit: int) -> None:
        if not url.startswith('https://'):
            raise UpdateError('Solo se descargan actualizaciones por https')
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with urllib.request.urlopen(url, timeout=60) as response, destination.open('wb') as sink:
            for block in iter(lambda: response.read(1 << 20), b''):
                written += len(block)
                if written > limit:
                    raise UpdateError('La descarga supera el tamaño admitido')
                sink.write(block)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class Updater:
    trust: dict
    paths: Paths = field(default_factory=Paths.default)
    system: System | None = None
    report: Report = lambda step, message: None

    def __post_init__(self) -> None:
        self.system = self.system or System(self.paths)
        try:
            self.keyring = Keyring.from_trust(self.trust)
        except PackageError as exc:
            raise UpdateError(str(exc)) from exc
        self.technician_limiter = Limiter(self.paths.updates / 'intentos-tecnico.json', 'la clave del técnico')
        self.owner_limiter = Limiter(self.paths.updates / 'intentos-dueno.json', 'la contraseña del dueño')
        self.mutex = updater_mutex(self.paths.data_root)

    # --- registro, estado y journal --------------------------------------------------------
    def log(self, message: str) -> None:
        self.paths.updates.mkdir(parents=True, exist_ok=True)
        with self.paths.log.open('a', encoding='utf-8') as stream:
            stream.write(f'{now()} {message}\n')
            stream.flush()
            os.fsync(stream.fileno())

    def state(self) -> dict:
        try:
            data = read_json_strict(self.paths.state, STATE_FIELDS)
        except CorruptStateError as exc:
            raise UpdateError(f'{exc}. Revisá {self.paths.state} antes de actualizar.') from exc
        if data is None:
            return {}
        for key in ('installed_version', 'highest_installed'):
            try:
                package.parse_version(data[key])
            except PackageError as exc:
                raise UpdateError(f'state.json está dañado: {key}. Revisá {self.paths.state}.') from exc
        return data

    def write_state(self, version: str) -> None:
        highest = self.state().get('highest_installed')
        if not highest or package.parse_version(version) > package.parse_version(highest):
            highest = version
        atomic_write_json(self.paths.state, {'installed_version': version, 'highest_installed': highest, 'updated_at': now()})

    def journal(self) -> dict | None:
        try:
            data = read_json_strict(self.paths.journal, JOURNAL_FIELDS)
        except CorruptStateError as exc:
            raise UpdateError(f'{exc}: la recuperación necesita revisión manual del técnico') from exc
        if data is not None and (data['phase'] not in PHASES or not data['id'].isalnum()):
            raise UpdateError('update-journal.json está dañado: la recuperación necesita revisión manual del técnico')
        return data

    def set_phase(self, journal: dict, phase: str, **changes) -> dict:
        journal = {**journal, **changes, 'phase': phase, 'updated_at': now()}
        atomic_write_json(self.paths.journal, journal)
        return journal

    def pending(self) -> dict | None:
        """Actualización interrumpida que hay que recuperar antes de cualquier otra cosa."""
        return self.journal()

    # --- versiones -------------------------------------------------------------------------
    def installed_version(self) -> str | None:
        if self.paths.exe.is_file():
            try:
                code, output = self.system.run([str(self.paths.exe), '--version'], timeout=60)
                candidate = output.strip().splitlines()[-1] if output.strip() else ''
                if code == 0 and package.VERSION.match(candidate):
                    return candidate
            except (OSError, subprocess.SubprocessError):
                pass
        version = self.system.registry_version() or self.state().get('installed_version')
        return version if version and package.VERSION.match(version) else None

    def check_compatible(self, version: str) -> None:
        new = package.parse_version(version)
        installed = self.installed_version()
        floor = self.state().get('highest_installed')
        for current, label in ((installed, 'la instalada'), (floor, 'una ya instalada antes')):
            if current and new <= package.parse_version(current):
                raise UpdateError(f'La versión {version} no es posterior a {label} ({current}). No se permite volver atrás.')

    # --- autorización (centralizada) --------------------------------------------------------
    def authorize(self, technician: str, owner_password: str) -> Authorization:
        try:
            check_technician(self.trust.get('technician_hash', ''), technician, self.technician_limiter)
            return Authorization(check_owner(self.paths.database, owner_password, self.owner_limiter))
        except AuthError as exc:
            raise UpdateError(str(exc)) from exc

    # --- pasos 1 a 3 ------------------------------------------------------------------------
    def available(self) -> IndexEntry:
        self.report(1, 'Consultando versiones disponibles…')
        url = self.trust.get('index_url', '')
        try:
            data = self.system.open_url(url, package.MAX_MANIFEST)
            signature = self.system.open_url(url + '.sig', 512)
        except (OSError, urllib.error.URLError) as exc:
            raise UpdateError('No se pudo consultar internet. Podés usar un archivo .gipupdate.') from exc
        try:
            return package.parse_index(data, signature, self.keyring)
        except PackageError as exc:
            raise UpdateError(str(exc)) from exc

    def download(self, entry: IndexEntry) -> Path:
        self.check_compatible(entry.version)
        self.report(2, f'Descargando versión {entry.version}…')
        target = self.paths.updates / 'tmp' / f'{entry.version}.gipupdate'
        try:
            self.system.download(entry.package_url, target, MAX_DOWNLOAD)
        except (OSError, urllib.error.URLError) as exc:
            target.unlink(missing_ok=True)
            raise UpdateError('Falló la descarga. Reintentá o usá un archivo .gipupdate.') from exc
        if file_sha256(target) != entry.package_sha256:
            target.unlink(missing_ok=True)
            raise UpdateError('El archivo descargado no coincide con el índice firmado')
        return target

    def verify(self, package_path: Path) -> tuple[Manifest, Path]:
        self.report(3, 'Verificando firma y compatibilidad…')
        work = self.paths.updates / 'tmp' / 'verificado'
        shutil.rmtree(work, ignore_errors=True)
        try:
            manifest = package.open_package(package_path, self.keyring, work)
        except PackageError as exc:
            shutil.rmtree(work, ignore_errors=True)
            raise UpdateError(str(exc)) from exc
        self.check_compatible(manifest.version)
        return manifest, work / 'installer.exe'

    # --- paso 4 -----------------------------------------------------------------------------
    def stop_pos(self, auth: Authorization, password: str) -> NamedLock:
        """Cierra el POS si está abierto y devuelve su bloqueo de instancia TOMADO."""
        self.report(4, 'Cerrando el POS de forma segura…')
        api = self.system.api()
        if api.alive():
            if auth.owner is None:
                raise UpdateError('El POS está abierto. Cerralo desde Herramientas y reintentá.')
            api.login(auth.owner, password)
            api.shutdown()
        lock = self.system.pos_lock()
        for _ in range(120):
            try:
                lock.acquire()
                return lock
            except LockBusy:
                self.system.sleep(0.5)
        raise UpdateError('El POS sigue abierto (su bloqueo de instancia no se liberó). No se cambió nada.')

    # --- paso 5 -----------------------------------------------------------------------------
    def snapshot(self, journal: dict) -> dict:
        """Copia verificada de programa y base. No toca copias anteriores."""
        self.report(5, 'Generando respaldo verificado de programa y datos…')
        target = self.paths.rollback / journal['id']
        shutil.rmtree(target, ignore_errors=True)
        (target / 'data').mkdir(parents=True)
        for name in DB_FILES:
            source = self.paths.database.with_name(name)
            if source.exists():
                shutil.copy2(source, target / 'data' / name)
        app_present = self.paths.app_dir.exists()
        if app_present:
            shutil.copytree(self.paths.app_dir, target / 'app', symlinks=False)
        fsync_tree(target)
        meta = {
            'id': journal['id'], 'from_version': journal['from_version'], 'created_at': now(),
            'app_present': app_present,
            'app': tree_manifest(target / 'app') if app_present else {},
            'data': tree_manifest(target / 'data'),
        }
        # La copia debe coincidir con el original (el POS está cerrado y bloqueado).
        if app_present and meta['app'] != tree_manifest(self.paths.app_dir):
            raise UpdateError('La copia del programa no coincide con el original')
        for name, digest in meta['data'].items():
            if file_sha256(self.paths.database.with_name(name)) != digest:
                raise UpdateError('La copia de la base no coincide con el original')
        self.check_database_copy(target / 'data')
        atomic_write_json(target / 'snapshot.json', meta)
        return meta

    def check_database_copy(self, folder: Path) -> None:
        """integrity_check sobre una copia descartable (abrirla aplica el WAL)."""
        if not (folder / 'pos.db').exists():
            return
        with tempfile.TemporaryDirectory(dir=self.paths.updates) as scratch:
            for item in folder.iterdir():
                shutil.copy2(item, Path(scratch) / item.name)
            with closing(sqlite3.connect(Path(scratch) / 'pos.db')) as db:
                result = db.execute('PRAGMA integrity_check').fetchone()[0]
        if result != 'ok':
            raise UpdateError('La base actual no pasa el control de integridad; no se actualiza')

    def verify_snapshot(self, snapshot_id: str) -> dict:
        folder = self.paths.rollback / snapshot_id
        try:
            meta = read_json_strict(folder / 'snapshot.json', {'id': str, 'app_present': bool, 'app': dict, 'data': dict})
        except CorruptStateError as exc:
            raise UpdateError('La copia de seguridad está dañada; no se restaura') from exc
        if meta is None or meta['id'] != snapshot_id:
            raise UpdateError('La copia de seguridad está incompleta; no se restaura')
        try:
            actual_app = tree_manifest(folder / 'app') if meta['app_present'] else {}
            actual_data = tree_manifest(folder / 'data')
        except OSError as exc:
            raise UpdateError('La copia de seguridad no se puede leer; no se restaura') from exc
        if meta['app'] != actual_app or meta['data'] != actual_data:
            raise UpdateError('La copia de seguridad no coincide con sus hashes; no se restaura')
        return meta

    # --- paso 6 -----------------------------------------------------------------------------
    def install(self, installer: Path, manifest: Manifest) -> None:
        self.report(6, 'Instalando nueva versión…')
        log = self.paths.updates / 'instalador.log'
        with self.system.locked_file(installer) as stream:
            digest, size = hashlib.sha256(), 0
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block)
                size += len(block)
            if size != manifest.installer_size or digest.hexdigest() != manifest.installer_sha256:
                raise UpdateError('El instalador cambió después de verificarlo; no se ejecuta')
            code, _ = self.system.run([str(installer), *INSTALLER_ARGS, f'/LOG={log}'])
        if code != 0:
            raise UpdateError(f'El instalador terminó con error ({code})')

    def migrate(self, password: str, token: str) -> None:
        self.report(6, 'Migrando base de datos…')
        code, output = 1, ''
        for _ in range(10):
            code, output = self.system.run([str(self.paths.exe), '--prepare-stdin'], stdin=password + '\n',
                                           env={ENV_TOKEN: token})
            if code == 0 or 'Cerrá la aplicación' not in output:
                break
            self.system.sleep(1)
        if code != 0:
            detail = output.strip().splitlines()[-1][:200] if output.strip() else 'sin detalle'
            raise UpdateError(f'La migración de la base falló: {detail}')

    # --- paso 7 -----------------------------------------------------------------------------
    def check_running(self, version: str, auth: Authorization, password: str, token: str) -> None:
        self.report(7, 'Comprobando la nueva versión…')
        if self.installed_version() != version:
            raise UpdateError('La versión instalada no es la esperada')
        process = self.system.start_pos({ENV_TOKEN: token})
        api = self.system.api()
        try:
            for _ in range(120):
                if api.alive():
                    break
                if process.poll() is not None:
                    raise UpdateError('La nueva versión no arrancó')
                self.system.sleep(0.5)
            else:
                raise UpdateError('La nueva versión no respondió a tiempo')
            if auth.owner is not None:
                if api.login(auth.owner, password).get('role') != 'ADMIN':
                    raise UpdateError('La cuenta del dueño no quedó como ADMIN')
                api.shutdown()
                process.wait(timeout=30)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=15)

    # --- restauración (idempotente) -----------------------------------------------------------
    def restore(self, snapshot_id: str) -> None:
        meta = self.verify_snapshot(snapshot_id)  # nada se toca si la copia no es confiable
        folder = self.paths.rollback / snapshot_id
        app_dir = self.paths.app_dir
        staging = app_dir.with_name(app_dir.name + '.restaurando')
        discarded = app_dir.with_name(app_dir.name + f'.descartado-{snapshot_id}')
        if meta['app_present']:
            shutil.rmtree(staging, ignore_errors=True)
            shutil.copytree(folder / 'app', staging, symlinks=False)
            fsync_tree(staging)
            if tree_manifest(staging) != meta['app']:
                raise UpdateError('La restauración del programa no se pudo verificar')
            if app_dir.exists():
                shutil.rmtree(discarded, ignore_errors=True)
                os.replace(app_dir, discarded)
            os.replace(staging, app_dir)
        elif app_dir.exists():
            shutil.rmtree(discarded, ignore_errors=True)
            os.replace(app_dir, discarded)
        shutil.rmtree(discarded, ignore_errors=True)
        data_dir = self.paths.database.parent
        data_dir.mkdir(parents=True, exist_ok=True)
        # Primero quitar WAL/SHM ajenos: un WAL nuevo sobre una base vieja la corrompe.
        for name in DB_FILES:
            if name not in meta['data']:
                (data_dir / name).unlink(missing_ok=True)
        for name in meta['data']:
            staged = data_dir / f'{name}.restaurando'
            shutil.copy2(folder / 'data' / name, staged)
            with staged.open('rb') as stream:
                os.fsync(stream.fileno())
            os.replace(staged, data_dir / name)
        restored = {name: file_sha256(data_dir / name) for name in meta['data']}
        if restored != meta['data'] or (meta['app_present'] and tree_manifest(app_dir) != meta['app']):
            raise UpdateError('La restauración no coincide con la copia; reintentá la recuperación')

    def prune(self, keep: str) -> None:
        if not self.paths.rollback.exists():
            return
        for folder in self.paths.rollback.iterdir():
            if folder.name != keep:
                shutil.rmtree(folder, ignore_errors=True)

    # --- orquestación ---------------------------------------------------------------------------
    @contextmanager
    def exclusive(self) -> Iterator[None]:
        try:
            self.mutex.acquire()
        except LockBusy as exc:
            raise UpdateError('Ya hay otro actualizador abierto') from exc
        try:
            yield
        finally:
            self.mutex.release()

    def update(self, package_path: Path, technician: str, owner_password: str) -> str:
        with self.exclusive():
            if self.pending():
                raise UpdateError('Hay una actualización interrumpida: recuperala primero')
            if self.paths.restore_journal.exists():
                raise UpdateError('Hay una restauración interrumpida del POS. Resolvela con "Recuperar restauración interrumpida".')
            self.state()  # estado dañado: frena antes de tocar nada
            manifest, installer = self.verify(package_path)
            from_version = self.installed_version()
            auth = self.authorize(technician, owner_password)  # revalidación inmediata antes de actuar
            lock = self.stop_pos(auth, owner_password)
            journal = {'id': secrets.token_hex(8), 'phase': 'snapshotting', 'from_version': from_version,
                       'to_version': manifest.version, 'handoff_token': '', 'started_at': now(), 'updated_at': now()}
            try:
                atomic_write_json(self.paths.journal, journal)
                self.log(f'Inicio {journal["id"]}: {from_version} -> {manifest.version}')
                try:
                    self.snapshot(journal)
                except Exception:
                    shutil.rmtree(self.paths.rollback / journal['id'], ignore_errors=True)
                    self.paths.journal.unlink(missing_ok=True)
                    raise
                journal = self.set_phase(journal, 'snapshot_ok')
            finally:
                lock.release()  # el journal ya bloquea el arranque; Inno exige el mutex libre
            try:
                journal = self.set_phase(journal, 'installing')
                self.install(installer, manifest)
                token = secrets.token_hex(32)
                journal = self.set_phase(journal, 'migrating', handoff_token=token)
                self.migrate(owner_password, token)
                journal = self.set_phase(journal, 'checking')
                self.check_running(manifest.version, auth, owner_password, token)
            except Exception as exc:
                self.log(f'Error {journal["id"]}: {exc}. Restaurando {from_version}.')
                self.report(0, 'Error: restaurando versión y datos anteriores…')
                try:
                    self._recover(journal)
                except UpdateError as restore_exc:
                    self.log(f'RECUPERACIÓN PENDIENTE {journal["id"]}: {restore_exc}')
                    raise UpdateError(f'{exc}. ATENCIÓN: la restauración no terminó ({restore_exc}). '
                                      'Cerrá todo y abrí de nuevo el actualizador para recuperar.') from exc
                raise UpdateError(f'{exc}. Se restauraron la versión {from_version or "anterior"} y sus datos.') from exc
            journal = self.set_phase(journal, 'committing', handoff_token='')
            self._commit(journal)
            self.report(8, f'Listo: versión {manifest.version} instalada y comprobada.')
            return manifest.version

    def _commit(self, journal: dict) -> None:
        self.write_state(journal['to_version'])
        self.paths.journal.unlink(missing_ok=True)
        self.prune(keep=journal['id'])
        shutil.rmtree(self.paths.updates / 'tmp', ignore_errors=True)
        self.log(f'Éxito {journal["id"]}: versión {journal["to_version"]}')

    def _recover(self, journal: dict) -> str:
        """Lleva una actualización interrumpida a un estado final. Repetible."""
        phase = journal['phase']
        if phase == 'committing':
            self._commit(journal)
            return f'La versión {journal["to_version"]} ya estaba instalada; se completó el cierre.'
        lock = self.system.pos_lock()
        for attempt in range(20):
            try:
                lock.acquire()
                break
            except LockBusy as exc:
                if attempt == 19:
                    raise UpdateError('El POS está abierto: cerralo para poder recuperar') from exc
                self.system.sleep(0.5)
        try:
            if phase == 'snapshotting':  # no se llegó a tocar programa ni datos
                shutil.rmtree(self.paths.rollback / journal['id'], ignore_errors=True)
                self.paths.journal.unlink(missing_ok=True)
                self.log(f'Recuperado {journal["id"]}: interrumpida antes de modificar; nada que restaurar')
                return 'La actualización se cortó antes de modificar nada.'
            self.set_phase(journal, 'restoring', handoff_token='')
            self.restore(journal['id'])
            self.paths.journal.unlink(missing_ok=True)
            self.log(f'Restaurado {journal["id"]}: versión {journal["from_version"]}')
            return f'Se restauraron la versión {journal["from_version"] or "anterior"} y sus datos.'
        finally:
            lock.release()

    def recover(self, technician: str = '', owner_password: str = '') -> str:
        """Recuperación tras corte o cierre forzado: clave del técnico O contraseña del dueño
        (validada contra la copia verificada, porque la base actual puede estar a medio migrar)."""
        with self.exclusive():
            journal = self.pending()
            if journal is None:
                return 'No hay actualizaciones interrumpidas.'
            try:
                if technician:
                    check_technician(self.trust.get('technician_hash', ''), technician, self.technician_limiter)
                else:
                    if journal['phase'] not in ('snapshotting', 'committing'):
                        self.verify_snapshot(journal['id'])
                    copy = self.paths.rollback / journal['id'] / 'data'
                    folder = copy if (copy / 'pos.db').exists() else self.paths.database.parent
                    with tempfile.TemporaryDirectory(dir=self.paths.updates) as scratch:
                        for name in DB_FILES:
                            if (folder / name).exists():
                                shutil.copy2(folder / name, Path(scratch) / name)
                        if check_owner(Path(scratch) / 'pos.db', owner_password, self.owner_limiter) is None:
                            raise AuthError('Sin cuenta de dueño en la copia: usá la clave del técnico')
            except AuthError as exc:
                raise UpdateError(str(exc)) from exc
            return self._recover(journal)


def load_trust() -> dict:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    for path in (base / 'trust.json', base / 'gip_updater' / 'trust.json', Path(__file__).parent / 'trust.json'):
        if path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
            if not (data.get('public_keys') or data.get('public_key')) or not data.get('technician_hash'):
                raise UpdateError('Actualizador sin configurar: falta la clave pública o la clave del técnico')
            return data
    raise UpdateError('Actualizador sin configurar: falta trust.json')
