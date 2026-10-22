# Hallazgos de ingeniería y prácticas aprendidas

Registro mantenido desde la revisión de F2 (2026-10-22). Cada hallazgo conserva su
reproducción, causa, fix y prueba preventiva. Un resultado positivo del flujo habitual
no sustituye pruebas de interrupción, recuperación y rechazo de estados incompatibles.

## H-F2-001 — DDL SQLite fuera de una transacción física

- Prioridad: P2. Estado: corregido y validado; ver resultados finales en [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).
- Síntoma reproducido: interrumpir 0002 antes de crear sessions dejaba users y bootstrap,
  pero alembic_version seguía en 0001. Reintentar fallaba con «table users already exists».
- Causa: sqlite3 en modo legacy no inicia automáticamente una transacción para CREATE
  TABLE. El contexto lógico de SQLAlchemy/Alembic no demostraba atomicidad del DDL.
- Fix: BEGIN IMMEDIATE físico dentro del contexto transaccional de SQLAlchemy;
  transactional_ddl=True en Alembic. DDL y revisión se confirman juntos o se revierten.
  El engine se libera también si ocurre una excepción. El modo offline emite BEGIN/COMMIT.
- Regresión: test_failed_identity_migration_rolls_back_ddl_and_can_retry, que copia las
  migraciones a una carpeta temporal, inyecta un fallo intermedio, comprueba que solo
  persiste el baseline y luego ejecuta el upgrade real correctamente.
- Por qué no se detectó antes: se probaba upgrade exitoso y repetido, sin fallos a mitad.
- Práctica para otro proyecto: verificar la transacción física del driver usado, no
  inferirla del nombre del contexto. Probar fallo intermedio, estado en una conexión nueva
  y reintento. No reparar producción borrando tablas ni cambiando la revisión a mano.
- Límite: la prueba inyecta una excepción real; no demuestra tolerancia a daño físico,
  corrupción o fallos del disco. Los respaldos siguen siendo obligatorios en despliegues.

## H-F2-002 — Arranque sin comprobar compatibilidad del esquema

- Prioridad: P2. Estado: corregido y validado; ver resultados finales en [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).
- Síntoma reproducido: FastAPI iniciaba y devolvía 200 en health con una migración incompleta.
- Causa: lifespan construía los servicios sin validar la revisión ni la estructura necesaria.
- Fix: verificar revisión exacta y presencia de tablas/columnas requeridas antes de habilitar
  endpoints. Ante incompatibilidad se rechaza el arranque con un mensaje operativo seguro;
  no se migra, borra ni repara automáticamente. Se dispone el engine incluso si falla la validación.
- Regresión: tests/test_schema.py cubre base vacía, revisión anterior/futura, tabla ausente,
  columna ausente y base válida. Los casos de versión comprueban conservación de datos.
  Los tests de health ahora usan una base realmente migrada.
- Por qué no se detectó antes: health se trataba como prueba suficiente de disponibilidad;
  los casos de identidad solo se ejecutaban con fixtures correctamente migradas.
- Práctica para otro proyecto: definir las condiciones de disponibilidad y comprobarlas
  antes de aceptar tráfico. Probar versiones anteriores y posteriores, además de estructura
  incompleta. Actualizar el contrato de arranque cada vez que cambia la revisión requerida.
- Límite: el contrato comprueba revisión, tablas y columnas; no sustituye una comprobación
  integral de corrupción, restricciones, índices, permisos del sistema o compatibilidad Windows.

## H-F2-003 — Metadatos incompletos podían proponer borrados

- Prioridad: P2. Estado: corregido y validado; ver resultados finales en [F2_DEVELOPMENT.md](../F2_DEVELOPMENT.md).
- Síntoma reproducido: compare_metadata contra Base.metadata vacío proponía remove_table
  para users, sessions, bootstrap y audit_log. No se ejecutaron esos borrados.
- Causa: las tablas se creaban por migraciones SQL manuales, mientras Alembic recibía un
  MetaData vacío como si fuera la definición completa deseada.
