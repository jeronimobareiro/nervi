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

`cargas_barra`: `tipo` 0 = uniforme en toda la luz (`vx, vy` = `qx, qy`, `a` se ignora), 1 = puntual a la distancia `a` del nudo `i` (`vx, vy` = `px, py`), 2 = trapezoidal entre `a` y `b` (distancias desde el nudo `i`, `0 ≤ a < b ≤ L`), que vale `vx, vy` = `qx1, qy1` en `a` y `vx2, vy2` = `qx2, qy2` en `b`. 3 = térmica en toda la barra: `a` = `α` (coeficiente de dilatación), `vx` = `ΔT` uniforme, `vy` = `ΔT_g` = `T(cara -y) - T(cara +y)`, `b` = `h` (canto; puede ser 0 si `ΔT_g = 0`); `ejes` se ignora. 4 = momento concentrado a la distancia `a` del nudo `i` (`0 ≤ a ≤ L`): `vx` = `Mz`, antihorario positivo; `ejes` se ignora. Las columnas que un tipo no usa se ignoran (conviene dejarlas en 0). `ejes` 0 = local, 1 = global.

### Historial de versiones

| Versión | Cambio |
|---|---|
| 1 | Versión inicial: `cargas_barra` con 7 columnas, tipos 0 y 1. |
| 2 | `cargas_barra` pasa a 10 columnas (`b, vx2, vy2`) y se agrega el tipo 2, carga trapezoidal o uniforme parcial (issue #2). Un arreglo de 7 columnas se rechaza con `ValueError`. |
| 2 (ampliación compatible) | Argumento opcional `combinaciones` y salida `diagramas_combinaciones` (issue #21). |
| 2 (ampliación compatible) | Tipo 3, acción térmica (issue #4). No cambia la forma de ningún arreglo: los datos válidos de antes siguen valiendo, por eso no se sube la versión. |
| 2 (ampliación compatible) | Tipo 4, momento concentrado en el tramo (issue #3). Tampoco cambia la forma de ningún arreglo. |

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

# Contrato de datos del pórtico espacial (versión 3D 2)

Función: `nervi._core.resolver_portico_3d(version, coords, conectividad, props, referencias, liberaciones, restricciones, resortes, cargas_nodales, cargas_barra, despl_impuestos, n_estaciones=11, brazos=None, diafragmas=None, maestros=None)` (issues #12, #13 y #14).

Se versiona aparte con `nervi._core.VERSION_CONTRATO_3D` (hoy 2), para que agregar el pórtico espacial no cambie el contrato plano: `resolver_portico_2d` y `VERSION_CONTRATO = 2` siguen iguales. Mismas reglas que arriba: NumPy con forma y tipo fijos, `ValueError` con el nombre del arreglo si una forma no coincide, GIL liberado durante el cálculo y `n_casos` deducido de `cargas_nodales`. Ejes y signos en [`convenciones.md`](convenciones.md) §Pórtico espacial.

## Entrada

| Arreglo | dtype | Forma | Contenido |
|---|---|---|---|
| `coords` | float64 | `(n_nudos, 3)` | `[x, y, z]`, Z vertical hacia arriba |
| `conectividad` | int64 | `(n_barras, 2)` | `[nudo_i, nudo_j]` |
| `props` | float64 | `(n_barras, 6)` | `[E, G, A, Iy, Iz, J]` |
| `referencias` | float64 | `(n_barras, 3)` | vector de referencia del plano `x`–`y` local, en globales; una fila de ceros aplica la regla por defecto |
| `liberaciones` | uint8 | `(n_barras, 12)` | 1 = fuerza de extremo liberada `(N, Vy, Vz, T, My, Mz)` en `i` y luego en `j` |
| `restricciones` | uint8 | `(n_nudos, 6)` | 1 = GDL restringido `(ux, uy, uz, rx, ry, rz)` |
| `resortes` | float64 | `(n_nudos, 6)` | rigidez de apoyo elástico `(kx, ky, kz, krx, kry, krz)` |
| `cargas_nodales` | float64 | `(n_casos, n_nudos, 6)` | `[Fx, Fy, Fz, Mx, My, Mz]` globales |
| `cargas_barra` | float64 | `(n_cargas, 12)` | `[caso, barra, tipo, ejes, a, b, qx1, qy1, qz1, qx2, qy2, qz2]` |
| `despl_impuestos` | float64 | `(n_casos, n_nudos, 6)` | asentamientos; solo se usan en GDL restringidos |
| `brazos` (opcional) | float64 | `(n_barras, 6)` | brazos rígidos `[bix, biy, biz, bjx, bjy, bjz]` en globales, del nudo a la cara; `None` o ceros = sin brazos |
| `diafragmas` (opcional) | int64 | `(n_nudos,)` | índice del diafragma rígido de cada nudo; -1 = ninguno |
| `maestros` (opcional) | int64 | `(n_diafragmas,)` | nudo maestro de cada diafragma; se da junto con `diafragmas` |

`cargas_barra`: `tipo` 0 = uniforme en toda la luz (`q1`; `a`, `b` y `q2` se ignoran), 1 = puntual `q1 = (px, py, pz)` a la distancia `a` del nudo `i`, 2 = trapezoidal entre `a` y `b` (`0 ≤ a < b ≤ L`) que vale `q1` en `a` y `q2` en `b`. `ejes` 0 = local, 1 = global. Un arreglo con otro número de columnas se rechaza con `ValueError`.

## Salida

| Clave | Forma | Contenido |
|---|---|---|
| `desplazamientos` | `(n_casos, n_nudos, 6)` | `[ux, uy, uz, rx, ry, rz]` globales |
| `reacciones` | `(n_casos, n_nudos, 6)` | `[Rx, Ry, Rz, Mx, My, Mz]` globales; cero en GDL libres |
| `fuerzas_extremo` | `(n_casos, n_barras, 12)` | fuerzas sobre la barra en ejes locales, `[Fx, Fy, Fz, Mx, My, Mz]` en `i` y en `j` |
| `ejes` | `(n_barras, 3, 3)` | filas: versores `x, y, z` locales de cada barra en globales |
| `gdl_sin_rigidez` | lista de `(nudo, "ux"…"rz")` | GDL fijados automáticamente |
| `diagramas` | lista (por caso) de diccionarios | arreglos planos `barra, x, N, Vy, Vz, T, My, Mz, u, v, w, rx` (`u, v, w` desplazamientos y `rx` giro de torsión, en ejes locales); estaciones equidistantes, puntos de carga y puntos donde `Vy` o `Vz` se anulan |

Errores: los mismos que en el plano. `MecanismoError.gdl` puede valer además `"uz"`, `"rx"` o `"ry"`.

### Historial de versiones (3D)

| Versión | Cambio |
|---|---|
| 1 | Versión inicial (issues #11 y #12): cargas uniformes, puntuales y trapezoidales. |
| 2 | Brazos rígidos (`brazos`, #13) y diafragmas rígidos (`diafragmas`, `maestros`, #14), opcionales: un modelo sin ellos da lo mismo que en la versión 1. Con brazos, `L`, las cargas en el tramo, los diagramas y las fuerzas de extremo se refieren a la parte flexible, entre las caras. |

# Contrato de datos de la dinámica del pórtico espacial (versión 2)

Funciones: `nervi._core.resolver_modal_3d(version, modelo, masas_nodales, masas_lineales, masas_casos, gravedad, tipo_masa, n_modos, metodo=0)` y `nervi._core.espectro_3d(version, modelo, omegas, modos, inercias, periodos_espectro, aceleraciones_espectro, direccion, amortiguamiento, combinacion, n_estaciones=11)` (issues #16, #17 y #18).

Se versiona aparte con `nervi._core.VERSION_CONTRATO_DINAMICA` (hoy 2). `modelo` es un diccionario con los arreglos de entrada del contrato 3D (las claves de la tabla de arriba, lo que devuelve `Modelo3D.arreglos()`; `brazos`, `diafragmas` y `maestros` pueden faltar); los dos contratos anteriores no cambian. Convenciones en [`convenciones.md`](convenciones.md) §Dinámica.

## Entrada de `resolver_modal_3d`

| Argumento | dtype | Forma | Contenido |
|---|---|---|---|
| `masas_nodales` | float64 | `(n_nudos, 6)` | `[mx, my, mz, Jx, Jy, Jz]` globales |
| `masas_lineales` | float64 | `(n_barras,)` | masa por unidad de longitud de cada barra |
| `masas_casos` | float64 | `(n_casos,)` | factor de cada caso para convertir sus cargas verticales en masa (0 = no se usa) |
| `gravedad` | float | — | en las unidades del modelo |
| `tipo_masa` | int | — | 0 = concentrada, 1 = consistente |
| `n_modos` | int | — | cantidad de modos pedidos (al menos 1) |
| `metodo` | int | — | 0 = automático, 1 = denso, 2 = Lanczos |

## Salida de `resolver_modal_3d`

| Clave | Forma | Contenido |
|---|---|---|
| `omegas`, `periodos`, `frecuencias` | `(n_modos,)` | `ω`, `T = 2π/ω`, `f = 1/T`, de menor a mayor frecuencia |
| `modos` | `(n_modos, n_nudos, 6)` | formas modales normalizadas a masa, globales |
| `inercias` | `(n_modos, n_nudos, 6)` | `M φ` de cada modo en los GDL independientes libres (cero en los restringidos; con diafragma, la parte horizontal del piso está en el maestro) |
| `factores_participacion` | `(n_modos, 3)` | `Γ` en X, Y y Z |
| `masas_efectivas` | `(n_modos, 3)` | `Γ²` en X, Y y Z |
| `masa_total` | `(3,)` | `rᵀ M r` en X, Y y Z |
| `n_gdl_masa` | int | GDL libres con masa |
| `metodo` | `"denso"` o `"lanczos"` | método usado |
| `gdl_sin_rigidez` | lista de `(nudo, gdl)` | GDL libres sin rigidez ni masa fijados automáticamente |
| `diafragmas` | lista de diccionarios | por diafragma: `maestro`, `masa` `[mx, my]`, `centro_masa` `[x, y]` e `inercia` alrededor del eje vertical por el centro de masa |

## Entrada y salida de `espectro_3d`

`omegas (n_modos,)`, `modos` e `inercias (n_modos, n_nudos, 6)` son los de `resolver_modal_3d` con el mismo modelo. `periodos_espectro` y `aceleraciones_espectro` (float64, mismo largo, periodos estrictamente crecientes y aceleraciones no negativas), `direccion` (float64 `(3,)`), `amortiguamiento` en `[0, 1)` y `combinacion` 0 = SRSS, 1 = CQC.

| Clave | Forma | Contenido |
|---|---|---|
| `desplazamientos`, `reacciones` | `(n_nudos, 6)` | combinados, valores absolutos |
| `fuerzas_extremo` | `(n_barras, 12)` | combinadas, valores absolutos |
| `cortante_basal` | `(3,)` | combinación de los cortantes basales de cada modo |
| `cortante_basal_modal` | `(n_modos, 3)` | suma de reacciones de cada modo, con signo |
| `aceleraciones`, `factores` | `(n_modos,)` | `Sa(Tₙ)` y `Γₙ` en la dirección de excitación |
| `correlacion` | `(n_modos, n_modos)` | coeficientes `ρᵢⱼ` (identidad en SRSS) |
| `diagramas` | diccionario | como un caso de `resolver_portico_3d`, combinado, en `n_estaciones` estaciones equidistantes por barra |

Errores: `ValueError` por datos inválidos (masas negativas, modelo sin masa, espectro mal definido) y `MecanismoError` si la estructura es inestable o hay masa en un GDL sin rigidez.

### Historial de versiones (dinámica)

| Versión | Cambio |
|---|---|
| 1 | Versión inicial (issues #16, #17 y #18): masas nodales, lineales y desde casos; modal denso y Lanczos; espectro con SRSS y CQC. |
| 2 | El modelo admite brazos rígidos y diafragmas (contrato 3D 2); `resolver_modal_3d` devuelve además `diafragmas`, y las `inercias` se dan en los GDL independientes. |

# Contrato de datos del diseño (versión 2)

Funciones de `nervi._core` que usan `nervi.design.aci318.columna` (issue #24) para la flexocompresión biaxial de columnas, calculada en `nervi_core::diseno::columna`, y `nervi.design.aci318.flexion` (issue #22) para la flexión de vigas, calculada en `nervi_core::diseno::viga`. No son API pública: se llaman a través de `verificar_columna`, `diagrama_interaccion`, `elegir_armadura_columna`, `disenar_columna`, `resistencia_flexion`, `armadura_flexion`, `elegir_barras` y `disenar_viga`, que no cambiaron. Se versiona aparte con `nervi._core.VERSION_CONTRATO_DISENO` (hoy 2); los contratos del análisis no cambian.

Argumentos comunes (float64 contiguos, mm y MPa): `contorno (k, 2)` con los vértices `(y, z)` del polígono convexo antihorario con el origen en el baricentro, `barras (n, 2)` con las posiciones `(y, z)`, `areas (n,)` en mm² (las barras de área nula se ignoran), `fc`, `fy` y `zunchada`. Signos de [`convenciones.md`](convenciones.md) y del módulo de Python: `Pn` y `Pu` positivos en compresión.

| Función | Entrada propia | Salida |
|---|---|---|
| `columna_seccion_en(version, contorno, barras, areas, fc, fy, zunchada, theta, c)` | `theta (m,)` inclinación del eje neutro (rad), `c (m,)` profundidad (mm) | diccionario con `pn` (N), `mz`, `my` (N·mm), `eps_t` y `phi`, cada uno `(m,)` |
| `columna_capacidad(version, contorno, barras, areas, fc, fy, zunchada, p_obj, alfa)` | `p_obj (m,)` en N y `alfa (m,)` dirección en el plano `(Mz, My)` | `(phi_mn (N·mm), theta, c, ok)`, cada uno `(m,)` |
| `columna_razones(version, contorno, barras, areas, fc, fy, zunchada, solicitaciones_kn, phi_pn_max, phi_pnt)` | `solicitaciones_kn (m, 3)` = `(Pu, Mz, My)` en kN y kN·m; `φPn,max` y `φPnt` en kN | `(phi_mn (kN·m), razon_momento, razon_axial, razon)`, cada uno `(m,)` |
| `columna_elegir_armadura(version, contorno, barras, areas, phi_pn_max, phi_pnt, fc, fy, zunchada, solicitaciones_kn)` | `barras (K, n, 2)` y `areas (K, n)` con K armaduras candidatas ordenadas por área (completadas con barras de área nula), `phi_pn_max` y `phi_pnt (K,)` en kN | índice de la primera candidata que resiste todas las solicitaciones, o `None` |

Errores: `ValueError` si la versión no coincide, las formas no son las esperadas, el contorno tiene menos de 3 vértices o `f'c` o `fy` no son positivos.

## Flexión de vigas

Argumentos comunes (mm, mm² y MPa; momentos en kN·m): `b`, `d`, `fc`, `fy`. La validación de los datos y los mensajes de error de la API quedan en Python. `resistencia` es la tupla `(Mn, φ, φMn, c, a, εt, fs, fs_comp)` de `ResistenciaFlexion`, con `Mn` y `φMn` en kN·m.

| Función | Entrada propia | Salida |
|---|---|---|
| `viga_resistencia(version, b, d, As, fc, fy, As_comp, d_comp, dt)` | armaduras traccionada y comprimida, `d_comp` y `dt` (capa más traccionada) | `resistencia` |
| `viga_armadura_simple(version, Mu, b, d, dt, fc, fy, lim)` | `Mu` en valor absoluto y `lim`, el `εt` mínimo | `(As_lim, c_lim, resistencia con As_lim, simple)`, donde `simple` es `None` si hace falta armadura de compresión o `(As_req, As, resistencia con As)` |
| `viga_elegir_barras(version, Mu, b, h, recubrimiento, d_estribo, d_agregado, fc, fy, lim, diametros, max_capas, max_barras)` | `diametros (k,)` float64 positivos | `None` o `(capas, As, d, dt, b_nec, s_libre, As_req, resistencia)`, con `capas` como listas de índices en `diametros`, desde la capa más traccionada |

### Historial de versiones (diseño)

| Versión | Cambio |
|---|---|
| 1 | Versión inicial: flexocompresión biaxial de columnas (antes en NumPy, mismos resultados). |
| 2 | Flexión de vigas: `viga_resistencia`, `viga_armadura_simple` y `viga_elegir_barras` (antes en Python, mismos resultados). Las funciones de columnas no cambian. |
