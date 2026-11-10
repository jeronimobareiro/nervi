# 2026-11-10-08 · Combinaciones de carga ACI 318-19 y envolventes

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-40bfxu`
- **Fase de la hoja de ruta:** Fase 3, diseño de hormigón armado · issue [#21](https://github.com/jeronimobareiro/nervi/issues/21)

## Qué se pidió

Cuarto punto del plan de la semana: asignar tipos de carga a los casos, generar las combinaciones de una norma intercambiable y calcular envolventes por sección con la combinación que produce cada extremo (issue #21). Debe quedar listo para sumar la norma paraguaya cuando se decida (#20).

## Qué se hizo

- **Motor** (`analisis.rs`): `Resultados::seccion_combinada` (combinación lineal exacta por superposición), `diagrama_combinado` y `estaciones_comunes`, que reúne los puntos de carga de todos los casos y los puntos de cortante nulo de **cada** combinación. `diagrama` de un caso ahora es el combinado con un solo factor.
- **Contrato** (ampliación compatible de la v2): argumento opcional `combinaciones (n_comb, n_casos)` y salida `diagramas_combinaciones`, con todas las combinaciones en las mismas estaciones por barra.
- **Python**: `Modelo.resolver(combinaciones={nombre: {caso: factor}})`; `res[nombre]` devuelve la combinación como un caso, con diagramas exactos (antes `combinar` interpolaba cuando los casos tenían estaciones distintas, por ejemplo el cortante nulo). `res.combinaciones` y `res.factores(nombre)`.
- **`nervi.design`** (experimental, emite `ModuloExperimentalWarning`):
  - `generar(tipos, norma="aci318-19", estados, alternar_sobrecarga, invertir_laterales, reducir_sobrecarga)`: tipos `D, L, Lr, S, R, W, E`; sobrecarga alternada (todos los juegos de casos `L`); viento y sismo en ambos sentidos; sin combinaciones repetidas.
  - `normas/aci318_19.py`: §5.3.1 a–g y servicio según §24.2. Cada norma es un módulo; una regional se suma registrándola en `_NORMAS`.
  - `envolvente(res, barra)` y `envolvente_reacciones(res)`: máximos y mínimos con el nombre de la combinación.

## Cómo se verificó

- `tests/test_design_combinaciones.py` (9 pruebas): combinaciones generadas contra una lista hecha a mano (D, L, Lr, W±); sismo, nieve, reducción de `L` y servicio; juegos de sobrecarga alternada; envolvente de una viga continua de dos tramos con sobrecarga alternada contra el cálculo manual (`M_B = -wL²/8` con los dos tramos cargados; `M⁺ = R_A²/2w1` en `x = R_A/w1` con solo el tramo 1, y la combinación que lo produce); reacción máxima del apoyo central; combinación exacta con un salto de carga puntual; errores; doctest del módulo.
- `crates/nervi-core/tests/combinaciones.rs`: el diagrama combinado encuentra el máximo de la combinación y las estaciones comunes incluyen el cortante nulo de cada una.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test`, `pytest` (97, con la GUI y la biblioteca de verificación), `ruff`; el pórtico de 8 100 barras sigue resolviéndose en unos 50 ms.

## Decisiones tomadas

- Las combinaciones se resuelven **junto con el modelo** (en Rust) para que los diagramas sean exactos y las envolventes se comparen punto a punto sin interpolar. `Resultados.combinar` se mantiene por compatibilidad.
- En "Lr o S o R" también se genera la variante sin carga de cubierta, porque puede aliviar algún esfuerzo (voladizos).
- Servicio: cargas sin mayorar (`D`, `D + L`, `D + L + cubierta`), que es lo que pide ACI 318-19 §24.2 para flechas inmediatas. No se implementaron todavía las combinaciones ASD de ASCE 7 §2.4.
- No se incluyen `H`, `F` ni `T` (empujes y efectos diferidos).

## Pendiente y problemas conocidos

- **Revisión de un ingeniero estructural** de `nervi/design/normas/aci318_19.py` antes de quitar la marca de experimental.
- Norma regional (#20): decisión del usuario; el módulo está preparado para sumarla.
- La GUI y el formato `.nrv` todavía no guardan tipos de carga ni combinaciones.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-10 a las 13:30 UTC ("firmalo todo por mi, te autorizo"), que el agente firme en su nombre los aportes de este plan de trabajo, como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Diseño a flexión y cortante de vigas (#22, #23) puede usar `envolvente(res, barra)` directamente.
