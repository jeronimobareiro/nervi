# 2026-11-24-04 · Servidor MCP de solo lectura (`nervi-mcp`)

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`, PR #65
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 4

## Qué se pidió

Seguir en orden con la etapa 4 del plan de integración: un servidor MCP para que el agente de IA que ya usa la persona consulte un proyecto de Nervi, primero de solo lectura.

## Qué se hizo

- `python/nervi/ia/herramientas.py` (nuevo): las consultas como funciones comunes de Python, sin depender de MCP. `Herramientas` trabaja sobre una fuente: `FuenteArchivo` (un `.nrv` en disco, que se vuelve a abrir si cambia su fecha o tamaño) o `FuenteProyecto` (un `Proyecto` abierto, para la etapa 5). Diez herramientas: `resumen_proyecto`, `leer_modelo`, `revisar_modelo`, `listar_resultados`, `leer_nudo`, `leer_barra` (fuerzas de extremo, diagramas y máximo y mínimo de N, V y M con su posición), `envolvente_barra`, `leer_reacciones` (de un caso o la envolvente), `leer_verificaciones` y `leer_modos`. Usan los mismos cálculos que la interfaz y la memoria (`_resolver_con_combinaciones`, `design.envolvente`, `Proyecto.disenar` y `analizar_dinamica`) y devuelven los `float64` sin redondear. Un id que no existe, un modelo inestable o un proyecto sin datos de diseño dan `ErrorConsulta` con el motivo en palabras.
- `python/nervi/ia/servidor.py` (nuevo): `crear_servidor(fuente)` publica las diez como herramientas MCP con `readOnlyHint`, y los recursos `nervi://modelo` y `nervi://resultados`. Las instrucciones del servidor le piden al agente no inventar cifras, decir de qué herramienta y combinación sale cada una, respetar las unidades del modelo y repetir el aviso del diseño experimental. `main` es el comando `nervi-mcp ruta.nrv` (por `stdio`). Funciona con el SDK de MCP 1.x (`FastMCP`) y 2.x (`MCPServer`).
- `pyproject.toml`: extra `ia = ["mcp>=1.2,<3"]`, `mcp` en `dev` y el comando `nervi-mcp`. `.github/workflows/ci.yml` instala `mcp` para correr sus pruebas.
- `docs/agentes-ia.md` (nuevo): instalación, configuración de Claude Desktop, Claude Code y otros clientes con servidores locales, qué hace cada herramienta y la nota de privacidad. Publicado en el sitio, en Documentación técnica.

## Cómo se verificó

- `tests/test_ia.py` (nuevo, 18 pruebas): cada herramienta da exactamente los números del motor (desplazamientos, reacciones, fuerzas de extremo, diagramas, envolventes, verificaciones y periodos, comparados sin tolerancia); los ids se aceptan como `2`, `"2"` o `"N2"`; los errores dicen el motivo; un mecanismo se explica en vez de romper; consultar no cambia los bytes del `.nrv` y, si la persona guarda otra versión, la consulta siguiente la ve. Del servidor: lista las diez herramientas, todas de solo lectura, y `call_tool` da lo mismo que la función. Una prueba lanza `python -m nervi.ia.servidor` y le habla por `stdio` con JSON-RPC, como un cliente real (`initialize`, `tools/list`, `tools/call`, un error de herramienta y `resources/read`).
- Probado a mano también con el SDK 1.30 (en un entorno aparte): mismas herramientas, anotaciones y errores.
- Suite completa: 373 en verde y 4 omitidas. `scripts/medir_diseno.py --comparar` contra `main`: igual a la referencia.

## Decisiones tomadas

- Las consultas viven en un módulo sin MCP, para probarlas sin el SDK, usarlas desde scripts y no atar Nervi a un protocolo: si mañana hace falta otro, se publica la misma clase.
- El servidor lee el archivo guardado, no la ventana abierta. Así es de solo lectura por construcción y no necesita que la interfaz esté abierta; la conexión con la ventana abierta es la etapa 5.
- `leer_verificaciones` y `leer_modos` no diseñan ni analizan si el proyecto no tiene esos datos: le dicen al agente que la persona los cargue. Diseñar con valores por omisión daría números que nadie eligió.
- No hay herramienta de "todos los resultados" para el agente: con 775 barras son varios MB que llenarían su contexto. Está como recurso (`nervi://resultados`) para el cliente que lo quiera.
- ChatGPT en la web solo se conecta a servidores remotos; `nervi-mcp` no abre puertos de red, así que queda para el canal local de la etapa 5.
- Firma DCO: misma autorización escrita que en las entradas 2026-11-24-01 a 03.

## Documentación actualizada

- `docs/agentes-ia.md` (nuevo), `docs/ESTADO.md`, `docs/hoja-de-ruta.md` (etapa 4 hecha), `docs/glosario.md`, los cuatro README, `mkdocs.yml` y `scripts/preparar_sitio.py`.

## Pendiente y problemas conocidos

- Los instaladores (`.exe` y AppImage) no incluyen todavía el SDK de MCP ni el comando `nervi-mcp`; hoy se usa con `pip install nervi[ia]`.
- Con `FuenteProyecto` sobre la ventana abierta, `leer_verificaciones` y `leer_modos` diseñan o analizan el proyecto abierto si no está al día, lo que la interfaz ve como un cambio. Hay que resolverlo en la etapa 5.

## Para quien siga

- Etapa 5: canal local con la ventana abierta, botón "Conectar con mi IA" y panel del asistente con las propuestas pendientes, con muestra visual en los dos temas antes de implementarlo. Las herramientas que escriban usan `Proyecto.proponer`, nunca `editar`, con `origen` de la forma `ia: <cliente>`.
