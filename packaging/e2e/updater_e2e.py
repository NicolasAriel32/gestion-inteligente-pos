"""E2E REAL del actualizador en Windows (ADR-019), con instaladores Inno Setup.

1. Instala la versión vieja (main 0.5.1), crea dueño, productos y ventas por la API.
2. Con el POS ABIERTO, actualiza a la versión de prueba (0.6.0 + migración 0007):
   cierre ordenado, respaldo, instalación silenciosa, migración, comprobación.
   Verifica versión, migración y que ventas/stock/usuarios quedaron idénticos.
3. Falla controlada (paquete 0.7.0 con instalador 0.6.0): debe restaurar programa y datos.
4. Corte forzado: mata el proceso del actualizador (árbol completo) durante la instalación;
   el POS no debe arrancar; la recuperación restaura y el POS vuelve a funcionar.
5. Dos actualizadores a la vez: el segundo se rechaza.

Claves y contraseñas: DESCARTABLES, generadas en cada corrida. Escribe un informe JSON.
Uso: python updater_e2e.py <instalador-viejo.exe> <instalador-nuevo.exe> <informe.json>
     python updater_e2e.py --child <paquete> <trust.json>     (uso interno)
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import closing
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'updater'))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from gip_updater import package
from gip_updater.auth import hash_technician
from gip_updater.engine import LocalApi, Paths, UpdateError, Updater
from gip_updater.locks import updater_mutex
from gip_updater.storage import file_sha256

TECH = 'tecnico-descartable-' + uuid4().hex[:8]
OWNER_PW = 'Dueno-descartable-' + uuid4().hex[:8]
report: dict = {'steps': [], 'ok': False}


def step(name: str, **data) -> None:
    report['steps'].append({'step': name, **data})
    print(f'[E2E] {name} {json.dumps(data, ensure_ascii=False)}', flush=True)


def run(args, **kw):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=600, check=False, **kw)


def business(db: Path) -> dict:
    """Datos comerciales que la actualización NO debe alterar."""
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as c:
        return {
            'sales': c.execute('SELECT id, total_cents, status, user_id FROM sales ORDER BY id').fetchall(),
            'items': c.execute('SELECT sale_id, product_id, quantity, unit_price_cents FROM sale_items ORDER BY id').fetchall(),
            'payments': c.execute('SELECT sale_id, method, amount_cents FROM payments ORDER BY id').fetchall(),
            'stock': c.execute('SELECT id, name, price_cents, stock_quantity FROM products ORDER BY id').fetchall(),
            'users': c.execute('SELECT username, role, is_active FROM users ORDER BY id').fetchall(),
            'movements': c.execute('SELECT count(*) FROM stock_movements').fetchone()[0],
        }


def revision(db: Path) -> str:
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as c:
        return c.execute('SELECT version_num FROM alembic_version').fetchone()[0]


def wait_alive(api: LocalApi, process=None, seconds=60) -> None:
    for _ in range(seconds * 5):
        if api.alive():
            return
        if process is not None and process.poll() is not None:
            raise AssertionError(f'El POS terminó con código {process.returncode}')
        time.sleep(0.2)
    raise AssertionError('El POS no respondió')


def start_pos(paths: Paths) -> subprocess.Popen:
    process = subprocess.Popen([str(paths.exe), '--no-browser'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_alive(LocalApi(), process)
    return process


def stop_pos(process: subprocess.Popen) -> None:
    api = LocalApi()
    api.login('owner', OWNER_PW)
    api.shutdown()
    process.wait(timeout=60)


def sell(api: LocalApi, product_id: int, quantity: int, method: str = 'CASH') -> dict:
    items = [{'product_id': product_id, 'quantity': quantity}]
    status, quote = api.request('POST', '/api/sales/quote', {'items': items})
    assert status == 200, quote
    status, sale = api.request('POST', '/api/sales', {'items': items, 'payment_method': method,
                                                      'idempotency_key': str(uuid4()),
                                                      'quote_fingerprint': quote['quote_fingerprint']})
    assert status == 201, sale
    return sale


def seed(paths: Paths) -> None:
    result = run([paths.exe, '--prepare'], input='PREPARAR\n')
    assert result.returncode == 0, result.stdout + result.stderr
    process = start_pos(paths)
    api = LocalApi()
    token = (paths.data_root / 'config' / 'setup-token.txt').read_text()
    assert api.request('POST', '/api/auth/setup', {'username': 'owner', 'password': OWNER_PW, 'setup_token': token})[0] == 201
    api.login('owner', OWNER_PW)
    products = []
    for name, price, stock in [('Alfajor', 12550, 40), ('Gaseosa 500', 21000, 30), ('Chicle', 3300, 100)]:
        status, body = api.request('POST', '/api/products', {'name': name, 'code': None, 'price_cents': price,
                                                            'initial_stock': stock, 'initial_reason': 'Carga inicial'})
        assert status == 201, body
        products.append(body['id'])
    for index in range(12):
        sell(api, products[index % 3], 1 + index % 4, 'CASH' if index % 2 else 'TRANSFER')
    api.shutdown()
    process.wait(timeout=60)
    step('seed', version=run([paths.exe, '--version']).stdout.strip() or 'sin --version', sales=12)


def child(package_path: str, trust_path: str) -> None:
    """Proceso del actualizador que el E2E mata a mitad de camino."""
    updater = Updater(json.loads(Path(trust_path).read_text()), Paths.default())
    updater.update(Path(package_path), os.environ['E2E_TECH'], os.environ['E2E_OWNER'])


def main(old_installer: Path, new_installer: Path, output: Path) -> None:
    paths = Paths.default()
    work = Path(tempfile.mkdtemp(prefix='updater-e2e-'))
    key = Ed25519PrivateKey.generate()  # descartable
    trust = {'public_keys': [base64.b64encode(package.raw_public(key.public_key())).decode()],
             'technician_hash': hash_technician(TECH), 'index_url': 'https://example.invalid/latest.json'}
    trust_file = work / 'trust.json'
    trust_file.write_text(json.dumps(trust))
    updater = Updater(trust, paths, report=lambda s, m: print(f'  paso {s}: {m}', flush=True))

    # 1. versión vieja con datos reales
    result = run([old_installer, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'])
    assert result.returncode == 0, result.stdout
    seed(paths)
    before = business(paths.database)
    old_revision = revision(paths.database)

    # 2. actualización real con el POS abierto
    pos = start_pos(paths)
    pkg_new = package.create_package(new_installer, '0.6.0', key, work / 'new.gipupdate', 'E2E')
    t0 = time.monotonic()
    assert updater.update(pkg_new, TECH, OWNER_PW) == '0.6.0'
    pos.wait(timeout=30)
    after = business(paths.database)
    assert run([paths.exe, '--version']).stdout.strip() == '0.6.0'
    assert revision(paths.database) == '0007_e2e_update_probe' != old_revision
    with closing(sqlite3.connect(paths.database)) as c:
        probe = c.execute('SELECT sales_at_migration FROM update_probe').fetchone()[0]
    assert probe == len(before['sales']) == 12
    assert after == before, 'La actualización alteró datos comerciales'
    assert not paths.journal.exists() and json.loads(paths.state.read_text())['installed_version'] == '0.6.0'
    step('update_ok', seconds=round(time.monotonic() - t0, 1), from_revision=old_revision,
         to_revision='0007_e2e_update_probe', sales=len(after['sales']), business_data='idéntica')
    pos = start_pos(paths)  # arranque normal sin token
    api = LocalApi()
    api.login('owner', OWNER_PW)
    product = after['stock'][0][0]
    sell(api, product, 2)
    api.shutdown()
    pos.wait(timeout=60)
    step('new_version_sells', sales=len(business(paths.database)['sales']))

    # 3. falla controlada -> restauración real
    baseline_db = file_sha256(paths.database)
    baseline = business(paths.database)
    pkg_bad = package.create_package(new_installer, '0.7.0', key, work / 'bad.gipupdate', 'E2E falla')
    try:
        updater.update(pkg_bad, TECH, OWNER_PW)
        raise AssertionError('La actualización fallida no falló')
    except UpdateError as exc:
        assert 'Se restauraron la versión 0.6.0' in str(exc), str(exc)
    assert run([paths.exe, '--version']).stdout.strip() == '0.6.0'
    assert file_sha256(paths.database) == baseline_db and business(paths.database) == baseline
    assert not paths.journal.exists()
    assert not list(paths.app_dir.parent.glob('*.restaurando')) and not list(paths.app_dir.parent.glob('*.descartado-*'))
    step('failure_restored', error='versión instalada no coincide', database='idéntica (sha256)')

    # 4. corte forzado durante la instalación -> bloqueo del POS -> recuperación
    pkg_crash = package.create_package(new_installer, '0.7.1', key, work / 'crash.gipupdate', 'E2E corte')
    env = {**os.environ, 'E2E_TECH': TECH, 'E2E_OWNER': OWNER_PW}
    victim = subprocess.Popen([sys.executable, __file__, '--child', str(pkg_crash), str(trust_file)], env=env)
    phase = None
    for _ in range(3000):
        if paths.journal.exists():
            try:
                phase = json.loads(paths.journal.read_text())['phase']
            except (ValueError, OSError):
                phase = None
            if phase == 'installing':
                time.sleep(1.0)
                break
        if victim.poll() is not None:
            raise AssertionError('El actualizador terminó antes del corte')
        time.sleep(0.05)
    assert phase == 'installing', phase
    subprocess.run(['taskkill', '/PID', str(victim.pid), '/T', '/F'], capture_output=True, check=False)
    victim.wait(timeout=60)
    time.sleep(3)
    killed_phase = json.loads(paths.journal.read_text())['phase']
    blocked = run([paths.exe, '--no-browser'])
    assert blocked.returncode == 3, (blocked.returncode, blocked.stdout)
    step('crash_blocks_pos', killed_during=killed_phase, pos_exit_code=blocked.returncode)
    fresh = Updater(trust, paths)
    assert fresh.pending() is not None
    message = fresh.recover(technician=TECH)
    assert run([paths.exe, '--version']).stdout.strip() == '0.6.0'
    assert business(paths.database) == baseline and not paths.journal.exists()
    pos = start_pos(paths)
    stop_pos(pos)
    step('crash_recovered', message=message)

    # 5. dos actualizadores a la vez
    with updater_mutex(paths.data_root):
        try:
            Updater(trust, paths).update(pkg_crash, TECH, OWNER_PW)
            raise AssertionError('Se permitieron dos actualizadores')
        except UpdateError as exc:
            assert 'otro actualizador' in str(exc)
    step('single_updater')
    report['ok'] = True
    report['log'] = paths.log.read_text(encoding='utf-8')[-4000:]
    assert OWNER_PW not in report['log'] and TECH not in report['log']
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1] == '--child':
        child(sys.argv[2], sys.argv[3])
        sys.exit(0)
    out = Path(sys.argv[3])
    try:
        main(Path(sys.argv[1]), Path(sys.argv[2]), out)
        print('[E2E] OK', flush=True)
    except BaseException:  # noqa: BLE001 - el informe debe guardarse ante cualquier falla
        report['error'] = traceback.format_exc()
        log = Paths.default().log
        report['log'] = log.read_text(encoding='utf-8')[-4000:] if log.exists() else ''
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(report['error'], flush=True)
        sys.exit(1)
