# PERSISTENCE — base de datos, transacciones y respaldos

- Versión: 0.1
- Propuesta: SQLite + SQLAlchemy + Alembic en una sola PC

## Ubicación
En MVP con una misma cuenta de Windows:
%LOCALAPPDATA%\\GestionInteligentePOS\\data\\pos.db
%LOCALAPPDATA%\\GestionInteligentePOS\\backups\\
%LOCALAPPDATA%\\GestionInteligentePOS\\logs\\
%LOCALAPPDATA%\\GestionInteligentePOS\\config\\

No guardar DB en Program Files ni en el binario. Si una instalación debe funcionar entre distintas cuentas Windows, rediseñar permisos/ruta antes de prometer soporte.

## Integridad
- Habilitar PRAGMA foreign_keys=ON en **cada conexión**.
- WAL para operación normal y busy_timeout razonable.
- Transacciones breves y una política explícita de reintentos ante bloqueos.
- No compartir SQLite por unidades de red; un único escritor a la vez.
- Restricciones CHECK: stock >= 0, precios >= 0, cantidad de ítem > 0.
- Idempotency_key de venta UNIQUE; código de producto UNIQUE cuando no sea NULL.
- Claves foráneas e índices para fecha, código, usuario y relaciones.
- Moneda en centavos enteros; cantidades de inventario solo unidades enteras MVP.
- Guardar fecha/hora en UTC con zona explícita para reportes de Buenos Aires.

## Modelo lógico
Entidades y relaciones detalladas en DOMAIN_MODEL.md: users, categories, products, sales, sale_items, payments, stock_movements, audit_log. No borrado físico de registros históricos.

## Registrar venta (una transacción)
1. Autenticar/autorizar empleado; validar solicitud y clave idempotente.
2. Abrir transacción que obtenga bloqueo de escritura antes de leer stock para decidir.
3. Si ya se usó la clave idempotente, devolver operación previa sin duplicarla.
4. Leer productos/precios actuales, validar activos y stock suficiente.
5. Calcular total en servidor en enteros y crear cabecera, ítems, pago registrado.
6. Reducir stock y crear movimientos de salida con referencia.
7. Confirmar; si algo falla: rollback completo.

No usar SELECT FOR UPDATE de PostgreSQL como si existiera en SQLite. Probar múltiples solicitudes simultáneas y doble clic.

## Anular venta (una transacción)
- ADMIN autenticado, motivo obligatorio.
- Si ya anulada: no repetir movimientos; devolver estado adecuado e idempotente.
- Registrar marca de anulación, responsable y fecha.
- Reponer exactamente lo vendido y registrar movimientos compensatorios.
- Confirmar todo o revertir todo.
- La venta permanece visible en histórico, excluida de agregados comerciales.

## Ajustar stock
ADMIN, motivo obligatorio, stock resultante >= 0, movimiento antes/después y auditoría. Usar la misma protección transaccional.

## Respaldos
- Implementar backup consistente mediante **SQLite Backup API** o equivalente probado; no copiar solamente pos.db activo en WAL.
- Respaldo manual y automático configurable, metadatos de fecha/esquema, integridad y política de retención documentada.
- Restauración con aprobación ADMIN, aplicación detenida para escritura, respaldo del estado previo y verificación de integridad al finalizar.
- Probar restauración de verdad antes del piloto.
- Un backup solo en el mismo disco NO protege contra rotura/robo: recomendar copia externa segura y documentar cómo hacerla.

## Migraciones
- Alembic versionado; respaldo previo obligatorio para despliegue cliente.
- Migrar cuando no existan ventas activas; fallos deben impedir uso con esquema incompatible.
- Distinguir reversión de **binarios** de reversión de **esquema/datos**.
- Nunca ejecutar migraciones destructivas sin plan de recuperación y aprobación humana.

## Pruebas prioritarias
Invariantes de stock, dos ventas simultáneas, idempotencia, anulación repetida, excepción en mitad de transacción, persistencia al reiniciar, FK, migración, respaldo/restauración, base corrupta, acceso denegado.
