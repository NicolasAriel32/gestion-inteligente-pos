# DOMAIN_MODEL — vocabulario, entidades y eventos

- Versión: 0.1; definición inicial del dominio (revisar con comercio piloto)

## Lenguaje compartido
**Producto**: ítem vendible por unidades enteras.
**Stock disponible**: unidades registradas que pueden venderse ahora.
**Ajuste**: movimiento manual autorizado, nunca una venta.
**Venta completada**: transacción validada, cobro declarado y existencias descontadas.
**Venta anulada**: operación histórica conservada cuya reversión repone stock.
**Pago**: medio e importe informado por usuario; no es confirmación bancaria.
**Caja**: único puesto comercial del MVP, sin arqueo ni cierre de caja.

## Entidades mínimas
- **users**: id, username UNIQUE, password_hash, role ENUM(ADMIN, EMPLOYEE), is_active, created_at. Sin credenciales en logs.
- **categories**: id, name, is_active.
- **products**: id, code TEXT nullable UNIQUE, name, category_id FK, price_cents integer, cost_cents nullable, stock_quantity integer, minimum_stock integer, is_active, created_at, updated_at.
- **sales**: id, idempotency_key UNIQUE, user_id FK, status COMPLETED/VOIDED, total_cents, created_at_utc, voided_at_utc nullable, voided_by FK nullable, void_reason nullable.
- **sale_items**: id, sale_id FK, product_id FK, product_name_snapshot, unit_price_cents, quantity integer > 0, subtotal_cents.
- **payments**: id, sale_id FK, method CASH/TRANSFER/DEBIT/CREDIT, amount_cents. MVP un pago por venta; múltiples pagos quedan fuera.
- **stock_movements**: id, product_id FK, movement_type INITIAL/IN/ADJUSTMENT/SALE/VOID, quantity_delta (con signo), stock_before, stock_after, reference_type, reference_id, performed_by FK, reason nullable según tipo, created_at_utc.
- **audit_log**: id, actor_id FK, action, entity_type, entity_id, event_data (sin secretos), created_at_utc.

## Invariantes
- Stock jamás negativo.
- Cada subtotal = precio histórico × cantidad; total = suma de subtotales y coincide con pago declarado.
- No cambiar ítems o precio de venta completada.
- No modificar producto ya vendido mediante borrado físico.
- El estado VOIDED no retorna a COMPLETED.
- Una venta completada tiene al menos un ítem y un pago.
- No registrar saldo a cobrar, descuentos, impuestos desglosados ni pagos mixtos en v0.1.

## Eventos de dominio (descriptivos; no requiere event sourcing)
PRODUCT_CREATED, PRODUCT_UPDATED, STOCK_ADJUSTED, SALE_COMPLETED, SALE_VOIDED, EMPLOYEE_CREATED, EMPLOYEE_DISABLED.

## Secuencia
Usuario autenticado → agrega productos → confirma venta → validación server-side → transacción de venta + ítems + pago + reducción de stock + movimientos → evento de auditoría.

ADMIN anula → transacción cambia estado y registra movimiento compensatorio exactamente una vez.

## Reporting
Ventas válidas = status COMPLETED. Agregación por fecha local Buenos Aires; conservar timestamps UTC. Para “productos más vendidos” ofrecer orden por unidades o ingresos. Horas pico significa máximo número de transacciones en intervalos horarios locales, con métrica alternativa de monto.

## Evolución
Separar dominio de infraestructura para incorporar MySQL/API remota/MCP después; no modelar varias empresas ni multi-caja como funcionalidad del MVP.
