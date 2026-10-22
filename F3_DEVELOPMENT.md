# F3 — Catálogo e inventario

## Diseño previo a la implementación — 2026-10-22

Rama feat/f3-catalog-inventory desde main 058a92f, después del merge autorizado del diseño.
Alcance: categorías, productos, edición/desactivación y ajustes manuales de existencias.
Sin ventas, caja, pagos, importación CSV ni reportes de F4/F6. Sin servicios cloud.

Capas: contratos HTTP Pydantic, casos de uso, puertos de persistencia e infraestructura
SQLAlchemy/SQLite. Se reutilizan sesiones, validación Host/Origin y CSRF de F2.
Cambios previstos: migración 0003, catálogo/inventario por capas, contrato de arranque,
interfaz con Manrope/amarillo, pruebas de DB/API/UI y documentación.

Riesgos a verificar: stock negativo por concurrencia, pérdida de auditoría por fallo parcial,
precios decimales redondeados, doble ajuste tras reintento, permisos y preservación de F2.
Aceptación: escrituras ADMIN exclusivamente; datos tipados y restricciones reales SQLite;
transacciones atómicas; persistencia después de reiniciar; tests/lint/build/E2E aprobados.

## Auditoría sin pérdida de datos

La tabla audit_log de F2 tiene FK entity_id → users, que no admite productos/categorías.
0003 agrega audit_events como registro general, copia todos los eventos previos y conserva
la tabla audit_log intacta para compatibilidad. Los nuevos eventos de identidad se escriben
en ambas tablas en la misma transacción; catálogo/inventario usa audit_events. No se deben
sumar ambas tablas al consultar la auditoría general. Actor siempre FK a users; entity_id
es una referencia polimórfica validada por los casos de uso, no una FK a una sola entidad.
No se ejecutan DROP ni reconstrucciones destructivas. Se prueba la conservación exacta
de eventos de identidad, hashes y sesiones al actualizar desde 0002.

## Reglas concretas

- API monetaria en enteros de centavos; UI convierte texto decimal sin multiplicar floats.
  Cantidades enteras. Se rechazan booleanos, fracciones y enteros fuera de rango seguro de JS
  (0 a 2^53−1) para evitar truncamientos de transporte y almacenamiento.
- Código opcional como string, preservando ceros iniciales; espacios externos se recortan,
  cadena vacía se almacena como NULL. Códigos no vacíos únicos, incluidos productos inactivos.
- Stock no se modifica desde PATCH de producto: únicamente carga inicial o ajuste con motivo.
- Productos nuevos: stock inicial por defecto 0; si es positivo exige motivo y crea INITIAL.
- Ajustes: delta entero no cero, motivo de 3–240 caracteres, usuario y antes/después.
  BEGIN IMMEDIATE para validar/escribir. Resultado nunca negativo ni fuera de rango.
- Cada ajuste exige idempotency_key UUID. Un reintento idéntico del mismo actor devuelve
  el movimiento existente; misma clave con datos distintos devuelve 409, sin doble ajuste.
- No hay DELETE de productos/categorías. Desactivación preserva movimientos e historia.
  Producto inactivo no admite ajuste. ADMIN puede reactivar productos/categorías.
- Categoría organiza catálogo: desactivarla no desactiva sus productos automáticamente.
  No asignar productos nuevos a categoría inactiva; los existentes pueden conservarla.
- EMPLOYEE consulta productos/categorías activos, precio de venta y stock. No recibe costos,
  no consulta movimientos y no puede gestionar catálogo ni ajustar inventario.
- Paginación acotada, búsqueda por nombre/código, filtros de categoría/activo/stock bajo.

## Contratos HTTP

