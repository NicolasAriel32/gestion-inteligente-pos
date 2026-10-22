# ACCEPTANCE_TESTS — criterios de aceptación trazables

Versión 0.1. La matriz define el objetivo completo. Solo los casos señalados en las
secciones de evidencia cuentan como ejecutados; ventas, reportes y Windows siguen pendientes.

## Conjunto mínimo (automático + piloto)
| Test | Reglas | Escenario y resultado esperado |
| --- | --- | --- |
| AT-001 | BR-001, BR-002 | Vender cantidad superior a stock: error y estado DB intacto |
| AT-002 | BR-007 | Vender 2 unidades: venta, ítems, pago, dos unidades descontadas y movimiento coherente |
| AT-003 | BR-003 | EMPLOYEE modifica precio por API: 403/denegación sin cambio |
| AT-004 | BR-004, BR-008 | ADMIN anula venta dos veces: devolución exacta una vez |
| AT-005 | BR-010 | Venta VOIDED no aparece en monto, tickets, ticket promedio ni ranking |
| AT-006 | BR-014 | Dos ventas simultáneas compiten por última unidad: nunca stock negativo ni doble venta válida |
| AT-007 | BR-005 | Repetir POST de venta con misma idempotency_key: una venta |
| AT-008 | BR-006, BR-009 | Cambiar precio después: histórico conserva precio y nombre; UI manipulada no altera cobro |
| AT-009 | BR-007 | Provocar excepción tras crear cabecera: rollback de todo (stock y filas) |
| AT-010 | BR-013 | Primer ADMIN inicializado una sola vez; segundo intento rechazado |
| AT-011 | BR-012 | Precio, ajustes, anulación, alta/baja de usuario dejan log atribuible |
| AT-012 | BR-015 | Desconectar internet: login local y flujo de venta siguen operativos |
| AT-013 | BR-011 | Desactivar producto histórico: ventas anteriores siguen consultables |
| AT-014 | BR-002 | Ajuste de stock negativo: rechazo y movimiento no creado |
| AT-015 | BR-010 | Horas pico y filtros “hoy” con fecha local Buenos Aires |
| AT-016 | BR-003 | EMPLOYEE consulta ventas ajenas: denegación; ADMIN sí puede |
| AT-017 | BR-016 | Método transferencia se registra como declaración, sin afirmar confirmación externa |
| AT-018 | Persistencia | Reiniciar aplicación mantiene datos y esquema correcto |
| AT-019 | Respaldo | Hacer backup con DB activa en WAL y restaurar copia consistente |
| AT-020 | Instalación | Instalar en PC Windows limpia sin Python/Node, iniciar y detener correctamente |

## Niveles de prueba
- **Unitarias:** cálculos de importes, validaciones y reportes.
- **Integración SQLite real:** BEGIN IMMEDIATE/concurrencia, FK/CHECK, idempotencia, anulación, rollback, backup API.
- **API:** auth, roles, Host/origen, respuestas de error y permisos por endpoint.
- **E2E interfaz:** login → catálogo → stock → caja → reportes → anulación.
- **Distribución:** instalador, arranque, reinstalación, migración y restauración en Windows.

No sustituir integración real por mocks cuando la regla depende de transacciones/bloqueos/SQL.

## Datos y evidencias
Usar fixtures reproducibles que incluyan: producto con stock 0/1/2, producto inactivo, usuario ADMIN/EMPLOYEE, venta anulada, dos ventas con mismo idempotency_key, período con cambio de día Buenos Aires. Sin datos comerciales reales en repositorio.

Registrar comandos, resultados, fallos conocidos y evidencia del piloto. Una prueba solo está aprobada si se ejecutó contra implementación concreta y produjo el resultado esperado.

## Definición de listo para piloto
Todas las pruebas críticas de dinero, stock, roles, backup/restauración y concurrencia pasan; instalación validada en PC objetivo; dueño da aprobación explícita.

## Evidencia F2 — 2026-10-22

- AT-010 ejecutada: inicialización válida única; dos solicitudes concurrentes producen
  201/409, exactamente un ADMIN y un evento de auditoría.
- AT-011 parcial (identidad): alta/desactivación con actor y UTC; rollback ante fallo de auditoría.
  Operaciones comerciales siguen pendientes.
- AT-012 parcial (identidad): inicialización, login y gestión de empleados en Chromium,
  bloqueando solicitudes externas. No se afirma validación del flujo de venta inexistente.
- AT-018 parcial (identidad): reinicio real de Python conserva usuarios y sesiones válidas.
- Autorización: EMPLOYEE recibe 403 en GET/POST/PATCH administrativos; no puede escalar rol.
- Seguridad: Host/Origin, CSRF, cookies, credenciales inválidas, expiración, logout,
  desactivación concurrente y ausencia de secretos en respuestas/auditoría probados.

Resultados, comandos y alcance: [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).
El resto de la matriz comercial y Windows continúa pendiente.

## Evidencia F3 — 2026-10-22

- AT-003: EMPLOYEE recibe 403 al crear/editar precios, categorías, productos o stock,
  incluso enviando solicitudes directas. No recibe costos ni movimientos administrativos.
- AT-011 parcial: categorías, productos y ajustes dejan evento con actor y UTC;
  fallo de auditoría revierte producto/stock/movimiento. Ventas/anulaciones pendientes.
- AT-014: ajuste que dejaría stock negativo devuelve 409; stock, movimientos y auditoría
  quedan intactos. Dos solicitudes de la última unidad producen una confirmación y un rechazo.
- AT-012 parcial: flujo de identidad, catálogo e inventario en Chromium con solicitudes
  externas bloqueadas y cero intentos externos. No se probó un flujo de venta inexistente.
- AT-013 parcial: desactivar preserva producto y movimientos; no hay ventas históricas aún.
- AT-018 parcial: reinicio real de Python conserva productos, stock, movimientos y sesiones.
- Upgrade F2→F3 conserva datos/sesiones/auditoría; fallo intermedio y reintento verificados.
- Idempotencia de ajuste, datos inválidos, CHECK/FK y desbordamientos probados con SQLite real.

Comandos, resultados y límites: [F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md).
