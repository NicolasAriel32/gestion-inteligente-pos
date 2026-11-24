"""Bloqueos entre procesos.

- UpdaterMutex: un solo actualizador a la vez (`Local\\GestionInteligentePOS-Actualizador`).
- PosInstanceLock: el mismo bloqueo de instancia que usa el POS (`Local\\GestionInteligentePOS`
  + config/instance.lock). Tenerlo prueba que el POS no está corriendo y le impide abrir.

En Windows el mutex se crea SIN dueño inicial: lo que cuenta es que exista un handle
abierto (así lo comprueban el POS y el AppMutex de Inno Setup), y se puede soltar desde
cualquier hilo cerrando el handle.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Self

ERROR_ALREADY_EXISTS = 183


class LockBusy(Exception):
    pass


class NamedLock:
    def __init__(self, name: str, file: Path):
        self.name = name
        self.file = file
        self.handle = None
        self.stream = None

    def acquire(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateMutexW(None, False, self.name)
            if not handle or ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
                if handle:
                    kernel.CloseHandle(handle)
                raise LockBusy(self.name)
            self.handle = handle
        else:
            import fcntl
            stream = self.file.open('a+b')
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                stream.close()
                raise LockBusy(self.name) from exc
            self.stream = stream

    def release(self) -> None:
        if self.handle:
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(self.handle)
            self.handle = None
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    @property
    def held(self) -> bool:
        return bool(self.handle or self.stream)

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def updater_mutex(data_root: Path) -> NamedLock:
    return NamedLock('Local\\GestionInteligentePOS-Actualizador', data_root / 'updates' / 'updater.lock')


def pos_instance_lock(data_root: Path) -> NamedLock:
    return NamedLock('Local\\GestionInteligentePOS', data_root / 'config' / 'instance.lock')
