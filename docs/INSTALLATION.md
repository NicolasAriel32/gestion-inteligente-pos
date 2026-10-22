# INSTALLATION — instalación, uso y actualizaciones

- Versión: 0.1
- Modalidad aprobada: aplicación local y sin internet
- Destino objetivo: Windows 11 de 64 bits; Windows 10 requiere evaluación explícita por fin de soporte general.

## Distribución objetivo (a validar en prototipo)
- Backend Python/FastAPI empaquetado con PyInstaller.
- Frontend React compilado y servido por backend local.
- Instalador Windows con Inno Setup y acceso directo.
- Sin necesidad de Python, Node, MySQL o Docker instalados en el cliente.

**Advertencia:** este documento define el objetivo, no confirma que el empaquetado ya funcione. Testear binario limpio en Windows antes de vender.

## Primer inicio
1. Comprobar arquitectura, permisos y espacio.
2. Crear carpetas privadas en LOCALAPPDATA.
3. Crear o migrar SQLite y verificar versión de esquema.
4. Ejecutar asistente local protegido de uso único.
5. Registrar cuenta ADMIN con contraseña segura, sin autorregistro público.
6. Mostrar inicio de sesión y comenzar la operación.

No admitir inicializaciones múltiples simultáneas; el bloqueo debe ser persistente y transaccional. El sistema no debe abrir puertos externos.

## Arranque
Acceso directo inicia la aplicación, comprueba una sola instancia, inicia servidor solo en 127.0.0.1 (puerto inicial 8765), espera health-check y abre navegador local. Si el puerto está ocupado, error entendible o selección segura alternativa (sin exponer red pública). Fallas registradas localmente.

## Apagado
Ofrecer salida controlada y cierre del servidor; cerrar una pestaña no debe cancelar a la fuerza una transacción iniciada. No terminar a mitad de escritura.

## Datos de usuario
Separados de instalación; actualización y desinstalación por defecto **no** eliminan DB, backups ni configuración. Borrado definitivo solo con consentimiento específico y advertencias.

## Respaldo y restauración
Herramienta administrativa con estado, fecha y resultado. Antes de restaurar detener escrituras, crear respaldo previo y verificar integridad. Explicar al usuario que backups del mismo equipo no protegen contra daño físico; habilitar exportación a medio externo.

## Actualizaciones futuras (fuera de MVP funcional)
Actualizador separado, iniciado por usuario: comprobar versión, descargar paquete por canal seguro cuando exista internet, validar firma/autenticidad + integridad, crear backup, detener proceso, aplicar actualización y migración, comprobar salud y permitir recuperación. Nunca reemplazar binarios mientras están en uso ni prometer rollback de datos sin prueba.

En la primera versión se acepta actualización manual asistida y documentada; no se implementa actualizador silencioso.

## Pruebas en PC limpia
- Instalación y primer ADMIN desde cero.
- Abrir y vender sin internet (cuando venta exista).
- Cerrar/reabrir y persistir datos.
- Bloqueo de segunda instancia.
- Puerto ocupado, falta de espacio y errores de archivos.
- Recuperación de respaldo real.
- Desinstalación preservando datos.
- Actualización de prueba sin pérdida de información.

## Desarrollo de identidad F2

La secuencia de desarrollo disponible está en [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).
Después de migrar, `python -m app.bootstrap` genera el secreto para el asistente inicial,
con vigencia de 30 minutos; `--renew` revoca uno pendiente, únicamente antes de inicializar.
Nunca imprime el secreto ni admite volver a inicializar una base con ADMIN.
Este procedimiento de desarrollo no equivale a instalador Windows validado.
