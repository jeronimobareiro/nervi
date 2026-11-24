# Conectar un agente de IA (`nervi-mcp`)

Nervi trae un servidor [MCP](https://modelcontextprotocol.io) (Model Context Protocol) para que el agente de IA que ya usa la persona consulte un proyecto: qué hay en el modelo, desplazamientos y reacciones de un nudo, diagramas y envolventes de una barra, verificaciones del diseño y modos de vibración. Sirve para preguntar en lenguaje natural ("¿qué combinación manda en la viga B2?", "¿cuánto se desplaza N3 con viento?") y para que el agente explique los resultados.

**El agente nunca produce un número de resultado.** Cada cifra sale del motor de Nervi a través de una herramienta, sin redondear, y el servidor le pide al agente que diga de qué herramienta y de qué caso o combinación la sacó. La responsabilidad del cálculo sigue siendo de la persona profesional que firma.

Esta primera versión es **de solo lectura**: ninguna herramienta cambia el `.nrv`. Las que cambien el proyecto (cargar datos, importar un DXF) van a llegar como propuestas que la persona aplica o descarta ([`hoja-de-ruta.md`](hoja-de-ruta.md), línea "Integración con agentes de IA", etapas 5 y 6).

## Instalación

```bash
pip install "nervi[ia]"
```

Suma el SDK oficial de MCP (licencia MIT) y el comando `nervi-mcp`. Funciona con las versiones 1.x y 2.x del SDK.

## Cómo se usa

El agente lanza el servidor con la ruta del proyecto y le habla por la entrada y salida estándar (`stdio`):

```bash
nervi-mcp ruta/al/portico.nrv
```

El servidor lee el archivo guardado. Si la persona lo vuelve a guardar desde la interfaz, la consulta siguiente ve lo nuevo, sin reiniciar nada. Lo que se calcula para responder (el análisis, el diseño, la dinámica) se hace en memoria y no se escribe.

### Claude Desktop

En `claude_desktop_config.json` (menú *Configuración → Desarrollador → Editar configuración*):

```json
{
  "mcpServers": {
    "nervi": {
      "command": "nervi-mcp",
      "args": ["C:\\Proyectos\\portico.nrv"]
    }
  }
}
```

Si `nervi-mcp` no está en el `PATH`, poné la ruta completa del ejecutable (en Windows, algo como `C:\\Users\\vos\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\nervi-mcp.exe`) o usá `"command": "python", "args": ["-m", "nervi.ia.servidor", "…/portico.nrv"]`.

### Claude Code

```bash
claude mcp add nervi -- nervi-mcp ruta/al/portico.nrv
```

### Gemini CLI y otros clientes con servidores locales

Gemini CLI (`~/.gemini/settings.json`), VS Code, Cursor, LM Studio y la mayoría de los clientes MCP aceptan servidores locales por `stdio` con la misma forma: un `command` (`nervi-mcp`) y sus `args` (la ruta del `.nrv`). La clave exacta del archivo de configuración cambia de un cliente a otro; está en la documentación de cada uno.

### ChatGPT y clientes que solo aceptan servidores remotos

Algunos clientes, como ChatGPT en la web, solo se conectan a servidores MCP remotos por HTTP, no a programas locales. Para ellos hace falta el canal local con la ventana abierta (etapa 5 de la hoja de ruta); `nervi-mcp` no abre ningún puerto de red.

## Herramientas

Todas son de solo lectura (`readOnlyHint`) y devuelven JSON. Nudos y barras se nombran como en la interfaz (`N3`, `B2`); también se acepta el número solo. Las unidades son las del modelo y vienen en cada respuesta.

| Herramienta | Qué devuelve |
|---|---|
| `resumen_proyecto` | Unidades, cantidades, casos, combinaciones con sus factores, apoyos, si hay datos de diseño y de dinámica, la revisión del modelo y la huella de `modelo.json` |
| `leer_modelo` | `modelo.json` completo ([`formato-nrv.md`](formato-nrv.md) §4) |
| `revisar_modelo` | Avisos de la revisión del modelo, los del panel de la interfaz |
| `listar_resultados` | Nombres de los casos y de las combinaciones |
| `leer_nudo(nudo, resultado?)` | Desplazamientos `ux, uy, rz` y, si tiene apoyo, reacciones `Rx, Ry, Mz`, en un caso o combinación o en todos |
| `leer_barra(barra, resultado)` | Fuerzas de extremo en ejes locales, diagramas N, V, M y deformada por estación, y el máximo y el mínimo de N, V y M con su posición |
| `envolvente_barra(barra)` | Máximo y mínimo de N, V y M sobre todas las combinaciones, con la combinación y la posición de cada uno |
| `leer_reacciones(resultado?)` | Reacciones de cada apoyo en un caso o combinación; sin `resultado`, la envolvente con la combinación que manda |
| `leer_verificaciones(barra?)` | Diseño de hormigón armado (ACI 318-19, experimental): estado, armadura y cada verificación con solicitación, resistencia, relación y artículo. Solo si el proyecto tiene datos de diseño |
| `leer_modos` | Periodo, frecuencia y masa participante en X e Y de cada modo. Solo si el proyecto tiene datos de dinámica con masa |

Además publica dos recursos: `nervi://modelo` (el `modelo.json`) y `nervi://resultados` (todos los resultados sin redondear, en el formato de [`formato-resultados.md`](formato-resultados.md)).

Cuando una consulta no se puede responder (un nudo que no existe, un modelo inestable, un proyecto sin datos de diseño), la herramienta devuelve un error con el motivo en palabras, y el servidor le pide al agente que lo explique en vez de suplirlo.

## Sin MCP

Las mismas consultas están en `nervi.ia.herramientas` como funciones comunes de Python, para scripts o para otros protocolos:

```python
from nervi.ia.herramientas import FuenteArchivo, Herramientas

h = Herramientas(FuenteArchivo("portico.nrv"))
h.envolvente_barra("B2")["envolvente"]["M"]
```

## Privacidad

`nervi-mcp` no se conecta a internet. Lo que el agente lee del proyecto llega al proveedor de IA que use la persona, con las condiciones de ese proveedor; conviene tenerlo en cuenta con proyectos confidenciales.
