# PROJECT_SPEC — Gestión Inteligente POS

- Versión: 0.1 (especificación inicial)
- Estado: alcance de MVP acordado; arquitectura técnica con propuestas registradas en DECISIONS.md
- Moneda: ARS; idioma: español argentino; reportes: America/Argentina/Buenos_Aires

## Misión
Facilitar ventas e inventario de kioscos y pequeños comercios, con datos confiables para que el dueño pueda decidir. Producto comercial sencillo, instalable para **un comercio, una sucursal, una caja y una PC**, operativo sin internet.

## Actores y permisos
**ADMIN (dueño):** cuenta principal, altas/bajas lógicas de productos y usuarios, precios, categorías, stock, anulaciones, reportes completos y auditoría.
**EMPLOYEE:** venta y consulta de catálogo/stock, consulta de sus ventas; no cambia precios, inventario manual, usuarios ni anula ventas.
Sin autorregistro público. El dueño puede crear/desactivar empleados; los permisos se controlan en servidor, no solo en UI.

## Módulos funcionales
1. **Caja:** búsqueda por nombre/código, carrito, cantidades, total, confirmación, efectivo/transferencia/débito/crédito registrados manualmente, comprobante imprimible **no fiscal**.
2. **Productos:** alta, edición y desactivación; código opcional, nombre, categoría, precio, costo opcional, stock mínimo, búsqueda y filtros.
3. **Inventario:** carga inicial, entradas y ajustes con motivo, alerta de stock bajo y movimientos auditables.
4. **Ventas:** historial, filtro por empleado según rol, detalle con instantánea de nombre y precio, anulación solo por ADMIN con motivo.
5. **Panel ADMIN:** facturación, transacciones, ticket promedio, unidades, productos más vendidos por unidades o ingresos, ventas por hora por monto y cantidad, hora pico; filtros hoy, ayer, 7 y 30 días, rango personalizado.
6. **Empleados:** alta y desactivación de cuentas; no eliminar historia atribuida.

## Comportamiento observable
- No permitir confirmar una venta si falta stock, sin alterar ningún dato.
- Un reintento no duplica ventas; simultaneidad no ocasiona sobreventa.
- Precio y total se recalculan en servidor usando datos vigentes.
- Venta confirmada descuenta stock y registra movimientos en una sola transacción.
- Anulación autorizada conserva historia y revierte stock una única vez.
- Venta anulada queda fuera de reportes comerciales.
- Los productos se desactivan; no se borran si forman parte de historia.
- Catálogo de demostración optativo, marcado como ejemplo; **no cargar ventas simuladas como reales**.

## Requisitos no funcionales
- Operación sin internet; usuario no necesita Python, Node ni MySQL.
- Arranque confiable, respuesta ágil para una PC de kiosco, uso teclado/mouse.
- Recuperación ante errores; copias y restauración **probadas** antes de piloto.
- Versionamiento de esquema, logs sin datos secretos y posibilidad de reparación.
- Software entendible por Codex y otras herramientas mediante specs y pruebas versionadas.

## Fuera de alcance v0.1
Facturación fiscal ARCA, múltiples sucursales/cajas, sincronización en nube, fiado/cuentas corrientes, proveedores, compras automáticas, pagos online, devoluciones parciales, lector por cámara, e-commerce, MCP operativo, LLM, modo multi-PC.

## Criterio de aceptación comercial
Instalar en PC piloto, inicializar ADMIN, crear EMPLOYEE, cargar productos, ingresar stock, vender, anular, verificar indicadores, reiniciar conservando datos y **restaurar una copia**. Autorizar piloto únicamente tras pruebas documentadas; ninguna spec equivale a una función ya construida.
