# 2026-11-24-03 · Deshacer, rehacer y propuestas de cambio

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`, PR #65
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 3

## Qué se pidió

Seguir el plan de integración en orden: después de la capa sin Qt y de los resultados sin redondeo, deshacer, rehacer y propuestas de cambio, para que lo que haga un agente de IA, un importador o un complemento quede pendiente hasta que la persona lo aplique, se pueda deshacer y quede registrado.

## Qué se hizo

- `python/nervi/proyecto.py`: `editar`, `editar_diseno` y `editar_dinamica` reciben `origen` (por omisión `"persona"`) y `descripcion`, y guardan el cambio para `deshacer()` y `rehacer()` (hasta 100, con `puede_deshacer`, `que_deshacer` y sus pares). Cada parte se restaura por separado: deshacer un cambio de diseño no toca el modelo. `proponer(modelo, origen, descripcion)` valida el modelo y deja una `Propuesta` pendiente con la huella del modelo base y `resumir_cambios` (frases como "Agrega N5", "Cambia B2 (A, I)", "Cargas en nudos: 1 → 2"); `aplicar(id)` la aplica solo si el modelo no cambió desde entonces, y `descartar(id)` la borra. Evento nuevo `"historial"`.
- `python/nervi/formato/historial.py` (nuevo) y `contenedor.py`: módulo opcional `historial` 1 del `.nrv` con los cambios aplicados, deshechos o rehechos que no hizo la persona (fecha, acción, parte, origen, descripción, resumen y huellas antes y después). Las ediciones a mano no se anotan.
- `python/nervi/gui/sesion.py`: señal `historial_cambiado`. `python/nervi/gui/ventana.py`: acciones **Deshacer** y **Rehacer** (Ctrl+Z y Ctrl+Y, con la descripción del cambio en el texto) y **Exportar resultados a precisión completa (JSON)…** en el menú del logo y en el buscador. No se agregó ningún control nuevo ni cambió el aspecto.
- `tests/datos/nrv/historial-v1.nrv` y `historial-v1.esperado.json` (nuevos archivos de referencia), con su prueba en `tests/test_formato_compatibilidad.py`.

## Cómo se verificó

- `tests/test_proyecto.py` suma 9 pruebas: deshacer y rehacer del modelo con sus eventos, de diseño y dinámica hasta volver a "sin datos", que lo guardado no cambie si quien editó toca su diccionario, que abrir otro proyecto borre la pila y las propuestas, que una propuesta no cambie nada hasta aplicarla y quede en el historial, que no se aplique sobre un modelo que cambió, que se rechacen propuestas inválidas o sin origen, que el historial se guarde y se abra, y el resumen de cambios.
- `tests/test_gui.py` suma 2: Ctrl+Z y Rehacer después de editar una tabla, y exportar resultados desde la ventana.
- Suite completa: 355 en verde y 4 omitidas. `scripts/medir_diseno.py --comparar` contra `main`: igual a la referencia.
- Costo de deshacer: una edición del modelo pasa de 0,8 a 1,5 ms en el pórtico de 130 barras y de 5,8 a 9,3 ms en uno de 775 barras. Cada copia de ese modelo ocupa unos 0,5 MB; con el límite de 100 cambios y reusando la copia anterior cuando la parte no cambió, la pila llega a unos 53 MB en el peor caso.

## Decisiones tomadas

- Se guarda el estado completo de la parte (no un parche), porque las ediciones de la interfaz ya reemplazan el diccionario entero y así deshacer es exacto. Para no duplicar memoria, el "antes" de un cambio reusa la copia del cambio anterior si la parte no cambió; las copias guardadas no se modifican nunca.
- Solo se anotan en el `.nrv` los cambios que vienen de afuera: es lo que importa auditar, y anotar cada celda editada a mano llenaría el archivo.
- Una propuesta sobre un modelo que cambió se rechaza en vez de mezclarse: mezclar cambios de dos fuentes podría dejar un modelo que nadie revisó.
- `origen` es un texto libre con la forma `tipo: nombre`; la lista de tipos se fija cuando existan el servidor MCP y los complementos.
- Firma DCO: Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (24/11/2026) que el agente agregue su `Signed-off-by` a los commits de este trabajo, con el nombre `bareirojero` y su correo `noreply` de GitHub.

## Documentación actualizada

- `docs/formato-nrv.md` (§2, §3.1, §4d nuevo y §9), `tests/datos/nrv/README.md`, `docs/ESTADO.md`, `docs/hoja-de-ruta.md` (etapa 3 hecha), `docs/glosario.md` y los cuatro README (deshacer y rehacer en la interfaz). Las páginas de `sitio/` no listan atajos de la interfaz, así que no cambian.

## Pendiente y problemas conocidos

- Panel de propuestas en la interfaz: va con el panel del asistente, con muestra visual en los dos temas antes de implementarlo.
- Deshacer no cubre todavía cambios que no pasan por `editar*`: los datos de diseño o dinámica que se crean al diseñar o analizar por primera vez.

## Para quien siga

- Etapa 4: servidor MCP `nervi-mcp` de solo lectura sobre `nervi.proyecto` y `nervi.resultados`. Las herramientas que escriban usan `proponer`, nunca `editar`.
