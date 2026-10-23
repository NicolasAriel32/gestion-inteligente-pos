# Prueba temporal de publicación en Cloudflare Workers

Fecha: 2026-10-22. Rama: `test/cloudflare-workers-preview`.
Punto de retorno: `4b40e3f8fd6b0ac0a239135906ccbfe7fb2c2a6d` en `main`.

## Alcance y criterio de aceptación

El propietario autorizó una prueba reversible de configuración para Workers. El
HTML publicado apuntaba a `/src/main.tsx`, sin compilar, y la página quedaba vacía.
Esta prueba publica exclusivamente los archivos compilados en `frontend/dist`.

Archivos afectados: configuración Wrangler, herramientas npm de raíz con lockfile,
adaptador HTTP de vista previa con pruebas, selección explícita del modo `workers`
en la interfaz y documentación. No cambia esquema, servidor, reglas comerciales,
contratos locales ni versión 0.5.1. No inicia la distribución Windows/F6.

Aceptación: TypeScript/Vite compilan tanto el modo local como `workers`; el paquete
de Wrangler se genera sin publicar; HTML/JS/CSS compilados se sirven correctamente;
la vista previa explica su alcance y no pide credenciales; `/api` y `/api/*`
devuelven JSON 503, nunca el HTML de la SPA ni un health de negocio ficticio.

## Qué se puede probar

- Carga de la interfaz con React compilado, estilos y fuente locales.
- Vista previa identificada y ayuda para visitantes desde el botón `?`.
- Recarga de rutas de página mediante fallback SPA.

La prueba **no incluye** login, alta de usuarios, catálogo editable, ventas, stock,
reportes operativos ni persistencia remota. El backend FastAPI/SQLite de esta
aplicación sigue siendo local. No hay datos simulados, contraseñas de demostración,
base cloud ni conexión desde el sitio público a `127.0.0.1` del visitante.
Todos los métodos de `/api/*` se rechazan con `LOCAL_BACKEND_REQUIRED` y 503.
Publicar el POS completo requeriría otro alcance y arquitectura de persistencia.

## Cloudflare conectado a GitHub

En el Worker existente `gestion-inteligente-pos`, seleccionar:

| Campo | Valor |
| --- | --- |
| Repositorio | `NicolasAriel32/gestion-inteligente-pos` |
| Rama para esta prueba | `test/cloudflare-workers-preview` |
| Root directory / directorio raíz | Raíz del repositorio (`/`), no `frontend` |
| Build command | Vacío: Wrangler ejecuta el build personalizado de `wrangler.jsonc` |
| Deploy command | `npm run deploy` |
| Node | 22 o superior |

Workers Builds debe instalar las dependencias npm de raíz usando su lockfile
(comportamiento automático habitual). Si esa instalación está desactivada, usar
`npm ci` como Build command. El comando de despliegue usa el Wrangler fijado en
`package-lock.json`; su build instala el frontend con `npm ci` y lo compila con
`--mode workers`. No requiere introducir secretos en el repositorio.

No usar `--assets .` ni `--assets frontend`: el único directorio público es
`frontend/dist`, declarado en la configuración. El adaptador Worker recibe primero
las rutas `/api`, para evitar que el fallback SPA responda HTML a solicitudes JSON.

La configuración GitHub del panel (rama, directorio y comandos) no se cambia por
crear este commit. Si el Worker sigue vinculado a `main`, este experimento no se
publica automáticamente. No se verificó un despliegue remoto desde esta sesión.

## Comandos desde la raíz

```sh
npm ci
npm run test:workers
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
npm run check:workers
npm run preview:workers -- --ip 127.0.0.1 --port 8787
```

`check:workers` compila con el modo web y ejecuta `wrangler deploy --dry-run`:
prepara el paquete sin publicarlo ni necesitar acceso a la cuenta. `preview:workers`
inicia una prueba local con el runtime de Workers. Abrir http://127.0.0.1:8787.

Solo cuando se quiera publicar, con autenticación propia de Cloudflare disponible:

```sh
npm run deploy
```

Las herramientas de compilación requieren internet para instalar paquetes. El modo
local conserva los comandos de README y su operación comercial sin servicios cloud.
`npm --prefix frontend run build` sigue generando la aplicación local normal; solo
`--mode workers` activa el aviso web y evita las llamadas de inicialización de API.

## Volver a PC

`main` permanece intacta: volver a esa rama recupera el código previo. Si el commit
se integra posteriormente, revertir exclusivamente el commit de este experimento
con `git revert <sha-del-commit>`; no hacer reset forzado ni borrar datos SQLite.
El Worker remoto conserva su última publicación hasta que se cambie o retire
explícitamente; cambiar una rama local no revierte una publicación de Cloudflare.

Para descargar el código previo como ZIP, usar Code → Download ZIP sobre `main`
en GitHub. Ese ZIP es código fuente: no equivale a un instalador para una PC sin
Python/Node. La distribución autónoma Windows sigue pendiente según INSTALLATION.

## Referencias oficiales

- https://developers.cloudflare.com/workers/static-assets/binding/
- https://developers.cloudflare.com/workers/wrangler/configuration/
- https://developers.cloudflare.com/workers/ci-cd/builds/configuration/

## Validación ejecutada

- `npm run test:workers`: 5 pruebas aprobadas (rutas API GET/POST y passthrough de assets).
- `npm --prefix frontend test`: 51 pruebas aprobadas, incluida una prueba DOM de la
  vista web sin inputs de credenciales, spinner ni solicitudes de API.
- `npm --prefix frontend run lint`: aprobado.
- `npm --prefix frontend run build`: TypeScript y compilación local normal aprobados.
- `npm run check:workers`: build en modo `workers` y empaquetado Wrangler dry-run
  aprobados, con 11 archivos estáticos y binding ASSETS. No subió archivos a la cuenta.
- Comprobación HTTP con servidor estático temporal en loopback: HTML, JS y CSS
  compilados devuelven 200 con sus tipos correctos; HTML sin `/src/main.tsx`.
- `git diff --check` y `node --check` del Worker y sus pruebas: aprobados.

Límites del entorno de validación: `wrangler dev --local` compiló pero no pudo iniciar
el runtime por `uv_interface_addresses returned Unknown system error 1`. La descarga
del navegador de Playwright no produjo un ZIP válido; no se ejecutó prueba visual/E2E
en Chromium. La prueba DOM no sustituye esa validación. No se ejecutaron pruebas backend
en esta intervención porque no cambió código Python ni migraciones. El despliegue remoto
y la prueba real de la URL de Workers quedan pendientes de seleccionar esta rama en el panel.
