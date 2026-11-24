# Diseño de la interfaz de escritorio

Línea de diseño de `nervi.gui`, acordada con el responsable del proyecto el 2026-11-19 (entrada [2026-11-19-03](bitacora/2026-11-19-03-sistema-diseno-interfaz.md)). Todo cambio en la interfaz la sigue y todo control nuevo toma su estilo de este sistema, sin aspecto nativo antiguo. Si hace falta cambiarla, se muestra antes una **muestra visual** (captura o maqueta, en los dos temas), se acuerda con el responsable del proyecto y se documenta acá en el mismo PR.

## Principios

- **Plana, sobria y precisa.** Superficies lisas, bordes finos de 1 px, sin degradados ni sombras dibujadas. Un solo color de acento por tema.
- **Un único sistema.** Los colores, radios y alturas salen de un `Tema` en [`python/nervi/gui/estilo.py`](../python/nervi/gui/estilo.py). No se escriben colores sueltos en otros archivos: los dibujos propios (vista 2D, visor 3D, tablas) leen las constantes de `estilo` (`estilo.PANEL`, `estilo.ACENTO`, `estilo.ESTRUCTURA`…) en el momento de dibujar, así cambian con el tema.
- **Controles completos.** Cada control compuesto se estila entero: flecha del desplegable, botones del campo numérico, marca de casillas y opciones, tirador del deslizador. Si la hoja de estilos de Qt define solo el borde y el fondo, Qt dibuja el resto con el relieve biselado de los estilos viejos (el aspecto "Windows 98"). Las flechas y marcas son SVG que `estilo.iconos` genera con los colores del tema.
- **Toda la aplicación.** La hoja se instala con `estilo.aplicar(app, tema)` sobre la `QApplication`, no sobre una ventana, para que diálogos, menús y listas abiertas también la tengan.

## Temas

| Token | A · Claro preciso (por defecto) | B · Nocturno Nervi (oscuro) |
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

El oscuro usa los colores del logo y de la maqueta (azul marino, azul y cian). Se elige en **Preferencias › Apariencia** o en el menú del logo (**Tema claro** / **Tema oscuro**) y se guarda en las preferencias (`interfaz/tema`). **Tamaño de letra** (Normal 9,5 pt o Grande 11 pt) cambia el token `tamano` del tema.

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

## Menús y ajustes

Decidido el 23/11/2026 con muestras en los dos temas.

- **Barra lateral de menús.** Una columna de íconos de 52 px a la izquierda (`riel`, botones `menu_riel` de 40 px con íconos de 20 px). Arriba: Archivo, Editar, Modelo, Calcular, Ver, Herramientas y Asistente de IA; abajo: Ayuda y Preferencias. Cada ícono abre su menú **hacia la derecha** y muestra su nombre al pasar el mouse; mientras el menú está abierto el botón queda marcado con acento suave y el ícono en color de acento. *Preferencias* abre directamente su ventana. El menú del logo se conserva como acceso rápido.
- **Íconos propios** de 24 × 24 con trazo de 1,7 px (`estilo.ICONOS_MENU`), en el color del texto secundario o del acento. No se copian íconos de otros programas.
- **Solo acciones que existen.** Un menú no muestra opciones grises de cosas que todavía no hace (complementos, por ejemplo); se agregan cuando llegan. *Editar* tiene Deshacer y Rehacer, que muestran qué deshacen o rehacen y quedan inactivos cuando no hay nada.
- **Dos ventanas de ajustes**, con la misma forma: apartados a la izquierda (`apartados`), contenido en cajas (`caja_ajustes`) con título de `seccion`, buscador arriba y *Restablecer este apartado*, *Cancelar*, *Aplicar* y *Aceptar* abajo.
  - **Preferencias** (`ajustes.Preferencias`): de la persona, en esta computadora. Apartados General (qué abrir al iniciar) y Apariencia (tema y tamaño de letra).
  - **Configuración del proyecto** (`ajustes.ConfiguracionProyecto`): dentro del `.nrv`. Apartados Datos del proyecto (carátula de la memoria), Unidades (solo con el modelo vacío, porque cambiarlas exige convertir los valores), Materiales y Diseño (criterios y diámetros permitidos para columnas).
- **Regla para un ajuste nuevo:** si cambiarlo puede cambiar un número del cálculo o de la memoria, va en Configuración del proyecto y en el `.nrv` (con su versión de módulo y migración); si solo cambia cómo se ve o se usa la aplicación, va en Preferencias. Una preferencia se declara una sola vez en `ajustes.PREFERENCIAS` y la ventana se arma sola. Un apartado nuevo aparece recién cuando tiene algo que ajustar.

## Asistente de IA

