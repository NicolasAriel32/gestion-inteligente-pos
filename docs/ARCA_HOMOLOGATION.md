# Conexión ARCA de homologación

Este candidato agrega una conexión de prueba. **Todavía no factura**: no emite CAE,
notas de crédito ni QR fiscal. Los comprobantes actuales siguen siendo no fiscales y
el comercio debe conservar su medio de facturación actual. Producción no tiene endpoint
ni configuración habilitados. No se fusionan F6 ni esta rama por publicar un candidato.

## Qué se puede comprobar

ADMIN → Herramientas → ARCA permite consultar la configuración local, comprobar
infraestructura con FEDummy (no requiere certificado) y verificar autenticación WSAA
con consulta de puntos de venta WSFEv1. Cada conexión requiere pulsar un botón e internet;
la aplicación arranca y opera localmente sin consultar ARCA ni versiones del programa.
Una respuesta OK de FEDummy no verifica el certificado ni habilita facturación.

## Configurar el certificado localmente

El titular/responsable debe obtener un certificado **de homologación** en WSASS y
asociarlo al servicio **wsfe** para el CUIT representado siguiendo la
[documentación oficial WSAA](https://www.arca.gob.ar/ws/documentacion/wsaa.asp).
Este incremento no genera CSR, obtiene certificados ni modifica habilitaciones ARCA.
No usar credenciales de producción ni compartir claves por chat/email.

1. Terminar operaciones y cerrar desde Herramientas → Cerrar aplicación.
2. Windows: menú Inicio → Gestión Inteligente POS → Configurar ARCA homologación.
   Desarrollo: desde backend con el entorno activado, `python -m app.runtime --configure-arca`.
3. Autenticarse con ADMIN del POS y confirmar `CONFIGURAR ARCA`.
4. Ingresar CUIT (11 dígitos) y rutas completas de certificado X.509 PEM RSA ≥2048 bits
   vigente y clave PEM correspondiente. Se permite representar otro CUIT autorizado;
   no se infiere condición fiscal desde el certificado.
5. Ingresar contraseña de la clave fuente si está cifrada; elegir y repetir una nueva
   contraseña local de 12–128 caracteres. Se guarda una copia PKCS8 cifrada aunque el
   original no lo esté. La contraseña no se almacena ni se pasa por argumentos CLI.
6. Reabrir → Herramientas → ARCA e ingresar esa contraseña local para verificar acceso.
   El resultado lista puntos, modalidad, bloqueo y baja; no selecciona ni habilita uno.

Solo se comprueban formato, vigencia y coincidencia local del certificado/clave; su
cadena/emisor y autorización se comprueban al consultar WSAA. Guardar un archivo no
demuestra que ARCA lo haya emitido o autorizado. Los ejemplos de tests son autofirmados
y ficticios, nunca credenciales válidas ni facturas.

## Custodia, respaldo y errores

Archivos privados bajo `%LOCALAPPDATA%\GestionInteligentePOS\config\fiscal`, fuera de
binarios y SQLite. En Linux se exigen archivos 0600/directorio 0700; Windows hereda ACL
del perfil del usuario. La clave se cifra siempre. El TA de WSAA contiene token/sign
en cache privado, sin exportación HTTP; no está cifrado adicionalmente y requiere
mantener protegido el perfil del sistema. No protege frente a un administrador del SO
o malware que controle la cuenta. Ninguna contraseña/token/clave se devuelve a UI/logs.

Los `.posbackup` contienen solo datos comerciales y manifiesto: **no incluyen** estos
archivos. Conservá originales cifrados y contraseñas por separado en un medio privado.
Reinstalar/desinstalar conserva el perfil; restaurar SQLite no reemplaza las credenciales
ni revoca un TA. Configurar el mismo CUIT/certificado conserva el cache vigente; otro
CUIT/fingerprint nunca lo reutiliza. No borrarlo para forzar renovación: WSAA puede
responder `coe.alreadyAuthenticated`. Si se pierde, esperar su vencimiento.

Errores de red, SOAP inválido, contraseña o configuración no bloquean el POS. La UI
indica el error sin copiar respuestas remotas. Revisar reloj, certificado, CUIT y
asociación wsfe. Configuración corrupta debe repararse mediante el procedimiento
ADMIN; cache corrupto requiere intervención local, sin renovación automática oculta.

## Lo que sigue pendiente

Confirmar régimen/clases/impuestos, diseñar estados y migración fiscal, emisión y
consulta recuperable, receptor, notas de crédito, QR, contingencia y conciliación
tras restaurar. Luego ejecutar homologación autenticada y validación contable antes
de habilitar producción con autorización concreta del titular. Este incremento no
declara satisfechos AT-FIS-01..10 ni la entrega comercial completa.