- Fix: target_metadata=None: Alembic rechaza --autogenerate antes de generar una revisión.
  Se conserva el esquema de migraciones manuales; no se modifica la migración 0002 publicada
  ni se introduce un modelo ORM paralelo incompleto.
- Regresión: test_autogenerate_refused_without_changing_files_or_data ejecuta el comando
  CLI real, exige rechazo por falta de MetaData y compara archivos y datos antes/después.
- Por qué no se detectó antes: se validaban upgrades escritos manualmente, sin comprobar
  el comportamiento de las herramientas de generación.
- Práctica para otro proyecto: una herramienta automática necesita una fuente de verdad
  completa. Si aún no existe, deshabilitar explícitamente esa capacidad y probar el bloqueo.
  Antes de habilitarla, una comparación contra una DB en head debe producir cero diferencias.
- Límite: la autogeneración permanece deshabilitada deliberadamente. No afirmar que está
  soportada ni usar un MetaData vacío para eludir el bloqueo.

## Cómo usar este registro en el próximo proyecto

Copiar o adaptar [PROJECT_REVIEW_CHECKLIST.md](PROJECT_REVIEW_CHECKLIST.md) y revisar estos
hallazgos al definir persistencia, arranque y validación. Para cada nuevo fallo agregar ID,
impacto, reproducción, causa, fix, prueba, resultado y práctica transferible. Vincularlo desde
AGENTS.md del nuevo repositorio; este archivo no configura automáticamente otros proyectos.


## H-UI-001 — Contexto TypeScript incompleto en pruebas del navegador

- Prioridad: P2. Estado: corregido y validado.
- Reproducción: al agregar evaluaciones DOM a Playwright, build falló con TS2584/TS2304:
  document, getComputedStyle y HTMLInputElement no existían en el proyecto TypeScript de Node.
- Causa: e2e estaba incluido en tsconfig.node.json, que solo declaraba ES2022.
- Fix: separar tsconfig.e2e.json, con tipos de Node y bibliotecas DOM/DOM.Iterable;
  añadirlo a las referencias del build. No silenciar errores ni usar ts-ignore.
- Regresión: npm run build comprueba también los archivos E2E.
- Práctica transferible: identificar qué código corre en Node y qué callbacks se ejecutan
  en el navegador; darles un proyecto de tipado explícito sin debilitar el código de producción.

## H-UI-002 — Foco perdido al cerrar un diálogo y recorrido Tab impredecible

- Prioridad: P2. Estado: corregido y validado.
- Reproducción: Escape desmontaba el diálogo y el foco no regresaba al botón Desactivar.
  Al tabular desde la última acción, Chromium podía llevar foco fuera de las acciones del diálogo.
- Causa: se confiaba únicamente en la restauración nativa al desmontar el componente React;
  el ciclo de vida y los extremos de tabulación no estaban cubiertos.
- Fix: guardar el elemento invocador y restaurarlo si sigue conectado; enfocar Cancelar
  al abrir; gestionar Tab/Shift+Tab entre acciones habilitadas. Mantener dialog modal nativo
  para la semántica y la inactividad del contenido de fondo.
- Regresión: Playwright prueba Cancelar inicial, Escape, retorno al invocador, Enter,
  ambos extremos de tabulación y confirmación. Axe analiza también el diálogo visible.
- Práctica transferible: probar abrir, actuar, cancelar y volver con teclado; no validar un
  diálogo solo con mouse. Si el invocador desaparece tras una acción, dirigir foco al resultado.

## H-UI-003 — Dos componentes competían por el foco tras una operación

- Prioridad: P2. Estado: corregido y validado.
- Reproducción: tras crear un empleado, el aviso de éxito recibía foco cuando debía
  volver al campo Usuario para continuar. El intento de focus previo ocurría con fieldset deshabilitado.
- Causa: un aviso global y un formulario administraban el mismo cambio de foco, sin esperar
  a que terminara el estado busy.