Todos requieren sesión; escrituras requieren ADMIN, Origin, JSON y X-CSRF-Token.
GET /api/categories; POST /api/categories {name}; PATCH /api/categories/{id} {name?,is_active?}.
GET /api/products?search=&category_id=&active_only=true&low_stock=false&limit=50&offset=0;
GET /api/products/{id}; POST /api/products; PATCH /api/products/{id}.
POST /api/stock/adjustments {product_id,quantity_delta,reason,idempotency_key}.
GET /api/stock/movements?product_id=&limit=50&offset=0 (solo ADMIN).

Creación de producto: name, code?, category_id?, price_cents, cost_cents?, minimum_stock=0,
initial_stock=0, initial_reason?; el servidor decide stock_quantity e is_active=true.
PATCH admite name/code/category_id/price_cents/cost_cents/minimum_stock/is_active y
rechaza campos ajenos, null en obligatorios y cambios directos de stock.
Respuestas: 201 creación/ajuste (también al repetir el mismo ajuste, con idéntico movimiento),
200 consulta/edición; 401 sin sesión,
403 sin permiso/CSRF, 404 inexistente, 409 duplicado/conflicto/stock insuficiente, 422 inválido.

## Implementación y uso

ADMIN dispone de Equipo, Catálogo e Inventario; EMPLOYEE de Mi cuenta y Catálogo.
Catálogo permite crear/editar categorías y productos, desactivar/reactivar, buscar por
nombre/código, filtrar por categoría, stock bajo e inactivos y paginar de a 20 productos.
No hay datos de negocio simulados en la aplicación. El stock inicial positivo requiere
motivo; Inventario registra ajustes con motivo y presenta los últimos 100 movimientos
del producto, indicando si existen más. La API ofrece paginación de movimientos.

Se conserva inicialización, autenticación, logout, expiración, revocación, cookies,
validación Host/Origin y CSRF de F2. Sin recuperación de credenciales ni bypass nuevos.
La UI mantiene la clave UUID de ajuste tras un error de respuesta para un reintento
manual idéntico, y descarta la clave después de confirmar. El servidor resuelve carreras.
Las altas/ediciones de producto no prometen idempotencia: el bloqueo de doble envío es
de interfaz y los códigos no nulos son únicos. Los ajustes sí son idempotentes en DB.

## Instalación y dependencias

No se agregaron ni cambiaron dependencias respecto del diseño aprobado. package-lock.json
se conserva. Instalación desde una copia nueva, con las dependencias de desarrollo:

```sh
python -m venv backend/.venv
. backend/.venv/bin/activate
python -m pip install -e './backend[dev]'
npm --prefix frontend ci
```

En esta fase se reutilizaron los entornos ya instalados; no se afirma haber reinstalado
dependencias al no requerir cambios. pip check y npm ls --depth=0 se ejecutaron correctamente.
Para iniciar localmente, seguir README: migración explícita, bootstrap solo en una base
nueva sin ADMIN, python -m app y Vite en loopback. No migrar datos comerciales para validar.

Entorno real Linux: Python 3.12.14, Node v24.19.0, npm 11.9.0; FastAPI 0.159.1,
Uvicorn 0.54.0, SQLAlchemy 2.1.6, Alembic 1.20.0, argon2-cffi 25.1.0,
pytest 9.1.1, httpx 0.28.1 y Ruff 0.17.1. React/react-dom 19.3.1,
TypeScript 5.7.3, Vite 6.4.5, Vitest 2.1.9, ESLint 9.39.5,
Playwright 1.64.1 y @axe-core/playwright 4.14.0. Chromium 154.0.8037.57 del sistema,
en /usr/bin/chromium.
Sin nuevas dependencias de producción ni bibliotecas de animación.

## Comandos ejecutados y resultados — 2026-10-22

