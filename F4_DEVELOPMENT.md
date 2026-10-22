# F4 — Caja e historial

## Diseño previo — 2026-10-22

El propietario aprobó la revisión de F3 y autorizó fusionar PR #3 y comenzar F4.
Merge F3: 3848d55ad84398e99e1907c404ddc5a426b861ff.
Rama: feat/f4-checkout-history desde ese main. No modificar ramas F1/F2/F3 ni comenzar F5.

Alcance: carrito por nombre/código, cantidades enteras, cotización del servidor,
confirmación manual de un único medio CASH/TRANSFER/DEBIT/CREDIT, historial y detalle,
anulación ADMIN con motivo y comprobante no fiscal imprimible desde el navegador.
Actualización del propietario durante F4: formato para térmicas de 58 mm, por ejemplo
Global o Waggs económicas. Se prepara ticket para controlador local de Windows y
reimpresión; modelo/enlace y prueba física pendientes. No afirmar compatibilidad universal
ni estado de papel/recepción física desde window.print. Detalle en docs/PRINTING.md.
Sin pasarelas, confirmación bancaria, pagos mixtos, descuentos, fiado, cierre de caja,
reportes F5, integración con impresora fiscal ni servicios externos.
Se conserva la propuesta de pago único ya concretada en DOMAIN_MODEL; la política
definitiva y compatibilidad con impresoras físicas se validarán en piloto.

Archivos previstos: migración aditiva 0004, ventas por capas, contrato de esquema,
pruebas SQLite/API, interfaz Caja/Historial, E2E y documentación/hallazgos.
Riesgos: sobreventa concurrente, respuesta perdida y doble registro, precio cambiado
sin confirmación, acceso a ventas ajenas, reversión repetida y fallos parciales.
Aceptación: todas las invariantes BR-001..009/011..014/016 de venta aplicables pasan,
datos anteriores preservados, operación local y verificaciones técnicas ejecutadas.
AT-005/015 de reportes, backup y Windows no forman parte de esta fase.

## Contratos y autorización

ADMIN y EMPLOYEE pueden cotizar/registrar ventas. EMPLOYEE solo consulta las suyas;
ADMIN consulta todas y filtra por usuario. Solo ADMIN anula. Sesión, Host/Origin, JSON,
HttpOnly y CSRF se conservan; el actor nunca se recibe como permiso desde el navegador.

- POST /api/sales/quote {items:[{product_id,quantity}]}: cotización actual sin escritura.
- POST /api/sales {items,payment_method,idempotency_key,quote_fingerprint}.
- GET /api/sales?user_id=&status=&limit=50&offset=0: historial paginado, máximo 100.
- GET /api/sales/{id}: detalle/comprobante autorizado con instantáneas históricas.
- POST /api/sales/{id}/void {reason}: anulación total, sin borrados ni devoluciones parciales.

DTO estrictos, extras rechazados, de 1 a 100 productos distintos y cantidades positivas.
No aceptar precios, subtotal, total, vendedor ni estado del cliente. Centavos enteros,
subtotales y total en 0..2^53−1. La UI siempre ingresa/muestra pesos argentinos.
La cotización devuelve nombre/código/precio/cantidad/subtotal, total y fingerprint SHA-256
del contenido económico canónico. Confirmar vuelve a calcular con productos vigentes;
si cambian nombre/código/precio devuelve 409 y exige revisar una nueva cotización.
El fingerprint detecta cambios; no concede permisos ni sustituye validación del servidor.
No reserva stock; se valida nuevamente al confirmar bajo bloqueo de escritura.

## Transacciones e idempotencia

BEGIN IMMEDIATE antes de leer sesión/stock para escribir. Crear cabecera, ítems con
nombre/código/precio histórico, un pago declarado por el total, movimientos SALE,
descuento de existencias y auditoría en la misma unidad. Sin stock o fallo: rollback.
UUID UNIQUE e hash del pedido normalizado (actor, productos/cantidades, método,
fingerprint). Mismo UUID/mismos datos devuelve la venta existente, incluso después de
cambiar el catálogo o anular; distinto actor/datos produce 409. No reintentar automáticamente.
La API devuelve 201 también al repetir una venta ya registrada, conservando su ID.

