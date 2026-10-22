# F2 — Identidad y usuarios

## Diseño previo a implementación (2026-10-22)

Alcance: identidad, sesión y empleados. Conserva F1; no incluye F3 ni operaciones comerciales.
Archivos previstos: backend/domain, application, infrastructure, api, migración 0002,
pruebas; frontend de identidad; documentación y dependencias. Riesgos principales:
carreras de bootstrap, robo/fijación de sesión, CSRF y permisos del archivo SQLite.
Aceptación: todas las verificaciones F1 y F2, concurrencia SQLite y flujo real del navegador.

- Argon2id con parámetros explícitos (64 MiB, 3 iteraciones, paralelismo 1).
  Contraseñas de 12 a 128 caracteres; usernames ASCII de 3 a 32, normalizados a minúsculas.
- Un comando local `python -m app.bootstrap` crea un secreto aleatorio de inicialización
  en un archivo de configuración privado, nunca en logs ni argumentos. La API guarda solo
  su SHA-256. El usuario lo introduce en un formulario password; no se almacena en el navegador.
  El comando se rechaza si ya existe una inicialización o un ADMIN. Token expira en 30 minutos.
- Inicialización mediante BEGIN IMMEDIATE, marcador singleton persistente y un índice único
  parcial para ADMIN. Creación de ADMIN, consumo del token y auditoría en una transacción.
  No hay endpoint de autorregistro ni creación de nuevos ADMIN.
- Sesiones aleatorias de 256 bits: solo SHA-256 en SQLite, expiración absoluta de 8 horas.
  Cookie pos_session HttpOnly, SameSite=Strict, Path=/api, sin Domain. HTTP exclusivamente
  loopback implica Secure=false; no usar este diseño sobre una red o bajo despliegue público.
  Login rota la sesión anterior. Logout y desactivación revocan sesiones en servidor.
- CSRF derivado con SHA-256 de la sesión y un prefijo de dominio; se entrega por /auth/me
  y login, se conserva solo en memoria y se exige en X-CSRF-Token para escrituras autenticadas.
  Todas las escrituras exigen Origin exacto permitido y Content-Type application/json;
  bootstrap y login se protegen también así. No habilitar CORS general.
- Orígenes: http://127.0.0.1:8765, http://localhost:8765 y sus equivalentes en puerto 5173.
  Host solo localhost/127.0.0.1. Nunca confiar en Forwarded o roles enviados por cliente.
- Roles consultados en SQLite en cada operación, junto con sesión y usuario activo.
  Alta/desactivación exclusivamente ADMIN, con autorización y escritura serializadas.
- Auditoría transaccional de inicialización, login correcto, logout, alta y desactivación:
  actor, objetivo y timestamp UTC; nunca passwords, hashes, tokens o identificadores de sesión.
- Recuperación: decisión del propietario pendiente. No se implementa reset, ADMIN alternativo,
  contraseña predeterminada ni bypass. No eliminar la base para recuperar acceso. Diseñar
  un procedimiento verificado y autorizado antes de ofrecer recuperación.
- Migración aditiva. No se ejecutarán downgrades ni migraciones contra datos existentes.
  Se rechaza downgrade F2 para evitar borrar identidad/auditoría accidentalmente.
- En Linux se crean directorios privados 0700 y archivos bootstrap 0600. Windows depende
  del perfil privado y ACL heredadas; validación de ACL y distribución sigue en F6.

## Contratos

GET /api/auth/setup: initialized boolean, sin secretos.
POST /api/auth/setup: username, password, setup_token → 201; 403 token inválido/vencido;
409 ya inicializado. POST /api/auth/login → usuario y csrf_token; 401 credenciales inválidas.
GET /api/auth/me → usuario y csrf_token; 401 sesión ausente, vencida o revocada.
POST /api/auth/logout → 204. GET/POST /api/employees y PATCH /api/employees/{id}
({is_active:false}) → 200/201; 403 rol insuficiente, 404 empleado inexistente,
409 username duplicado, 422 esquema inválido. No se permite activar ni editar ADMIN.
Escrituras sin Origin/JSON o con CSRF incorrecto → 403/415.


