# Candidato Windows desde main — 2026-10-23 UTC

El propietario pide que los cambios implementados estén en main antes de descargar el
ZIP. Esto autoriza integrar F6 (PR #7), la especificación fiscal (PR #8, ya incluida en
la rama ARCA) y conexión de homologación (PR #9). No autoriza F7 ni emisión fiscal real.
La integración no completa la validación pendiente Windows 11/impresora ni transforma
el candidato 0.5.1 en entrega fiscal comercial. Las restricciones históricas de no
fusionar respondían a autorizaciones anteriores, sustituidas por esta instrucción.

## Diseño previo

Se constató main en 4b40e3f y PR #7/#8/#9 todavía en borrador. PR #9 tiene como ancestros
F6 452ae71 y propuesta fiscal 0d32499. Orden: integrar #7, retarget #9 a main e integrar
#9 conservando sus ancestros. Verificar que #8 quede incorporado y cerrar su estado si
GitHub no lo reconoce automáticamente. No incorporar ramas experimentales Cloudflare.

Hallazgo: windows-candidate.yml no construye en pushes a main; sus ZIP existentes son
de ramas/PR. La publicación usaba always(), por lo que podía ofrecer binario aunque
fallase smoke. Corregir: incluir main/ejecución manual, preparar ZIP descargable después
de smoke correcto y subir solo si todo aprobó. Build-info identifica commit/ref reales.
El ZIP descargable tendrá instalador y LEEME en raíz, guía ARCA, manifest, smoke y hashes.
No confundir Code → Download ZIP (fuentes) con artefacto Windows (programa empaquetado).
Nunca reinstalar automáticamente ni consultar actualizaciones al iniciar el POS.

Archivos afectados: workflow, packaging/build.py, packaging/prepare_download.py y
documentación vigente. Sin cambios a negocio, esquema, bases de comercios o dependencias
runtime. Riesgos: enlazar un ZIP viejo/de PR, entregar binario sin smoke, confundir merge
con homologación fiscal. Aceptación: ancestros #7/#8/#9 en main, build/smoke Windows desde
main correctos, ZIP descargado con hash/manifest de ese commit y entradas esperadas.

## Evidencia previa y limitaciones

Windows CI de PR #9 39911245533 aprobó; pruebas previas 187 backend/54 frontend y E2E
están en ARCA_DEVELOPMENT.md. Deben distinguirse de la regresión y build de esta integración.
Check externo Cloudflare Workers del mismo head falló con «This Worker does not exist
on your account». No es el build Windows ni una dependencia del POS local; no se modifica
esa integración externa. No afirmar que todos los checks del repositorio están verdes.
No se ejecuta ahora la auditoría integral: su prompt se entregó por separado.
