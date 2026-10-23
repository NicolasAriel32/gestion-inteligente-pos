# PROJECT_SPEC — Gestión Inteligente POS

- Versión de referencia: 0.5.1 (2026-10-22); ver VERSIONS.md
- Estado: núcleo F1–F5 implementado y validado localmente; F5 fusionada en PR #5 (fb85521).
  F6 candidata con CI Windows y prueba general del propietario satisfactorias; este usó
  otra versión de Windows, aún por identificar. Windows 11 limpio, impresora física y piloto pendientes.
- Requisito comercial añadido: facturación fiscal integrada obligatoria, aún no implementada;
  ver [FISCAL_INVOICING.md](FISCAL_INVOICING.md). F6 candidata en PR #7, sin merge.
- Moneda: ARS; idioma: español argentino; reportes: America/Argentina/Buenos_Aires

## Misión
Facilitar ventas e inventario de kioscos y pequeños comercios, con datos confiables para que el dueño pueda decidir. Producto comercial sencillo, instalable para **un comercio, una sucursal, una caja y una PC**, con gestión local sin internet. La entrega comercial debe integrar facturación fiscal; la autorización y contingencia tienen requisitos propios de comunicación.

## Actores y permisos
**ADMIN (dueño):** cuenta principal, altas/bajas lógicas de productos y usuarios, precios, categorías, stock, anulaciones, reportes completos y auditoría.
**EMPLOYEE:** venta y consulta de catálogo/stock, consulta de sus ventas; no cambia precios, inventario manual, usuarios ni anula ventas.
Sin autorregistro público. El dueño puede crear/desactivar empleados; los permisos se controlan en servidor, no solo en UI.

## Módulos funcionales
1. **Caja:** búsqueda por nombre/código, carrito, cantidades, total, confirmación, efectivo/transferencia/débito/crédito registrados manualmente, comprobante imprimible **no fiscal**.
   Requisito añadido por el propietario durante F4: ticket para térmicas económicas de
   58 mm (por ejemplo Global/Waggs), con controlador local de Windows. Modelo y prueba
   física pendientes; detalle en PRINTING.md. Impresión fallida no duplica ni revierte la venta.
2. **Productos:** alta, edición y desactivación; código opcional, nombre, categoría, precio, costo opcional, stock mínimo, búsqueda y filtros.
3. **Inventario:** carga inicial, entradas y ajustes con motivo, alerta de stock bajo y movimientos auditables.
4. **Ventas:** historial, filtro por empleado según rol, detalle con instantánea de nombre y precio, anulación solo por ADMIN con motivo.
5. **Panel ADMIN:** facturación, transacciones, ticket promedio, unidades, productos más vendidos por unidades o ingresos, ventas por hora por monto y cantidad, hora pico; filtros hoy, ayer, 7 y 30 días, rango personalizado.
6. **Empleados:** alta y desactivación de cuentas; no eliminar historia atribuida.
7. **Facturación fiscal obligatoria (pendiente):** emitir y consultar comprobantes ante
   ARCA, conservar autorización y representación fiscal, gestionar notas de crédito y
   contingencias según el régimen del comercio. El comprobante no fiscal actual no
   satisface este requisito. Alcance y aceptación: FISCAL_INVOICING.md.

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
- Gestión local sin internet; usuario no necesita Python, Node ni MySQL. Emisión fiscal
  requiere autorización o contingencia habilitada, con estados de comunicación explícitos.
- Arranque confiable, respuesta ágil para una PC de kiosco, uso teclado/mouse.
- Recuperación ante errores; copias y restauración **probadas** antes de piloto.
- Versionamiento de esquema, logs sin datos secretos y posibilidad de reparación.
- Software entendible por Codex y otras herramientas mediante specs y pruebas versionadas.

## Fuera de alcance del MVP
Múltiples sucursales/cajas, sincronización en nube, fiado/cuentas corrientes, proveedores, compras automáticas, pagos online, devoluciones parciales, lector por cámara, e-commerce, MCP operativo, LLM, modo multi-PC.

Facturación fiscal dejó de estar excluida por decisión posterior del propietario (ADR-016).

## Criterio de aceptación comercial
Instalar en PC piloto, inicializar ADMIN, crear EMPLOYEE, cargar productos, ingresar stock, vender, anular, verificar indicadores, reiniciar conservando datos y **restaurar una copia**. Autorizar piloto únicamente tras pruebas documentadas; ninguna spec equivale a una función ya construida.

La aceptación comercial requiere además la integración fiscal validada, autorización y
corrección de comprobantes, contingencia/conciliación y controles de credenciales. La
prueba del candidato local con datos ficticios no equivale a facturación fiscal habilitada.

## Ayuda de uso integrada — mejora 0.5.1

Botón ? en encabezado, ayuda local con buscador/temas y pasos según rol. Explica los
controles existentes sin ejecutar operaciones ni modificar formularios/pedidos; disponible
sin red. Guías administrativas solo para ADMIN; acceso/conexión/impresión también sin sesión.
No incorpora funciones comerciales nuevas ni inicia F6. Diseño/evidencia en USER_HELP_DEVELOPMENT.md.
