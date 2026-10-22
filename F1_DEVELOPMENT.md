# F1 — Entorno local

Solo esqueleto, sin ventas ni auth. Desarrollo requiere Python >=3.11, Node >=22, npm; no requiere cloud.

Backend:
```sh
cd backend
python -m venv .venv
# activar el entorno
python -m pip install -e '.[dev]'
python -m alembic -c alembic.ini upgrade head
python -m app
```
API: http://127.0.0.1:8765/api/health

Frontend (otra terminal):
```sh
cd frontend
npm install
npm run dev
```
Abrir http://127.0.0.1:5173 (proxy local /api).

Verificaciones:
```sh
cd backend
python -m pytest -q
python -m ruff check .
python -m alembic -c alembic.ini current
cd ../frontend
npm run test
npm run lint
npm run build
```
SQLite: %LOCALAPPDATA%/GestionInteligentePOS/data/pos.db en Windows, ~/.local/share/GestionInteligentePOS/data/pos.db en otros sistemas. F1 no crea tablas de negocio. Resultados previos locales: pytest 3 passed; npm/Ruff sin dependencias disponibles, frontend no validado. No marcar F1 como aceptada hasta pruebas completas.
