# Frontend — identidad visual y validación

Estado posterior: el propietario autorizó la fusión el 2026-10-22. PR #2 quedó fusionado
a main con merge 058a92ffb0a226adc434d2cafe0dda68608d7ba3. La evidencia histórica que
sigue corresponde al diseño de F2 antes de esa autorización. Catálogo e inventario se
validan en [F3_DEVELOPMENT.md](F3_DEVELOPMENT.md), con capturas en docs/screenshots/f3.

Fecha: 2026-10-22. Rama: feat/frontend-yellow-manrope, creada desde main en
3442de4e05af951d28b501f58c6863be1bc94bd6. Entrega para revisión visual, sin merge.
F3 no iniciada. No se modificó ningún archivo del backend, migraciones o contratos API.

## Cambio y criterio de aceptación

Aplicar la dirección C aprobada a configuración inicial, ingreso y gestión de empleados:
Manrope real local, negro #171714 sobre amarillo #FFD633, paneles #FFF3B0 y acciones claras.
Se extrajeron Button, Field, Notice, Panel, Icon, ConfirmDeactivation y CredentialForm.
Solo se muestran funciones existentes; el número de empleados se obtiene de la API.

Riesgos: pérdida de foco durante actualizaciones asíncronas, contraste durante transiciones,
fuentes sustituidas y alteración accidental del flujo de identidad. Aceptación: conservar
F2, demostrar carga local de la fuente, flujos reales, teclado, estados y responsive;
ejecutar todas las verificaciones y entregar capturas sin secretos.

## Entorno y dependencias

Python 3.12.14; Node 24.19.0; npm 11.9.0; Chromium local /usr/bin/chromium (Linux).
Se mantienen React 19.3.1, TypeScript 5.7.3, Vite 6.4.5, Vitest 2.1.9 y Playwright 1.64.1.

- Sin nuevas dependencias JavaScript de producción ni bibliotecas de UI/animaciones.
- Se agregó @axe-core/playwright 4.14.0, con axe-core 4.14.0, solo para auditoría de desarrollo.
- Manrope WOFF2 variable latino: 24 836 bytes; origen @fontsource-variable/manrope 5.3.0.
  Se extrajo y versionó el archivo; Fontsource no es dependencia de ejecución.
- Licencia OFL en frontend/public/licenses/Manrope-OFL.txt, copiada al build.
  Se comparó con cmp contra dist/licenses/Manrope-OFL.txt: código 0.
- package-lock.json actualizado; npm ci comprobado con éxito (273 paquetes).

## Comandos ejecutados y resultados finales

Desde backend, con backend/.venv/bin/python:
```sh
python -m pytest -q
python -m ruff check .
POS_VISUAL_DATA_ROOT=$(mktemp -d /tmp/pos-visual-validation.XXXXXX)
LOCALAPPDATA="$POS_VISUAL_DATA_ROOT" python -m alembic -c alembic.ini upgrade head
LOCALAPPDATA="$POS_VISUAL_DATA_ROOT" python -m alembic -c alembic.ini current
```

Desde frontend:
```sh
npm ci --cache /tmp/gestion-pos-npm-cache
npm run test
npm run lint
npm run build
POS_TEST_CHROMIUM=/usr/bin/chromium \
POS_CAPTURE_DIR=/workspace/gestion-inteligente-pos/docs/screenshots/frontend \
npm run test:e2e
cmp public/licenses/Manrope-OFL.txt dist/licenses/Manrope-OFL.txt
```

POS_CAPTURE_DIR se puede cambiar a una carpeta de salida propia. Sin esa variable, E2E
no escribe capturas en el repositorio. En otro equipo usar Chromium instalado para Playwright
o POS_TEST_CHROMIUM y el entorno Python del backend (POS_TEST_PYTHON si es necesario).
La prueba requiere puertos locales 5173 y 8765 libres; nunca reutiliza servidores existentes.

| Comprobación | Resultado ejecutado |
| --- | --- |
| pytest | 40 aprobadas, 0 fallidas; 1 warning previo Starlette/HTTPX |
| Ruff | All checks passed; código 0 |
| Alembic upgrade/current | Código 0; 0002_identity (head), base nueva aislada |
| Vitest | 6 aprobadas, 0 fallidas |
| ESLint | Código 0; sin errores ni warnings en el código final |
| TypeScript/Vite | Código 0; 33 módulos compilados |
| Playwright | 1 flujo ampliado aprobado, 0 fallidos |
| Axe | 0 violaciones A/AA detectadas en las vistas analizadas |
| Git diff backend | Vacío respecto de main |

Total: **47 pruebas aprobadas, 0 fallidas**. Las auditorías y aserciones internas del flujo
E2E no se cuentan como pruebas adicionales. Build final: JS 239.96 kB (75.05 kB gzip),
CSS 11.24 kB (3.11 kB gzip), WOFF2 24.84 kB, HTML 0.37 kB. CSS/JS gzip: unos 6 kB más
que la base F2; la fuente local se descarga del mismo servidor como recurso separado.

## Evidencia de la experiencia

El flujo E2E crea una base temporal nueva, aplica migraciones, genera el secreto de prueba,
inicia FastAPI/Vite y verifica:

