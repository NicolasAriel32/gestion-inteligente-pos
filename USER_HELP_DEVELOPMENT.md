# Ayuda local para usuarios

## Diseño previo — 2026-10-22

Pedido del propietario: signo de pregunta en esquina superior con respuestas rápidas y
pasos de configuración/carga de productos/cambio de precios. Mejora de ayuda sobre main
fb85521 (F5 fusionada), rama feat/local-user-help. F6 continúa sin iniciar; no se modifica
main directamente ni se asume autorización para fusionar esta mejora.

Incremento: botón «?» y etiqueta accesible Ayuda en encabezado; diálogo nativo con buscador
local, filtro de temas y respuestas desplegables. Texto breve con listas numeradas y nombres
exactos de controles existentes. Contenido estático versionado incluido en la aplicación:
sin internet, IA, servicios externos ni carga de datos comerciales. Disponible también en
acceso para problemas de sesión; guías administrativas visibles solo con rol ADMIN.

Temas: productos/precios/categorías, stock, caja/historial, reportes, equipo/acceso e
impresión/problemas frecuentes. Explicar límites actuales sin presentar backup/importación,
restablecimiento de contraseña o instalador pendientes como funciones disponibles. La guía
no ejecuta acciones, navega de pantalla ni cambia borradores/pedidos. Nunca aconseja borrar
SQLite, desactivar seguridad o registrar otra venta ante respuesta incierta.

Archivos previstos: HelpCenter.tsx y userHelp.ts (contenido/búsqueda tipada), integración
mínima App.tsx, CSS local; pruebas E2E de búsqueda, permisos visibles, cero escrituras,
conservación de formularios y foco. Reutilizar pruebas frontend/backend previas donde
corresponda; sin pruebas redundantes para texto estático. README/specs/diseño y este informe.
Sin cambios de esquema, API, reglas comerciales o dependencias. Versión de mejora 0.5.1,
alineada según VERSIONS.md al entregar verificada.

Aceptación: abrir desde encabezado por teclado/mouse en escritorio/móvil; buscar sin
distinguir mayúsculas/acentos, filtro y estado vacío; guías de alta/precio con etiquetas
reales y rol explícito. Escape/cierre devuelve foco; Tab no sale del diálogo; fondo inerte.
Conservar valores al abrir/cerrar, impedir solapamiento con confirmaciones en curso.
Revisar capturas reales, axe/contraste/desborde a 1366/390/320 px y movimiento reducido.
Suite frontend/lint/build y E2E F1–F5 locales completos; registrar resultados reales.

## Implementación y contenido

Botón circular ? de 44 px al extremo derecho del encabezado, nombre accesible Abrir
ayuda y tooltip. Ayuda disponible sin sesión para acceso, conexión e impresión; después
de ingresar aparecen guías según rol. ADMIN accede a 18 respuestas en seis temas.
Búsqueda por todas las palabras en título/resumen/pasos/notas, sin distinguir acentos o
mayúsculas. Filtro por tema y recuperación del estado sin resultados. Respuestas nativas
details/summary, listas numeradas, encabezado con Cerrar ayuda y cuerpo desplazable.

No hay navegación ni escrituras desde la ayuda, solicitudes API, almacenamiento de
credenciales, carga remota de contenido o nueva dependencia. La visibilidad por rol es
presentación de documentación pública; los permisos efectivos siguen en backend.
El contenido menciona expresamente límites de impresión física, recuperación de contraseña
y pago manual sin verificación bancaria. No presenta futuras funciones de F6 como disponibles.

HelpCenter.tsx controla diálogo/foco/scroll y cierre con Escape; userHelp.ts contiene las
guías y búsqueda tipadas. App.tsx integra solo el encabezado y reinicia la ayuda al cambiar
sesión/rol. El botón se deshabilita junto con otras acciones en escrituras de gestión;
los diálogos nativos mantienen inerte el fondo. No se desmontan Caja/Catálogo al abrir.
CSS conserva Manrope/paleta y adapta búsqueda/tema a móvil. Sin animación nueva.

## Comandos y resultados reales — 2026-10-22

Entorno conservado: Linux, Python 3.12.14, Node 24.19.0, npm 11.9.0, Chromium
154.0.8037.57 del sistema, dependencias declaradas idénticas a main.

Desde frontend:

```sh
npm run test
npm run lint
npm run build
POS_TEST_CHROMIUM=/usr/bin/chromium \
POS_HELP_CAPTURE_DIR=/workspace/gestion-inteligente-pos/docs/screenshots/help npm run test:e2e
```

- Vitest: **50 aprobadas, 0 fallidas finales** (45 anteriores y 5 de búsqueda/roles),
  seis archivos, última ejecución 2.66 s.
- ESLint sin errores; TypeScript/Vite correcto, incluido tipado E2E.
- Build: JS principal 259.81 kB (81.35 gzip), CSS 23.79 kB (5.50 gzip), WOFF2 Manrope
  24.84 kB; módulos Caja/Catálogo/Reportes continúan diferidos.
