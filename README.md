# Gestión Inteligente POS

Sistema de gestión y punto de venta local para un kiosco o pequeño comercio argentino. **Identidad, catálogo e inventario locales implementados; caja y ventas todavía pendientes.**

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

FastAPI, React/Vite y SQLite/Alembic funcionan localmente. F2 agrega inicialización
protegida de ADMIN, sesiones y empleados. F3 incorpora categorías, productos, precios
en centavos, desactivación y ajustes de stock auditados e idempotentes, exclusivamente
por ADMIN. EMPLOYEE consulta productos activos, precios y existencias, sin costos.
Instalación, comandos y resultados: [F3_DEVELOPMENT.md](F3_DEVELOPMENT.md),
[F2_DEVELOPMENT.md](F2_DEVELOPMENT.md) y [F1_DEVELOPMENT.md](F1_DEVELOPMENT.md).
Sin ventas, caja, reportes ni instalador. F4 requiere autorización.

## Desarrollo local

Requiere Python >=3.11 y Node >=22. Crear y activar un entorno virtual:
```sh
python -m venv backend/.venv
# Linux/macOS:
. backend/.venv/bin/activate
# Windows PowerShell: backend/.venv/Scripts/Activate.ps1
python -m pip install -e './backend[dev]'
cd backend
python -m alembic -c alembic.ini upgrade head
python -m app.bootstrap
python -m app
```

El comando bootstrap indica la ruta del secreto local; no imprime su contenido.
Abrir el archivo localmente e introducirlo en el formulario inicial. No compartirlo ni
versionarlo. Después de crear ADMIN eliminar ese archivo. No ejecutar bootstrap de nuevo
sobre una instalación ya inicializada. Para datos existentes: respaldo previo antes de migrar.

En otra terminal:
```sh
cd frontend
npm ci
npm run dev -- --strictPort
```
Abrir http://127.0.0.1:5173. Ambos servicios escuchan solo en loopback.
No se necesita un servicio cloud. Recuperación de credenciales pendiente de decisión;
no borrar SQLite ni recrear ADMIN para recuperar acceso.

## Prácticas aprendidas

El [registro de hallazgos](docs/ENGINEERING_FINDINGS.md) conserva causas, fixes y pruebas
de F2, diseño y F3. El [checklist reutilizable](docs/PROJECT_REVIEW_CHECKLIST.md) reúne
las prácticas para próximas fases y proyectos.

## Identidad visual aprobada

Manrope local y negro sobre amarillo, con superficies suaves y controles accesibles.
El diseño de acceso/empleados fue fusionado por autorización del propietario (PR #2,
merge 058a92f). F3 conserva esa identidad. Ver [sistema visual](docs/DESIGN_SYSTEM.md),
[validación original](FRONTEND_DESIGN_VALIDATION.md) y
[capturas reales de catálogo/inventario](docs/screenshots/f3/).
