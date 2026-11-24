"""Prueba de la ventana: desbloqueo, modo recuperación y protección contra el cierre.
Se saltea si no hay tkinter o pantalla (en Linux se corre con xvfb-run)."""
import pytest

tk = pytest.importorskip('tkinter')

from gip_updater import gui
from tests.test_updater import OWNER_PW, TECH, Crash, make_package


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip('sin pantalla')
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def dialogs(monkeypatch):
    shown = []
    for name in ('showerror', 'showinfo', 'showwarning'):
        monkeypatch.setattr(gui.messagebox, name, lambda *a, _n=name: shown.append((_n, a)))
    monkeypatch.setattr(gui.messagebox, 'askyesno', lambda *a: True)
    return shown


def test_desbloqueo_y_verificacion(root, setup, tmp_path, key, dialogs):
    _, build = setup
    updater, _, _ = build()
    app = gui.App(root, updater)
    assert str(app.file_btn['state']) == 'disabled'
    app.technician.insert(0, 'incorrecta-incorrecta')
    app.owner_pw.insert(0, OWNER_PW)
    app.authorize()
    assert dialogs[-1][0] == 'showerror' and not app.unlocked
    app.technician.delete(0, 'end')
    app.technician.insert(0, TECH)
    app.authorize()
    assert app.unlocked and str(app.file_btn['state']) == 'normal'
    app.check(make_package(tmp_path, key, '0.6.0'))
    app.poll()
    assert str(app.go['state']) == 'normal' and '0.6.0' in app.selected['text']


def test_no_se_cierra_durante_operacion_critica(root, setup, dialogs):
    _, build = setup
    updater, _, _ = build()
    app = gui.App(root, updater)
    app.busy = True
    app.on_close()
    assert dialogs[-1][0] == 'showwarning' and root.winfo_exists()


def test_modo_recuperacion_al_abrir_con_actualizacion_interrumpida(root, setup, tmp_path, key, dialogs):
    _, build = setup
    updater, _, _ = build(crash_at='migrate')
    with pytest.raises(Crash):
        updater.update(make_package(tmp_path, key, '0.6.0'), TECH, OWNER_PW)
    fresh, _, _ = build()
    app = gui.App(root, fresh)
    assert str(app.unlock['state']) == 'disabled' and app.recovery.winfo_manager() == 'pack'
    assert 'interrumpió' in app.status.get('1.0', 'end')