- Inicialización real de ADMIN, login válido e inválido, alta de empleado y logout.
- EMPLOYEE no ve administración y GET /api/employees responde 403 con esa sesión.
- Reinicio real de Python preserva usuarios y sesiones. Desactivar revoca acceso y login.
- Se espera la fuente local .woff2 con HTTP 200 y document.fonts.ready. Chromium CDP informa
  glifos de fuente personalizada Manrope ExtraLight, nombre interno de la base variable;
  el título tiene peso CSS 800. No se acepta una fuente de sistema como reemplazo.
- Link de salto al contenido; Tab entre usuario/contraseña/enviar; contorno visible de 3 px.
- Error de login recibe foco. Después del alta, foco en Usuario. El diálogo enfoca Cancelar,
  admite Escape, devuelve foco al invocador y mantiene el recorrido Tab/Shift+Tab.
- Login retenido temporalmente para observar Procesando, campos/botón deshabilitados y
  un solo request ante un intento de submit repetido.
- prefers-reduced-motion desactiva animación del indicador y transiciones; conserva texto.
- Auditorías axe en setup/login/empleados a 1366 y 390 px, además del error y diálogo.
- Sin desbordamiento horizontal en esas vistas a 1366, 390 y 320 px.
- Contextos de navegador bloquean solicitudes HTTP fuera de localhost/127.0.0.1:
  0 solicitudes externas intentadas y 0 errores de página. Health confirma conexión real.

Contrastes calculados con luminancia WCAG: negro/amarillo 12.76:1, negro/panel 15.99:1,
texto secundario/panel 8.03:1, error/panel 9.24:1, placeholder/campo 5.91:1,
borde/campo aproximadamente 4.50:1. Las transiciones de botón no interpolan texto/fondo.

## Capturas reales

Generadas por Playwright/Chromium contra la aplicación funcionando con cuentas ficticias.
No son imágenes generadas por IA. Antes de cada captura se verifica que todos los inputs
password estén vacíos. No se guardan trazas, videos, cookies o secretos. Los viewports son
1366×768 y 390×844; las imágenes full-page pueden ser más altas que el viewport.

| Pantalla | Escritorio | Pantalla pequeña |
| --- | --- | --- |
| Configuración inicial | [Ver](docs/screenshots/frontend/setup-desktop.png) | [Ver](docs/screenshots/frontend/setup-mobile.png) |
| Ingreso tras crear ADMIN | [Ver](docs/screenshots/frontend/login-desktop.png) | [Ver](docs/screenshots/frontend/login-mobile.png) |
| Gestión de empleados | [Ver](docs/screenshots/frontend/employees-desktop.png) | [Ver](docs/screenshots/frontend/employees-mobile.png) |

Otros estados: [error de ingreso](docs/screenshots/frontend/login-error-desktop.png) y
[confirmación de desactivación](docs/screenshots/frontend/deactivate-desktop.png).

## Hallazgos resueltos y límites

Se corrigieron y documentaron H-UI-001 a H-UI-004 en
[ENGINEERING_FINDINGS.md](docs/ENGINEERING_FINDINGS.md): tipado mixto Node/DOM,
foco del diálogo, competencia por foco tras carga y contraste de transiciones.
Durante las pruebas también se ajustó la expectativa del nombre interno de Manrope:
la comprobación sigue exigiendo archivo local, fuente personalizada y glifos realmente renderizados.
No se ignoraron pruebas ni reglas de contraste para obtener un resultado positivo.

No quedan verificaciones solicitadas fallidas o bloqueadas. La revisión visual del propietario
está pendiente; no se fusiona el PR. Axe y las pruebas de teclado ejecutadas no equivalen a
certificación completa WCAG ni a prueba manual con lectores de pantalla. No se validaron
Windows, Safari/Firefox ni tecnologías de asistencia de esos entornos en esta entrega.
En pantalla pequeña se usa desplazamiento vertical natural; no se simula una app móvil nativa.
Se conservan los avisos de deprecación heredados de Starlette/HTTPX y paquetes npm.
No se implementa recuperación de credenciales ni funcionalidad comercial de F3/F4.

## Sistema visual

Tokens, componentes, tipografía, licencia y estados: [DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md).

## Archivos de la entrega

- `FRONTEND_DESIGN_VALIDATION.md`
- `README.md`
- `docs/DECISIONS.md`
- `docs/DESIGN_SYSTEM.md`
- `docs/ENGINEERING_FINDINGS.md`
- `docs/screenshots/frontend/deactivate-desktop.png`
- `docs/screenshots/frontend/employees-desktop.png`
- `docs/screenshots/frontend/employees-mobile.png`
- `docs/screenshots/frontend/login-desktop.png`
- `docs/screenshots/frontend/login-error-desktop.png`
- `docs/screenshots/frontend/login-mobile.png`
- `docs/screenshots/frontend/setup-desktop.png`
- `docs/screenshots/frontend/setup-mobile.png`
- `frontend/e2e/identity.spec.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/public/licenses/Manrope-OFL.txt`
- `frontend/src/App.tsx`
- `frontend/src/CredentialForm.tsx`
- `frontend/src/assets/fonts/Manrope-latin-variable.woff2`
- `frontend/src/assets/fonts/README.md`
- `frontend/src/style.css`
- `frontend/src/ui.tsx`
- `frontend/tsconfig.e2e.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