Decidido el 24/11/2026 con muestras en los dos temas.

- **Ícono en la barra lateral** (`ia`, una chispa), debajo de Herramientas. No abre un menú: abre y cierra el **panel del asistente** junto a la barra, antes del árbol del modelo. Una `insignia` del color de acento sobre el ícono dice cuántas propuestas esperan.
- **Sin chat.** La persona conversa en su propia app de IA; el panel muestra el estado de la conexión (`conexion`, verde cuando está conectada), las **propuestas pendientes** como `tarjeta` con borde y fondo de acento (descripción, origen, resumen de cambios y los botones *Aplicar* `primario`, *Vista previa* y *Descartar* `fantasma`) y las **consultas del agente** (hora, herramienta en `codigo` y ✓ `bien` o ✕ `mal`).
- *Vista previa* abre el modelo propuesto en una ventana aparte, sin aplicarlo. *Aplicar* se deshace con Ctrl+Z.
- Abajo, *Conectar con mi IA* (`primario`) o *Desconectar*, *Cómo conectar mi app…* y el aviso de que lo que lee el agente viaja a su proveedor.

## Importar DXF

Decidido el 24/11/2026 con muestras en los dos temas.

- *Archivo › Importar DXF…* abre un diálogo con la misma cabecera y el mismo pie que Preferencias (`barra`, `pie_ajustes`): título y nombre del archivo arriba; *Cancelar* e *Importar* (`primario`) abajo.
- A la izquierda, en cajas (`caja_ajustes`) con su título de `seccion`: **Capas** (una casilla por capa con su cantidad de líneas), **Dibujo** (unidad y tolerancia) y **Opciones** (llevar al origen, que solo se ofrece con el modelo vacío, y empotrar los nudos más bajos), y una nota tenue sobre los ejes del dibujo y Ctrl+Z.
- A la derecha, el modelo que quedaría en una vista 2D, recalculado con cada cambio, sin leyenda de resultados. Si el modelo ya tenía barras, las nuevas van en color de acento. Arriba, cuánto se agrega; abajo, los avisos del importador en palabras. Si las opciones no alcanzan (sin unidad, sin capas), el motivo reemplaza al resumen e *Importar* queda inactivo.

## Árbol del modelo

Decidido el 24/11/2026 con muestras en los dos temas (entrada [2026-11-24-07](bitacora/2026-11-24-07-arbol-del-modelo.md)).

- **Panel *Estructura*** (`arbol.ArbolModelo`, nombre de objeto `arbol_modelo`) a la izquierda de la vista, con título `titulo_arbol`. Secciones plegables en este orden: Nudos, Barras, Apoyos, Secciones, Cargas y Combinaciones, separadas por una línea de 1 px del color de borde.
- **Cabecera de sección:** ícono propio de 16 × 16 con trazo de 1,4 px (`arbol.ICONOS_ARBOL`) en texto secundario, título en negrita, contador en texto tenue y chevrón a la derecha (abajo si está abierta, a la derecha si está plegada). Clic en el título: despliega o pliega y, al abrir, muestra su tabla abajo. Clic en el chevrón: solo despliega o pliega. Abren desplegadas Barras, Cargas y Combinaciones, y el árbol recuerda qué abrió la persona mientras dura la sesión.
- **Filas** colgadas de una guía vertical de 1 px: código (`B1`, `N1`, `D`) y detalle en texto secundario (`Columna 30×30`, `Empotrado`, `Permanente`). Con el panel de 300 px o más, a la derecha va un dato tenue (nudos de la barra, coordenadas del nudo, barras que usan la sección); más angosto se oculta en todas las filas a la vez y queda en la ayuda emergente.
- **Dos resaltados:** la barra o el nudo elegido lleva fondo de acento suave con esquinas de 4 px y texto de acento; el caso o la combinación que muestran los diagramas lleva texto de acento y un punto de acento a la derecha.
- Los nombres de los casos salen de su símbolo (ACI 318-19 §5.3: D Permanente, L Sobrecarga, W Viento, E Sismo…); la sección de cada barra es la rectangular equivalente de la etapa Diseño, en centímetros.

## Cómo agregar algo

1. Usá los nombres de objeto existentes (`primario`, `fantasma`, `peligro`, `segmento`, `seccion`, `tenue`, `aviso`…) antes de crear uno nuevo.
2. Si hace falta un estilo nuevo, agregalo en `estilo.qss` con tokens del tema, nunca con un color fijo ni con `setStyleSheet` en el widget (salvo colores de estado calculados, que igual salen de `estilo`).
3. Probalo en los dos temas. `tests/test_estilo.py` comprueba que la hoja estile las partes de los controles compuestos.
