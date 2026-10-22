# Identidad visual — Gestión Inteligente POS

Dirección C aprobada por el propietario: comercial y enérgica, profesional y cercana.
Alcance de esta entrega: configuración inicial, ingreso y gestión de empleados de F2.
No incorpora catálogo, inventario, caja, ventas ni navegación hacia funciones inexistentes.

## Color y contraste

| Token | Color | Uso |
| --- | --- | --- |
| ink | #171714 | Texto, títulos, bordes principales y botones primarios |
| yellow | #FFD633 | Fondo e identidad; texto sobre botón negro |
| surface | #FFF3B0 | Paneles y listas para lectura prolongada |
| field | #FFF9DC | Campos y avisos de éxito |
| muted | #514924 | Texto de apoyo |
| border | #81723C | Bordes de campos y botones secundarios |
| line | #C6B35E | Separadores decorativos |
| error | #762317 | Texto de error; acompañado por icono y mensaje |

No comunicar un estado solo con color. Activo/inactivo se distingue con texto e indicador.
Comprobar contraste AA de texto (4.5:1 normal, 3:1 grande) y 3:1 para límites de controles.
Los separadores decorativos no representan el único límite de un control.
La validación automatizada de contraste se complementa con revisión visual; no constituye
una certificación integral de accesibilidad.

## Tipografía local

Manrope variable 200–800, normal, sin síntesis. Peso 800 en títulos, 750 en acciones,
650 en indicadores y 400–500 en lectura. Usar cifras tabulares en contadores.
Escala: título de bienvenida 38–64 px; título de equipo 28–40 px; títulos de panel 20–27 px;
texto principal 13–17 px; ayudas y metadatos 10–12 px. En móvil, inputs de 16 px.

Fuente versionada: frontend/src/assets/fonts/Manrope-latin-variable.woff2, 24 836 bytes.
Origen: @fontsource-variable/manrope 5.3.0, subconjunto latino (incluye español).
Licencia SIL OFL 1.1 en frontend/public/licenses/Manrope-OFL.txt (copiada a dist/licenses al compilar); autoría Manrope Project Authors.
SHA-256: a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972.
Se importan archivos locales mediante @font-face y Vite los incluye con hash en el build.
No se carga Google Fonts, CDN ni recursos remotos durante la operación.
El nombre interno que Chromium informa es Manrope ExtraLight; corresponde a la instancia
base de la fuente variable. La familia CSS es Manrope y el título selecciona el eje de peso 800.

## Composición y espaciado

Fondo amarillo; encabezado con marca, conexión real y cierre de sesión cuando corresponde.
Inicio/configuración: dos columnas en escritorio, una en pantalla pequeña. Gestión:
lista y formulario en paralelo, apilados por debajo de 760 px. Sin tarjetas de métricas ficticias.
Espaciado base de 4 px; separaciones habituales 8/12/16/24/32/48. Paneles de 16 px de radio;
campos y botones de 8 px. Controles de al menos 44 px de alto; inputs y acción principal, 48 px.
El contador de empleados se calcula a partir de las cuentas reales devueltas por la API.
El monograma gi. es un recurso tipográfico local de interfaz; no implica registro de marca.

## Componentes y estados

- Button: variantes primary, secondary y quiet. Disabled y aria-busy durante operaciones.
- Field: etiqueta visible, ayuda vinculada por aria-describedby, autocomplete adecuado.
- Panel: superficie contenida; título y agrupación semántica.
- Notice: éxito mediante role=status, error mediante role=alert y foco al aparecer.
- ConfirmDeactivation: dialog nativo; explica el efecto, enfoca Cancelar, admite Escape
  mantiene el recorrido Tab/Shift+Tab entre sus acciones y devuelve foco al control que lo abrió. El backend sigue siendo responsable del permiso.
- CredentialForm: formulario reutilizable para configuración, ingreso y empleados;
  bloqueo de doble envío, errores claros y conservación del flujo de teclado.

Username normalizado y roles siguen definidos por la API. El diseño no cambia los contratos,
la autorización ni el manejo de sesiones/CSRF. No se añade almacenamiento de credenciales
ni secretos en localStorage, capturas o documentación.

## Movimiento y teclado

Transiciones de fondo/borde de campos y transform de botones de 150 ms; pulsación de 1 px.
El texto y fondo de los botones cambian de forma instantánea al habilitar/deshabilitar:
interpolar ambos colores producía cuadros intermedios de contraste insuficiente.
Indicador de espera en CSS, sin biblioteca de animaciones. Con prefers-reduced-motion: reduce
se desactivan transiciones y animación del indicador, conservando el texto de espera.
Foco de controles: contorno negro de 3 px y separación de 4 px. Orden natural de tabulación,
link para saltar al contenido, títulos enfocados tras cambios de pantalla y diálogo nativo.

## Revisión

Capturas reales y resultados en [FRONTEND_DESIGN_VALIDATION.md](../FRONTEND_DESIGN_VALIDATION.md).
No fusionar esta propuesta hasta la revisión visual del propietario.
