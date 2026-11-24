# Conectar un agente de IA (`nervi-mcp`)

Nervi trae un servidor [MCP](https://modelcontextprotocol.io) (Model Context Protocol) para que el agente de IA que ya usa la persona consulte un proyecto: qué hay en el modelo, desplazamientos y reacciones de un nudo, diagramas y envolventes de una barra, verificaciones del diseño y modos de vibración. Sirve para preguntar en lenguaje natural ("¿qué combinación manda en la viga B2?", "¿cuánto se desplaza N3 con viento?") y para que el agente explique los resultados.

**El agente nunca produce un número de resultado.** Cada cifra sale del motor de Nervi a través de una herramienta, sin redondear, y el servidor le pide al agente que diga de qué herramienta y de qué caso o combinación la sacó. La responsabilidad del cálculo sigue siendo de la persona profesional que firma.

**El agente no cambia el proyecto.** Con la ventana abierta puede *proponer* un cambio del modelo: Nervi calcula un resumen de lo que cambia ("Agrega N5", "Cambia B2 (A, I)") y la persona lo aplica o lo descarta; lo aplicado se puede deshacer con Ctrl+Z y queda anotado en el historial del `.nrv` con su origen.

## Instalación

```bash
pip install "nervi[ia]"
```

Suma el SDK oficial de MCP (licencia MIT) y el comando `nervi-mcp`. Funciona con las versiones 1.x y 2.x del SDK.

## Cómo se usa

La app de IA lanza `nervi-mcp` y le habla por la entrada y salida estándar (`stdio`). Hay dos modos:

- **Con la ventana abierta** (`nervi-mcp`, sin argumentos). En Nervi, la persona busca "Conectar con mi IA" (Ctrl+K). Desde ahí el agente consulta lo que está abierto, aunque no esté guardado, ve lo que la persona tiene seleccionado ("¿cuánto momento tiene esta barra?") y puede dejar propuestas. Al desconectar o cerrar Nervi, el agente deja de tener acceso y lo dice.
- **Con un archivo** (`nervi-mcp ruta/al/portico.nrv`). Solo lectura, no necesita la ventana. Si la persona vuelve a guardar el archivo, la consulta siguiente ve lo nuevo.

En los dos modos, lo que se calcula para responder (el análisis, el diseño, la dinámica) se hace sobre una copia: no cambia lo que ve la persona ni el archivo.

El canal con la ventana escucha solo en `127.0.0.1`, en un puerto que elige el sistema, y exige un secreto que Nervi genera al conectar y deja en un archivo que solo puede leer el usuario (`%APPDATA%\Nervi\canal.json` en Windows, `~/.config/nervi/canal.json` en Linux y macOS). Al desconectar, el archivo se borra y el secreto deja de valer.

### Claude Desktop

En `claude_desktop_config.json` (menú *Configuración → Desarrollador → Editar configuración*):

```json
{
  "mcpServers": {
    "nervi": {
      "command": "nervi-mcp"
    }
  }
}
```

Así se conecta con la ventana abierta. Para consultar un archivo fijo, agregá `"args": ["C:\\Proyectos\\portico.nrv"]`. Si `nervi-mcp` no está en el `PATH`, poné la ruta completa del ejecutable (en Windows, algo como `C:\\Users\\vos\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\nervi-mcp.exe`) o usá `"command": "python", "args": ["-m", "nervi.ia.servidor"]`.

### Claude Code

```bash
claude mcp add nervi -- nervi-mcp                     # ventana abierta
claude mcp add nervi-portico -- nervi-mcp portico.nrv  # un archivo, solo lectura
```

### Gemini CLI y otros clientes con servidores locales

Gemini CLI (`~/.gemini/settings.json`), VS Code, Cursor, LM Studio y la mayoría de los clientes MCP aceptan servidores locales por `stdio` con la misma forma: un `command` (`nervi-mcp`) y, si se quiere un archivo fijo, sus `args` (la ruta del `.nrv`). La clave exacta del archivo de configuración cambia de un cliente a otro; está en la documentación de cada uno.

### ChatGPT y clientes que solo aceptan servidores remotos

Algunos clientes, como ChatGPT en la web, solo se conectan a servidores MCP remotos por HTTP, no a programas locales. `nervi-mcp` no abre ningún puerto hacia afuera de la computadora, así que con ellos no funciona. Más adelante está previsto un chat dentro de Nervi con clave de API del proveedor ([`hoja-de-ruta.md`](hoja-de-ruta.md)).

## Herramientas

Las de consulta son de solo lectura (`readOnlyHint`) y devuelven JSON. Nudos y barras se nombran como en la interfaz (`N3`, `B2`); también se acepta el número solo. Las unidades son las del modelo y vienen en cada respuesta.

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

Con la ventana abierta hay tres más:

| Herramienta | Qué hace |
|---|---|
| `leer_seleccion` | El nudo o la barra que la persona tiene seleccionado y la combinación que está mirando |
| `proponer_modelo(modelo, descripcion)` | Deja pendiente un `modelo.json` nuevo (el de `leer_modelo` con lo pedido cambiado) con su resumen de cambios; la persona lo aplica o lo descarta. Si el modelo propuesto no es válido, dice por qué |
| `listar_propuestas` | Las propuestas que siguen pendientes; una que ya no aparece fue aplicada o descartada |

Además publica dos recursos: `nervi://modelo` (el `modelo.json`) y, con un archivo, `nervi://resultados` (todos los resultados sin redondear, en el formato de [`formato-resultados.md`](formato-resultados.md)).

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