- Fix: el formulario restaura foco después de habilitarse. Los avisos de éxito anuncian
  el resultado sin mover foco, salvo acciones como desactivación que eliminan el invocador.
  Los errores sí reciben foco. Se bloquean acciones relacionadas mientras se envía un alta.
- Regresión: E2E exige foco en Usuario después del alta y en el aviso tras error de login;
  verifica campos/botón deshabilitados y un único envío ante un submit repetido.
- Práctica transferible: asignar un único responsable del foco por operación y probar el
  momento posterior a la actualización del DOM, no solo la apariencia de carga.

## H-UI-004 — Animar colores podía romper el contraste durante una transición

- Prioridad: P2. Estado: corregido y validado.
- Reproducción: axe detectó 2.32:1 durante el paso de botón deshabilitado a habilitado,
  aunque ambos estados finales tenían colores legibles.
- Causa: transición simultánea del texto oscuro/fondo claro a texto amarillo/fondo negro;
  los colores interpolados cruzaban tonos de luminancia similar.
- Fix: cambiar texto/fondo del botón instantáneamente y animar solo su desplazamiento
  de 1 px a 150 ms. Los campos conservan transiciones compatibles con su contraste.
- Regresión: axe se ejecuta también inmediatamente después de altas y en vistas activas;
  la prueba de carga y reducción de movimiento sigue comprobando los estilos efectivos.
- Práctica transferible: evaluar estados intermedios de movimiento, foco y carga. Una
  auditoría de la paleta estática no demuestra accesibilidad de las transiciones.

## H-F3-001 — Auditoría de identidad con FK incompatible con otras entidades

- Prioridad: P2. Estado: corregido y validado en F3.
- Reproducción: audit_log de F2 exige entity_id FK users; una categoría con id=1 y un
  único ADMIN histórico id=7 no puede registrarse como entidad de catálogo en esa tabla.
- Causa: una referencia que parecía general quedó restringida a usuarios en el esquema.
- Fix informado antes de implementar: migración aditiva 0003 agrega audit_events, copia
  IDs/datos anteriores y conserva audit_log. Identidad escribe ambos en la misma transacción;
  catálogo usa el registro general. No sumar ambos al consultar eventos.
- Regresión: test_upgrade_preserves_identity_sessions_and_audit preserva exactamente F2,
  usa una sesión anterior y crea la categoría id=1 con actor id=7. Fallo intermedio de
  migración revierte el esquema y admite reintento. Fallo de auditoría revierte cada operación.
- Práctica transferible: revisar FKs de referencias polimórficas antes de ampliar dominios.
  Probar con IDs distintos, no solo fixtures donde todas las entidades tienen id=1.
- Límite: se mantiene duplicación compatible de eventos de identidad; futuras consultas
  generales deben usar audit_events. No hay visor/exportación de auditoría en esta fase.

## H-F3-002 — Conversión decimal con float introduce fracciones de centavo

- Prioridad: P2. Estado: prevenido y validado antes de publicar F3.
- Reproducción ejecutada en Node: 0.29 * 100 produce 28.999999999999996.
  No se detectó una pérdida de dinero en una instalación; fue una comprobación preventiva.
- Causa: representación binaria inexacta de decimales; truncar o aceptar rangos ilimitados
  entre JSON/JavaScript/SQLite puede cambiar el importe.
- Fix: parsear texto decimal con BigInt y convertir a Number únicamente dentro del rango
  entero seguro. Formatear con división/resto enteros. API rechaza floats/bool y SQLite
  impone tipo/rango. Se aceptan coma o punto decimal; no separadores de miles ambiguos.
- Regresión: 14 pruebas frontend de importes/cantidades, ida y vuelta de límites y rechazos;
  API prueba booleanos, fracciones, negativos y desbordamientos con DB real.
- Práctica transferible: mantener dinero entero en toda la cadena y probar límites de
  transporte además de límites de almacenamiento. Distinguir riesgo prevenido de fallo real.

## H-F3-003 — Reelección del mismo producto vaciaba el historial