## Instalación y uso

Requisitos comprobados: Python 3.12.14, Node.js 24.19.0, npm 11.9.0.
Python mínimo 3.11, Node mínimo 22. Desde la raíz:
```sh
python -m venv backend/.venv
. backend/.venv/bin/activate
# Windows PowerShell: backend/.venv/Scripts/Activate.ps1
python -m pip install -e './backend[dev]'
cd backend
python -m alembic -c alembic.ini upgrade head
python -m app.bootstrap
python -m app
```

En otra terminal, desde frontend: `npm ci` y `npm run dev -- --strictPort`.
Abrir http://127.0.0.1:5173; el proxy /api apunta a 127.0.0.1:8765.
Leer el secreto del archivo indicado por bootstrap e introducirlo en el formulario password.
No usar argumentos de shell ni compartir su contenido. Eliminar el archivo después de crear
ADMIN. Si vence antes de usarse, ejecutar `python -m app.bootstrap --renew` para revocarlo y
crear uno nuevo. Después de inicializar, ambos comandos rechazan regenerar ADMIN.
La generación del secreto puede repetirse con --renew ante una falla de disco, siempre
antes de completar la inicialización. No existe recuperación de contraseñas en F2.

Dependencias agregadas:
- argon2-cffi 25.1.0; transitivas argon2-cffi-bindings 26.1.0, cffi 2.1.1, pycparser 3.11.
- @playwright/test 1.64.1 (solo desarrollo), playwright y playwright-core de la misma versión.
- Sin nuevas dependencias frontend de producción. Versiones exactas en package-lock.json.
  Dependencias previas del backend: ver F1_DEVELOPMENT.md; no se cambian sus rangos.

## Verificaciones iniciales (2026-10-22, antes de la revisión)

Con el entorno virtual activado, desde backend:
```sh
python -m pytest -q
python -m ruff check .
python -m pip check
POS_F2_DATA_ROOT=$(mktemp -d /tmp/pos-f2-final.XXXXXX)
LOCALAPPDATA="$POS_F2_DATA_ROOT" python -m alembic -c alembic.ini upgrade head
LOCALAPPDATA="$POS_F2_DATA_ROOT" python -m alembic -c alembic.ini current
```
`LOCALAPPDATA` en estas verificaciones apunta exclusivamente a una carpeta temporal nueva.
También se ejecutó upgrade head repetido y el recorrido baseline → head en bases nuevas.
No se ejecutaron downgrades ni operaciones sobre una instalación real.

Desde frontend:
```sh
npm ci --cache /tmp/gestion-pos-npm-cache
npm run test
npm run lint
npm run build
POS_TEST_CHROMIUM=/usr/bin/chromium npm run test:e2e
```

E2E usa Chromium local preinstalado y Playwright. En otro equipo se puede instalar el
navegador con `npx playwright install chromium` y ejecutar `npm run test:e2e`.
`POS_TEST_PYTHON` permite elegir el Python del entorno virtual (por defecto backend/.venv).
La prueba requiere puertos 5173 y 8765 libres; nunca reutiliza servidores existentes.
Crea y elimina solo su propia carpeta temporal, inicia y detiene Vite/Python y reinicia
Python conservando SQLite. No graba screenshots, videos, trazas ni cookies en el repositorio.

| Verificación | Resultado final |
| --- | --- |
| pytest | 32 aprobadas, 0 fallidas; 1 warning de deprecación de Starlette/HTTPX |
| Ruff | All checks passed; código 0 |
| pip check | Sin dependencias rotas; código 0 |
| Alembic upgrade head | Aplicadas 0001 y 0002; código 0 |
| Alembic current | 0002_identity (head); código 0 |
| npm ci | Instalación desde lockfile; código 0 |
| Vitest | 6 aprobadas, 0 fallidas, 2 archivos |
| ESLint | Sin errores; código 0 |
| TypeScript + Vite | Build aprobado; 31 módulos; código 0 |
| Playwright/Chromium | 1 flujo E2E aprobado, 0 fallidos |