Desde backend, con el Python del venv:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m pip check
```

- pytest: **78 aprobadas, 0 fallidas**, última suite completa en 72.49 s.
  Incluye las 40 de F1/F2 y 38 nuevas de catálogo/migraciones.
- Ruff: All checks passed.
- pip check: No broken requirements found.
- Advertencia no bloqueante de Starlette: uso de httpx con TestClient en deprecación;
  no se suprimió ni se cambió una dependencia para ocultarla. Reevaluar antes de actualizar.

Migración CLI ejecutada con un directorio nuevo y aislado mediante este script desde backend:

```sh
.venv/bin/python - <<'PY'
import os, subprocess, sys, tempfile
with tempfile.TemporaryDirectory(prefix='pos-f3-final-migration-') as folder:
    env = dict(os.environ, LOCALAPPDATA=folder)
    for command in [('upgrade', 'head'), ('current',), ('upgrade', 'head')]:
        subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.ini', *command],
                       env=env, check=True)
PY
```

Resultado: 0001 → 0002 → **0003_catalog_inventory (head)**; reaplicación sin cambios,
todos con salida 0. El directorio temporal creado por el script se elimina al salir;
ninguna base comercial ni archivo preexistente fue modificado. Pytest prueba además
upgrade con datos F2, fallo intermedio, conservación y reintento.

Desde frontend:

```sh
npm run test
npm run lint
npm run build
POS_TEST_CHROMIUM=/usr/bin/chromium \
POS_F3_CAPTURE_DIR=/workspace/gestion-inteligente-pos/docs/screenshots/f3 npm run test:e2e
```

- Vitest: **20 aprobadas, 0 fallidas**, tres archivos (6 anteriores y 14 nuevas).
- ESLint: salida 0, sin errores ni advertencias.
- TypeScript y Vite: compilación de producción correcta, incluyendo tipado del E2E.
  JS principal 242.65 kB (76.05 kB gzip), catálogo diferido 14.39 kB (4.96 kB gzip),
  CSS 14.53 kB (3.74 kB gzip), WOFF2 24.84 kB. Sin dependencias nuevas.
- Playwright: **1 flujo completo aprobado, 0 fallidos**, última ejecución en 18.1 s.
  Es una única prueba con múltiples
  pasos; no se cuentan las aserciones internas como pruebas independientes.
- Total de la validación: **99 pruebas aprobadas, 0 fallidas**. Las repeticiones de las
  suites no se suman como pruebas adicionales.

La primera ejecución de las pruebas nuevas detectó un uso inválido de TestClient.delete
con json en el propio test; se corrigió a request('DELETE', ...), conservando la expectativa
405 del contrato sin borrado. Ruff detectó una variable sin uso y ESLint señaló una
dependencia inestable del efecto de movimientos; ambos corregidos. Los resultados anteriores
son de ejecuciones posteriores reales. Los hallazgos de producto y prevención están en
[ENGINEERING_FINDINGS.md](docs/ENGINEERING_FINDINGS.md), H-F3-001 a H-F3-006.

## Seguridad, concurrencia y persistencia verificadas

- SQLite real por caso de prueba, nunca una base con datos de usuario.
- Permisos ADMIN en servidor: EMPLOYEE no crea/edita categorías, productos, precios ni
  stock y no consulta movimientos. Ocultar controles no es la defensa de permisos.
- Anónimo 401 y escritura sin CSRF 403. Se ejecuta también toda la suite de seguridad F2.
- Precio/costo/cantidades estrictos, códigos con ceros, duplicados, Unicode, filtros,
  paginación, null/edición parcial y rechazo de stock por PATCH.
- Dos ajustes concurrentes de la última unidad: 201 y 409, un movimiento y stock cero.
- Dos ajustes con el mismo UUID: un único movimiento. Reutilizar clave con datos distintos
  produce 409; repetir datos válidos devuelve el movimiento previo.
- Stock negativo y overflow rechazados; SQL directo confirma CHECK, FK y rangos.
- Fallo inducido de auditoría revierte alta con stock inicial y ajuste completo.
- Desactivar preserva registros; producto inactivo no se ajusta. Reactivación disponible.
- Upgrade F2→F3 conserva exactamente usuarios/hashes, sesiones, bootstrap y auditoría;
  una sesión creada antes del upgrade sigue válida. No se ejecutaron downgrades.
- Fallo inyectado a mitad de 0003 conserva el dump F2 completo; reintento llega a head.
- Reinicio real de Python en E2E conserva sesiones, producto, stock 4 e historial de
  tres movimientos. El ajuste fallido no creó movimiento ni cambió existencias.

## Navegador, comunicación y capturas

Playwright inicia FastAPI 127.0.0.1:8765 y Vite 127.0.0.1:5173 con datos ficticios,
confirma health y opera las APIs reales por el proxy local. Hace setup, login ADMIN y
EMPLOYEE, alta/desactivación de empleado, categoría, alta/edición/desactivación/reactivación
de producto, ajuste positivo/negativo, rechazo por stock insuficiente, reinicio y logout.
Solicitudes externas bloqueadas: **0 intentos externos**, **0 errores JavaScript**.
Manrope local descargada con 200 y fuente real renderizada verificada con CDP.

Se comprueban teclado/foco, diálogo y sus extremos Tab/Escape, errores, carga/doble envío,
prefers-reduced-motion y axe A/AA sin violaciones detectadas. Catálogo/inventario se analizan
en 1366 y 390 px y no desbordan tampoco a 320 px. La revisión visual mejoró los filtros
móviles; el historial se prueba seleccionando dos veces el mismo producto.
No equivale a certificación integral WCAG ni prueba con todos los lectores de pantalla.

Capturas PNG reales de Chromium, fullPage, sin campos secretos poblados:
Se vuelve al inicio antes de capturar cada ancho para estabilizar elementos fijos tras
los cambios de viewport y foco, sin ocultar ni reemplazar contenido del producto.

- [Catálogo escritorio](docs/screenshots/f3/catalog-desktop.png)
- [Catálogo móvil](docs/screenshots/f3/catalog-mobile.png)
- [Inventario escritorio](docs/screenshots/f3/inventory-desktop.png)
- [Inventario móvil](docs/screenshots/f3/inventory-mobile.png)

## Archivos y entrega

- Backend: nuevo catálogo en api/application/domain/infrastructure, migración 0003,
  registro dual de identidad, función SQLite casefold, verificador de esquema y wiring.
- Pruebas: test_catalog.py, test_catalog_migrations.py, expectativas de test_migrations.py;
  catalog.test.ts y extensión del flujo Playwright existente.
- Frontend: CatalogWorkspace.tsx, cliente catalog.ts, navegación App.tsx, estilos y
  ConfirmDialog reutilizable sin cambiar comportamiento de confirmación de empleados.
- Documentación: este archivo, README, ROADMAP, ARCHITECTURE, PERSISTENCE, DOMAIN_MODEL,
  BUSINESS_RULES, ACCEPTANCE_TESTS, INSTALLATION, DECISIONS, DESIGN_SYSTEM, estado posterior
  en FRONTEND_DESIGN_VALIDATION, ENGINEERING_FINDINGS y PROJECT_REVIEW_CHECKLIST.
- Cuatro capturas de navegador en docs/screenshots/f3.

El diseño original está fusionado mediante PR #2, merge **058a92f**. F3 se publica por
separado en **feat/f3-catalog-inventory**, desde ese main, para revisión humana.
Las ramas F1 y F2 no se modifican. No se fusiona F3 ni se inicia F4 sin nueva autorización.

## Limitaciones y pendientes

No quedan verificaciones técnicas fallidas de F3. Pendientes: revisión humana de la
extensión visual/flujo, piloto con comercio, Windows/instalador/respaldos (F6), otros
navegadores y lectores de pantalla, y política del propietario para recuperar credenciales.
Catálogo usa búsqueda al enviar el formulario, paginación simple e historial UI de los
últimos 100 movimientos; no hay importación CSV, visor general de auditoría ni reportes.
No se implementaron caja, ventas, pagos, anulación ni otras funciones F4.
