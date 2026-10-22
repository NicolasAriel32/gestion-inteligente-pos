# DECISIONS — decisiones arquitectónicas y de producto

Formato: ID, fecha, estado, decisión, motivo, consecuencias. Distinguir **aprobado** de **propuesto**. Fecha documental: 2026-10-21.

## Aceptadas por el propietario
### ADR-001 — Una caja local sin conexión obligatoria (ACEPTADA)
El MVP opera en una sola PC del kiosco, un comercio, una sucursal y una caja. Venta y stock sin internet. Consecuencia: no necesita backend cloud ni sincronización remota inicial.

### ADR-002 — SDD, repositorio central y agentes de desarrollo (ACEPTADA)
GitHub es fuente de verdad; specs y AGENTS.md guían a Codex y otras herramientas. Las reglas críticas se validan con pruebas, no únicamente con prompts.

### ADR-003 — Retirar Lovable (ACEPTADA)
No usar Lovable en el proyecto. Controlamos el código y las decisiones de arquitectura directamente en el repositorio.

### ADR-004 — Roles y núcleo funcional (ACEPTADA)
Dos roles (ADMIN/EMPLOYEE), catálogo, inventario, venta, historial, productos más vendidos, horas pico y dashboard. Operaciones críticas con permisos backend.

## Propuestas técnicas para validar durante F1
### ADR-005 — React/TypeScript/Vite + FastAPI (PROPUESTA)
Frontend web estático servido por backend Python local. Beneficio: separa UI de negocio y permite empaquetado Windows. Pendiente: medir arranque y distribución.

### ADR-006 — SQLite/SQLAlchemy/Alembic (PROPUESTA)
Base local apropiada para una caja, sin MySQL instalado. Usar transacciones de escritura y backups consistentes. Futuro MySQL implica adaptación, migración y pruebas; no es automático.

### ADR-007 — PyInstaller + Inno Setup (PROPUESTA)
Binarios e instalador Windows sin runtimes de desarrollo. Validar con PC limpia.

### ADR-008 — Datos privados en LOCALAPPDATA (PROPUESTA)
Una cuenta Windows por instalación. Si cambia a uso multiusuario de Windows, revisar ACL, ruta y propiedad de datos.

### ADR-009 — MCP y automatización diferidos (ACEPTADA COMO ALCANCE)
Preparar contratos de negocio para uso posterior por agentes; no implementar MCP o LLM en MVP.

### ADR-010 — Un pago declarado por venta (PROPUESTA)
Registrar efectivo, transferencia, débito o crédito; sin verificación externa de cobro ni pagos mixtos. Determinar política definitiva en piloto.

## Pendientes materiales
- Política de respaldo externo, restauración y frecuencia predeterminada.
- Criterio de soporte Windows 10, ya fuera de soporte general; Windows 11 es objetivo principal.
- Experiencia de cierre de aplicación sin dejar servidor huérfano.
- Política de recuperación de credenciales sin bypass de permisos.
- Comprobante no fiscal y requerimientos de impresora del piloto.
- Definir si exportación de ventas y stock en CSV se incorpora en F6 (solicitud previa; recomendable).
- Confirmar si lectura de código de barras mediante lector USB tipo teclado es prioritaria (distinto de cámara).

Registrar decisiones futuras con fecha y efecto en PROJECT_SPEC/BUSINESS_RULES/ACCEPTANCE_TESTS.
