# F1 — Entorno local validado

Validación ejecutada el 2026-10-22 sobre `feat/f1-technical-skeleton`, en Linux.
F1 completada: esqueleto técnico local, sin usuarios, ventas ni inventario. F2 no iniciada.
No requiere servicios cloud para ejecutar backend, frontend o SQLite. La instalación inicial sí descarga paquetes.
El empaquetado y la instalación en Windows siguen fuera de esta validación (F6).

## Versiones instaladas

- Python 3.12.14, Node.js 24.19.0, npm 11.9.0.
- Backend: fastapi 0.159.1, uvicorn 0.54.0, sqlalchemy 2.1.6, alembic 1.20.0, pytest 9.1.1, httpx 0.28.1, ruff 0.17.1.
- Frontend (dependencias directas): react 19.3.1, react-dom 19.3.1, @eslint/js 9.39.5, @types/node 22.20.5, @types/react 19.3.0, @types/react-dom 19.3.0, @vitejs/plugin-react 4.7.0, eslint 9.39.5, eslint-plugin-react-hooks 5.2.0, globals 15.15.0, typescript 5.7.3, typescript-eslint 8.72.0, vite 6.4.5, vitest 2.1.9, jsdom 25.0.1.
- Versiones transitivas del frontend e integridad: `frontend/package-lock.json` (lockfileVersion 3).
- El backend conserva los rangos declarados en pyproject.toml; no tiene lockfile.

## Instalación reproducible del frontend y entorno backend

Desde la raíz:
```sh
python -m venv backend/.venv
# Linux:
. backend/.venv/bin/activate
# Windows PowerShell, en lugar de la línea anterior:
# backend/.venv/Scripts/Activate.ps1
python -m pip install -e './backend[dev]'
cd frontend
npm ci
```

En esta validación se ejecutó primero `npm install --cache /tmp/gestion-pos-npm-cache`
para generar el lockfile, y después `npm ci --cache /tmp/gestion-pos-npm-cache`:
ambos finalizaron con código 0. La caché por defecto no era escribible y el primer
`npm install` falló con ENOENT; se corrigió usando esa carpeta temporal, sin cambiar dependencias.
`python -m pip check`: código 0, sin dependencias rotas.

## Verificaciones ejecutadas y resultados finales

Con el entorno Python activado, desde `backend`:
```sh
python -m pytest -q
python -m ruff check .
LOCALAPPDATA=/tmp/gestion-pos-f1-validation python -m alembic -c alembic.ini upgrade head
LOCALAPPDATA=/tmp/gestion-pos-f1-validation python -m alembic -c alembic.ini current
```

| Comando | Resultado real |
| --- | --- |
| `python -m pytest -q` | 4 aprobadas, 0 fallidas; 1 advertencia; código 0 |
| `python -m ruff check .` | All checks passed; código 0 |
| `python -m alembic -c alembic.ini upgrade head` | Migración inicial aplicada; código 0 |
| `python -m alembic -c alembic.ini current` | `0001_empty_baseline (head)`; código 0 |

Las ejecuciones usaron `backend/.venv/bin/python`. LOCALAPPDATA apuntó a una carpeta
nueva de validación en /tmp; no se migraron datos preexistentes. La prueba de regresión
aplica upgrade dos veces y abre SQLite en conexiones nuevas: persiste la revisión y solo
existe `alembic_version`, sin tablas comerciales.

Desde `frontend`:
```sh
npm run test
npm run lint
npm run build
```

| Comando | Resultado real |
| --- | --- |
| `npm run test` | 2 aprobadas, 0 fallidas, 1 archivo; código 0 |
| `npm run lint` | Sin errores; código 0 |
| `npm run build` | TypeScript y Vite aprobados; 29 módulos; código 0 |

Build: `dist/index.html` 0.30 kB; JS 224.74 kB (69.98 kB gzip).
Total final: **6 pruebas aprobadas, 0 fallidas**.

## Fallos detectados y corregidos

- Ruff: 4 errores I001 de imports; corregidos con `python -m ruff check . --fix`.
- Alembic devolvía código 0 pero `current` no mostraba revisión: los PRAGMA abrían una
  transacción implícita que se revertía al cerrar. Se agregó commit antes de la
  transacción de Alembic y una prueba de persistencia e idempotencia de la migración.
- Build inicial falló con TS2769 por `test` dentro de la configuración de Vite.
  Se separó `vitest.config.ts`, incluido en la comprobación de TypeScript.
- El sandbox sin acceso de red impedía clonar y bloqueaba TestClient. Se repitieron
  con acceso de red habilitado en el entorno; las verificaciones finales terminaron.

## Arranque y comunicación real

Backend (entorno Python activado, desde `backend`):
```sh
LOCALAPPDATA=/tmp/gestion-pos-f1-validation python -m app
```
Frontend, otra terminal desde `frontend`:
```sh
npm run dev -- --strictPort
```

Ambos iniciaron correctamente: Uvicorn en `127.0.0.1:8765`, Vite en `127.0.0.1:5173`.
`curl --noproxy '*' -fsS http://127.0.0.1:8765/api/health` devolvió
`{"status":"ok"}`, código 0.

Se ejecutó Playwright con Chromium `/usr/bin/chromium`, abriendo
`http://127.0.0.1:5173/` y bloqueando mediante `context.route('**/*', ...)`
todas las solicitudes HTTP cuyo hostname no fuera `127.0.0.1` o `localhost`.
Se esperó la respuesta real de `/api/health` y el texto del elemento `role=status`.
Resultado: HTTP 200, `{"status":"ok"}`, UI **Servidor local conectado**,
0 errores de página y 0 solicitudes externas. El proxy Vite → FastAPI funcionó.
No hubo servicios cloud usados por la aplicación. Los servidores se detuvieron al terminar.

## Datos y pendientes

Ruta normal de SQLite: `%LOCALAPPDATA%/GestionInteligentePOS/data/pos.db` en Windows;
`~/.local/share/GestionInteligentePOS/data/pos.db` en otros sistemas.
No usar el override temporal anterior para datos reales.

No quedan verificaciones F1 fallidas o bloqueadas. Advertencias no bloqueantes:
Starlette depreca httpx en TestClient; npm informa deprecación de whatwg-encoding y
fin de soporte de ESLint 9. No se cambiaron versiones mayores ni decisiones arquitectónicas.
La distribución Windows y funcionalidades comerciales quedan para sus fases autorizadas.