Total: **39 pruebas aprobadas, 0 fallidas** (32 backend + 6 frontend + 1 E2E).
Build: HTML 0.37 kB, CSS 0.65 kB, JS 230.00 kB (71.85 kB gzip).
La suite conserva health, Host, PRAGMA y persistencia del baseline de F1.

La prueba E2E verificó inicialización, login ADMIN, alta de empleado, login EMPLOYEE,
403 al consultar administración, reinicio real del backend, persistencia de ambas sesiones,
desactivación, revocación, rechazo de login desactivado y logout. La UI mostró
Servidor local conectado mediante GET /api/health. Cero solicitudes externas y cero errores
de página; el contexto del navegador aborta toda solicitud HTTP fuera de loopback.

Pruebas SQLite adicionales: bootstrap simultáneo 201/409 con un único ADMIN;
rollback completo si falla auditoría de bootstrap o alta; expiración absoluta; sesiones
rotadas/revocadas; desactivación entre verificación Argon2 y emisión de sesión; permisos
POSIX; hashes Argon2id y sesiones SHA-256; ausencia de secretos en auditoría/errores.

## Incidencias resueltas durante la validación

- Se corrigieron imports/estilo indicados por Ruff.
- Se eliminó una advertencia del test HTTPX usando content en vez de data para texto crudo.
- Primer intento E2E: puerto 5173 ocupado por Vite de una verificación previa; la prueba
  abortó sin usarlo. Se detuvo ese proceso propio y el flujo se ejecutó correctamente.
- Se unificó la creación de SQLite en Alembic y aplicación para evitar permisos públicos
  al crear la base desde migraciones. El archivo y las carpetas se verificaron en POSIX.

## Estado y límites

F2 completada; F3 no iniciada. No se crearon productos, inventario ni ventas.
No hay verificaciones F2 fallidas o bloqueadas. No se cambiaron decisiones aceptadas.
Recuperación de credenciales sigue pendiente del propietario y no se ofrece un bypass.
ACL/instalador en Windows, cierre de aplicación distribuida y protección del equipo local
requieren la validación de F6; esta evidencia se obtuvo en Linux.
Continúan las advertencias de Starlette/HTTPX y deprecación de paquetes npm heredadas de F1.
No se utilizaron servicios cloud como dependencia operativa de la aplicación.

## Archivos de esta entrega

- `.gitignore`
- `F2_DEVELOPMENT.md`
- `README.md`
- `backend/alembic/env.py`
- `backend/alembic/versions/0002_identity.py`
- `backend/app/api/__init__.py`
- `backend/app/api/identity.py`
- `backend/app/application/__init__.py`
- `backend/app/application/identity.py`
- `backend/app/bootstrap.py`
- `backend/app/domain/__init__.py`
- `backend/app/domain/identity.py`
- `backend/app/infrastructure/database.py`
- `backend/app/infrastructure/identity.py`
- `backend/app/infrastructure/passwords.py`
- `backend/app/main.py`
- `backend/pyproject.toml`
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/test_health.py`
- `backend/tests/test_identity.py`
- `backend/tests/test_migrations.py`
- `docs/ACCEPTANCE_TESTS.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/DOMAIN_MODEL.md`
- `docs/INSTALLATION.md`
- `docs/PERSISTENCE.md`
- `docs/ROADMAP.md`
- `frontend/e2e/identity.spec.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `frontend/src/App.tsx`
- `frontend/src/identity.ts`
- `frontend/src/style.css`
- `frontend/tests/identity.test.ts`
- `frontend/tsconfig.node.json`
- `frontend/vitest.config.ts`


