# 2026-11-24-07 · Árbol del modelo: panel Estructura con secciones plegables

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-xx9mmx`
- **Fase de la hoja de ruta:** Fase 5 (interfaz gráfica, vía paralela)

## Qué se pidió

Rehacer el árbol del modelo de la izquierda (Modelo, Nudos, Barras, Apoyos, Cargas, Combinaciones, plano y con flechas) para que sea más estético, interpretando una propuesta con secciones plegables, íconos, contadores y barras con su tipo y sección.

## Qué se hizo

- `python/nervi/gui/arbol.py` (nuevo): `ArbolModelo`, un `QTreeWidget` con delegado propio que dibuja el panel **Estructura**. Secciones Nudos, Barras, Apoyos, Secciones, Cargas y Combinaciones con ícono (`ICONOS_ARBOL`, trazos propios de 16 px), contador y chevrón a la derecha, separadas por una línea fina; filas colgadas de una guía vertical. `filas(modelo, elementos)` arma el contenido sin Qt: barras con tipo y sección equivalente (`B1 Columna 30×30`, de `nervi.design.proyecto.elementos`), apoyos con su tipo (`tipo_apoyo`), secciones agrupadas con la cantidad de barras y casos con su nombre (`NOMBRES_CASO`, ACI 318-19 §5.3).
- Clic en el título de una sección: la pliega o despliega y, al abrirla, muestra su tabla. Clic en el chevrón: solo pliega o despliega. Clic en una barra o nudo: lo selecciona; en un caso o una combinación: cambia el diagrama. El árbol recuerda las secciones abiertas al rearmarse.
- Dos resaltados: la barra o el nudo elegido (fondo de acento suave) y el caso o la combinación que se ve (texto de acento y un punto).
- `ventana.py`: el explorador usa `ArbolModelo`; `_marcar_arbol` sincroniza la selección y la combinación; el árbol se rearma también cuando cambia el diseño (tipo o sección de una barra).
- `estilo.py`: reglas `titulo_arbol` y `arbol_modelo` con tokens del tema.

## Cómo se verificó

- `tests/test_arbol.py` (11 pruebas): contenido de las filas, apoyos, secciones plegables y recordadas, clics (barra, combinación, título y chevrón), resaltado desde el dibujo y dibujo en los dos temas.
- Suite de Python completa, `ruff check` y `ruff format --check` en verde.
- Capturas de la ventana real en los dos temas, mostradas y aprobadas en el hilo del proyecto antes de abrir el PR.
- No toca cálculo: no hace falta el banco de tiempos.

## Decisiones tomadas

- Los nombres de los casos (Permanente, Sobrecarga, Viento…) se deducen del símbolo y no se guardan: no cambia el formato `.nrv`. Un caso con otro nombre muestra solo su nombre.
- *Secciones* sale de la sección rectangular equivalente de la etapa Diseño (o la que fijó la persona), agrupada por medidas; no hay todavía una lista de secciones en el modelo.
- El dato de la derecha (nudos de la barra, coordenadas) se muestra o se oculta según el ancho del panel para todas las filas a la vez, para no cortar el detalle ni dejar filas distintas.
- El panel del asistente de IA (PR #65) va antes del árbol en el mismo divisor; se coordinó con ese hilo para no tocar las mismas partes.

## Documentación actualizada

- `docs/diseno-interfaz.md`: sección nueva *Árbol del modelo*.
- `docs/ESTADO.md`: el panel Estructura en la interfaz y la cuenta de pruebas.
- `docs/hoja-de-ruta.md`: Fase 5, lo que ya tiene la interfaz.
- `sitio/primeros-pasos.md` y sus traducciones (en, pt, ru): el panel Estructura en lugar del "árbol del proyecto".
- README, `CONTRIBUTING.md` y `AGENTS.md` no cambian: no hay reglas ni instalación nuevas.

## Firma DCO

- Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (24/11/2026, "Confirmado, firmalo por mi") que el agente agregue su firma a este aporte. Se usó `bareirojero <345933350+bareirojero@users.noreply.github.com>` (AGENTS.md §3.5).

## Pendiente y problemas conocidos

- Las secciones todavía no se editan desde el árbol; el clic lleva a la tabla de barras.
- Falta un filtro de búsqueda en el árbol para modelos grandes.

## Para quien siga

- Una categoría nueva (materiales, pisos del pórtico espacial) se suma en `arbol.filas` con su clave, su ícono en `ICONOS_ARBOL` y, si tiene tabla, en `TABLAS`.
