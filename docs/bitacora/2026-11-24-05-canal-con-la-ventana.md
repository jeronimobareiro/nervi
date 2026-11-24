# 2026-11-24-05 · Canal con la ventana abierta y propuestas por MCP

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`, PR #65
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 5 (primera parte)

## Qué se pidió

Empezar la etapa 5: que la app de IA de la persona trabaje con la ventana de Nervi abierta. Jerónimo eligió que la conversación siga en la app de IA de cada persona (sin clave de API ni costo extra) y que el chat dentro de Nervi venga después, sobre la misma base.

## Qué se hizo

- `python/nervi/ia/canal.py` (nuevo, sin Qt): protocolo del canal local, una línea JSON por pedido y por respuesta, con versión y secreto. `publicar` y `retirar` manejan el archivo de descubrimiento (`%APPDATA%\Nervi\canal.json` o `~/.config/nervi/canal.json`, modo 0600, `NERVI_CANAL` lo cambia); `atender` es el lado de la ventana y `consultar` el del puente.
- `python/nervi/gui/canal.py` (nuevo): `CanalVentana` escucha con `QTcpServer` solo en `127.0.0.1`, en un puerto que elige el sistema, y atiende cada pedido en el hilo de la interfaz. Señales `consulta` (herramienta y si salió bien) y `estado_cambiado`, para el panel.
- `python/nervi/gui/ventana.py`: acción "Conectar con mi IA" (en el buscador, Ctrl+K), que abre o cierra el canal; cerrar la ventana lo cierra. Sin controles nuevos a la vista hasta aprobar la muestra del panel.
- `python/nervi/ia/herramientas.py`: con la ventana, las consultas usan una copia del proyecto que se renueva cuando cambia el modelo, el diseño o la dinámica, así que calcular, diseñar o analizar para responder no cambia lo que ve la persona (era un pendiente de la entrada 04). Herramientas nuevas para la ventana: `leer_seleccion`, `proponer_modelo` (por `Proyecto.proponer`, con origen `ia: agente MCP`) y `listar_propuestas`. `ejecutar(nombre, argumentos)` valida el nombre y los argumentos de lo que llega por el canal.
- `python/nervi/ia/servidor.py`: `nervi-mcp` sin argumentos se conecta con la ventana; con un `.nrv`, como antes. Las herramientas se publican con la firma de `Herramientas`, sea que las atienda el mismo proceso o la ventana. Si la ventana no está conectada, el agente recibe "Pedile a la persona que abra Nervi y toque «Conectar con mi IA»". Las instrucciones del servidor le piden no decir que un cambio está hecho hasta que la persona lo aplique.

## Cómo se verificó

- `tests/test_ia.py` suma 6: selección, propuesta que no cambia nada hasta aplicarla, modelos inválidos, que con un archivo no se pueda proponer, que consultar no avise ningún evento ni ponga al día nada en el proyecto abierto, validación de nombres y argumentos, el protocolo (secreto incorrecto, versión, error de consulta, JSON roto) y el archivo de descubrimiento (sin ventana, puerto cerrado, permisos, borrar solo el propio).
- `tests/test_gui.py` suma 2: conectar y desconectar desde la ventana con consultas reales por el socket, y una sesión completa como la de una app de IA: lanza `python -m nervi.ia.servidor` sin argumentos, le habla por `stdio` y el puente le pasa la consulta a la ventana abierta.
- Suite completa: 381 en verde y 4 omitidas.

## Decisiones tomadas

- La conversación queda en la app de IA de la persona: las suscripciones (Claude Pro, ChatGPT Plus) no incluyen clave de API, y así no hay costo extra ni claves que guardar. El chat integrado queda como etapa 8 de la hoja de ruta.
- Puente por `stdio` y no un servidor MCP por HTTP en la ventana: las apps de IA de escritorio se configuran con un comando, y así la ventana no necesita el SDK de MCP ni expone MCP a la red. El canal es TCP en `127.0.0.1` (igual en Windows, Linux y macOS) con un secreto de 256 bits que cambia en cada conexión.
- La ventana atiende en el hilo de la interfaz para no leer el proyecto mientras la persona lo edita. Las consultas pesadas (diseño de un pórtico grande) pueden frenar la ventana unos segundos; si molesta, se pasa a un hilo con la copia.
- `proponer_modelo` recibe el `modelo.json` entero en vez de operaciones sueltas: el agente ya lo lee con `leer_modelo`, la validación y el resumen de cambios ya existen, y no hay un segundo formato que mantener.

## Documentación actualizada

- `docs/agentes-ia.md` (modo ventana, seguridad del canal, herramientas nuevas), `docs/ESTADO.md`, `docs/hoja-de-ruta.md` (etapa 5 en curso, etapa 8 nueva), `docs/glosario.md` y los cuatro README.

## Pendiente y problemas conocidos

- Las propuestas que deja el agente todavía no se ven ni se aplican desde la ventana: falta el panel del asistente (estado de la conexión, consultas del agente y propuestas con Aplicar y Descartar), que se implementa después de aprobar la muestra visual en los dos temas.
- ChatGPT en la web sigue sin poder conectarse: solo acepta servidores remotos.

## Para quien siga

- Panel del asistente con `CanalVentana.consulta`, `estado_cambiado` y `Sesion.historial_cambiado` (propuestas), con la muestra aprobada.