## Correcciones posteriores a la revisión — 2026-10-22

La validación inicial de 39 pruebas no cubría tres fallos reproducidos en la revisión.
Se corrigieron sin modificar la migración 0002 publicada ni tocar datos existentes:

| Hallazgo | Fix | Regresión |
| --- | --- | --- |
| H-F2-001: DDL parcial tras una interrupción | BEGIN IMMEDIATE físico y transactional_ddl=True; liberación de recursos en finally | Fallo intermedio, rollback de tablas/revisión y reintento exitoso |
| H-F2-002: arranque con esquema incompatible | Validación previa de revisión exacta, tablas y columnas; rechazo antes de habilitar API | Base vacía, anterior, futura, tabla/columna ausentes y base válida |
| H-F2-003: metadatos vacíos proponían borrados | target_metadata=None bloquea autogeneración; migraciones manuales | CLI rechaza --autogenerate sin modificar datos ni archivos |

Causas, reproducciones, límites y prácticas preventivas:
[ENGINEERING_FINDINGS.md](docs/ENGINEERING_FINDINGS.md).
Checklist para reutilizar en otro proyecto: [PROJECT_REVIEW_CHECKLIST.md](docs/PROJECT_REVIEW_CHECKLIST.md).
AGENTS.md exige consultar esos aprendizajes en futuras tareas pertinentes de este repositorio.

Comandos ejecutados, desde backend con su entorno virtual:
```sh
python -m pytest tests/test_migrations.py tests/test_schema.py -q
python -m pytest -q
python -m ruff check .
POS_FIX_DATA_ROOT=$(mktemp -d /tmp/pos-f2-fixes.XXXXXX)
LOCALAPPDATA="$POS_FIX_DATA_ROOT" python -m alembic -c alembic.ini upgrade head
LOCALAPPDATA="$POS_FIX_DATA_ROOT" python -m alembic -c alembic.ini current
LOCALAPPDATA="$POS_FIX_DATA_ROOT" python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini upgrade head --sql
python -m pip check
```

Desde frontend: `npm run test`, `npm run lint`, `npm run build` y
`POS_TEST_CHROMIUM=/usr/bin/chromium npm run test:e2e`.

Resultados reales finales:
- Regresiones dirigidas: 9 aprobadas (incluidas en la suite completa).
- Backend: 40 aprobadas, 0 fallidas; Ruff aprobado; pip check sin dependencias rotas.
- Migraciones: upgrade y reaplicación correctos; current = 0002_identity (head).
- SQL offline: generado con BEGIN/COMMIT, sin aplicarlo a ninguna base.
- Frontend: 6 pruebas aprobadas; lint y build aprobados.
- Chromium: 1 E2E aprobada, incluyendo reinicio real y comunicación sin solicitudes externas.
- Total actualizado: **47 pruebas aprobadas, 0 fallidas**, sin sumar dos veces las dirigidas.
- No se agregaron dependencias. Se configuró path_separator=os para evitar la advertencia
  nueva de Alembic al ejecutar pruebas programáticas; persiste el warning previo de Starlette/HTTPX.

Las migraciones siguen siendo manuales. El rechazo de --autogenerate es una protección
intencional, no un comando de desarrollo habilitado. Para habilitarlo en el futuro se requiere
un modelo completo y una comparación sin diferencias contra una base en head.

El arranque no modifica la revisión ni repara estructuras. Si una instalación ya quedó
parcialmente migrada con una versión anterior, detenerla y preparar un plan de recuperación
con respaldo y revisión humana; estos fixes no borran automáticamente sus tablas residuales.
F2 permanece completada tras esta revalidación. F3 no iniciada.

Archivos de los fixes: AGENTS.md, backend/alembic.ini, backend/alembic/env.py,
backend/app/main.py, backend/app/infrastructure/schema.py, backend/tests/test_health.py,
backend/tests/test_migrations.py, backend/tests/test_schema.py y documentación enlazada.
