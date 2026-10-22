# AGENTS.md — instrucciones para agentes de desarrollo

## Objetivo
Desarrollar Gestión Inteligente POS: sistema local-first para una caja de kiosco argentino. Este repositorio contiene inicialmente **especificaciones**, no software funcional. No usar Lovable ni agregar servicios cloud obligatorios.

## Orden de lectura
1. docs/PROJECT_SPEC.md — alcance y actores
2. docs/BUSINESS_RULES.md — invariantes
3. docs/DOMAIN_MODEL.md — modelo de dominio
4. docs/ARCHITECTURE.md — capas y contratos
5. docs/PERSISTENCE.md — transacciones, integridad y respaldo
6. docs/INSTALLATION.md — instalación y ejecución local
7. docs/ROADMAP.md — secuencia de entregables
8. docs/DECISIONS.md — decisiones aceptadas y propuestas
9. docs/ACCEPTANCE_TESTS.md — verificación

Ante conflicto, **detener la implementación relacionada y señalarlo**. No reinterpretar decisiones explícitas para acomodar código existente.

## Rutina SDD obligatoria
- Leer las specs afectadas antes de modificar código.
- Definir cambio acotado, archivos afectados, riesgos y criterio de aceptación.
- Implementar el incremento más pequeño que pueda verificarse.
- Ejecutar pruebas relevantes; informar comandos y resultados reales (no inventarlos).
- Actualizar las specs y DECISIONS.md cuando cambie una decisión.
- No usar el historial de chat como fuente de verdad del producto.

## Reglas innegociables
- No confiar en permisos, precios ni totales enviados desde el navegador.
- Nunca vender sin stock suficiente ni dejar stock negativo.
- Venta y reversión: operaciones atómicas, idempotentes y auditables.
- No borrar ventas históricas ni productos referenciados por ellas.
- Roles autorizados en backend; usar usuarios individuales.
- No exposición pública del backend: escuchar solamente en loopback.
- Aplicar validaciones de origen/Host y proteger sesión y credenciales.
- No poner archivos de datos comerciales en el directorio de binarios.
- No introducir LLM, MCP operativo, pagos online o telemetría sin decisión documentada.
- Nunca registrar secretos ni contraseñas en logs, repositorio o respuestas.
- No ejecutar operaciones destructivas, migraciones irreversibles ni cambios sensibles sin autorización humana.

## Convenciones para código futuro
- Estructura por capas y módulos de dominio; frontend sin acceso directo a SQLite.
- Tipado explícito, contratos OpenAPI y pruebas automáticas.
- Comandos de entorno y dependencias versionadas y documentadas en README.
- Pruebas de integración reales para concurrencia de SQLite, auth y operaciones monetarias.
- GitHub es fuente de verdad. Un cambio no está listo por verse correcto visualmente.

## Definition of done
- Aceptación verificable; pruebas realizadas y resultados reportados.
- Sin regresión de reglas críticas ni cambios fuera de alcance.
- Documentación coherente y riesgos pendientes explícitos.
- La creación de documentación por sí sola **no implica software implementado**.
