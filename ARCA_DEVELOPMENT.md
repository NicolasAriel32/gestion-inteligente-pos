# Integración ARCA — incremento de conexión y homologación

## Diseño previo

El propietario pide integrar ARCA y probar con un primer comercio que ya factura por
otro medio. Al consultar condición fiscal y medio actual responde «No lo se no tengo
ejemplos». No se inventan esos datos. Es posible avanzar con contratos oficiales y
homologación, sin tomar una venta real como ensayo ni duplicar lo emitido por otro sistema.

Rama feat/arca-integration sobre candidato F6 452ae71, incorpora la especificación
obligatoria de PR #8. No se fusiona PR #7/#8 ni inicia F7. Producto candidato conserva
0.5.1; no se declara entrega fiscal completa ni versión 0.6.0 validada.

Incremento independiente verificable: configuración local protegida para homologación,
cliente SOAP de WSAA/WSFEv1, diagnóstico FEDummy sin credenciales y consulta autenticada
de puntos de venta. Interfaz ADMIN en Herramientas. No hay endpoints de emisión fiscal
ni conexiones a producción. Los comprobantes actuales siguen siendo no fiscales.
La emisión, impuestos, notas de crédito, contingencia y conciliación de documentos no
pueden declararse resueltos por este incremento: se mantienen como entregables pendientes.

## Contratos y seguridad

- GET /api/fiscal/status: ADMIN, metadatos públicos del certificado/configuración y
  etapa real. Sin claves privadas/tokens ni rutas recibidas desde HTTP.
- POST /api/fiscal/connection: ADMIN/CSRF, consulta explícita a FEDummy de homologación.
- POST /api/fiscal/access: ADMIN/CSRF, firma TRA PKCS#7 en Python, WSAA y
  FEParamGetPtosVenta. Contraseña opcional de clave privada en SecretStr/transitoria.
- --configure-arca offline: bloqueo de instancia, confirmación explícita, autenticación
  ADMIN actual, CUIT válido y archivos locales; copia protegida en perfil privado.
  Certificado/clave deben corresponder y estar vigentes. No pedirlos por chat.
- Configuración y cache TA privados fuera de SQLite/backups; publicación atómica y
  metadatos del certificado. Cache separado por certificado/CUIT/servicio/homologación,
  expiración con margen. Copia PKCS8 siempre cifrada con contraseña local nueva;
  contraseña nunca se guarda. Windows hereda ACL del perfil; TA privado sin cifrado
  adicional y fuera del respaldo comercial, límite de custodia explicado en la guía.
- Cryptography empaquetada firma CMS sin exigir OpenSSL en PC cliente. TLS verificado,
  endpoints fijos de homologación, sin redirects, tiempos/tamaños acotados, rechazo de
  DTD/entidades XML y errores genéricos sin reflejar XML/credenciales. No requests al
  arrancar ni reintentos automáticos de red.
- Sin tablas/migraciones nuevas ni cambios a venta/stock/dinero/restauración. Red fiscal
  solo por acción ADMIN; todo F1–F6 continúa local y sin actualización obligatoria.

## Archivos y verificación

Módulos domain/application/infrastructure/api fiscal, runtime CLI, FiscalPanel/cliente,
pruebas de parser/certificados/transporte/cache/auth y E2E; pyproject/build/CI/licencias,
specs y guía de configuración. Tests con claves efímeras y certificados ficticios.
Prueba real FEDummy sin credenciales si la red lo permite; no equivale a homologación
autenticada ni emisión. Documentar bloqueos reales del proxy/red por separado.
Regresión completa backend/frontend y E2E local sin solicitudes externas al operar;
build nativo y smoke Windows del paquete. No certificar otra versión Windows a partir
del reporte general del propietario ni marcar impresora probada.

## Fuentes

- https://www.arca.gob.ar/ws/documentacion/wsaa.asp
- https://www.arca.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.2.pdf
- https://www.arca.gob.ar/fe/ayuda/homologacion_externa.asp
- https://www.arca.gob.ar/fe/ayuda/documentos/wsfev1-RG-4291.pdf
- https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL

