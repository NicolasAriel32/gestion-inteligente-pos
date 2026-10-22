# Gestión Inteligente POS

Sistema de gestión y punto de venta local para un kiosco o pequeño comercio argentino. **F1 validada: esqueleto técnico local; todavía sin funcionalidades comerciales.**

## Decisiones de producto

- MVP: un comercio, una sucursal, una caja y una PC.
- Funciona sin internet para las operaciones comerciales principales.
- Roles: **ADMIN** (dueño) y **EMPLOYEE** (empleado).
- Módulos: autenticación, productos, inventario, caja, historial de ventas, panel de indicadores y empleados.
- Idioma español argentino, moneda ARS, reportes en `America/Argentina/Buenos_Aires`.
- Las ventas no pueden producir stock negativo ni duplicarse por reintentos.
- No incluye facturación fiscal ARCA, pasarelas de pago, varias cajas ni agentes autónomos en el MVP.

## Arquitectura objetivo (sujeta a validación técnica)

- Frontend: React + TypeScript + Vite.
- Backend local: Python + FastAPI en loopback.
- Persistencia: SQLite + SQLAlchemy + Alembic.
- Distribución Windows: PyInstaller + Inno Setup.
- Extensiones futuras: MySQL, MCP, n8n.
- Sin Lovable, Supabase ni dependencias obligatorias de nube.

## Fuente de verdad

1. [Especificación del proyecto](docs/PROJECT_SPEC.md)
2. [Arquitectura](docs/ARCHITECTURE.md)
3. [Modelo de dominio](docs/DOMAIN_MODEL.md)
4. [Reglas de negocio](docs/BUSINESS_RULES.md)
5. [Persistencia](docs/PERSISTENCE.md)
6. [Instalación](docs/INSTALLATION.md)
7. [Roadmap](docs/ROADMAP.md)
8. [Decisiones](docs/DECISIONS.md)
9. [Criterios de aceptación](docs/ACCEPTANCE_TESTS.md)
10. [Instrucciones para agentes](AGENTS.md)

## Para Codex y otros agentes

Leer `AGENTS.md` y las especificaciones pertinentes **antes de escribir código**. No asumir que los archivos representan funcionalidades ya implementadas; cada etapa del roadmap requiere implementación, pruebas y revisión.

## Estado actual

**F1 completada.** FastAPI, React/Vite y SQLite/Alembic validados localmente; 6 pruebas aprobadas. Instalación, comandos y versiones en [F1_DEVELOPMENT.md](F1_DEVELOPMENT.md). Usar `python -m pip install -e './backend[dev]'` en un entorno virtual y `npm ci` desde frontend. Sin instalador ni funcionalidades comerciales; F2 no iniciada.
