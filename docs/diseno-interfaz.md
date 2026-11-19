# Diseño de la interfaz de escritorio

Línea de diseño de `nervi.gui`, acordada con el responsable del proyecto el 2026-11-19 (entrada [2026-11-19-03](bitacora/2026-11-19-03-sistema-diseno-interfaz.md)). Todo cambio en la interfaz la sigue; si hace falta cambiarla, se acuerda antes y se documenta acá.

## Principios

- **Plana, sobria y precisa.** Superficies lisas, bordes finos de 1 px, sin degradados ni sombras dibujadas. Un solo color de acento por tema.
- **Un único sistema.** Los colores, radios y alturas salen de un `Tema` en [`python/nervi/gui/estilo.py`](../python/nervi/gui/estilo.py). No se escriben colores sueltos en otros archivos: los dibujos propios (vista 2D, visor 3D, tablas) leen las constantes de `estilo` (`estilo.PANEL`, `estilo.ACENTO`, `estilo.ESTRUCTURA`…) en el momento de dibujar, así cambian con el tema.
- **Controles completos.** Cada control compuesto se estila entero: flecha del desplegable, botones del campo numérico, marca de casillas y opciones, tirador del deslizador. Si la hoja de estilos de Qt define solo el borde y el fondo, Qt dibuja el resto con el relieve biselado de los estilos viejos (el aspecto "Windows 98"). Las flechas y marcas son SVG que `estilo.iconos` genera con los colores del tema.
- **Toda la aplicación.** La hoja se instala con `estilo.aplicar(app, tema)` sobre la `QApplication`, no sobre una ventana, para que diálogos, menús y listas abiertas también la tengan.

## Temas

| Token | Claro (por defecto) | Oscuro (marca) |
|---|---|---|
| Fondo de ventana | `#F4F5F7` | `#0B132B` |
| Paneles, tablas, menús | `#FFFFFF` | `#0F172A` |
| Campos | `#FFFFFF` con borde | `#131E36` |
| Bordes | `#DFE3E8` / `#C5CBD3` | `#1F2C47` / `#2A3A5C` |
| Texto | `#14171C` · `#4A5260` · `#6B7280` | `#DCE6F5` · `#A9B8D0` · `#7184A3` |
| Acento (selección, pestaña activa, casillas) | `#2563EB` | `#3B82F6` |
| Foco | `#2563EB` | cian `#00E5FF` |
| Botón primario | negro `#14171C` | azul `#3B82F6` |
| Cumple / no cumple | `#15803D` / `#C2410C` | `#22C55E` / `#F97316` |

El oscuro usa los colores del logo y de la maqueta (azul marino, azul y cian). Se elige en el menú del logo (**Tema claro** / **Tema oscuro**) y se guarda en `QSettings` (`interfaz/tema`).

Medidas comunes: esquinas de 6 px (4 px dentro de otro control), controles de 28 px de alto, letra del sistema a 9,5 pt.

## Controles

- **Botones:** secundario (fondo de panel con borde), `primario` (acción principal de la pantalla, uno por zona), `fantasma` (sin borde, para Cancelar), `peligro` (texto en color negativo, para quitar o borrar). Los botones que alternan van como `segmento` dentro de un `grupo`.
- **Etapas:** `etapa`, texto con subrayado de 2 px del color de acento en la activa.
- **Campos, numéricos y desplegables:** misma altura, radio y borde; borde de foco del color de foco; con error, `setProperty("error", True)` pinta el borde del color negativo. Flechas en chevrón fino.
- **Lista abierta del desplegable:** rectangular (es una ventana aparte y no puede tener esquinas redondeadas sin que asomen las de la ventana), con borde en los cuatro lados y la opción elegida con fondo de acento suave.
- **Casillas y opciones:** cuadrado de 14 px con esquinas de 4 px y círculo de 14 px; marcadas, rellenas del color de acento con la marca en blanco.
- **Deslizador:** riel de 4 px y tirador **rectangular** macizo del color de acento (no circular).
- **Pestañas:** texto con subrayado de acento en la activa, sin cajas.
- **Tablas:** encabezados en texto tenue y negrita, filas alternadas con el color de fondo, selección con acento suave. Números alineados a la derecha.
- **Avisos:** `aviso` con fondo, borde y texto ámbar; etiquetas de estado `etiqueta`.

## Cómo agregar algo

1. Usá los nombres de objeto existentes (`primario`, `fantasma`, `peligro`, `segmento`, `seccion`, `tenue`, `aviso`…) antes de crear uno nuevo.
2. Si hace falta un estilo nuevo, agregalo en `estilo.qss` con tokens del tema, nunca con un color fijo ni con `setStyleSheet` en el widget (salvo colores de estado calculados, que igual salen de `estilo`).
3. Probalo en los dos temas. `tests/test_estilo.py` comprueba que la hoja estile las partes de los controles compuestos.