La página general lista manual WSFEv1 4.7 y homologación lista 4.8. Contrastar el PDF y
WSDL descargados para este incremento; no inferir soporte de emisión/CAEA aún no probado.

## Implementación y resultados reales — 2026-10-23 UTC

Módulos backend/app/{domain,application,api}/fiscal.py e infrastructure/arca*.py,
runtime --configure-arca, frontend FiscalPanel/fiscal.ts, OpenAPI y guía Windows.
Un archivo atómico contiene certificado/clave PKCS8 cifrada, fuera de SQLite/backup.
Contraseña local exigida incluso con TA cacheado; no se persiste en navegador. La
configuración exige instancia cerrada, ADMIN y confirmación; audita intención/resultado
con fingerprint público. No hay API HTTP para certificados, rutas locales o endpoints.

Tres operaciones SOAP1.1 fijas en homologación: loginCms, FEDummy, FEParamGetPtosVenta.
CMS adjunto DER RSA/SHA256 en Python, TRA servicio wsfe, uniqueId 32 bits, fechas UTC.
Cache durable ligado a identidad/expiración, margen 120 s. Acceso concurrente rechazado
409 sin cola/reintento. Transacción de autorización liberada antes de red. SOAPFault
traducido con mensajes propios sin reflejar payload. Sin tablas/migraciones fiscales.

Evidencia Linux Python 3.12.14/Node 24.19/Chromium 154:

| Comando / operación | Resultado observado |
| --- | --- |
| backend `.venv/bin/pytest -q` | 187 passed, 141.63 s; 16 nuevas fiscales |
| backend `.venv/bin/pytest tests/test_fiscal.py -q` | 16 passed, 3.78 s tras lectura acotada y ampliación de permisos EMPLOYEE |
| frontend `npm test` | 54 passed, 7 archivos |
| frontend `npm run build`, `npm run lint` | Aprobados |
| frontend `npx tsc --project tsconfig.e2e.json` | Aprobado |
| raíz `backend/.venv/bin/ruff check backend packaging` | Aprobado |
| backend pip check | Sin dependencias rotas |
| `POS_TEST_CHROMIUM=/usr/bin/chromium POS_F6_CAPTURE_DIR=/tmp/pos-arca-captures npm run test:e2e` | 1 passed, 46.1 s; F1–F6/ayuda, error fiscal simulado y gestión local preservada |
| FEDummy real con ArcaGateway/SoapTransport | homologation, healthy=true, application=OK, database=OK, authentication=OK |

Certificados efímeros autofirmados: firma CMS verificada con OpenSSL **solo en test**,
cifrado/mismatch/contraseña/vigencia, CUIT, namespace/escaping, XML inválido/DTD/UTF16/
tamaño/profundidad, SOAPFault/red sin secretos, TA tras reinicio/reconfiguración/cambio
CUIT, exclusión concurrente, roles/CSRF, auditoría y frontera de restauración. Backup
no incluye fiscal; restaurar conserva configuración y revoca sesiones. Sin certificado real.

Advertencia deprecación Starlette 1.9.0/httpx TestClient; suite aprobada. Venv limpio:
FastAPI 0.161.1, SQLAlchemy 2.1.6, Alembic 1.20.1, Cryptography 50.0.2. No se cambia
contrato del producto por esa advertencia. PNG móvil real 390 px inspeccionado, sin
desborde; axe/anchos 1366/390/320 pasan. Capturas locales /tmp/pos-arca-captures,
regenerables, sin contraseñas. Identidad Manrope/amarillo conservada.

### Contratos contrastados y límites

Descargas oficiales de esta ejecución (PDFs no se suben al repo):

| Recurso | SHA256 |
| --- | --- |
| WSFEv1 PDF 4.8 | 07c1866f67f3e95524464674de6d754fc1e75cfc9f9e915313ba2730f5cd1bf8 |
| WSFEv1 WSDL vivo | 16f5b8450c35a2cfc0187f07d6236162bb57b663954a1e1f0267e71afe90af24 |
| WSAA especificación 1.2.2 | ad7a68bc8b3dc3a8899e03457fb3d158274f0320676ac57fbda61479ab8447d6 |
| WSAA manual desarrollador | b52436973e46adcf848a14fe2a0595e8566ccf9e3be616a8985d43c7f65dfbff |
| WSAA WSDL vivo homologación | c8910060052496f248b125e676085db689e0f21b2f32728417725c376b97b4b3 |