La UI guarda el intento confirmado en sessionStorage, separado por usuario, antes de
enviarlo. No contiene contraseñas, cookies ni tokens de sesión/CSRF. Si la respuesta
queda incierta, bloquea otra venta y permite reenviar exactamente el mismo intento,
incluso tras recargar/navegar; no descarta la clave por un error de transporte/5xx.
Solo una respuesta definitiva de rechazo o una venta recuperada libera el intento.
El borrador sin confirmar puede conservarse en la misma pestaña; nunca se envía solo.

Anular también usa BEGIN IMMEDIATE: validar ADMIN y motivo, leer instantáneas, comprobar
rango del stock restaurado, registrar movimientos VOID, actualizar estado/responsable/UTC
y auditoría juntos. Permitir devolver stock a productos inactivos conservando su estado.
Repetir anulación con el mismo motivo devuelve el registro; otro motivo devuelve 409.
Sin cambios de motivo histórico ni reposición repetida. Overflow rechaza toda la reversión.

## Persistencia y comprobante

0004 agrega sales, sale_items y payments; FK/CHECK/UNIQUE y restricciones de inmutabilidad.
La inserción del pago comprueba existencia de ítems y suma del total; después bloquea
agregar/modificar ítems o pagos. Cabecera económica e historial no se editan ni se borran.
Los casos de uso completan los invariantes entre tablas dentro de una sola transacción;
no se afirma que un INSERT SQL directo de una cabecera aislada constituya una venta válida.
Índice parcial impide repetir SALE/VOID para el mismo producto/venta. Se reutiliza
stock_movements y audit_events de F3 sin reconstruir tablas ni modificar migraciones publicadas.
El arranque exige 0004; autogeneración sigue bloqueada. Probar upgrade F3 con datos,
fallo intermedio y reintento, además de instalación nueva y reaplicación.

Comprobante React con datos históricos autorizados; encabezado «Comprobante no fiscal»,
ID, fecha Buenos Aires, vendedor, ítems, total, medio declarado y estado/anulación.
Impresión mediante window.print/CSS local, sin HTML interpolado ni ventanas remotas.
No inventar datos fiscales del comercio ni afirmar recepción bancaria del pago.

## Verificación prevista

SQLite temporal real: stock insuficiente/inactivo, cantidades/dinero inválidos, payload
manipulado, precio cambiado, última unidad concurrente, mismo UUID concurrente, doble
anulación, venta versus ajuste/anulación, rollback por fallo en pasos intermedios,
FK/CHECK/historia inmutable, permisos, persistencia y migración segura.
Ejecutar pytest, Ruff, Alembic en base nueva, Vitest, ESLint, build y E2E local con
solicitudes externas bloqueadas. Capturas reales, teclado/foco, móvil y comprobante impreso.
Registrar resultados reales al terminar; esta sección de diseño no certifica pruebas.

## Instalación y dependencias efectivas

Se conservaron backend/pyproject.toml, frontend/package.json y package-lock.json.
No se agregaron dependencias ni bibliotecas de impresora/animación. Se reutilizaron
venv/node_modules ya instalados; no se afirma una reinstalación innecesaria en esta fase.
Para una copia nueva: crear venv, pip install -e './backend[dev]' y npm --prefix frontend ci,
como indica README. No ejecutar bootstrap sobre una base que ya tiene ADMIN.

Entorno validado: Linux, Python 3.12.14, Node 24.19.0, npm 11.9.0; FastAPI 0.159.1,
Uvicorn 0.54.0, SQLAlchemy 2.1.6, Alembic 1.20.0, argon2-cffi 25.1.0,
pytest 9.1.1, httpx 0.28.1, Ruff 0.17.1; React/react-dom 19.3.1,
TypeScript 5.7.3, Vite 6.4.5, Vitest 2.1.9, ESLint 9.39.5,
Playwright 1.64.1, axe 4.14.0 y Chromium 154.0.8037.57 (/usr/bin/chromium).
La licencia Manrope local se conserva y la fuente se verifica renderizada con CDP.

