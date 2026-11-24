"""Ventana del actualizador.

- Si hay una actualización interrumpida, solo ofrece RECUPERAR (técnico o dueño).
- Para actualizar: clave del técnico + contraseña del dueño. El motor vuelve a validarlas
  justo antes de tocar nada; la ventana no decide nada de seguridad por su cuenta.
- Mientras corre una operación crítica la ventana no se puede cerrar.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .engine import Paths, UpdateError, Updater, load_trust


class App:
    def __init__(self, root: tk.Tk, updater: Updater | None = None):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.package: Path | None = None
        self.busy = False
        self.unlocked = False
        root.title('Actualizador — Gestión Inteligente POS')
        root.geometry('580x560')
        root.resizable(False, False)
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        try:
            self.updater = updater or Updater(load_trust(), Paths.default())
            self.updater.report = lambda step, msg: self.events.put(('step', step, msg))
            pending = self.updater.pending()
            installed = self.updater.installed_version() or 'desconocida'
        except UpdateError as exc:
            messagebox.showerror('Actualizador', str(exc))
            root.destroy()
            return
        ttk.Label(frame, text=f'Versión instalada: {installed}', font=('Segoe UI', 11, 'bold')).pack(anchor='w')

        keys = ttk.LabelFrame(frame, text='Autorización', padding=10)
        keys.pack(fill='x', pady=(12, 6))
        ttk.Label(keys, text='Clave del técnico').grid(row=0, column=0, sticky='w')
        self.technician = ttk.Entry(keys, show='•', width=36)
        self.technician.grid(row=0, column=1, padx=6, pady=3)
        ttk.Label(keys, text='Contraseña del dueño (ADMIN)').grid(row=1, column=0, sticky='w')
        self.owner_pw = ttk.Entry(keys, show='•', width=36)
        self.owner_pw.grid(row=1, column=1, padx=6, pady=3)
        self.unlock = ttk.Button(keys, text='Desbloquear', command=self.authorize)
        self.unlock.grid(row=2, column=1, sticky='e', pady=(6, 0))

        self.recovery = ttk.Button(frame, text='Recuperar actualización interrumpida', command=self.recover)
        source = ttk.LabelFrame(frame, text='Actualización', padding=10)
        source.pack(fill='x', pady=6)
        self.file_btn = ttk.Button(source, text='Elegir archivo .gipupdate…', command=self.choose, state='disabled')
        self.file_btn.pack(side='left')
        self.net_btn = ttk.Button(source, text='Buscar en internet', command=self.search, state='disabled')
        self.net_btn.pack(side='left', padx=8)
        self.selected = ttk.Label(frame, text='Sin paquete seleccionado')
        self.selected.pack(anchor='w', pady=(4, 0))
        self.go = ttk.Button(frame, text='Actualizar', command=self.update, state='disabled')
        self.go.pack(fill='x', pady=10)
        self.progress = ttk.Progressbar(frame, maximum=8)
        self.progress.pack(fill='x')
        self.status = tk.Text(frame, height=9, state='disabled', wrap='word')
        self.status.pack(fill='both', expand=True, pady=(8, 0))
        if pending:
            self.enter_recovery(pending)
        root.after(100, self.poll)

    # --- utilidades ---------------------------------------------------------------------
    def say(self, message: str) -> None:
        self.status.configure(state='normal')
        self.status.insert('end', message + '\n')
        self.status.see('end')
        self.status.configure(state='disabled')

    def enter_recovery(self, journal: dict) -> None:
        self.unlock.configure(state='disabled')
        self.recovery.pack(fill='x', pady=6, before=self.selected)
        self.say(f'⚠ Se interrumpió la actualización {journal["from_version"]} → {journal["to_version"]} '
                 f'(fase: {journal["phase"]}). El POS no abre hasta recuperarla. '
                 'Ingresá la clave del técnico o la contraseña del dueño y tocá "Recuperar".')

    def on_close(self) -> None:
        if self.busy:
            messagebox.showwarning('Actualizador', 'Hay una operación en curso. No cierres ni apagues la PC hasta que termine.')
            return
        self.root.destroy()

    def set_sources(self) -> None:
        state = 'normal' if self.unlocked and not self.busy else 'disabled'
        self.file_btn.configure(state=state)
        self.net_btn.configure(state=state)

    def poll(self) -> None:
        while not self.events.empty():
            kind, *data = self.events.get()
            if kind == 'step':
                step, message = data
                if step:
                    self.progress['value'] = step
                self.say(message)
            elif kind == 'ready':
                self.package, label = data
                self.selected.configure(text=label)
                self.go.configure(state='normal')
            elif kind == 'error':
                self.say('✖ ' + data[0])
                messagebox.showerror('Actualizador', data[0])
            elif kind == 'idle':
                self.busy = False
                self.set_sources()
            elif kind == 'done':
                self.busy = False
                messagebox.showinfo('Actualizador', data[0])
                self.root.destroy()
                return
        self.root.after(100, self.poll)

    def background(self, target, critical: bool = False) -> None:
        self.busy = critical
        self.file_btn.configure(state='disabled')
        self.net_btn.configure(state='disabled')
        self.go.configure(state='disabled')

        def run():
            try:
                target()
            except UpdateError as exc:
                self.events.put(('error', str(exc)))
            except Exception:  # noqa: BLE001 - detalle en el registro del actualizador
                self.events.put(('error', 'Error inesperado. Revisá updates/actualizaciones.log'))
            finally:
                self.events.put(('idle',))
        # No daemon: si igual se mata el proceso, el journal obliga a recuperar al reabrir.
        threading.Thread(target=run, daemon=False).start()

    # --- acciones -----------------------------------------------------------------------
    def authorize(self) -> None:
        try:
            self.updater.authorize(self.technician.get(), self.owner_pw.get())
        except UpdateError as exc:
            messagebox.showerror('Autorización', str(exc))
            return
        self.unlocked = True
        self.technician.configure(state='disabled')
        self.owner_pw.configure(state='disabled')
        self.unlock.configure(state='disabled')
        self.set_sources()
        self.say('Autorizado. Elegí el archivo o buscá en internet.')

    def recover(self) -> None:
        technician, owner = self.technician.get(), self.owner_pw.get()

        def work():
            message = self.updater.recover(technician=technician, owner_password=owner)
            self.events.put(('done', message + ' Ya podés abrir el POS.'))
        self.background(work, critical=True)

    def choose(self) -> None:
        name = filedialog.askopenfilename(filetypes=[('Actualización firmada', '*.gipupdate')])
        if name:
            self.background(lambda: self.check(Path(name)))

    def search(self) -> None:
        def work():
            entry = self.updater.available()
            self.events.put(('step', 1, f'Disponible: {entry.version}. {entry.notes}'.strip()))
            self.check(self.updater.download(entry))
        self.background(work)

    def check(self, path: Path) -> None:
        manifest, _ = self.updater.verify(path)
        self.events.put(('step', 3, f'Firma válida. Versión {manifest.version}. {manifest.notes}'.strip()))
        self.events.put(('ready', path, f'Listo para instalar: versión {manifest.version}'))

    def update(self) -> None:
        if not self.package or not messagebox.askyesno('Actualizar', 'Se cerrará el POS durante unos minutos. ¿Continuar?'):
            return
        package_path, technician, owner = self.package, self.technician.get(), self.owner_pw.get()

        def work():
            version = self.updater.update(package_path, technician, owner)
            self.events.put(('done', f'Versión {version} instalada y comprobada. Ya podés abrir el POS.'))
        self.background(work, critical=True)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
