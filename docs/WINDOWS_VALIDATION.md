# Validación Windows F6 — pendiente de PC objetivo

No completar esta lista por construir en Linux o por revisar scripts. La CI Windows
Server y una PC Windows 11 limpia son evidencias diferentes; registrar cada resultado.
La prueba física de impresora de 58 mm mantiene su pendiente independiente.

## Construcción nativa

En Windows 11 x64 con Python 3.12, Node >=22 e Inno Setup 6.x:

```powershell
./packaging/build-windows.ps1
python packaging/smoke_installer.py
```

PyInstaller 6.16.0 fijado en requirements-build.txt. La PC que construye necesita esas
herramientas; la PC cliente no. El script genera onedir, inventario SHA-256/build-info y
setup candidato; incluye frontend, Manrope/OFL, licencias, IANA y migraciones.
No es release firmado: no afirmar firma de código ni desactivar SmartScreen/antivirus
para ocultar un fallo. Registrar advertencias reales. Artefactos no se versionan en Git.

Workflow windows-candidate.yml: build nativo en runner Windows, prueba silenciosa de
instalar/preparar/iniciar/importar/respaldar/restaurar/reinstalar/desinstalar con datos
temporales. PATH del ejecutable no contiene herramientas de desarrollo. Esto no prueba
una PC Windows 11 limpia ni su cuenta estándar; conservar esa diferencia en el informe.

## Prueba humana en Windows 11 limpio

Usar Windows Sandbox/VM de prueba si está disponible, sin datos del comercio ni Python,
Node, herramientas de build o servicios externos obligatorios. No instalar sobre la
PC comercial para probar. Registrar Windows/build/arquitectura, usuario estándar,
checksum del setup y capturas reales.

- [ ] Instalación por usuario sin exigir elevación innecesaria.
- [ ] Preparación explícita de DB, secreto inicial privado y alta ADMIN única.
- [ ] Arranque de acceso directo, health, navegador y una sola instancia.
- [ ] Login, empleado, producto/stock, venta, anulación y reportes sin internet.
- [ ] Importación CSV válida/incorrecta, ceros iniciales y reintento sin duplicados.
- [ ] Crear respaldo con WAL/ventas, descargar externamente e incorporar/restaurar.
- [ ] Cierre de sesiones y conservación de ventas/stock/instantáneas restaurados.
- [ ] Cierre controlado y reapertura sin servidor huérfano ni bloqueo residual.
- [ ] Puerto ocupado: no cerrar servicio ajeno ni abrir red pública.
- [ ] Permisos/espacio insuficientes y archivos corruptos: error claro sin pérdida.
- [ ] Interrupción de restore: rechazo de arranque y recuperación ADMIN explícita.
- [ ] Actualización desde instalación anterior compatible, respaldo y verificación.
- [ ] Reinstalación y desinstalación conservan datos/backups/configuración.
- [ ] ACL de carpetas privadas y escucha exclusiva en 127.0.0.1.
- [ ] Teclado/foco, contraste, texto legible, escala Windows y navegador objetivo.

F6 permanece pendiente hasta que los criterios obligatorios tengan evidencia real.
Las casillas no autorizan F7/piloto; el propietario debe aprobarlo por separado.