- Prioridad: P2. Estado: corregido y validado.
- Reproducción identificada al revisar el código: seleccionar otra vez el producto elegido
  limpiaba movimientos, pero no cambiaba selectedId, por lo que no se ejecutaba la consulta.
- Causa: el evento invalidaba datos visibles sin invalidar la dependencia del efecto.
  Depender del objeto completo, que la consulta vuelve a reemplazar, podía producir un ciclo.
- Fix: depender del ID estable y una revisión explícita; la selección incrementa revisión
  y las respuestas tardías se ignoran al desmontar o cambiar de consulta.
- Regresión: E2E vuelve a seleccionar el mismo producto y exige tres movimientos reales,
  además de verificar stock/historial después de reiniciar Python.
- Práctica transferible: probar selección repetida, recarga y respuestas tardías. Diseñar
  explícitamente qué invalida la consulta; evitar depender de objetos reemplazados por ella.

## H-F3-004 — Avisos de una sección aparecían en otra

- Prioridad: P3. Estado: corregido y validado.
- Reproducción: las primeras capturas reales de catálogo/inventario mostraban «La cuenta
  de worker ya está creada» después de salir de Equipo.
- Causa: los avisos globales de identidad sobrevivían a la navegación agregada en F3.
- Fix: una función de navegación limpia mensajes y su solicitud de foco al cambiar sección.
  Los mensajes de sesión y formularios conservan su tratamiento propio.
- Regresión: E2E crea empleado, navega a Catálogo y exige ausencia del aviso anterior.
- Práctica transferible: revisar duración y propietario de los mensajes al introducir
  navegación. Usar capturas del flujo completo; una pantalla aislada no muestra estado residual.

## H-F3-005 — Límites de movimientos incompletos en SQLite

- Prioridad: P2. Estado: corregido y validado antes de publicar 0003.
- Reproducción: la revisión del primer DDL encontró stock_before sin cota máxima. Una
  escritura SQL directa podía combinar un antes fuera del rango seguro con un delta negativo
  y un después válido; la API ya rechazaba esos valores.
- Causa: se comprobó el resultado, pero no todo el registro que luego recibe JavaScript.
- Fix: acotar también antes y delta en CHECK, además de los DTO y el stock del producto.
- Regresión: test_sqlite_checks_and_foreign_keys_are_real intenta escrituras directas,
  fracciones, desbordamientos, stock negativo y FK inexistentes; todas se rechazan.
- Práctica transferible: revisar cada campo persistido que atraviesa un contrato numérico,
  especialmente históricos. La validación HTTP no demuestra integridad de la base.

## H-F3-006 — Filtros demasiado estrechos en pantalla pequeña

- Prioridad: P3. Estado: corregido y validado.
- Reproducción: la primera captura de inventario a 390 px mostraba categoría y dos
  casillas en la misma fila; etiqueta y selector quedaban innecesariamente estrechos.
- Causa: flex distribuía el espacio por igual sin una disposición específica para móvil.
- Fix: a 600 px o menos, selector de categoría en fila completa y casillas con ancho mínimo.
- Regresión: E2E y capturas reales a 390 px, controles etiquetados, axe y ausencia de
  desbordamiento horizontal también a 320 px.
- Práctica transferible: revisar comodidad y legibilidad en capturas reales; no basta con
  que una pantalla no tenga scroll horizontal o pase una auditoría automatizada.

## H-F4-001 — Una respuesta perdida puede inducir un segundo cobro registrado

- Prioridad: P1. Estado: prevenido y validado en F4, sin incidente en datos comerciales.
- Reproducción real de prueba: Playwright deja que POST /sales confirme en SQLite y
  corta la respuesta. Si el cliente descartara la identidad del pedido, otro UUID crearía
  una venta nueva al reintentar, aunque el primer registro ya exista.
- Causa: confundir ausencia de respuesta con ausencia de commit. Deshabilitar un botón
  solo mientras se envía no resuelve el estado posterior ni una recarga.
