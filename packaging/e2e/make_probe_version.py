"""SOLO PARA CI (E2E del actualizador, ADR-019). Convierte una copia de trabajo en una
versión de prueba con una migración Alembic real (0007_e2e_update_probe) que agrega una
tabla y registra cuántas ventas había al migrar. Nunca se aplica al repositorio ni se
distribuye: el workflow la ejecuta sobre un worktree descartable.

Uso: python make_probe_version.py <raíz-del-worktree> <versión>
"""
import re
import sys
from pathlib import Path

root, version = Path(sys.argv[1]), sys.argv[2]
assert re.fullmatch(r'\d+\.\d+\.\d+', version)


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding='utf-8')


replace(root / 'backend/pyproject.toml', 'version = "0.5.1"', f'version = "{version}"')
replace(root / 'backend/app/main.py', 'version="0.5.1"', f'version="{version}"')
replace(root / 'backend/app/infrastructure/schema.py', 'EXPECTED_REVISION = "0006_local_operations"',
        'EXPECTED_REVISION = "0007_e2e_update_probe"')
(root / 'backend/alembic/versions/0007_e2e_update_probe.py').write_text('''"""SOLO E2E CI: migración de prueba del actualizador (no se distribuye)."""
from alembic import op

revision = "0007_e2e_update_probe"
down_revision = "0006_local_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TABLE update_probe (id INTEGER PRIMARY KEY, sales_at_migration INTEGER NOT NULL, note TEXT NOT NULL)")
    op.execute("INSERT INTO update_probe(sales_at_migration, note) SELECT count(*), 'migrado por el actualizador' FROM sales")


def downgrade() -> None:
    raise RuntimeError("Sin downgrade")
''', encoding='utf-8')
print(f'Versión de prueba {version} con migración 0007_e2e_update_probe en {root}')
