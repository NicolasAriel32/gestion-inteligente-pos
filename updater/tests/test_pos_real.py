"""Integración con el POS real (backend del repo): --version, --prepare-stdin y cierre ordenado
por la API. Requiere frontend compilado (npm run build) y el backend instalado."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / 'backend'
pytest.importorskip('app.runtime', reason='backend no instalado')
if not (BACKEND.parent / 'frontend' / 'dist' / 'index.html').exists():
    pytest.skip('frontend sin compilar', allow_module_level=True)

from gip_updater.auth import AuthError, Limiter, check_owner
from gip_updater.engine import LocalApi, UpdateError

PW = 'Owner-password-1234'


def pos(env, *args, stdin=None):
    return subprocess.run([sys.executable, '-m', 'app.runtime', *args], cwd=BACKEND, env=env, check=False,
                          input=stdin, capture_output=True, text=True, timeout=180)


@pytest.fixture
def env(tmp_path):
    return {**os.environ, 'LOCALAPPDATA': str(tmp_path)}


def initialize(env, tmp_path):
    assert pos(env, '--prepare-stdin', stdin='\n').returncode == 0  # base nueva: sin ADMIN todavía
    token = (tmp_path / 'GestionInteligentePOS' / 'config' / 'setup-token.txt').read_text()
    server = subprocess.Popen([sys.executable, '-m', 'app.runtime', '--no-browser'], cwd=BACKEND, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    api = LocalApi()
    for _ in range(100):
        if api.alive():
            break
        time.sleep(0.2)
    status, _ = api.request('POST', '/api/auth/setup', {'username': 'owner', 'password': PW, 'setup_token': token})
    assert status == 201
    return server, api


def test_version_y_migracion_con_contrasena_por_stdin(env, tmp_path):
    result = pos(env, '--version')
    assert result.returncode == 0 and result.stdout.strip() == '0.5.1'
    server, api = initialize(env, tmp_path)
    api.login('owner', PW)
    api.shutdown()
    server.wait(timeout=30)
    database = tmp_path / 'GestionInteligentePOS' / 'data' / 'pos.db'
    wrong = pos(env, '--prepare-stdin', stdin='contraseña-equivocada\n')
    assert wrong.returncode == 1
    right = pos(env, '--prepare-stdin', stdin=PW + '\n')
    assert right.returncode == 0, right.stderr
    assert 'Respaldo previo guardado' in right.stdout and PW not in right.stdout + right.stderr
    assert check_owner(database, PW, Limiter(tmp_path / 'l.json', 'dueño')) == 'owner'
    with pytest.raises(AuthError):
        check_owner(database, 'otra-cosa-larga', Limiter(tmp_path / 'l.json', 'dueño'))


def test_cierre_ordenado_por_api_y_no_migra_con_pos_abierto(env, tmp_path):
    server, api = initialize(env, tmp_path)
    try:
        busy = pos(env, '--prepare-stdin', stdin=PW + '\n')
        assert busy.returncode == 1 and 'Cerrá la aplicación' in busy.stdout
        with pytest.raises(UpdateError):
            LocalApi().login('owner', 'contraseña-equivocada')
        api.login('owner', PW)
        api.shutdown()
        assert server.wait(timeout=30) == 0
        assert not LocalApi().alive()
    finally:
        if server.poll() is None:
            server.kill()


def test_pos_real_respeta_el_bloqueo_de_mantenimiento(env, tmp_path):
    """Con journal de actualización el POS no arranca ni migra; solo el traspaso correcto pasa."""
    import json
    journal = tmp_path / 'GestionInteligentePOS' / 'updates' / 'update-journal.json'
    journal.parent.mkdir(parents=True)
    token = 'c' * 64
    journal.write_text(json.dumps({'phase': 'installing', 'handoff_token': token}))
    for args in (['--no-browser'], ['--prepare-stdin'], ['--recover-restore']):
        blocked = pos({**env, 'GIP_MAINTENANCE_TOKEN': token}, *args, stdin='\n')
        assert blocked.returncode == 3 and 'actualización del POS' in blocked.stdout
    assert pos(env, '--version').returncode == 0  # informar la versión no toca datos
    journal.write_text(json.dumps({'phase': 'migrating', 'handoff_token': token}))
    assert pos(env, '--prepare-stdin', stdin='\n').returncode == 3  # sin token
    allowed = pos({**env, 'GIP_MAINTENANCE_TOKEN': token}, '--prepare-stdin', stdin='\n')
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    journal.write_text('{dañado')
    assert pos({**env, 'GIP_MAINTENANCE_TOKEN': token}, '--prepare-stdin', stdin='\n').returncode == 3
