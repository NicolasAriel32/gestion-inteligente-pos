# Facturación fiscal integrada con ARCA

Estado: **requisito obligatorio aceptado por el propietario; no implementado**.
Registro: 2026-10-22, fecha local de Buenos Aires. ADR-016.

## Cambio de alcance y diseño previo

El propietario pide que la facturación fiscal sea obligatoria para el POS comercial.
Reemplaza la exclusión anterior de facturación fiscal del MVP. El software 0.5.1 y el
candidato F6 distribuido siguen emitiendo tickets no fiscales: esta especificación no
los convierte en facturadores ni modifica el ZIP entregado. F6 mantiene su cierre
pendiente; F7 no empieza por documentar este cambio. La obligación es una condición
de aceptación comercial, no una orden de bloquear el arranque de instalaciones existentes.

Incremento actual: actualizar alcance, reglas, arquitectura y aceptación; conservar
informes históricos, versiones, código y esquema. Publicar propuesta documental en una
rama separada de F6. No emitir comprobantes reales ni solicitar claves por chat.

Antes de implementar, definir condición fiscal del emisor/receptores, tipos de comprobante,
tratamiento impositivo y contingencia aplicable. Se consultó al propietario si la primera
integración debe cubrir monotributistas, responsables inscriptos o ambos; respuesta pendiente.
No deducir su situación tributaria de la experiencia de otra comerciante. La condición
de cada comercio y sus obligaciones deben validarse con su responsable contable.

## Resultado exigido

El usuario debe emitir desde el POS los comprobantes fiscales correspondientes a las
operaciones alcanzadas, obtener la autorización y conservar su vínculo con la venta,
sin recargarla manualmente en otro sistema. La interfaz debe distinguir venta registrada,
pago declarado y comprobante autorizado. La mensualidad de otro proveedor no determina
la modalidad fiscal ni el precio del producto.

Alcance obligatorio a concretar: configuración ADMIN de emisor/punto de venta, clases
de factura que correspondan (C y/o A/B según alcance confirmado), impuestos y datos de
receptor, autorización/consulta, representación con QR y datos fiscales, notas de crédito
vinculadas y conciliación. No equivale a implementar pagos bancarios ni liquidación
automática de impuestos. Otros regímenes especiales necesitan alcance propio.

## Fuentes oficiales revisadas

