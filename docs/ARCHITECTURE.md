# ARCHITECTURE — arquitectura del MVP local

- Versión: 0.1
- Estado: diseño objetivo sujeto a validación técnica
- Referencias: PROJECT_SPEC.md, BUSINESS_RULES.md y DECISIONS.md

## Despliegue
Un equipo Windows ejecuta:
- Frontend estático compilado de **React + TypeScript + Vite**.
- **FastAPI** local que sirve frontend y API REST; por defecto 127.0.0.1:8765 (solo loopback).
- **SQLite** en carpeta privada de datos; el frontend **nunca** accede al archivo directamente.

No se necesita conexión de red para operaciones esenciales. La distribución final buscará empaquetar todos los runtimes necesarios, sujeta a pruebas en Windows.

## Capas y dependencias
- Presentation: componentes React, vistas, estados de UI.
- HTTP/API: rutas FastAPI, esquemas Pydantic, autenticación/autorización, respuestas.
- Application: casos de uso tipados (crear venta, anular venta, ajustar stock, estadísticas).
- Domain: entidades, estados e invariantes sin acoplamiento a FastAPI/SQLite.
- Infrastructure: repositorios SQLAlchemy, migraciones, rutas de archivos, respaldo.

Dependencias hacia adentro: UI → API → Application → Domain; Infrastructure implementa puertos. No acoplar negocio al proveedor de base de datos.

## Módulos
auth, users, catalog, inventory, sales, reporting, audit, backup. Evitar servicios genéricos masivos y no introducir complejidad multiempresa prematuramente.

## API prevista (contratos a formalizar vía OpenAPI)
- POST /api/auth/login; POST /api/auth/logout; GET /api/auth/me
- GET/POST/PATCH /api/products; GET/POST /api/categories
- POST /api/stock/adjustments; GET /api/stock/movements
- POST /api/sales; GET /api/sales; GET /api/sales/{id}; POST /api/sales/{id}/void
- GET /api/reports/summary; GET /api/reports/top-products; GET /api/reports/peak-hours
- GET/POST/PATCH /api/employees
- POST /api/backups; procedimientos de restauración administrados y fuera de sesiones activas
- GET /api/health (sin información sensible)

Implementados y verificados en F2: health, auth/login, auth/logout, auth/me,
employees (GET/POST y PATCH de desactivación), además de auth/setup (GET/POST).
Implementados en F3: GET/POST /api/categories, PATCH /api/categories/{id},
GET/POST /api/products, GET/PATCH /api/products/{id}, POST /api/stock/adjustments y
GET /api/stock/movements. Contratos tipados y límites en OpenAPI; detalle en
[F3_DEVELOPMENT.md](../F3_DEVELOPMENT.md). Ventas, reportes y respaldos siguen pendientes.
Contratos y errores F2: [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).

## Seguridad local
- Credenciales únicas; contraseñas Argon2id; sesiones con expiración.
- Autorización backend en todos los endpoints.
- Si se utilizan cookies: HttpOnly, SameSite adecuado, defensa CSRF; origen y Host permitidos explícitamente.
- Escuchar exclusivamente 127.0.0.1; no aceptar orígenes arbitrarios ni interfaces de red.
- Configurar Host/CORS para mitigar acceso no autorizado desde sitios externos y DNS rebinding.
- Inicialización de ADMIN de uso único y protegida contra carreras.
- Validar entrada tipada y prohibir SQL interpolado.
- La seguridad de un equipo local también depende de permisos de Windows, mantenimiento y acceso físico.

## Operaciones de negocio
El backend fija precios, valida rol, maneja transacciones de inventario; idem-potencia con clave única por venta. SQLite no soporta SELECT FOR UPDATE: usar transacciones de escritura apropiadas (por ejemplo BEGIN IMMEDIATE), busy_timeout y pruebas de carrera. Véase PERSISTENCE.md.

## Observabilidad y calidad
- Logs locales rotativos, sin secretos ni datos sensibles innecesarios.
- pytest para backend y pruebas de integración SQLite; pruebas frontend donde apliquen.
- Documentar scripts de desarrollo, builds Windows y versiones de dependencias.
- Proteger invariantes con restricciones DB + tests + validaciones de aplicación.

## Evolución AI-native
AGENTS.md, especificaciones, decisiones y pruebas hacen el repositorio accesible a Codex/Claude Code/Cursor. En el futuro las operaciones de Application podrían ofrecerse con MCP, con permisos distintos, confirmación humana y auditoría. No implementar MCP en el MVP.

## Exclusiones técnicas iniciales
Sin Lovable, Supabase, dependencia obligatoria de cloud, sincronización distribuida, Docker requerido en cliente ni MySQL cliente. MySQL quedará como alternativa futura con adaptación y pruebas de persistencia, no migración automática.

## Concreción de seguridad F2

La API no ofrece autorregistro. La inicialización requiere secreto local temporal y
transacción BEGIN IMMEDIATE. Las sesiones son opacas, revocables y almacenadas como hashes;
cookie HttpOnly/SameSite=Strict, expiración absoluta y CSRF en escrituras autenticadas.
Origin y JSON obligatorios para login/setup; ninguna respuesta refleja secretos de validación.
Las capas HTTP, casos de uso, contratos de dominio y persistencia están separadas.
La política de recuperación no se implementa hasta decisión del propietario.

## Catálogo e inventario F3

Casos de uso con puertos tipados y adaptadores SQLite. La sesión y el rol se revalidan
dentro de la misma transacción que realiza cada escritura. ADMIN gestiona catálogo,
costos y movimientos; EMPLOYEE solo consulta activos, precio de venta y stock.
PATCH de producto no admite stock: se registra por carga inicial o ajuste con motivo.
Los ajustes usan UUID idempotente, BEGIN IMMEDIATE y auditoría atómica, sin reintentos
automáticos. Interfaz decimal exacta; API y DB conservan centavos enteros.
audit_events es el registro general; audit_log permanece como compatibilidad de identidad
sin modificar ni borrar eventos existentes. No se añadieron dependencias ni servicios.
