# ROADMAP — trabajo incremental SDD

**Estado inicial**: solo documentación. No existe programa compilado, API, interfaz, pruebas ejecutadas ni instalador.

Cada etapa empieza con criterios de aceptación claros y termina con pruebas reproducibles y revisión humana. No intentar entregar todas las etapas de una vez.

## F0 — Constitución y specs
- [x] Establecer alcance de MVP y operación local offline.
- [x] Versionar los documentos SDD y AGENTS.md.
- [ ] Revisar propuestas técnicas con prototipo y cerrar decisiones pendientes.

## F1 — Esqueleto técnico
- [ ] React/TypeScript/Vite + FastAPI.
- [ ] SQLite/SQLAlchemy/Alembic con migración inicial vacía.
- [ ] GET /api/health y frontend que consuma API local.
- [ ] Comandos de desarrollo, pytest, tests frontend, lint.
- Aceptación: ejecutar ambos lados localmente sin servicios cloud, comandos documentados y tests básicos pasando.

## F2 — Identidad y usuarios
- [ ] Inicialización segura de ADMIN de única ejecución.
- [ ] Login, logout, sesión y autorización de empleados.
- [ ] Auditoría básica.
- Aceptación: EMPLOYEE no accede a funciones admin vía API.

## F3 — Catálogo e inventario
- [ ] Categorías, productos, desactivación.
- [ ] Ajustes de stock con motivo y movimientos.
- [ ] Validaciones CHECK y FK.
- Aceptación: inventario consistente después de errores y reinicios.

## F4 — Caja e historial
- [ ] Carrito y cobro manual registrado.
- [ ] Venta atómica e idempotente en SQLite.
- [ ] Anulación ADMIN y comprobante no fiscal.
- [ ] Pruebas de concurrencia, rollback, duplicados.
- Aceptación: superar todas las invariantes de venta.

## F5 — Dashboard y reportes
- [ ] KPIs y comparación temporal.
- [ ] Ranking por unidades/ingresos, horas pico con timezone local.
- [ ] Filtros y estados sin datos.
- Aceptación: reportes excluyen anuladas y coinciden con datos de prueba.

## F6 — Respaldo, importación y distribución
- [ ] Backup consistente y restauración probada.
- [ ] CSV de productos con vista previa/validación (mejora para onboarding piloto).
- [ ] Build Windows, instalador y arranque único.
- [ ] Actualizaciones manuales documentadas.
- Aceptación: instalación limpia sin herramientas de desarrollo y recuperación demostrada.

## F7 — Piloto y comercialización
- [ ] Pruebas de flujo real con dueño y empleado.
- [ ] Usabilidad, monitoreo de errores y ajustes.
- [ ] Guía de uso y recuperación de datos.
- Aceptación: aprobación explícita del piloto; no confundir demo con producción.

## Futuro, no MVP
MySQL multi-PC, servidor remoto, MCP, n8n, actualizador asistido, pagos online, varias cajas, facturación fiscal. Cada evolución requiere nueva spec y análisis de riesgos.
