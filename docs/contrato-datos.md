# Contrato de datos Rust ↔ Python (versión 2)

Función: `nervi._core.resolver_portico_2d(version, coords, conectividad, props, liberaciones, restricciones, resortes, cargas_nodales, cargas_barra, despl_impuestos, n_estaciones=11, combinaciones=None)`.

Reglas:

- Todos los arreglos son NumPy con la forma y el tipo indicados. Rust verifica cada forma y lanza `ValueError` con el nombre del arreglo si no coincide.
- `version` debe ser `nervi._core.VERSION_CONTRATO`. Cualquier cambio incompatible del contrato incrementa este número.
- El cálculo se hace con el GIL liberado.
- `n_casos` se deduce de `cargas_nodales.shape[0]`.

## Entrada

| Arreglo | dtype | Forma | Contenido |
|---|---|---|---|
| `coords` | float64 | `(n_nudos, 2)` | `[x, y]` |
| `conectividad` | int64 | `(n_barras, 2)` | `[nudo_i, nudo_j]` |
| `props` | float64 | `(n_barras, 3)` | `[E, A, I]` |
| `liberaciones` | uint8 | `(n_barras, 6)` | 1 = fuerza de extremo liberada `(N_i, V_i, M_i, N_j, V_j, M_j)` |
| `restricciones` | uint8 | `(n_nudos, 3)` | 1 = GDL restringido `(ux, uy, rz)` |
| `resortes` | float64 | `(n_nudos, 3)` | rigidez de apoyo elástico `(kx, ky, krz)` |
| `cargas_nodales` | float64 | `(n_casos, n_nudos, 3)` | `[Fx, Fy, Mz]` globales |
| `cargas_barra` | float64 | `(n_cargas, 10)` | `[caso, barra, tipo, ejes, a, vx, vy, b, vx2, vy2]` |
| `despl_impuestos` | float64 | `(n_casos, n_nudos, 3)` | asentamientos; solo se usan en GDL restringidos |
| `combinaciones` (opcional) | float64 | `(n_comb, n_casos)` | factores de cada combinación lineal de casos |

`cargas_barra`: `tipo` 0 = uniforme en toda la luz (`vx, vy` = `qx, qy`, `a` se ignora), 1 = puntual a la distancia `a` del nudo `i` (`vx, vy` = `px, py`), 2 = trapezoidal entre `a` y `b` (distancias desde el nudo `i`, `0 ≤ a < b ≤ L`), que vale `vx, vy` = `qx1, qy1` en `a` y `vx2, vy2` = `qx2, qy2` en `b`. 3 = térmica en toda la barra: `a` = `α` (coeficiente de dilatación), `vx` = `ΔT` uniforme, `vy` = `ΔT_g` = `T(cara -y) - T(cara +y)`, `b` = `h` (canto; puede ser 0 si `ΔT_g = 0`); `ejes` se ignora. Las columnas que un tipo no usa se ignoran (conviene dejarlas en 0). `ejes` 0 = local, 1 = global.

### Historial de versiones

| Versión | Cambio |
|---|---|
| 1 | Versión inicial: `cargas_barra` con 7 columnas, tipos 0 y 1. |
| 2 | `cargas_barra` pasa a 10 columnas (`b, vx2, vy2`) y se agrega el tipo 2, carga trapezoidal o uniforme parcial (issue #2). Un arreglo de 7 columnas se rechaza con `ValueError`. |
| 2 (ampliación compatible) | Argumento opcional `combinaciones` y salida `diagramas_combinaciones` (issue #21). |
| 2 (ampliación compatible) | Tipo 3, acción térmica (issue #4). No cambia la forma de ningún arreglo: los datos válidos de antes siguen valiendo, por eso no se sube la versión. |

## Salida

Diccionario:

| Clave | Forma | Contenido |
|---|---|---|
| `desplazamientos` | `(n_casos, n_nudos, 3)` | `[ux, uy, rz]` globales |
| `reacciones` | `(n_casos, n_nudos, 3)` | `[Rx, Ry, Mz]` globales; cero en GDL libres |
| `fuerzas_extremo` | `(n_casos, n_barras, 6)` | fuerzas sobre la barra en ejes locales |
| `gdl_sin_rigidez` | lista de `(nudo, "ux"/"uy"/"rz")` | GDL fijados automáticamente |
| `diagramas` | lista (por caso) de diccionarios | arreglos planos `barra, x, N, V, M, u, v` |
| `diagramas_combinaciones` | lista (por combinación) de diccionarios | igual que `diagramas`, exactos por superposición; todas las combinaciones usan las **mismas estaciones** por barra (puntos de carga de todos los casos y cortante nulo de cada combinación), para comparar punto a punto. Vacía sin `combinaciones` |

## Errores

| Excepción | Cuándo |
|---|---|
| `ValueError` | formas incorrectas, índices fuera de rango, propiedades no positivas, barras de longitud nula, combinaciones de liberaciones inestables |
| `nervi.MecanismoError` | estructura inestable (falta de apoyos o articulaciones de más), o carga sobre un GDL sin rigidez |

`nervi.MecanismoError` trae además estos atributos (issue #9), que no cambian la versión del contrato porque son un agregado compatible:

| Atributo | Tipo | Contenido |
|---|---|---|
| `nudo` | `int` o `None` | nudo que más se mueve en el primer modo de mecanismo, o el nudo cargado sin rigidez; `None` si no se pudo localizar |
| `gdl` | `"ux"`, `"uy"`, `"rz"` o `None` | GDL de ese nudo (una traslación, salvo que el modo solo tenga giros) |
| `modos` | lista de listas de `(nudo, gdl, valor)` | modos de mecanismo (hasta 6), cada uno normalizado para que el GDL principal valga 1; solo las componentes con valor absoluto de al menos 1e-6. Vacía para la carga sin rigidez |