- E2E final: **1 flujo completo aprobado**, 32.5 s (33.3 s comando), cero fallidos.
  La ejecución previa también pasó (37.3 s); las repeticiones no suman casos distintos.

Desde backend:

```sh
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest tests/test_health.py -q
.venv/bin/python -m ruff check .
.venv/bin/python -m pip check
```

Reinstalación de metadata editable 0.5.1 correcta, sin actualizar dependencias.
**2 pruebas health aprobadas**, 0.97 s, Ruff correcto, pip check sin incompatibilidades.
No se volvió a ejecutar toda la suite backend: el diff demuestra que casos comerciales,
API de negocio, infraestructura, esquema, migraciones y tests backend están intactos;
solo cambia FastAPI.version y metadata de paquete. Las 142 aprobadas de F5 conservan
su evidencia histórica, no se presentan como una ejecución nueva. Total ejecutado en
esta mejora: **2 + 50 + 1 = 53 casos distintos aprobados**.

Siete valores comparados con tomllib/importlib.metadata/JSON: backend fuente/instalado,
FastAPI/OpenAPI, frontend y ambas raíces del lockfile coinciden en 0.5.1. Comparación de
lockfile contra main normalizando solo esas dos versiones: transitivos idénticos.
Esquema continúa 0005_reporting_indexes; no hay nueva migración ni tag/release.

## Navegador, permisos y conservación del trabajo

E2E usa SQLite temporal nueva y servidores en loopback; bloquea solicitudes externas.
Reejecuta identidad, stock, caja, respuesta perdida/reintento UUID, anulación, reporte,
impresión/PDF y reinicio de F1–F5. Cero intentos externos y cero errores JS no controlados.
Además demuestra:

- Ayuda sin sesión con recuperación de foco y sin instrucciones administrativas.
- EMPLOYEE con explicación de permisos y guía de venta pendiente; sin guía de cambio de precio.
- ADMIN con pasos reales de crear producto/cambiar precio y etiquetas existentes.
- Búsqueda CARGAR PRODUCTO, cambiar precio y mercaderia sin acento; filtros, vacío y
  Ver todas las guías. Palabras buscadas en el cuerpo, no solo título.
- Tab/Shift+Tab entre extremos del diálogo, foco inicial en búsqueda, Escape y cierre
  por botón. Controles de fondo inertes mientras está abierto el diálogo nativo.
- Campo Nombre del producto con «Borrador conservado» antes/después de abrir/cerrar.
  Listener de solicitudes exige cero escrituras /api durante la consulta de ayuda.
- Venta con respuesta perdida conserva el panel pendiente; abrir/cerrar ayuda no
  genera un segundo POST. Se recupera el mismo UUID siguiendo el flujo anterior.
- Contraste/axe WCAG A/AA sin violaciones detectadas en las vistas auditadas; sin
  desborde de documento a 1366/390/320 px y del cuerpo de ayuda en capturas auditadas.
- Movimiento reducido conserva transitionDuration=0s. No hay nuevas animaciones.

## Capturas revisadas

PNG reales de ventana visible, datos ficticios de prueba y campos secretos vacíos.
Se revisaron las primeras capturas completas y las finales de precio escritorio y
producto móvil. El cuerpo tiene scroll para continuar pasos; el cierre siempre permanece
visible. No se usa una captura larga del documento como si fuera el viewport de un modal.

- [Crear producto escritorio](docs/screenshots/help/help-product-desktop.png) · [móvil](docs/screenshots/help/help-product-mobile.png).
- [Cambiar precio escritorio](docs/screenshots/help/help-price-desktop.png) · [móvil](docs/screenshots/help/help-price-mobile.png).

## Incidencias y límites

Primer Vitest: 49 aprobadas y 1 fallida. El test esperaba cero respuestas de empleado
al buscar cambiar precio, pero se mostraba correctamente la explicación de permisos.
Se corrigió la expectativa para exigir solo esa explicación, conservando la exclusión de
la guía administrativa. Producto sin cambios por esa incidencia; última suite 50/50.
Capturas iniciales fullPage mostraban documento fuera del viewport con backdrop recortado;
se cambió solo la captura de ayuda al viewport real y se regeneró/verificó E2E.
Hallazgos/prácticas: H-HELP-001/002 en ENGINEERING_FINDINGS.md.

La revisión del diff corrigió ediciones documentales cruzadas antes de publicar y comprobó
que cada spec conserva su base original, títulos y evidencia F1–F5. No se modificaron
migraciones publicadas, datos comerciales ni las ramas de fases anteriores.
Advertencias existentes: Starlette TestClient/httpx y Playwright NO_COLOR/FORCE_COLOR;
no se suprimieron ni causaron fallo final.

Ayuda estática: no interpreta errores automáticamente ni realiza configuraciones. Requiere
mantener los pasos al cambiar etiquetas/flujos; esa revisión entra en el checklist.
No es una certificación integral de accesibilidad. Impresora física, Windows/instalador,
backups/restauración y piloto conservan sus pendientes. F6 no iniciada. Mejora en rama
separada/PR borrador para revisión, sin autorización asumida para fusionar.
