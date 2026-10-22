export type HelpRole = 'ADMIN' | 'EMPLOYEE' | 'GUEST'
export const helpTopics = ['Productos y precios', 'Stock', 'Caja e historial', 'Reportes', 'Equipo y acceso', 'Impresión y problemas'] as const
export type HelpTopic = typeof helpTopics[number]
export type HelpArticle = { id: string; title: string; topic: HelpTopic; audience: 'everyone' | 'signed-in' | 'ADMIN'; summary: string; steps: string[]; note?: string }

export const helpArticles: HelpArticle[] = [
  { id: 'create-product', title: '¿Cómo cargar un producto?', topic: 'Productos y precios', audience: 'ADMIN', summary: 'Creá el producto desde Catálogo. Solo el administrador puede hacerlo.', steps: [
    'Entrá en Catálogo. En el formulario Crear producto, completá Nombre del producto y Precio de venta (ARS).',
    'Si lo necesitás, completá Código, Categoría y Costo (ARS). El código es opcional y no se puede repetir; conserva los ceros iniciales.',
    'Indicá Stock mínimo para la alerta de pocas unidades. En Stock inicial cargá las unidades disponibles, o dejá cero.',
    'Si cargás unidades, escribí un Motivo de carga inicial de al menos 3 caracteres.',
    'Presioná Crear producto y esperá el aviso de confirmación. El producto aparecerá en la lista.',
  ], note: 'Escribí precios en pesos, sin separador de miles y con hasta dos decimales: por ejemplo 1250,50. Las cantidades son unidades enteras.' },
  { id: 'change-price', title: '¿Cómo cambiar el precio de un producto?', topic: 'Productos y precios', audience: 'ADMIN', summary: 'El nuevo precio se aplica a las próximas ventas; el historial conserva sus importes originales.', steps: [
    'Entrá en Catálogo y usá Buscar producto por nombre o código.',
    'En el producto, presioná Editar. En pantallas pequeñas, el formulario está debajo de la lista.',
    'Modificá Precio de venta (ARS), en pesos y sin separador de miles.',
    'Presioná Guardar producto y esperá la confirmación. Revisá el nuevo precio en la lista.',
  ], note: 'Si había una venta en revisión, quien vende debe revisar otra vez el importe actualizado antes de confirmarla.' },
  { id: 'categories', title: '¿Cómo organizo productos por categoría?', topic: 'Productos y precios', audience: 'ADMIN', summary: 'Las categorías se gestionan al pie de Catálogo.', steps: [
    'Entrá en Catálogo y buscá la sección Categorías.',
    'Escribí Nombre de categoría y presioná Crear categoría.',
    'Al crear o editar un producto, elegí esa Categoría y guardalo.',
  ], note: 'Desactivar una categoría no desactiva sus productos. Una categoría inactiva no se puede asignar a productos nuevos.' },
  { id: 'inactive-product', title: '¿Cómo desactivo o recupero un producto?', topic: 'Productos y precios', audience: 'ADMIN', summary: 'Los productos se desactivan y conservan su historial.', steps: [
    'En Catálogo, buscá el producto y presioná Desactivar.',
    'Revisá el nombre en la confirmación y elegí Desactivar producto, o Cancelar.',
    'Para recuperarlo, marcá Incluir inactivos, buscá el producto y presioná Reactivar.',
  ], note: 'Un producto inactivo no se vende ni admite ajustes manuales. Sus ventas anteriores siguen disponibles.' },
  { id: 'adjust-stock', title: '¿Cómo ingreso mercadería o corrijo el stock?', topic: 'Stock', audience: 'ADMIN', summary: 'Cada cambio se registra con motivo y con tu usuario.', steps: [
    'Entrá en Inventario y buscá el producto.',
    'Presioná Ajustar en ese producto.',
    'En Cambio de unidades indicá cuánto sumar o restar: 5 agrega cinco unidades y -2 quita dos. No ingreses el stock final.',
    'Completá Motivo del ajuste y presioná Confirmar ajuste.',
    'Revisá el aviso y los Movimientos del producto para comprobar el stock antes y después.',
  ], note: 'El sistema rechaza cambios que dejarían stock negativo. Para corregir una venta registrada, usá su anulación cuando corresponda, sin descontar o reponer manualmente esas mismas unidades.' },
  { id: 'low-stock', title: '¿Cómo veo los productos con pocas unidades?', topic: 'Stock', audience: 'signed-in', summary: 'La alerta compara existencias con el stock mínimo de cada producto.', steps: [
    'Entrá en Catálogo y activá Solo stock bajo.',
    'Consultá las unidades disponibles y el mínimo indicado en cada producto.',
    'Si hace falta cambiar el mínimo o cargar mercadería, pedíselo al administrador.',
  ] },
  { id: 'checkout', title: '¿Cómo registro una venta?', topic: 'Caja e historial', audience: 'signed-in', summary: 'Revisá productos, cantidades y cobro antes de confirmar.', steps: [
    'Entrá en Caja y usá Buscar para vender por nombre o código.',
    'Presioná Agregar en los productos y revisá sus cantidades en Tu carrito.',
    'Elegí el Medio de pago declarado. Comprobá el cobro por tu cuenta.',
    'Presioná Revisar importe. Revisá el total y luego Confirmar venta y registrar cobro.',
    'Esperá el comprobante con el número de venta. Para continuar, elegí Nueva venta.',
  ], note: 'Registrar transferencia o tarjeta no verifica un pago con el banco. El sistema no permite vender sin stock suficiente.' },
  { id: 'pending-sale', title: '¿Qué hago si una venta queda pendiente o no llega la respuesta?', topic: 'Caja e historial', audience: 'signed-in', summary: 'Recuperá la misma operación para evitar registrar el cobro dos veces.', steps: [
    'Conservá la pestaña y sus datos. Si aparece Comprobar una venta pendiente, usá Reintentar la misma venta.',
    'Si tu sesión venció, ingresá con la misma cuenta y volvé a Caja en esa pestaña para recuperar el intento.',
    'Comprobá el número de venta y su comprobante. Si cerraste definitivamente la pestaña, consultá Historial antes de volver a registrar la operación.',
  ], note: 'No crees otra venta para recuperar un comprobante y no borres los datos del navegador. El reintento disponible recupera la venta ya registrada sin duplicarla.' },
  { id: 'changed-price', title: '¿Por qué me pide revisar otra vez el importe?', topic: 'Caja e historial', audience: 'signed-in', summary: 'Puede haber cambiado un nombre, código o precio desde la revisión anterior.', steps: [
    'Revisá el mensaje de Caja.',
    'Presioná Revisar importe otra vez y comprobá los datos actualizados.',
    'Confirmá la venta solo después de acordar el nuevo importe y comprobar el cobro.',
  ], note: 'Revisar el importe no reserva unidades. Al confirmar, el sistema vuelve a comprobar precio y stock.' },
  { id: 'history', title: '¿Dónde consulto una venta o vuelvo a imprimir el ticket?', topic: 'Caja e historial', audience: 'signed-in', summary: 'Historial conserva los comprobantes registrados.', steps: [
    'Entrá en Historial. Podés elegir el Estado de venta; el administrador también puede Filtrar por persona.',
    'Buscá el número de venta y presioná Ver detalle.',
    'Para reimprimir el mismo comprobante, elegí Imprimir ticket de 58 mm.',
  ], note: 'Cada empleado consulta sus propias ventas; el administrador puede consultar todas. Reimprimir no registra otro cobro ni modifica el stock.' },
  { id: 'void-sale', title: '¿Cómo anulo una venta?', topic: 'Caja e historial', audience: 'ADMIN', summary: 'La anulación es total, devuelve las unidades una vez y conserva la venta.', steps: [
    'En Historial, buscá la venta y presioná Ver detalle.',
    'Completá Motivo de anulación y presioná Revisar anulación.',
    'Comprobá número y motivo en el diálogo. Elegí Confirmar anulación de venta, o Cancelar.',
    'Verificá el estado Anulada. Esa venta queda excluida de los reportes comerciales.',
  ], note: 'Solo ADMIN puede anular. No hay devoluciones parciales ni edición de ventas históricas.' },
  { id: 'daily-report', title: '¿Qué muestra el reporte del día?', topic: 'Reportes', audience: 'ADMIN', summary: 'Facturación, ventas, ticket promedio y unidades desde las 00:00 de Buenos Aires hasta la consulta.', steps: [
    'Entrá en Reportes, elegí Hoy en Período y presioná Consultar.',
    'Compará las métricas con ayer hasta la misma hora. Los intervalos aparecen en Actual y Anterior.',
    'Consultá Productos más vendidos por Unidades o Ingresos, y Ventas por hora por Transacciones o Facturación.',
    'Presioná Consultar de nuevo para actualizar los números.',
  ], note: 'Las anuladas no cuentan. Hora pico usa cantidad de transacciones. Sin ventas anteriores se indica Sin base de comparación.' },
  { id: 'report-range', title: '¿Cómo consulto otras fechas?', topic: 'Reportes', audience: 'ADMIN', summary: 'Podés consultar ayer, últimos 7/30 días o un rango personalizado.', steps: [
    'En Reportes elegí el Período.',
    'Para Rango personalizado, completá Desde y Hasta; ambos días están incluidos.',
    'Presioná Consultar y comprobá las fechas de Actual y Anterior.',
  ], note: 'Máximo 366 días, sin fechas futuras. Si el rango incluye hoy, corta al momento de consultar. Usa la hora de Buenos Aires.' },
  { id: 'team', title: '¿Cómo creo o desactivo una cuenta de empleado?', topic: 'Equipo y acceso', audience: 'ADMIN', summary: 'Cada persona debe usar su cuenta; no compartas tu acceso de administrador.', steps: [
    'Entrá en Equipo. En Crear empleado completá Usuario y una Contraseña única de 12 a 128 caracteres.',
    'Presioná Crear empleado y comprobá que aparezca en la lista.',
    'Para quitar el acceso, elegí Desactivar en esa cuenta y confirmá la desactivación.',
  ], note: 'Desactivar corta el acceso y conserva su historial. La recuperación o el cambio de contraseñas todavía no están disponibles.' },
  { id: 'permissions', title: '¿Por qué no puedo cambiar precios o entrar a Reportes?', topic: 'Equipo y acceso', audience: 'signed-in', summary: 'Las opciones disponibles dependen de tu rol.', steps: [
    'Con cuenta de empleado podés vender, consultar catálogo y existencias, y ver tus propias ventas.',
    'Para cambiar precios, productos, stock manual, cuentas, anulaciones o reportes, pedí ayuda al administrador.',
  ] },
  { id: 'login', title: '¿Qué hago si no puedo ingresar?', topic: 'Equipo y acceso', audience: 'everyone', summary: 'Revisá tu cuenta antes de volver a intentar.', steps: [
    'Comprobá Usuario y Contraseña, respetando mayúsculas y minúsculas en la contraseña.',
    'Si sos empleado, consultá al administrador si tu cuenta sigue activa.',
    'Si aparece un mensaje de sesión vencida, volvé a ingresar con tu cuenta.',
  ], note: 'La recuperación de contraseñas todavía no está disponible. Conservá los datos del equipo y solicitá asistencia; no borres la base ni vuelvas a inicializar el administrador.' },
  { id: 'printer', title: '¿Cómo preparo la impresora de 58 mm?', topic: 'Impresión y problemas', audience: 'everyone', summary: 'La impresión se hace con el controlador local y el diálogo del navegador.', steps: [
    'Instalá en Windows el controlador correspondiente a tu modelo y comprobá su página de prueba.',
    'En las preferencias del controlador elegí papel de 58 mm.',
    'Desde el comprobante, presioná Imprimir ticket de 58 mm y elegí esa impresora en el diálogo.',
    'Revisá escala 100 %, sin encabezados ni pies del navegador, y los márgenes que admita el modelo.',
  ], note: 'La compatibilidad física sigue pendiente de prueba con el modelo concreto. Cancelar o fallar la impresión no anula la venta; consultá su detalle para reimprimir sin volver a cobrar.' },
  { id: 'local-connection', title: '¿Qué hago si aparece Servidor local no disponible?', topic: 'Impresión y problemas', audience: 'everyone', summary: 'La aplicación funciona sin internet, pero necesita que el servicio local esté iniciado.', steps: [
    'Comprobá que la aplicación local esté iniciada en este equipo.',
    'Si la pantalla ofrece Volver a intentar o Reintentar reporte, usá esa opción cuando el servicio esté disponible.',
    'Si el mensaje sigue apareciendo, solicitá asistencia y conservá los datos del equipo.',
  ], note: 'Si estabas confirmando una venta, conservá la pestaña y seguí la guía de venta pendiente. No borres datos para intentar solucionar la conexión.' },
]

export function findHelp(role: HelpRole, query: string, topic = ''): HelpArticle[] {
  const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es-AR')
  const words = normalize(query.trim()).split(/\s+/).filter(Boolean)
  return helpArticles.filter(article => (article.audience === 'everyone' || article.audience === 'ADMIN' && role === 'ADMIN' || article.audience === 'signed-in' && role !== 'GUEST') && (!topic || article.topic === topic) && words.every(word => normalize([article.title, article.summary, ...article.steps, article.note ?? ''].join(' ')).includes(word)))
}
