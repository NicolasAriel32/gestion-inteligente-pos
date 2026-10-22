# Instrucción para continuar con F5

Este archivo prepara el siguiente trabajo; no autoriza ni implementa F5 por sí mismo.
El propietario debe enviar la instrucción para comenzar. Baseline: main con PR #4
fusionado, versión 0.4.0 y esquema 0004_checkout_history. Ver VERSIONS.md.

```text
Trabajá sobre NicolasAriel32/gestion-inteligente-pos.

Objetivo: implementar F5 — Dashboard y reportes para ADMIN, manteniendo operación
local sin servicios cloud obligatorios y la identidad visual Manrope/amarillo.

Preparación:
1. Leé AGENTS.md y todas las specs que indica; además F4_DEVELOPMENT.md,
   docs/VERSIONS.md, docs/PRINTING.md, docs/ENGINEERING_FINDINGS.md y
   docs/PROJECT_REVIEW_CHECKLIST.md.
2. Actualizá main y verificá que contenga el merge del PR #4, versión 0.4.0 y
   esquema 0004_checkout_history. No alteres main ni las ramas F1–F4.
3. Creá feat/f5-dashboard-reports desde ese main.
4. Documentá en F5_DEVELOPMENT.md el diseño de consultas/contratos y las políticas
   de períodos, comparación, redondeo y límites numéricos antes de implementarlos.
   Informá conflictos con decisiones existentes y detené solo el trabajo afectado.

Alcance:
- Dashboard y reportes exclusivamente ADMIN, con autorización efectiva en backend.
- Facturación, cantidad de ventas, ticket promedio y unidades vendidas.
- Comparación con período anterior, con intervalos comparables explícitos.
- Ranking por unidades y por ingresos de productos.
- Ventas por hora, por cantidad de transacciones y monto; hora pico por transacciones.
- Filtros hoy, ayer, últimos 7/30 días y rango personalizado, usando
  America/Argentina/Buenos_Aires y timestamps UTC persistidos.
- Solo ventas COMPLETED: excluir VOIDED de todas las métricas y comparaciones.
- Usar instantáneas/precios históricos; cambios de catálogo o desactivación de un
  producto/empleado no deben cambiar ventas anteriores válidas.
- Dinero exacto en enteros y totales/aggregados seguros entre SQLite, Python y JS;
  nunca truncar, desbordar ni introducir float para resolver límites.
- Estados sin datos, carga, error y reintento; sin métricas simuladas ni navegación falsa.
- Lecturas consistentes y consultas acotadas/eficientes; evitar duplicar totales al
  unir cabeceras con ítems. Justificar índices o dependencias nuevas si hacen falta.

Restricciones:
- Conservar venta, anulación, stock, sesiones, Host/Origin, CSRF y permisos de F1–F4.
- Sin cambios arquitectónicos silenciosos, Lovable, cloud obligatorio ni datos reales
  para pruebas. Usar SQLite nuevo/temporal; no operaciones destructivas.
- La validación física de impresora de 58 mm sigue pendiente y no se declara aprobada.
- No iniciar F6 ni implementar instalador, backups, CSV o nuevas funciones comerciales.

Validación:
- Ejecutá todas las pruebas anteriores y nuevas de F5, Ruff, migraciones sobre una
  base nueva, tests frontend, lint, build y E2E real local con solicitudes externas bloqueadas.
- Probá datos conocidos, períodos vacíos, ventas anuladas, límites/redondeo de importes,
  cambios de precio, productos/empleados inactivos y límites de día/mes/año en Buenos Aires.
- Comprobá que EMPLOYEE reciba 403 al consultar reportes por API.
- Generá capturas reales en escritorio/móvil; verificá teclado/foco, contraste y
  reducción de movimiento. Documentá comandos y resultados reales, sin inventar pruebas.

Entrega:
- Actualizá README/specs, hallazgos y checklist; conservá la evidencia histórica.
- Alineá versión backend/API/frontend/lockfile en 0.5.0 al entregar F5 validada,
  según VERSIONS.md. Crear migración solo si cambia realmente el esquema.
- Marcá F5 completada solo si todos sus criterios y verificaciones pasan; documentá
  cualquier bloqueo y mantenela pendiente si corresponde.
- Publicá commits en feat/f5-dashboard-reports y abrí PR borrador a main con pruebas
  y capturas. No fusiones ni comiences F6 sin autorización.
- Informá funcionalidades, archivos, dependencias/versiones, pruebas aprobadas/fallidas,
  build, pendientes, commits, PR y conservación de las ramas anteriores.
```