- Fix: guardar el intento antes del envío, ligado al usuario, y bloquear otra venta
  mientras sea incierto. Reenviar el mismo UUID/pedido; el servidor busca la clave antes
  de revalidar catálogo. Validar el comprobante, importes y pago antes de liberar el intento.
  Auth, red, 5xx y JSON inválido no lo descartan. Un 409 de catálogo/stock sí prueba rechazo
  porque la búsqueda idempotente ocurre primero; conflicto de clave conserva el bloqueo.
- Regresión: E2E corta respuesta tras 201 real, recarga, sale/reingresa y recupera el mismo
  ID, con dos pedidos iguales y una venta/pago/movimiento. SQLite prueba UUID concurrente,
  conflicto de datos/actor, orden normalizado y reintento después de editar/anular.
  Vitest rechaza comprobantes inconsistentes y conserva intentos corruptos para revisión.
- Práctica transferible: probar resultado incierto después del commit, además del fallo
  previo. Un identificador comercial recuperable pertenece al diseño de la operación.
- Límite: sessionStorage cubre esa pestaña/recargas/reingreso, no cierre definitivo o
  borrado del almacenamiento. En ese caso consultar historial antes de repetir una venta;
  no se promete recuperación automática del carrito al reiniciar el navegador.

## H-F4-002 — FK y CHECK por fila no bastan para preservar un comprobante

- Prioridad: P2. Estado: prevenido y validado.
- Riesgo identificado al diseñar: cantidades/subtotales válidos por separado no prueban
  suma del pago ni impiden agregar/cambiar ítems después de confirmar.
- Fix: un único pago valida existencia de ítems y suma/total; su inserción sella la
  composición. Triggers bloquean edición/borrado de ítems/pagos, cabecera económica,
  borrado de venta y reapertura de anuladas. Los casos de uso completan todo en una unidad.
- Regresión: ventas multilínea y precio cero, SQL directo contra historia y FK de
  productos usados, snapshots después de cambiar/desactivar catálogo y rollback en
  cuatro pasos intermedios. No se afirma que DB sola prohíba toda cabecera incompleta
  insertada por un administrador de SQLite fuera de la aplicación.
- Práctica transferible: separar invariantes por fila de invariantes entre tablas y del
  ciclo de vida. Probar escrituras directas e interrupciones, sin inventar garantías de DB.

## H-F4-003 — SQLite acepta un CHECK cuyo resultado es NULL

- Prioridad: P2. Estado: corregido antes de publicar la migración.
- Reproducción ejecutada en SQLite en memoria: una tabla con CHECK(length(trim(reason))
  BETWEEN 3 AND 240) admitió INSERT de NULL (una fila confirmada).
- Causa: el primer borrador del estado VOIDED verificaba longitud pero no IS NOT NULL.
  SQLite solo rechaza CHECK falso; NULL no equivale a falso en esa restricción.
- Fix: condición explícita void_reason IS NOT NULL para anuladas, además de validación
  HTTP estricta y caso de uso ADMIN. Estado COMPLETED exige datos de anulación nulos.
- Regresión: SQL directo intenta anular sin motivo y es rechazado; pruebas API exigen
  motivo, misma causa al repetir y rechazo de reversión parcial/overflow.
- Práctica transferible: probar NULL en condiciones compuestas; no inferir NOT NULL de
  una comparación de longitud/rango, especialmente para campos condicionales de estado.

## H-F4-004 — Selector de prueba confundía texto de etiqueta y opciones

- Prioridad: P3. Estado: corregido y validado.
- Reproducción: primer E2E F4 agotó 90 s al seleccionar el medio de pago; no llegó a
  generar capturas F4. El snapshot mostraba el control nativo y sus opciones disponibles.
- Causa: getByLabel exacto sobre label que contiene select incorporaba texto de opciones;
  no coincidía con el selector, aunque el nombre accesible del combobox era correcto.
- Fix: getByRole('combobox', {name, exact:true}) para pago/filtros. actionTimeout=10 s
  aporta una ubicación de fallo más precisa. No se alteró el producto ni se amplió timeout
  para forzar verde. La ejecución posterior completó el flujo real.
