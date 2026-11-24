# Resultados a precisión completa (`nervi-resultados`, versión 1)

La memoria de cálculo en PDF redondea a 4 cifras significativas para que se lea. Este archivo guarda los mismos resultados **sin redondear**: cada número es el `float64` que dio el motor y se vuelve a leer igual, bit a bit, porque JSON escribe la representación más corta que identifica a cada número.

Sirve para revisar y auditar un cálculo, comparar dos versiones de un proyecto, llevar los resultados a otros programas y como fuente de datos para las integraciones (servidor MCP para agentes de IA, complementos).

## Cómo se genera

```python
from nervi.proyecto import Proyecto

p = Proyecto()
p.abrir("portico.nrv")
p.exportar_resultados("portico.resultados.json")   # o p.resultados_completos() -> dict
```

Para leerlo, `nervi.resultados.leer(ruta)`, que rechaza con `ResultadosError` un archivo de otro formato o de una versión más nueva.

El archivo va **aparte** del `.nrv`: los resultados se derivan del modelo, y guardarlos dentro del proyecto permitiría abrir un proyecto con resultados viejos. La `huella_modelo` dice a qué modelo corresponden.

## Contenido

| Clave | Contenido |
|---|---|
| `formato`, `version` | `"nervi-resultados"` y `1` |
| `programa` | nombre y versión de Nervi que lo generó |
| `contratos` | versiones de los contratos del motor: `plano`, `espacial`, `dinamica`, `diseno` |
| `fecha` | fecha y hora UTC (ISO 8601) |
| `huella_modelo` | `"sha256:…"` de `modelo.json` en forma canónica (claves ordenadas, sin espacios, UTF-8); `nervi.resultados.huella(modelo)` la recalcula |
| `unidades` | las de `modelo.json` (`fuerza`, `longitud`) |
| `componentes` | orden de las componentes de cada arreglo (abajo) |
| `casos` | un resultado por caso de carga |
| `combinaciones` | un resultado por combinación, con sus `factores` |
| `diseno` | solo si el diseño está al día: una entrada por barra |
| `dinamica` | solo si la dinámica está al día: modos y espectros |

Exportar no diseña ni analiza la dinámica por su cuenta, porque eso cambia el proyecto (suma sus datos al `.nrv`); si esos resultados no están al día, sus claves no aparecen.

### Un resultado (caso, combinación o espectro)

Nudos y barras se identifican con los `id` de `modelo.json`: `"N3"`, `"B2"`.

| Clave | Contenido |
|---|---|
| `desplazamientos` | `{"N1": [ux, uy, rz], …}` en ejes globales, todos los nudos |
| `reacciones` | `{"N1": [Rx, Ry, Mz], …}` en ejes globales, solo los nudos con apoyo |
| `fuerzas_extremo` | `{"B1": [N_i, V_i, M_i, N_j, V_j, M_j], …}` en ejes locales, actuando sobre la barra |
| `diagramas` | `{"B1": {"x": […], "N": […], "V": […], "M": […], "u": […], "v": […]}, …}` por estación |

Convenciones de signos en [`convenciones.md`](convenciones.md). Las combinaciones se resuelven junto con el modelo, así que sus diagramas son exactos y usan las mismas estaciones que la memoria ([`contrato-datos.md`](contrato-datos.md), `diagramas_combinaciones`).

### Diseño

Una entrada por barra: `barra`, `tipo` (`viga`, `columna` o `ninguno`), `seccion_mm` (`[b, h]`), `estado`, `relacion` (la mayor), `armadura`, `mensajes` y `verificaciones`, cada una con `nombre`, `solicitacion`, `resistencia`, `relacion`, `unidad` y `articulo` de la norma.

### Dinámica

`gravedad`, `masa_total` (`[X, Y]`), `modos` (por modo: `periodo`, `frecuencia`, `masa_participante` y `factor_participacion` en X e Y) y `espectros`, cada uno con su `direccion` y un resultado como los de arriba (valores absolutos combinados).

## Valores no finitos

JSON no admite `NaN` ni infinitos. `nervi.resultados.guardar` los rechaza con un `ValueError` que dice dónde están, en vez de escribir un archivo que otros programas no puedan leer.

## Historial de versiones

| Versión | Cambio |
|---|---|
| 1 | Versión inicial (pórtico plano: casos, combinaciones, diseño y dinámica). |
