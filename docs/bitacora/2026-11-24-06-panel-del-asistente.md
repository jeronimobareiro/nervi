# 2026-11-24-06 · Panel del asistente de IA en la barra lateral

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`, PR #65
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 5 (cierre)

## Qué se pidió

Terminar la etapa 5 con el panel del asistente, sin chat (la persona conversa en su app de IA). Se mostraron dos muestras en los dos temas: primero con un botón en la barra superior y una columna a la derecha; Jerónimo pidió llevarlo a la barra lateral izquierda que se acababa de sumar (#66), y aprobó esa segunda muestra ("Implementalo así").

## Qué se hizo

- `python/nervi/gui/asistente.py` (nuevo): `PanelAsistente`, con el estado de la conexión y *Conectar con mi IA* / *Desconectar*, las propuestas pendientes como tarjetas (descripción, origen, hace cuánto llegó, resumen de cambios, *Aplicar*, *Vista previa* y *Descartar*), las últimas consultas del agente con ✓ o ✕, *Cómo conectar mi app…* (abre `docs/agentes-ia.md`) y el aviso de privacidad. Si el modelo cambió desde la propuesta, *Aplicar* avisa y pide rehacerla. *Vista previa* abre el modelo propuesto en una ventana aparte con la vista 2D, sin aplicarlo.
- `python/nervi/gui/ventana.py`: ícono `ia` en la barra lateral, debajo de Herramientas; abre y cierra el panel junto a la barra, antes del árbol del modelo, con 370 px que toma de la vista central. Insignia con la cantidad de propuestas pendientes. La acción del buscador "Conectar con mi IA" queda sincronizada con el panel.
- `python/nervi/gui/estilo.py`: ícono `ia` (chispa) y estilos `insignia`, `tarjeta` (con `pendiente`), `conexion` (con `conectado`), `codigo`, `bien` y `mal`, con tokens del tema.
- `docs/diseno-interfaz.md`: nueva sección §Asistente de IA con lo acordado.

## Cómo se verificó

- `tests/test_gui.py` suma 2 y actualiza 1: abrir y cerrar el panel desde el ícono, conectar y desconectar, insignia, tarjeta con su resumen, vista previa que no aplica, *Aplicar* que cambia el modelo, queda en el historial con su origen y se deshace con Ctrl+Z, *Descartar* que no cambia nada, consultas a la vista, y una propuesta sobre un modelo que cambió que no se aplica y avisa. La prueba de la barra lateral incluye el ícono nuevo.
- Capturas de la ventana real en los dos temas, comparadas con la muestra aprobada.
- Suite completa: 407 en verde y 4 omitidas. `ruff` en verde.

## Decisiones tomadas

- Panel junto a la barra lateral, antes del árbol, como pidió Jerónimo; el botón de la barra superior de la primera muestra se descartó.
- La vista previa es una ventana aparte con la vista 2D del modelo propuesto, sin calcular: es lo más simple que deja ver la geometría y las cargas antes de aplicar. Mostrar las diferencias resaltadas sobre la vista principal queda para más adelante si hace falta.
- Las consultas del agente muestran solo la herramienta y si salió bien: los argumentos pueden ser largos (un modelo entero) y no aportan a la persona.

## Documentación actualizada

- `docs/diseno-interfaz.md`, `docs/agentes-ia.md`, `docs/ESTADO.md`, `docs/hoja-de-ruta.md` (etapa 5 hecha) y los cuatro README.

## Pendiente y problemas conocidos

- La barra lateral todavía no tiene menú *Editar*: Deshacer y Rehacer están en el menú del logo y con Ctrl+Z y Ctrl+Y.
- Los instaladores no incluyen el SDK de MCP ni `nervi-mcp` (entrada 04).

## Para quien siga

- Etapa 6: importar DXF con vista previa, que llega como propuesta (`Proyecto.proponer`, origen `importador: dxf`) y se aplica desde este mismo panel.
