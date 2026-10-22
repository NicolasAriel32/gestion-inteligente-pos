# F5 — Dashboard y reportes

## Diseño previo — 2026-10-22

Autorización: instrucción explícita del propietario para implementar F5 y publicar PR
borrador, sin fusionar ni comenzar F6. Baseline main 95d2ada, producto 0.4.0,
esquema 0004_checkout_history. Rama feat/f5-dashboard-reports; F1–F4 intactas.

Incremento: dominio de períodos/dinero, servicio con puerto de lectura, adaptador SQLite,
GET /api/reports/summary tipado en OpenAPI, vista Reportes ADMIN, pruebas y evidencia.
El contrato devuelve en una sola respuesta KPIs actuales/anteriores, diferencias absolutas
y porcentuales, dos rankings top 10 y 24 horas locales. Así la pantalla entera comparte
una única instantánea; los endpoints separados previstos en ARCHITECTURE no son necesarios.
No hay cambio de esquema, índices ni dependencias de ejecución inicialmente previstos.

Períodos: calendario America/Argentina/Buenos_Aires (zoneinfo); persistencia UTC.
Intervalos semiabiertos [inicio, fin), fechas personalizadas inclusivas, 1..366 días,
años 2000..2099, sin días futuros. Hoy/7/30 incluyen hoy hasta el instante de consulta;
ayer y rangos pasados incluyen días completos. Si termina hoy se corta en ahora.
Comparación: trasladar ambos extremos locales hacia atrás la cantidad de días calendario
seleccionada; misma cantidad de días y mismo corte horario local. Se exponen ambos
intervalos UTC y etiquetas locales exactas, incluso cuando hay días históricos con
cambios de offset. No se extrapolan ingresos ni se compara un parcial con un día completo.

Dinero/cantidades agregados: strings decimales de enteros no negativos en JSON.
SQLite usa agregado pos_sum implementado en Python (enteros arbitrarios, devuelve texto)
y nunca SUM/total/float para dinero/unidades. Cabeceras e ítems se agregan por separado
para no multiplicar facturación/tickets. Ticket medio redondea al centavo, mitad hacia
arriba, solamente al mostrar; comparación del promedio usa fracciones exactas.
Porcentajes: string con signo en centésimas de porcentaje (basis points), mitad alejándose
de cero. Base cero produce null (UI «Sin base de comparación»); ambos cero produce 0.
JS valida strings y calcula/formatea con BigInt, sin convertir importes a Number.
IDs/horas pequeños conservan números. Empates de ranking: métrica descendente, ID ascendente;
nombre/código de la última instantánea válida del producto en el período (fecha, ID).
Hora pico por tickets, todas las horas empatadas; sin ventas no hay hora pico.

Consistencia: BEGIN de lectura explícito antes de autorizar y consultar; no alcanza el
contexto SQLAlchemy con sqlite3 legacy. WAL permite escritores sin mezclar estados.
Consultas con límites temporales y estado COMPLETED, índices de fecha y sale_id existentes,
rankings limitados a 10, salida horaria fija 24. Sin joins a catálogo/usuarios activos.
Riesgos: overflow SQLite/JS, joins duplicados, lectura partida ante anulación, límites
locales y respuestas antiguas en UI. Validar cada uno con SQLite/API y navegador reales.

Aceptación: AT-005/015, permisos ADMIN efectivos, historia estable, exactitud y períodos,
estados carga/vacío/error/reintento, teclado/móvil/contraste y operación sin servicios
externos; suite F1–F4, Ruff, migraciones nuevas, frontend/lint/build y E2E completos.
La impresión física de 58 mm, Windows/piloto y F6 continúan pendientes.

### Ajuste del diseño tras inspeccionar índices (antes de migrar)

