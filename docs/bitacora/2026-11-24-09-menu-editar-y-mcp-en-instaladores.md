# 2026-11-24-09 · Menú Editar y `nervi-mcp` en los instaladores

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos" (pendientes de las etapas 4 y 5)

## Qué se pidió

Los dos pendientes chicos de la integración con IA: un menú *Editar* con Deshacer y Rehacer en la barra lateral, y que los instaladores traigan `nervi-mcp`, que hasta ahora solo se instalaba con `pip install nervi[ia]`.

## Qué se hizo

- `python/nervi/gui/ventana.py` y `estilo.py`: menú *Editar* en la barra lateral, debajo de Archivo, con Deshacer y Rehacer (los mismos de Ctrl+Z y Ctrl+Y, con la descripción del cambio). Ícono propio de flecha de deshacer, con el trazo de los demás.
- `packaging/pyinstaller/nervi.spec` (nuevo): receta de PyInstaller con dos ejecutables en la misma carpeta, que comparten bibliotecas: `Nervi` (ventana) y `nervi-mcp` (consola). En Windows hace falta un ejecutable de consola aparte, porque uno de ventana no tiene entrada y salida estándar para la app de IA. `packaging/pyinstaller/nervi_mcp.py` es su punto de entrada.
- `.github/workflows/publicacion.yml`: instala `mcp`, arma los dos ejecutables con la receta y suma una prueba de humo en Windows y Linux, `packaging/probar_nervi_mcp.py`, que habla con `nervi-mcp` por stdio como una app de IA.
- `packaging/linux/AppRun`: `Nervi.AppImage mcp [proyecto.nrv]` lanza `nervi-mcp` en vez de la ventana.

## Cómo se verificó

- `tests/test_gui.py`: la prueba de la barra lateral incluye *Editar* con Deshacer y Rehacer, inactivos sin cambios y activos con la descripción después de editar.
- Armado local en Linux con PyInstaller 6.22 y la receta nueva: la carpeta tiene `Nervi`, `nervi-mcp` y `_internal`; `probar_nervi_mcp.py` contra el `nervi-mcp` empaquetado responde las 13 herramientas y, sin ventana, explica cómo conectarla; la ventana empaquetada arranca. El armado de Windows se comprueba en el workflow.
- Suite completa: 418 en verde y 4 omitidas.

## Decisiones tomadas

- Un ejecutable de consola aparte y no un modo `--mcp` del de ventana: en Windows un ejecutable de ventana no recibe la entrada y salida estándar de forma confiable. Al compartir `_internal`, el agregado es chico.
- Deshacer y Rehacer quedan inactivos cuando no hay nada que deshacer, en vez de esconderse: así funcionan en todos los programas. La regla de "solo acciones que existen" de `diseno-interfaz.md` se aclara.

## Documentación actualizada

- `docs/agentes-ia.md` (dónde está `nervi-mcp` con cada instalador), `docs/diseno-interfaz.md` (menú Editar), `docs/ESTADO.md`.

## Pendiente y problemas conocidos

- Sigue la etapa 6, importar DXF, en su propio aporte.

## Para quien siga

- Si se agrega otro ejecutable a los instaladores, va en la misma receta (`nervi.spec`) para compartir bibliotecas.