- Práctica transferible: localizar por semántica observable y revisar snapshot/causa
  antes de aumentar esperas. Diferenciar defecto de automatización y defecto de aplicación.

## H-F4-005 — Abrir el diálogo no confirma impresión física

- Prioridad: P2. Estado: formato/flujo verificados; hardware pendiente.
- Riesgo: anunciar «impreso» tras window.print o prometer compatibilidad por marca
  ocultaría cancelación, falta de papel, controlador incorrecto o ancho imprimible menor.
- Fix: impresión posterior al commit, botón sin estado falso de éxito, reimpresión desde
  historial y contenido de 48 mm para papel nominal de 58 mm. UI/documentación distinguen
  registro de venta y salida física. Modelo/controlador Global/Waggs aún no proporcionado.
- Regresión: tres PDF reales de Chromium (normal, nombre largo/código de 64 caracteres,
  anulado), ancho nominal con tolerancia del motor, texto extraído y print CSS sin desborde;
  llamar Imprimir no genera otro POST ni altera stock/pago. No se conectó una impresora.
- Práctica transferible: comprobar qué confirma cada API; documento, spooler y hardware
  son evidencias diferentes. Registrar tamaño efectivo y probar controlador/dispositivo.

## H-F4-006 — Un type guard estrechaba demasiado el DTO antes de validarlo

- Prioridad: P3. Estado: corregido y validado.
- Reproducción: build reportó TS2339 en nombre/precio/código de líneas de venta y borrador.
- Causa: el guard de items reducía unknown a Item (ID/cantidad) antes de inspeccionar
  propiedades adicionales; esas propiedades no pertenecían al tipo reducido.
- Fix: guards separados de unknown a Line y Draft, sin any/ts-ignore ni debilitar strict.
  Validar importes, suma, pago y estado mantiene el intento bloqueado si la respuesta falla.
- Regresión: TypeScript/Vite y 14 pruebas nuevas de comprobante/intento; E2E con respuesta
  perdida y recuperación real. No se declaró compilación aprobada durante el fallo.
- Práctica transferible: diseñar guards por contrato completo y mantener la validación
  de entradas externas en unknown hasta demostrar cada propiedad.

## H-F4-007 — Reutilización de fixture con import sombreado

- Prioridad: P3. Estado: corregido y validado.
- Reproducción: Ruff F811 al importar old_database como fixture y usar el mismo nombre
  como argumento en otra fixture. Las pruebas corrían, pero el lint rechazaba el cierre.
- Fix: declarar el módulo compartido en pytest_plugins; sin suprimir F811 ni duplicar
  datos de identidad/migración. Se conservan bases temporales por caso.
- Regresión: siete pruebas de migraciones previas/nuevas aprobadas y Ruff correcto.
- Práctica transferible: dar una ubicación y mecanismo explícitos a fixtures compartidas;
  un test aprobado no reemplaza la comprobación de herramientas del proyecto.

## H-F4-008 — Detalles técnicos y contadores poco claros en móvil

- Prioridad: P3. Estado: corregido y validado.
- Reproducción: primera captura real mostraba «1 encontrados» en el encabezado y texto
  sobre el servidor en la descripción del carrito, sin ayudar a confirmar una venta.
- Fix: contadores con singular/plural, tamaño secundario y distribución adaptable;
  instrucciones centradas en revisar precios/cantidades y confirmar el pago informado.
  La revisión del estado incierto también mostró catálogo deshabilitado con stock previo
  al commit cuya respuesta se perdió: se oculta ese formulario y se muestra únicamente
  el pedido pendiente y su recuperación, sin presentar cantidades desactualizadas como actuales.
- Regresión: capturas finales, axe y ausencia de desborde a 1366/390/320 px. Se mantiene
  tipografía local y contraste, sin animaciones/dependencias añadidas.
- Práctica transferible: revisar datos reales de uno/muchos y texto orientado a la tarea,
  además de estructura técnica, para sostener una interfaz clara y cercana.