El índice F4 sales_user_date empieza por usuario, y no acota reportes globales por fecha.
Se añade únicamente índice sales_report_date(status,created_at_utc,id,total_cents) mediante
0005_reporting_indexes. Cubre cabeceras y permite buscar COMPLETED por rango; los ítems
usan UNIQUE(sale_id,product_id). Sin reconstrucciones ni cambios económicos/históricos.
El arranque F5 exige 0005 y el índice; se probarán upgrade F4 preservando filas, fallo
tras CREATE INDEX/reintento, revisión anterior/futura e índice ausente. Se conserva toda
migración publicada. No hay cambios de dependencias ni nueva tabla.

### Zona horaria portable

Python zoneinfo requiere datos IANA que Windows no suele incluir. Se declara tzdata
>=2025.2,<2027 como única dependencia nueva de ejecución, distribuida al instalar;
no descarga nada al operar. Se conserva zoneinfo y se verifica fallback con PYTHONTZPATH
vacío. No certifica el instalador Windows ni cambia la decisión local-first.

## Implementación entregada

Reportes disponible exclusivamente para ADMIN en navegación y API. GET
/api/reports/summary?period=today|yesterday|7d|30d|custom&start=YYYY-MM-DD&end=YYYY-MM-DD
contiene timezone, period/previous_period (UTC y local), current/previous, comparison,
top_units/top_revenue, hours y peak_hours. OpenAPI define DTOs con patrones decimales,
24 horas locales y métricas exactas. Los parámetros start/end solo se admiten en custom.
Sin datos simulados, exportación CSV, backups, instalador ni nuevos casos comerciales.

Archivos: backend domain/application/infrastructure/api/reporting.py; registro de
agregados SQLite en database.py, wiring en main.py, migración 0005 y contrato schema.py.
Pruebas test_reporting.py/test_reporting_migrations.py y expectativas head anteriores.
Frontend reporting.ts, ReportsWorkspace.tsx, navegación App.tsx y estilos propios;
11 pruebas Vitest y extensión del flujo E2E existente. README, specs vigentes, ADR-012,
hallazgos H-F5-001..005, checklist y versiones actualizados. Evidencia F1–F4 preservada.

## Entorno, instalación y versiones

Linux; Python 3.12.14, Node 24.19.0, npm 11.9.0, Chromium 154.0.8037.57 del sistema.
Instalación limpia: python -m venv backend/.venv; backend/.venv/bin/pip install -e
'./backend[dev]'; npm --prefix frontend ci. Solo la preparación requiere repositorios de
paquetes; la operación E2E bloquea solicitudes externas. tzdata se añadió después con
pip install 'tzdata>=2025.2,<2027' y se reinstaló editable --no-deps al alinear versiones.
FastAPI 0.159.1, SQLAlchemy 2.1.6, Alembic 1.20.1, argon2-cffi 25.1.0, pytest 9.1.1,
httpx 0.28.1, Ruff 0.17.1, tzdata 2026.5. Frontend conserva exactamente package-lock
transitivo de main; React/ReactDOM 19.3.1, TypeScript 5.7.3, Vite 6.4.5 y Vitest 2.1.9.
La única dependencia directa nueva es tzdata; no hay bibliotecas de gráficos/animaciones.

Paquete Python, metadata instalada, FastAPI, OpenAPI, package.json y dos raíces del
lockfile: **0.5.0** (siete valores comprobados con tomllib/importlib.metadata/JSON).
Comparación estructural del lockfile contra main normalizando solo versiones raíz:
idéntico. No se crearon tags ni release. Esquema independiente **0005_reporting_indexes**.

## Verificación ejecutada — 2026-10-22