El PDF 4.8 contiene una entrada 01/12/2026 posterior a esta ejecución: no se adoptan
cambios tributarios futuros. Las tres operaciones se contrastaron con WSDL vivo. La
especificación WSAA 1.2.2 menciona SHA1; el manual desarrollador oficial muestra
`openssl cms -sign` sin forzar digest. Se elige RSA/SHA256, firma verificada localmente;
aceptación con certificado autorizado **sin probar**, sin fallback automático a SHA1.
[Manual desarrollador](https://www.arca.gob.ar/ws/WSAA/WSAAmanualDev.pdf) y
[WSDL WSAA](https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL).

Autenticación real, puntos reales y emisión: **pendientes por falta de certificado y
perfil fiscal**. FEDummy no los sustituye. Paquete Windows con cryptography/smoke
nativo aprobado en esta rama (detalle debajo); no trasladar evidencia F6 previa. Windows 11
limpio, Windows exacto del propietario e impresora física pendientes. No se fusiona
F6 ni inicia F7. Producto permanece 0.5.1 candidato.

Capturas publicadas del estado sin certificado: [escritorio](docs/screenshots/arca/arca-tools-desktop.png) y [móvil](docs/screenshots/arca/arca-tools-mobile.png), productos ficticios y campos secretos vacíos.

## Paquete nativo Windows verificado

CI [39910712617](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39910712617)
y comprobación PR [39910783897](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39910783897)
aprobados para e4d4870. Entorno Windows Server 2025, Python builder 3.12.10,
PyInstaller 6.16.0; no certifica Windows 11 limpio ni la PC concreta del propietario.
Nueve comprobaciones del ejecutable instalado con PATH limitado a Windows System32:
instalación por usuario, preparación explícita, arranque, exclusión de instancia,
cryptography/clave cifrada/estado fiscal offline, importación/ventas/anulación/backup/
restauración/reportes/reautenticación, cierre, reinstalación y desinstalación preservando
DB/respaldos/configuración fiscal. Sin llamadas reales a ARCA en smoke Windows.
El builder genera certificado ficticio; la clave incorrecta devuelve 422 antes de red.
No se afirma firma CMS exitosa desde el ejecutable ni autenticación WSAA real.

ZIP artefacto [12482522256](https://github.com/NicolasAriel32/gestion-inteligente-pos/actions/runs/39910712617/artifacts/12482522256),
21 582 683 bytes, expira 2026-10-30. Incluye instalador, build-info.json y windows-smoke.json.
ZIP SHA256: `987ba9c0a71e2bedbc1bfe47917eacb4188ed28ce89c600f0bfe825996a3cb63`.
Instalador `GestionInteligentePOS-0.5.1-ARCA-connection-candidate-setup.exe`,
22 100 043 bytes, SHA256 `ce4420cff4b3e4ef7b8f1cf2171d9b840599938c76f9afc2daba012bb3b55ee1`.
Se descargó ZIP, verificó hash/contenido y se comprobó en build-info que están
cryptography-50.0.2, _rust.pyd, libcrypto-3.dll y sus licencias. No se ejecutó EXE en Linux.
[Evidencia smoke](docs/validation/arca/windows-smoke.json).

PR [#9](https://github.com/NicolasAriel32/gestion-inteligente-pos/pull/9) en borrador,
base feat/f6-backup-import-distribution. No fusionado. Las ampliaciones finales de tests/
documentación no cambian el software del paquete e4d4870; su CI se reporta por separado.
Metadata editable reinstalada sin actualizar dependencias: backend 0.5.1 y Requires-Dist
cryptography==50.0.2 confirmados. El entorno de instalación inicial precedía ese cambio
de pyproject; se corrigió la metadata además de instalar la biblioteca.
