"""Motor del actualizador. Pasos:
1 consultar versiones · 2 descargar a carpeta temporal · 3 verificar firma y compatibilidad
4 cerrar el POS · 5 respaldo consistente · 6 instalar y migrar · 7 comprobar funcionamiento
Éxito: confirmar versión. Error después del paso 5: restaurar binarios y datos anteriores.

Todo lo que toca el sistema operativo pasa por `System`, para poder probarlo sin Windows.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import package
from .package import IndexEntry, Manifest, PackageError

APP_ID = '{F95EAEE3-B79F-4501-9C08-02EF49B75021}_is1'
EXE = 'GestionInteligentePOS.exe'
BASE = 'http://127.0.0.1:8765'
MAX_DOWNLOAD = package.MAX_INSTALLER + 1024 * 1024
INSTALLER_ARGS = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL', '/SP-']

Report = Callable[[int, str], None]


class UpdateError(Exception):
    pass


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
    def state(self) -> Path:
        return self.updates / 'state.json'

    @property
    def log(self) -> Path:
        return self.updates / 'actualizaciones.log'

    @property
    def restore_journal(self) -> Path:
        return self.data_root / 'config' / 'restore-pending.json'


class LocalApi:
    """Cliente mínimo de la API local del POS (loopback, sin proxy, con cookie y CSRF)."""

    def __init__(self, base: str = BASE):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar))
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

    def run(self, args: list[str], stdin: str | None = None, timeout: float = 900) -> tuple[int, str]:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(args, input=stdin, check=False, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        return result.returncode, (result.stdout + result.stderr)[-2000:]

    def start_pos(self) -> subprocess.Popen:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        return subprocess.Popen([str(self.paths.exe), '--no-browser'], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=flags)

    def api(self) -> LocalApi:
        return LocalApi()

    def registry_version(self) -> str | None:
        if os.name != 'nt':
            return None
        import winreg
        key_path = rf'Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
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
        self.key = package.public_key(self.trust['public_key'])

    # --- estado y registro --------------------------------------------------------
    def log(self, message: str) -> None:
        self.paths.updates.mkdir(parents=True, exist_ok=True)
        with self.paths.log.open('a', encoding='utf-8') as stream:
            stream.write(f'{datetime.now().astimezone().isoformat(timespec="seconds")} {message}\n')

    def state(self) -> dict:
        try:
            data = json.loads(self.paths.state.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

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

    # --- pasos 1 a 3 --------------------------------------------------------------
    def available(self) -> IndexEntry:
        self.report(1, 'Consultando versiones disponibles…')
        url = self.trust.get('index_url', '')
        try:
            data = self.system.open_url(url, package.MAX_MANIFEST)
            signature = self.system.open_url(url + '.sig', 512)
        except (OSError, urllib.error.URLError) as exc:
            raise UpdateError('No se pudo consultar internet. Podés usar un archivo .gipupdate.') from exc
        try:
            return package.parse_index(data, signature, self.key)
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
        if package.file_sha256(target) != entry.package_sha256:
            target.unlink(missing_ok=True)
            raise UpdateError('El archivo descargado no coincide con el índice firmado')
        return target

    def verify(self, package_path: Path) -> tuple[Manifest, Path]:
        self.report(3, 'Verificando firma y compatibilidad…')
        work = self.paths.updates / 'tmp' / 'verificado'
        shutil.rmtree(work, ignore_errors=True)
        try:
            manifest = package.open_package(package_path, self.key, work)
        except PackageError as exc:
            shutil.rmtree(work, ignore_errors=True)
            raise UpdateError(str(exc)) from exc
        self.check_compatible(manifest.version)
        return manifest, work / 'installer.exe'

    # --- pasos 4 a 7 --------------------------------------------------------------
    def stop_pos(self, owner: str | None, password: str) -> None:
        self.report(4, 'Cerrando el POS de forma segura…')
        api = self.system.api()
        if not api.alive():
            return
        if owner is None:
            raise UpdateError('El POS está abierto. Cerralo desde Herramientas y reintentá.')
        api.login(owner, password)
        api.shutdown()
        for _ in range(60):
            self.system.sleep(0.5)
            if not api.alive():
                self.system.sleep(1)  # margen para liberar bloqueo de instancia y archivos
                return
        raise UpdateError('El POS no se cerró a tiempo. No se cambió nada.')

    def snapshot(self, from_version: str | None) -> None:
        self.report(5, 'Generando respaldo consistente de programa y datos…')
        if self.paths.restore_journal.exists():
            raise UpdateError('Hay una restauración interrumpida. Resolvela con "Recuperar restauración interrumpida".')
        rollback = self.paths.rollback
        shutil.rmtree(rollback, ignore_errors=True)
        (rollback / 'data').mkdir(parents=True)
        # Con el POS cerrado, copiar base + WAL + SHM juntos da un estado consistente.
        for suffix in ('', '-wal', '-shm'):
            source = self.paths.database.with_name('pos.db' + suffix)
            if source.exists():
                shutil.copy2(source, rollback / 'data' / source.name)
        if self.paths.app_dir.exists():
            package.copy_tree(self.paths.app_dir, rollback / 'app')
        (rollback / 'meta.json').write_text(json.dumps({'from_version': from_version,
                                                       'created_at': datetime.now().astimezone().isoformat()}), encoding='utf-8')

    def install(self, installer: Path, password: str) -> None:
        self.report(6, 'Instalando nueva versión…')
        log = self.paths.updates / 'instalador.log'
        code, _ = self.system.run([str(installer), *INSTALLER_ARGS, f'/LOG={log}'])
        if code != 0:
            raise UpdateError(f'El instalador terminó con error ({code})')
        self.report(6, 'Migrando base de datos…')
        for _ in range(10):
            code, output = self.system.run([str(self.paths.exe), '--prepare-stdin'], stdin=password + '\n')
            if code == 0 or 'Cerrá la aplicación' not in output:
                break
            self.system.sleep(1)  # el proceso anterior todavía libera su bloqueo de instancia
        if code != 0:
            detail = output.strip().splitlines()[-1][:200] if output.strip() else 'sin detalle'
            raise UpdateError(f'La migración de la base falló: {detail}')

    def check_running(self, version: str, owner: str | None, password: str) -> None:
        self.report(7, 'Comprobando la nueva versión…')
        if self.installed_version() != version:
            raise UpdateError('La versión instalada no es la esperada')
        process = self.system.start_pos()
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
            if owner is not None:
                user = api.login(owner, password)
                if user.get('role') != 'ADMIN':
                    raise UpdateError('La cuenta del dueño no quedó como ADMIN')
            if owner is not None:
                api.shutdown()
                process.wait(timeout=30)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()

    def restore(self) -> None:
        rollback = self.paths.rollback
        if not (rollback / 'meta.json').exists():
            raise UpdateError('No hay copia previa para restaurar')
        if (rollback / 'app').exists():
            package.copy_tree(rollback / 'app', self.paths.app_dir)
        for suffix in ('-wal', '-shm', ''):
            self.paths.database.with_name('pos.db' + suffix).unlink(missing_ok=True)
        for saved in (rollback / 'data').iterdir():
            self.paths.database.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, self.paths.database.parent / saved.name)

    def update(self, package_path: Path, owner: str | None, password: str) -> str:
        manifest, installer = self.verify(package_path)
        from_version = self.installed_version()
        if self.paths.restore_journal.exists():
            raise UpdateError('Hay una restauración interrumpida. Resolvela con "Recuperar restauración interrumpida".')
        self.log(f'Inicio: {from_version} -> {manifest.version}')
        self.stop_pos(owner, password)
        self.snapshot(from_version)
        try:
            self.install(installer, password)
            self.check_running(manifest.version, owner, password)
        except Exception as exc:
            self.log(f'Error: {exc}. Restaurando {from_version}.')
            self.report(0, 'Error: restaurando versión y datos anteriores…')
            try:
                self.restore()
            except Exception as restore_exc:  # noqa: BLE001 - doble falla: se informa al técnico
                self.log(f'FALLÓ LA RESTAURACIÓN: {restore_exc}')
                raise UpdateError(f'{exc}. ATENCIÓN: no se pudo restaurar automáticamente; la copia está en {self.paths.rollback}') from exc
            self.log('Restauración completa')
            raise UpdateError(f'{exc}. Se restauraron la versión {from_version or "anterior"} y sus datos.') from exc
        state = self.state()
        highest = state.get('highest_installed')
        if not highest or package.parse_version(manifest.version) > package.parse_version(highest):
            highest = manifest.version
        self.paths.state.write_text(json.dumps({'installed_version': manifest.version, 'highest_installed': highest,
                                               'updated_at': datetime.now().astimezone().isoformat()}), encoding='utf-8')
        shutil.rmtree(self.paths.updates / 'tmp', ignore_errors=True)
        self.log(f'Éxito: versión {manifest.version}')
        self.report(8, f'Listo: versión {manifest.version} instalada y comprobada.')
        return manifest.version


def load_trust() -> dict:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    candidates = [base / 'trust.json', base / 'gip_updater' / 'trust.json', Path(__file__).parent / 'trust.json']
    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
            if not data.get('public_key') or not data.get('technician_hash'):
                raise UpdateError('Actualizador sin configurar: falta la clave pública o la clave del técnico')
            return data
    raise UpdateError('Actualizador sin configurar: falta trust.json')
