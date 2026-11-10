# Contrato de datos Rust ↔ Python (versión 2)

Función: `nervi._core.resolver_portico_2d(version, coords, conectividad, props, liberaciones, restricciones, resortes, cargas_nodales, cargas_barra, despl_impuestos, n_estaciones=11)`.

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

`cargas_barra`: `tipo` 0 = uniforme en toda la luz (`vx, vy` = `qx, qy`, `a` se ignora), 1 = puntual a la distancia `a` del nudo `i` (`vx, vy` = `px, py`), 2 = trapezoidal entre `a` y `b` (distancias desde el nudo `i`, `0 ≤ a < b ≤ L`), que vale `vx, vy` = `qx1, qy1` en `a` y `vx2, vy2` = `qx2, qy2` en `b`. Las columnas que un tipo no usa se ignoran (conviene dejarlas en 0). `ejes` 0 = local, 1 = global.

### Historial de versiones

| Versión | Cambio |
|---|---|
| 1 | Versión inicial: `cargas_barra` con 7 columnas, tipos 0 y 1. |
| 2 | `cargas_barra` pasa a 10 columnas (`b, vx2, vy2`) y se agrega el tipo 2, carga trapezoidal o uniforme parcial (issue #2). Un arreglo de 7 columnas se rechaza con `ValueError`. |

## Salida

Diccionario:

| Clave | Forma | Contenido |
|---|---|---|
| `desplazamientos` | `(n_casos, n_nudos, 3)` | `[ux, uy, rz]` globales |
| `reacciones` | `(n_casos, n_nudos, 3)` | `[Rx, Ry, Mz]` globales; cero en GDL libres |
| `fuerzas_extremo` | `(n_casos, n_barras, 6)` | fuerzas sobre la barra en ejes locales |
| `gdl_sin_rigidez` | lista de `(nudo, "ux"/"uy"/"rz")` | GDL fijados automáticamente |
| `diagramas` | lista (por caso) de diccionarios | arreglos planos `barra, x, N, V, M, u, v` |

## Errores

| Excepción | Cuándo |
|---|---|
| `ValueError` | formas incorrectas, índices fuera de rango, propiedades no positivas, barras de longitud nula, combinaciones de liberaciones inestables |
| `nervi.MecanismoError` | estructura inestable (falta de apoyos o articulaciones de más), o carga sobre un GDL sin rigidez |
