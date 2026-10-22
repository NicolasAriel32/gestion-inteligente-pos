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