1. [Servicios de factura electrónica](https://arca.gob.ar/ws/documentacion/ws-factura-electronica.asp):
   WSFEv1 figura entre las interfaces disponibles; elegir el servicio según el régimen.
   La página enlaza el manual 4.7. Su PDF dio timeout en esta revisión: no se validaron
   contratos SOAP ni se probó el servicio. Leer el manual vigente antes de implementarlo.
2. [Autenticación WSAA](https://arca.gob.ar/ws/documentacion/wsaa.asp): certificados y
   habilitaciones separados para homologación y producción.
3. [Solicitud de autorización](https://www.arca.gob.ar/fe/emision-autorizacion/solicitud-autorizacion.asp):
   punto de venta habilitado y numeración correlativa.
4. [QR](https://www.arca.gob.ar/fe/qr/conceptos-generales.asp): representación del código
   y datos de comprobante según especificaciones oficiales.
5. [Contingencias](https://arca.gob.ar/fe/emision-autorizacion/contingencias.asp): existen
   modalidades y condiciones específicas; no basta una cola local de ventas pendientes.

Las referencias deben revalidarse al implementar. La página de servicios y la de
contingencias describen alcances CAEA diferentes para clases de comprobante; resolverlos
con manual/normativa vigente y situación del emisor antes de prometer cobertura offline.
No se presupone que CAEA esté disponible para todos los comercios.

## Diseño técnico propuesto, pendiente de implementación

- Módulo fiscal por capas, con puerto de emisión/consulta y adaptadores de ARCA. Backend
  sigue en loopback; las conexiones salientes fiscales son una excepción explícita a la
  independencia de red del núcleo. No se introduce una plataforma cloud de gestión ni
  un intermediario pago obligatorio por esta decisión.
- ADMIN configura CUIT, condición fiscal, punto de venta y certificados mediante un
  flujo local protegido. Empleado puede emitir al vender según permisos del caso de uso,
  sin ver claves. Claves privadas/tokens no van a frontend, repositorio, logs ni chat.
  Política de custodia, renovación y respaldo de credenciales pendiente de diseño.
- Separar venta, comprobante fiscal, intentos de autorización y documentos compensatorios.
  Conservar instantáneas fiscales e importes exactos, con impuestos/redondeos calculados
  en servidor. La extensión requerirá una migración nueva revisada: no editar 0001–0006.
- Persistir intención y resultado durables, con identidad de operación y exclusión
  concurrente por emisor/ambiente/punto/tipo/número. Nunca mantener una transacción SQLite
  de escritura abierta mientras se espera a ARCA. El flujo distribuido necesita
  recuperación y conciliación; no puede prometer atomicidad de SQLite con el servicio.
- Estados mínimos conceptuales: pendiente, en consulta por respuesta incierta, autorizado
  y rechazado. Consultar antes de reenviar una solicitud incierta; no asignar otro número
  ni volver a cobrar/reponer/descontar stock para resolver una respuesta perdida.
- El comprobante autorizado conserva su identidad y autorización. Reimpresión no emite
  otro. Una anulación local no cancela un documento fiscal: el flujo debe gestionar la
  nota de crédito correspondiente y distinguir efectos fiscales, de cobro y de inventario.
- Restaurar un respaldo no retrocede lo autorizado externamente. Antes de reanudar la
  emisión debe conciliarlos con ARCA y detectar documentos posteriores a la copia. No
  prometer reconstrucción de ítems perdidos a partir de una consulta sin ese detalle.

## Internet, contingencia y uso local

El POS conserva arranque, catálogo, inventario e historial locales. Tener otra versión
disponible, carecer de conexión o no actualizar no bloquea su apertura. Las actualizaciones
siguen siendo manuales y voluntarias. El ticket de prueba continúa identificado no fiscal.

La emisión con CAE requiere comunicarse con ARCA. Una operación registrada sin respuesta
de autorización no se presenta como factura emitida. Para uso comercial sin comunicación,
definir y validar una contingencia fiscal habilitada, sus plazos, numeración, información
posterior y conciliación. No asumir que emitir después de reconectar cumple por sí solo.
La aplicación debe mostrar el estado real y orientar al procedimiento habilitado; no
ofrecer una opción comercial para ocultar operaciones alcanzadas por facturación.

## Criterios de aceptación pendientes

| ID | Evidencia requerida |
| --- | --- |
| AT-FIS-01 | Configuración ADMIN y separación homologación/producción; sin secretos en UI/logs/respuestas |
| AT-FIS-02 | Emitir en homologación las clases acordadas y consultar autorización/estado con datos e impuestos exactos |
| AT-FIS-03 | Dos intentos concurrentes o respuesta perdida conservan un solo comprobante y una venta/stock/pago |
| AT-FIS-04 | Rechazo, timeout y reinicio dejan estado durable y recuperación sin inventar autorización |
| AT-FIS-05 | Documento autorizado con datos fiscales y QR válidos; reimpresión sin otra emisión |
| AT-FIS-06 | Nota de crédito vinculada y reintento sin doble efecto fiscal, cobro o inventario |
| AT-FIS-07 | Corte de red/caída de ARCA sigue el régimen de contingencia validado y concilia al recuperar |
| AT-FIS-08 | Restaurar copia anterior a una emisión externa no reutiliza números ni duplica comprobantes |
| AT-FIS-09 | Regresión F1–F6, roles y uso local preservados; migración interrumpida/reintentada con SQLite real |
| AT-FIS-10 | Validación contable del alcance y procedimiento; producción habilitada por acción concreta del titular |

Todos están **sin ejecutar**. Simular SOAP no constituye homologación. No usar datos
comerciales ni producción para probar. Los certificados de homologación se configurarán
localmente cuando corresponda; nunca pedir que se peguen claves fiscales aquí.

## Riesgos y siguientes decisiones

Duplicados tras timeout/restauración, huecos o reutilización de numeración, dinero/IVA
mal calculados, confundir anulación con nota de crédito, contingencia no habilitada y
exposición de claves. Definir además el tratamiento contable de ventas pendientes y
comprobantes de corrección en reportes, sin alterar retrospectivamente F1–F5.

Revisadas las páginas oficiales y la coherencia documental; todavía no hay adaptador,
tablas fiscales, endpoints, homologación ni habilitación de producción implementados.

## Validación de esta actualización documental

Se revisaron fuentes oficiales, referencias locales, reglas BR-FIS/AT-FIS y coherencia
del alcance; git diff --check sin errores. Cambios restringidos a Markdown, sin alterar
código, dependencias, versiones, migraciones ni documentos históricos F1–F6/ayuda.
No se ejecutaron suites de aplicación porque no cambió software. No hay resultados
de homologación ni de emisión real; los diez criterios fiscales siguen pendientes.
