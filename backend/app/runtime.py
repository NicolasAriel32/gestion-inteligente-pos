"""Launcher local empaquetable. Preparar/actualizar/recuperar son acciones explícitas."""
import argparse
import getpass
import json
import os
import socket
import sys
import time
import webbrowser
from pathlib import Path
from threading import Thread, Timer
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

import uvicorn

from app.bootstrap import prepare_setup
from app.domain.identity import IdentityError
from app.infrastructure.backups import BackupFiles
from app.infrastructure.database import build_engine, get_db_path
from app.infrastructure.maintenance import MaintenanceStore
from app.infrastructure.migrations import upgrade_database
from app.infrastructure.schema import verify_schema
from app.main import create_app


class InstanceLock:
    def __init__(self, path: Path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = path
        self.stream = None
        self.handle = None

    def acquire(self) -> bool:
        self.stream = self.path.open('a+b')
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.handle = kernel.CreateMutexW(None, True, 'Local\\GestionInteligentePOS')
            if not self.handle or ctypes.get_last_error() == 183:
                if self.handle:
                    kernel.CloseHandle(self.handle)
                self.handle = None
                self.stream.close()
                return False
        else:
            import fcntl
            try:
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.stream.close()
                return False
        if os.name != 'nt':
            self.path.chmod(0o600)
        return True

    def publish(self, instance: str) -> None:
        assert self.stream is not None
        self.stream.seek(0)
        self.stream.truncate()
        self.stream.write(instance.encode('ascii'))
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def release(self) -> None:
        if self.handle:
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.ReleaseMutex(self.handle)
            kernel.CloseHandle(self.handle)
            self.handle = None
        if self.stream is not None and not self.stream.closed:
            self.stream.close()


def frontend_directory() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'frontend'
    return Path(__file__).resolve().parents[2] / 'frontend' / 'dist'


def ready(instance: str, timeout: float = 10) -> bool:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with opener.open('http://127.0.0.1:8765/api/runtime/ping', timeout=0.5) as response:
                if json.load(response).get('instance') == instance:
                    return True
        except (URLError, OSError, ValueError):
            pass
        time.sleep(0.1)
    return False


def prepare(path: Path, approved: bool = False) -> None:
    if not approved and input('Escribí PREPARAR para crear/actualizar la base local: ') != 'PREPARAR':
        raise IdentityError(409, 'Preparación cancelada')
    files = BackupFiles(path)
    if files.journal.exists():
        raise IdentityError(409, 'Primero recuperá la restauración interrumpida')
    if path.exists() and path.stat().st_size:
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            owner = db.execute("SELECT username FROM users WHERE role='ADMIN'").fetchone()
        if owner:
            MaintenanceStore.credentials(path, owner[0], getpass.getpass('Contraseña ADMIN: '))
        saved = files.create('pre_upgrade', current=False)
        print('Respaldo previo guardado:', saved['id'])
    upgrade_database(path)
    engine = build_engine(path)
    try:
        verify_schema(engine)
        from app.infrastructure.identity import IdentityStore
        with IdentityStore(engine).transaction() as tx:
            initialized = tx.initialized()
        if not initialized:
            secret = path.parent.parent / 'config' / 'setup-token.txt'
            if not secret.exists():
                secret = prepare_setup(path)
            print('Secreto inicial disponible en el archivo local:', secret)
    finally:
        engine.dispose()
    print('Preparación completada. Ya podés iniciar la aplicación.')


def configure_arca(path: Path) -> None:
    from app.infrastructure.arca_credentials import CredentialFiles, local_bytes
    from app.infrastructure.catalog import CatalogTransaction
    from app.infrastructure.identity import IdentityStore

    files = BackupFiles(path)
    if files.journal.exists():
        raise IdentityError(409, 'Primero recuperá la restauración interrumpida')
    engine = build_engine(path)
    try:
        verify_schema(engine)
        actor = MaintenanceStore.credentials(path, input('Usuario ADMIN: ').strip().lower(), getpass.getpass('Contraseña ADMIN: '))
        print('Solo homologación: no habilita facturas ni conecta con producción. No uses credenciales de producción.')
        if input('Escribí CONFIGURAR ARCA para guardar o reemplazar el certificado de prueba: ') != 'CONFIGURAR ARCA':
            raise IdentityError(409, 'Configuración cancelada')
        cuit = input('CUIT representado (11 dígitos): ').strip()
        cert_path = Path(input('Ruta completa del certificado PEM de homologación: ').strip().strip('"'))
        key_path = Path(input('Ruta completa de la clave privada PEM: ').strip().strip('"'))
        if not cert_path.is_absolute() or not key_path.is_absolute():
            raise IdentityError(422, 'Usá rutas completas a los archivos locales')
        source_password = getpass.getpass('Contraseña del archivo de clave (vacío si no está cifrado): ')
        storage_password = getpass.getpass('Nueva contraseña local para proteger la copia (12–128 caracteres): ')
        if storage_password != getpass.getpass('Repetí la nueva contraseña local: '):
            raise IdentityError(422, 'Las contraseñas no coinciden')
        credentials = CredentialFiles(files.root)
        with IdentityStore(engine).transaction(write=True) as tx:
            CatalogTransaction(tx.connection).event(actor, 'FISCAL_CONFIGURATION_STARTED', 'fiscal', 0, {'environment': 'homologation'})
        metadata = credentials.configure(cuit, local_bytes(cert_path), local_bytes(key_path), source_password, storage_password, time.time())
        with IdentityStore(engine).transaction(write=True) as tx:
            CatalogTransaction(tx.connection).event(actor, 'FISCAL_CONFIGURATION_SAVED', 'fiscal', 0, {'environment': 'homologation', 'fingerprint': metadata['certificate_fingerprint']})
        print('Certificado de homologación guardado. Verificá acceso desde Herramientas → ARCA. La contraseña local no se guarda.')
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--recover-restore', action='store_true')
    parser.add_argument('--renew-setup', action='store_true')
    parser.add_argument('--configure-arca', action='store_true', help='Configurar certificado de homologación local (ADMIN, sin red)')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    path = get_db_path().resolve()
    lock = InstanceLock(path.parent.parent / 'config' / 'instance.lock')
    if not lock.acquire():
        if args.prepare or args.recover_restore or args.renew_setup or args.configure_arca:
            print('Cerrá la aplicación antes de realizar mantenimiento.')
            return 1
        try:
            instance = lock.path.read_text(encoding='ascii')
        except OSError:
            instance = ''
        if instance and ready(instance) and not args.no_browser:
            webbrowser.open('http://127.0.0.1:8765')
        print('La aplicación ya está iniciada o preparando su arranque.')
        return 0
    try:
        if args.configure_arca:
            configure_arca(path)
            return 0
        if args.prepare:
            prepare(path)
            return 0
        if args.renew_setup:
            print('Archivo del nuevo secreto inicial:', prepare_setup(path, renew=True))
            return 0
        if args.recover_restore:
            if input('Escribí RECUPERAR para volver al respaldo previo a la interrupción: ') != 'RECUPERAR':
                return 1
            engine = build_engine(path)
            try:
                MaintenanceStore(engine, BackupFiles(path), time.time).recover_interrupted(
                    input('Usuario ADMIN: ').strip().lower(), getpass.getpass('Contraseña ADMIN: '))
            finally:
                engine.dispose()
            print('Estado previo recuperado. Las sesiones fueron cerradas.')
            return 0
        files = BackupFiles(path)
        if files.journal.exists():
            raise IdentityError(409, 'Restauración interrumpida. Ejecutá --recover-restore con tu cuenta ADMIN.')
        resources = frontend_directory()
        if not (resources / 'index.html').is_file():
            raise IdentityError(503, 'Frontend no compilado. Prepará el build antes de iniciar.')
        instance = str(uuid4())
        lock.publish(instance)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if os.name == 'nt':
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(('127.0.0.1', 8765))
                listener.listen(128)
            except OSError as exc:
                raise IdentityError(409, 'Puerto local 8765 ocupado. No se inició ni se cerró otro proceso.') from exc
            application = create_app(path, frontend_path=resources)
            application.state.instance_id = instance
            server = uvicorn.Server(uvicorn.Config(application, host='127.0.0.1', port=8765, log_level='warning', access_log=False))
            def stop() -> None:
                server.should_exit = True
            application.state.request_shutdown = lambda: Timer(0.3, stop).start()
            if not args.no_browser:
                def open_when_ready():
                    if ready(instance):
                        webbrowser.open('http://127.0.0.1:8765')
                Thread(target=open_when_ready, daemon=True).start()
            print('Aplicación local: http://127.0.0.1:8765 — cerrar desde Herramientas o Ctrl+C.')
            server.run(sockets=[listener])
            if not server.started:
                return 1
        return 0
    except (IdentityError, OSError, RuntimeError) as exc:
        print(str(exc) if isinstance(exc, IdentityError) else 'No se pudo iniciar/preparar. Comprobá permisos, versión de esquema y respaldo.', file=sys.stderr)
        return 1
    finally:
        lock.release()


if __name__ == '__main__':
    raise SystemExit(main())
