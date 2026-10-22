# ROADMAP — trabajo incremental SDD

**Versión de referencia**: 0.4.0 (2026-10-22); esquema 0004_checkout_history.
**Estado actual**: F1–F4 implementadas y validadas técnicamente.
Identidad local, empleados, catálogo e inventario; evidencia en
[F1_DEVELOPMENT.md](../F1_DEVELOPMENT.md), [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md) y
[F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md). F3 aprobada y fusionada a main en 3848d55.
El propietario autorizó integrar F4 mediante PR #4, manteniendo pendiente la prueba física
de la impresora de 58 mm. La autorización de fusión no certifica ese hardware. Evidencia en
[F4_DEVELOPMENT.md](../F4_DEVELOPMENT.md). Sin reportes ni instalador; F5 no iniciada.

Cada etapa empieza con criterios de aceptación claros y termina con pruebas reproducibles y revisión humana. No intentar entregar todas las etapas de una vez.

## F0 — Constitución y specs
- [x] Establecer alcance de MVP y operación local offline.
- [x] Versionar los documentos SDD y AGENTS.md.
- [ ] Revisar propuestas técnicas con prototipo y cerrar decisiones pendientes.

## F1 — Esqueleto técnico
- [x] React/TypeScript/Vite + FastAPI.
- [x] SQLite/SQLAlchemy/Alembic con migración inicial vacía.
- [x] GET /api/health y frontend que consuma API local.
- [x] Comandos de desarrollo, pytest, tests frontend, lint.
- Aceptación: ejecutar ambos lados localmente sin servicios cloud, comandos documentados y tests básicos pasando.

## F2 — Identidad y usuarios
- [x] Inicialización segura de ADMIN de única ejecución.
- [x] Login, logout, sesión y autorización de empleados.
- [x] Auditoría básica.
- Aceptación: EMPLOYEE no accede a funciones admin vía API.

- Revisión posterior: H-F2-001/002/003 corregidos y revalidados; 47 pruebas aprobadas.
  [Hallazgos y prevención](ENGINEERING_FINDINGS.md).

## F3 — Catálogo e inventario
- [x] Categorías, productos, desactivación.
- [x] Ajustes de stock con motivo y movimientos.
- [x] Validaciones CHECK y FK.
- Aceptación: inventario consistente después de errores y reinicios.
- Evidencia: 78 pruebas backend, 20 frontend y 1 flujo E2E aprobados (99; 0 fallidas).
  Ruff, ESLint, TypeScript/Vite y migraciones sobre SQLite nuevo aprobados; concurrencia,
  idempotencia, rollback, upgrade desde F2 y reinicio real verificados. Revisión visual de
  la extensión F3 aprobada por el propietario. Windows/piloto continúan pendientes de sus fases.

## F4 — Caja e historial
- [x] Carrito y cobro manual registrado.
- [x] Venta atómica e idempotente en SQLite.
- [x] Anulación ADMIN y comprobante no fiscal (documento/flujo de impresión verificados).
- [x] Pruebas de concurrencia, rollback, duplicados.
- [ ] Validación física con modelo Global/Waggs u otra térmica de 58 mm y controlador Windows.
- Aceptación: superar todas las invariantes de venta.
- Software: 119 pruebas backend, 34 frontend y 1 flujo E2E aprobados; 154 en total,
  cero fallidas finales. Migraciones, Ruff, ESLint y build correctos. Recuperación después
  de perder respuesta, reautenticación, reinicio y PDF de 58 mm comprobados.
- Software aprobado para integración por el propietario en PR #4. No marcar validada la
  impresora: faltan modelo, controlador y prueba física. El cierre integral/piloto conserva
  ese pendiente. F5 todavía no fue autorizada ni iniciada.

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
