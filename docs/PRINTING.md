# Tickets locales de 58 mm

Requisito del propietario agregado durante F4: poder imprimir tickets no fiscales en
térmicas económicas de 58 mm, como modelos Global o Waggs de Mercado Libre.
La marca por sí sola no identifica interfaz, lenguaje ni compatibilidad de controlador.
Modelo exacto/enlace solicitado; no se presume una impresora conectada a este entorno.

## Primera integración

- Instalar el controlador de Windows correspondiente al modelo y comprobar su página
  de prueba. Preferir USB/controlador oficial para la PC local; no requiere cloud.
- Configurar papel de 58 mm en las preferencias del controlador. El ancho imprimible
  puede ser menor que 58 mm y varía por modelo; la vista F4 deja márgenes y usa 48 mm
  de contenido como punto inicial, que debe ajustarse con una impresión física.
- Desde una venta registrada o desde su historial, usar Imprimir ticket y seleccionar
  esa impresora en el diálogo del navegador. Escala 100 %, sin encabezados/pies del
  navegador, sin ajustar a A4. Revisar los márgenes que admita el controlador.
- Ticket blanco y negro, tipografía local y ajuste de nombres/códigos largos. Muestra
  moneda ARS en pesos, unidades, importes, fecha Buenos Aires, vendedor y estado.
- El botón dice Imprimir, nunca Impreso: window.print abre el diálogo pero no informa
  recepción, papel, corte ni éxito físico. Venta y stock ya están confirmados antes.
- Cancelar o fallar la impresión no repite la venta ni la anula. Reimprimir recupera el
  mismo ID y sus instantáneas; no crea movimientos ni pagos nuevos.

## Validación y límites

Validar con emulación print/PDF del navegador y prueba E2E de que Imprimir no envía un
nuevo POST de venta. Esto verifica el documento y el flujo, no el hardware.
La aprobación del soporte físico requiere modelo concreto, Windows/controlador y
ticket real legible, incluyendo acentos, nombres largos y anulación.

Evidencia digital F4: PDF/PNG reales en docs/screenshots/f4 y resultados en
[F4_DEVELOPMENT.md](../F4_DEVELOPMENT.md). Papel solicitado 58 × 200 mm;
pdfinfo muestra ~58.25 × 200.07 mm por redondeo del motor. Contenido de 48 mm sin
desborde, código de 64 caracteres y anulación legibles en el documento extraído.
El controlador sigue siendo quien configura el papel físico y sus márgenes.

No se implementa impresión silenciosa, envío ESC/POS directo, apertura de cajón ni
consulta de estado USB/Bluetooth en F4. Si se necesita alguno, evaluar modelo, protocolo,
permisos de Windows y spooler local antes de incorporar un adaptador. No agregar QZ Tray,
servicios cloud o bibliotecas de impresora sin justificar la necesidad y documentarla.