## Comandos ejecutados y resultados reales — 2026-10-22

Desde backend:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m pip check
```

- Suite completa: **119 aprobadas, 0 fallidas**, 111.55 s. Incluye las 78 anteriores
  y 41 nuevas de ventas/migraciones. Se ejecutó también una prueba dirigida posterior
  al ampliar la comprobación de reintento con orden de líneas invertido: 1 aprobada.
  No se suma esa repetición como una prueba adicional.
- Ruff: All checks passed. pip check: No broken requirements found.
- Dos advertencias en la suite completa: deprecación Starlette/TestClient con httpx
  y advertencia interna FastAPI/Pydantic sobre alias de body durante prueba concurrente.
  No se suprimieron; respuestas/invariantes de las pruebas fueron correctas. Revisar en
  una actualización controlada de dependencias, sin declarar que son errores de negocio.

Migraciones CLI reales desde backend, sobre directorio nuevo creado para esa ejecución:

```sh
.venv/bin/python - <<'PY'
import os, subprocess, sys, tempfile
with tempfile.TemporaryDirectory(prefix='pos-f4-final-migration-') as folder:
    env = dict(os.environ, LOCALAPPDATA=folder)
    for command in [('upgrade', 'head'), ('current',), ('upgrade', 'head')]:
        subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.ini', *command],
                       env=env, check=True)
subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
PY
```

Resultado: 0001 → 0002 → 0003 → **0004_checkout_history (head)**, reaplicación sin
cambios, salida 0. El script solo elimina su propio directorio temporal. Las pruebas
también actualizan una copia F3 con filas reales y comprueban interrupción/reintento.
No se migraron, borraron ni restauraron datos de una instalación existente.

Desde frontend:

```sh
npm run test
npm run lint
npm run build
POS_TEST_CHROMIUM=/usr/bin/chromium \
POS_F4_CAPTURE_DIR=/workspace/gestion-inteligente-pos/docs/screenshots/f4 npm run test:e2e
```

- Vitest: **34 aprobadas, 0 fallidas**, cuatro archivos (20 anteriores y 14 nuevas).
- ESLint: salida 0, sin advertencias/errores.
- TypeScript/Vite: build correcto, incluido tipado E2E. JS principal 243.76 kB
  (76.42 kB gzip), módulo Caja/Historial diferido 16.87 kB (5.81 kB gzip),
  catálogo compartido 1.83 kB (0.97 kB gzip), CSS 18.57 kB (4.52 kB gzip), WOFF2 24.84 kB.
- Playwright: **1 flujo completo aprobado, 0 fallidos**, última ejecución en 29.3 s.
  Múltiples aserciones y
  repeticiones no se cuentan como casos adicionales. Resultado final publicado en el PR.
- Total: **154 pruebas aprobadas, 0 fallidas finales**. Esta cifra no certifica hardware.

Incidencias iniciales corregidas: TS2339 en guards de DTO, Ruff F811 en fixture
compartida y timeout E2E por selector de select nativo. Los resultados anteriores son
ejecuciones posteriores a las correcciones; no se presentó el intento fallido como verde.
Hallazgos con causa/fix/regresión: H-F4-001..008 en docs/ENGINEERING_FINDINGS.md.

## Verificación funcional y de seguridad

- Venta multilínea y de precio cero, cuatro medios de pago, cantidades estrictas,
  importes exactos, límite 100 ítems y overflow de subtotal/suma.
- Payload con precio/total/vendedor/estado manipulado rechazado; productos inactivos,
  sin stock y cotización con precio cambiado no crean venta ni movimiento parcial.
- Dos ventas por última unidad: 201/409 y stock cero. Mismo UUID concurrente: una venta,
  un pago y un movimiento. Otro actor/datos con esa clave: 409.
- Reintento normalizado por producto y después de editar/desactivar/anular conserva
  la venta original. Nombre/código/precio histórico no cambia con el catálogo.
- Fallos inducidos en movimiento, segundo producto, pago y auditoría revierten todas
  las tablas. Anulación concurrente aplica una sola reposición/evento.
- Anulación con producto inactivo repone stock conservando el estado; motivo distinto
  al repetir y overflow rechazan sin cambios. Fallo de auditoría no deja reversión parcial.
- Venta versus ajuste compiten por última unidad; anulación versus ajuste suman en
  orden serial sin perder actualizaciones.
- FK/CHECK y triggers probados con SQL directo: historia no editable/borrable y motivo
  de anulación no nulo. Prueba SQLite en memoria demostró el riesgo de CHECK con NULL.
- EMPLOYEE registra ventas a su nombre, no recibe ventas ajenas ni anula; ADMIN filtra
  por usuario/estado y consulta todo. Anónimo, CSRF faltante, sesión vencida y usuario
  desactivado son rechazados; toda la suite previa de Host/Origin/auth sigue ejecutada.
- Arranque incompatible rechazado. Upgrade F3 conserva filas exactas y sesión anterior;
  fallo DDL conserva el dump completo y reintento alcanza head.

## Navegador real y operación sin servicios externos

E2E crea su propia SQLite temporal y arranca FastAPI 127.0.0.1:8765 y Vite
127.0.0.1:5173. Operación real por proxy local y GET /api/health comprobado.
Reejecuta identidad y catálogo/inventario, añade Caja/Historial y bloquea toda solicitud
fuera de localhost/127.0.0.1: **0 intentos externos**, **0 errores JavaScript sin controlar**.

La cotización obsoleta produce rechazo visible y exige revisión del nuevo importe.
Luego route.fetch deja confirmar la venta y corta la respuesta al navegador. Se recarga,
sale/reingresa y reenvía el mismo UUID/pedido: una venta y comprobante recuperado.
Imprimir llama al diálogo simulado de prueba, sin generar otro POST. No se envió papel
real ni se afirmó que la impresora recibió el trabajo.

EMPLOYEE vende, ve solo sus ventas y recibe 403 por API al pedir una ajena/anular.
ADMIN consulta, filtra y anula con diálogo; Escape devuelve foco al invocador.
Un segundo reinicio real de Python conserva las dos ventas, pago, anulación y stock.
Teclado/foco, espera/doble envío, errores, movimiento reducido y Manrope local siguen
comprobados. Axe A/AA sin violaciones detectadas en las vistas auditadas; sin desborde
a 1366/390/320 px. No equivale a certificación integral de accesibilidad.

## Impresión de 58 mm y evidencias

El propietario pidió térmicas económicas Global/Waggs durante la implementación.
Se incorporó formato, impresión local mediante controlador y reimpresión, sin dependencias.
Modelo exacto/enlace solicitado y no recibido al cerrar la entrega; no hay dispositivo
físico Windows en este entorno. **Compatibilidad de hardware pendiente**, sin promesa
universal por marca y sin activar impresión silenciosa ni envío ESC/POS directo.

Chromium generó tres PDF reales con papel solicitado de 58 × 200 mm y contenido de
48 mm: normal, nombre largo/código de 64 caracteres y anulado. Se verificaron MediaBox,
ausencia de desborde, texto negro, navegación oculta y contenido extraído con pdftotext.
pdfinfo informó 165.12 × 567.12 pt (~58.25 × 200.07 mm) por redondeo del motor; la
prueba admite 0.5 mm de tolerancia. El controlador físico debe seleccionar 58 mm real;
un PDF nominal no demuestra su margen imprimible, papel, corte ni estado USB.

Comandos adicionales ejecutados:

```sh
pdfinfo docs/screenshots/f4/ticket-58mm.pdf
pdftotext docs/screenshots/f4/ticket-58mm-long.pdf -
pdftotext docs/screenshots/f4/ticket-58mm-voided.pdf -
```

Capturas reales y documentos (datos ficticios, sin campos secretos poblados):

- [Caja escritorio](docs/screenshots/f4/checkout-desktop.png) / [móvil](docs/screenshots/f4/checkout-mobile.png).
- [Venta incierta escritorio](docs/screenshots/f4/checkout-pending-desktop.png) / [móvil](docs/screenshots/f4/checkout-pending-mobile.png).
- [Comprobante escritorio](docs/screenshots/f4/receipt-desktop.png) / [móvil](docs/screenshots/f4/receipt-mobile.png).
- [Historial ADMIN](docs/screenshots/f4/history-desktop.png) / [móvil](docs/screenshots/f4/history-mobile.png).
- [Historial EMPLOYEE](docs/screenshots/f4/history-employee-desktop.png) / [móvil](docs/screenshots/f4/history-employee-mobile.png).
- [Confirmación de anulación](docs/screenshots/f4/void-confirmation-desktop.png).
- [Ticket PDF](docs/screenshots/f4/ticket-58mm.pdf) / [PNG de navegador](docs/screenshots/f4/ticket-58mm.png).
- [Ticket largo PDF](docs/screenshots/f4/ticket-58mm-long.pdf) / [PNG](docs/screenshots/f4/ticket-58mm-long.png).
- [Ticket anulado PDF](docs/screenshots/f4/ticket-58mm-voided.pdf) / [PNG](docs/screenshots/f4/ticket-58mm-voided.png).

## Archivos y publicación

- Nuevo backend por capas: app/api/sales.py, application/sales.py, domain/sales.py,
  infrastructure/sales.py y migración 0004_checkout_history.py; wiring y esquema de arranque.
- Pruebas nuevas: test_sales.py y test_sales_migrations.py. Se actualizan expectativas
  head de tests de migraciones anteriores, sin cambiar migraciones publicadas.
- Frontend: sales.ts (contratos, validación e intento/borrador), SalesWorkspace.tsx,
  navegación App.tsx, CSS y extensión E2E/configuración de timeout de acciones.
  Catorce casos nuevos en tests/sales.test.ts.
- Documentación: este informe, README, actualización de estado histórico F3 y specs
  PROJECT_SPEC, BUSINESS_RULES, DOMAIN_MODEL, ARCHITECTURE, PERSISTENCE, INSTALLATION,
  ROADMAP, DECISIONS, ACCEPTANCE_TESTS, DESIGN_SYSTEM, PRINTING, ENGINEERING_FINDINGS y checklist.
- Evidencia en docs/screenshots/f4; ninguna base SQLite ni secreto se versiona.

F3 fusionada por autorización en 3848d55. F4 se publica en feat/f4-checkout-history
y PR borrador hacia main; no se fusiona esta fase. Ramas F1/F2/F3 se conservan.

## Estado y pendientes

Software F4 implementado y verificado técnicamente. **F4 no se marca completamente
cerrada**: falta revisión del propietario y prueba física del modelo de impresora de
58 mm en Windows. Ver docs/PRINTING.md para procedimiento y evidencia faltante.
No hay verificaciones automatizadas pendientes/fallidas; esta limitación de hardware
se informa por separado y no se reemplaza con capturas/PDF.

Otros límites: impresión mediante diálogo, sin cola directa/estado/corte/cajón;
un único pago por venta y anulación total; sin reportes, descuentos, pago mixto ni fiado.
Intento/borrador recuperables en esa pestaña: cerrar definitivamente o borrar su storage
puede perder la identidad del intento, aunque la venta confirmada sigue en SQLite.
Consultar historial antes de volver a registrar una operación incierta en ese caso.
La distribución/impresoras concretas/backup y recuperación del navegador requieren
validación en PC objetivo/piloto. Recuperación de credenciales sigue pendiente de decisión.
No se inició F5 ni se promete instalador o piloto aprobado.