Desde backend:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m pip check
```

Resultado final **142 aprobadas, 0 fallidas**, 111.60 s; incluye 119 anteriores y 23
nuevas de F5. Ruff: All checks passed. pip check: No broken requirements found.
Advertencia conservada: Starlette depreca TestClient/httpx; no se sustituyeron herramientas
ni se ocultó el aviso. Primera suite completa antes de añadir caso de hora pico:
141 aprobadas, 104.34 s; no se suman ejecuciones repetidas como nuevos casos.

Migraciones CLI reales en TemporaryDirectory(prefix='pos-f5-final-migration-'), con
LOCALAPPDATA apuntando a ese directorio: python -m alembic -c alembic.ini upgrade head,
current y upgrade head otra vez. Resultado 0001→0002→0003→0004→**0005 (head)**;
reaplicación sin cambios, salida 0. Los tests incluyen upgrade desde F4 con venta/pago,
conservación exacta de todas las filas/sesión, interrupción tras CREATE INDEX con dump
idéntico y reintento correcto. Base vacía/anterior/futura/incompleta e índice ausente
rechazados. No se tocaron datos comerciales ni se ejecutaron downgrades.

Subproceso con PYTHONTZPATH='' carga ZoneInfo('America/Argentina/Buenos_Aires') desde
tzdata y comprueba offset -10800 para 2026-01-01: correcto. No equivale a Windows probado.
EXPLAIN QUERY PLAN exige SEARCH sales USING COVERING INDEX sales_report_date.

Desde frontend:

```sh
npm run test
npm run lint
npm run build
POS_TEST_CHROMIUM=/usr/bin/chromium \
POS_F5_CAPTURE_DIR=/workspace/gestion-inteligente-pos/docs/screenshots/f5 npm run test:e2e
```

Vitest: **45 aprobadas, 0 fallidas**, cinco archivos (34 anteriores, 11 nuevas).
ESLint: salida 0. Build TypeScript (incluye E2E) y Vite correctos: JS principal 244.28 kB
(76.53 kB gzip), Reportes diferido 8.29 kB (3.13 gzip), CSS 21.20 kB (5.02 gzip),
Manrope local 24.84 kB; Catálogo/Caja conservan carga diferida.
E2E final: **1 flujo completo aprobado**, 39.4 s (40.4 s comando), cero fallidos.
Primera ejecución previa al ajuste visual también pasó (35.7 s); no cuenta dos casos.
Total distinto final: **142 + 45 + 1 = 188 aprobadas, cero fallidas finales**.

Incidencias de preparación: git clone dentro del sandbox no alcanzaba el proxy; se
completó mediante ejecución con red habilitada. Primer pytest aislado quedó esperando
sin producir casos; se terminó ese proceso y se ejecutó fuera de dicho aislamiento.
La misma suite con permisos de ejecución locales completó correctamente. No se afirma
que el intento sin resultados haya pasado. Ruff inicial detectó dos bloques de imports
sin ordenar; corregidos con --fix y verificados. npm avisó de deprecaciones de ESLint y
whatwg-encoding, y Playwright de NO_COLOR/FORCE_COLOR; no fallaron verificaciones.
No hubo fallos funcionales finales; revisión del diff corrigió además dos ediciones
documentales cruzadas antes de publicar, conservando sus contenidos históricos completos.

## Casos demostrados y garantías conservadas

- Venta multilínea no multiplica tickets/ingresos. Anuladas fuera de KPIs, anterior,
  rankings y horas. Sin ventas: valores 0, sin rankings/pico, mensajes explícitos.
- Totales/unidades >int64, fallo reproducido de SUM nativo y respuesta exacta pos_sum;
  JSON decimal/BigInt exactos. Ticket 100.5 centavos redondea a 101; porcentaje compara
  promedio exacto (100.5 contra 50 = 101 %). Base cero, disminución -100 % y empates.
- Día local versus UTC, límite exacto inicio incluido/fin excluido, cambio de año,
  mes y bisiesto; presets de 1/7/30 días y anterior con mismo corte, rangos inválidos.
- Precio/nombre editados, producto/empleado inactivos no cambian ventas válidas;
  última instantánea histórica nombra ranking. Top 10, orden estable y empate por ID.
- Hora pico por cantidad aunque otra hora facture más; horas empatadas y sin ventas.
- Anulación real confirma entre consultas del reporte: snapshot completo coherente,
  siguiente solicitud actualizada. No se duplican ni editan operaciones comerciales.
- EMPLOYEE 403 por API y sin enlace Reportes; anónimo 401. Toda regresión Host/Origin,
  CSRF, sesiones, autorizaciones, stock, idempotencia, rollback y concurrencia F1–F4 pasa.
- E2E reejecuta configuración/login, empleados, inventario, caja con respuesta perdida,
  recuperación del mismo UUID tras reautenticar, anulación y reinicio. Reportes comprueba
  datos reales de esa SQLite temporal después del reinicio, filtros, comparación visible,
  vacío, rango inválido y error 503/reintento. Solo ese error se induce; no se simulan KPIs.
- Cero intentos de solicitudes externas y cero pageerror no controlados. Manrope local,
  teclado Enter/Tab/Escape y foco tras resultado/error, movimiento reducido conservados.

## Capturas y revisión visual

Capturas reales con datos ficticios de pruebas, campos secretos vacíos, 1366×768 y
390×844. Se revisaron los PNG de resumen escritorio/móvil y error móvil después de
regenerarlos. Axe WCAG A/AA sin violaciones en las vistas auditadas, contraste incluido;
sin desborde horizontal también a 320 px. No constituye certificación integral de accesibilidad.

- [Resumen escritorio](docs/screenshots/f5/reports-summary-desktop.png) · [móvil](docs/screenshots/f5/reports-summary-mobile.png).
- [Sin ventas escritorio](docs/screenshots/f5/reports-empty-desktop.png) · [móvil](docs/screenshots/f5/reports-empty-mobile.png).
- [Carga escritorio](docs/screenshots/f5/reports-loading-desktop.png) · [móvil](docs/screenshots/f5/reports-loading-mobile.png).
- [Error/reintento escritorio](docs/screenshots/f5/reports-error-desktop.png) · [móvil](docs/screenshots/f5/reports-error-mobile.png).

## Checklist aplicado y límites

Persistencia: índice aditivo, sin DROP/DELETE de datos, upgrade/reaplicación/fallo/reintento,
FK e historia preservados, autogeneración continúa bloqueada. Arranque: revisión 0005 y
estructura/índice exigidos, sin reparación implícita. Dinero: rangos por fila y agregado,
fracciones exactas/redondeo, snapshot probado con escritor real, autorización backend.
UI: estados positivos, navegación explícita/repetida, teclado/foco, capturas y desborde.
Cierre: pruebas/lint/build reales, versiones alineadas, evidencias históricas conservadas,
ramas anteriores y main sin cambios remotos. Publicación en rama F5, PR borrador.

F5 implementada y verificada técnicamente; aprobación humana del PR pendiente. No hay
bloqueos técnicos de F5. No se validó impresora física de 58 mm, controlador Windows,
instalador, backups/restauración o piloto. No se inició F6. Rangos de máximo 366 días,
rankings top 10, consulta explícita para actualizar, sin CSV. El índice acota fechas pero
la cantidad de filas del período no tiene un máximo artificial: no se promete tiempo
medido en PC piloto; sumar exacto procesa filas válidas de ese rango. No hay telemetría.

### Corrección final de evidencia de carga

La revisión por tamaño/bytes detectó que las primeras capturas loading eran idénticas
al resumen: la retención de una sola solicitud no cubría la repetición de efectos en
StrictMode. Se corrigió el test para retener todas hasta finalizar screens y comprobar
Cargando otra vez antes de liberar; no cambia código de aplicación. Ver H-F5-006.
E2E final posterior a esta corrección: **1 aprobado, 0 fallidos, 31.4 s** (32.3 s comando).
Build TypeScript/Vite y lint nuevamente correctos; artefactos de aplicación idénticos.
Se inspeccionó PNG móvil de carga: mensaje Cargando reporte y Consultar ocupado visibles.
Se regeneraron todos los PNG F5; se mantienen **188 casos distintos aprobados**.
