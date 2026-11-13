# 2026-11-13-01 · Ejemplos de libros en la biblioteca de verificación

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-3sj09h`
- **Fase de la hoja de ruta:** Fase 1, issue [#6](https://github.com/jeronimobareiro/nervi/issues/6)

## Qué se pidió

Seguir con lo que queda de la Fase 1. Según `ESTADO.md` y los issues abiertos, lo siguiente era #6: ejemplos de libros como casos de verificación.

## Qué se hizo

- Carpeta `verification/libros/` con cinco casos del tipo de los que se resuelven en Análisis Estructural, todos con el método del capítulo citado de Hibbeler, *Structural Analysis*, 10.ª ed.:
  - `viga-continua-tres-tramos.toml`: extremo empotrado, carga uniforme, puntual y uniforme en tramos de 6, 8 y 5 m.
  - `viga-asentamiento-voladizo.toml`: asentamiento de 12 mm del apoyo central y voladizo con carga en la punta.
  - `portico-columnas-desiguales.toml`: columnas de 4 m (empotrada) y 6 m (articulada), carga lateral y gravitatoria, con desplazamiento lateral.
  - `portico-dos-pisos.toml`: una crujía, dos pisos, cargas laterales y gravitatorias.
  - `cercha-pratt.toml`: los 13 axiles por el método de los nudos y la flecha en el centro por trabajo virtual.
- `verification/libros/derivaciones.py`: la solución a mano de cada caso, escrita barra por barra (pendiente-deflexión con desplazamiento lateral, equilibrio de nudos y trabajo virtual) y resuelta con aritmética exacta en `sympy`, sin usar el motor. Los valores esperados de los `.toml` son las fracciones exactas que imprime.
- Tabla `[referencia]` obligatoria en `verification/libros/` (libro, edición, sección y `datos`): con `datos = "libro"` exige página y número de ejemplo; con `datos = "propios"` exige la función de `derivaciones.py` que lo resuelve, y el CI comprueba que exista. Pruebas nuevas en `tests/test_verificacion.py`.
- `verification/README.md`: sección "Ejemplos de libros" con cómo aportar un caso de cada tipo.
- `crates/nervi-core/tests/cargas_termicas.rs`: el clippy de Rust 1.100 del CI marcó `needless_range_loop` en una prueba existente; el bucle ahora recorre las reacciones con un iterador. No cambia lo que se comprueba.

## Cómo se verificó

- `pytest`: 119 pruebas en verde y 1 omitida (la de la GUI, por falta de `libEGL` en este entorno). Las 5 nuevas coinciden con la solución exacta: la cercha con la tolerancia por defecto (1e-9) y los pórticos con 1e-6 (diferencia real de ~5e-8, ver decisiones).
- `cargo fmt --check` y `cargo test -p nervi-core` en verde (no se tocó Rust). `ruff check` y `ruff format --check` en verde, también sobre `derivaciones.py`.

## Decisiones tomadas

- **Datos propios y no transcriptos.** En este entorno no hay ejemplares de los libros, y citar página y número de ejemplo de memoria podía dar referencias falsas. Por eso los cinco casos usan datos propios, se resuelven con el método del capítulo citado y dejan la derivación a la vista. La distinción queda explícita en `datos = "propios"`; los ejemplos transcriptos del libro van con `datos = "libro"` y su página.
- **Rigidez axial en los pórticos.** La pendiente-deflexión supone barras axialmente rígidas. Probando áreas: con `A = 1e2` la diferencia es ~5e-6 (acortamiento de las barras), con `A = 1e4` es ~5e-8 y con `A = 1e6` vuelve a subir a ~5e-6 por redondeo. Se usa `A = 1e4` y tolerancia 1e-6. El caso existente `porticos/portico-carga-lateral.toml` usa `A = 1e6`; pasa, pero cerca del límite de redondeo.

## Pendiente y problemas conocidos

- El issue #6 queda abierto: faltan ejemplos transcriptos de libros con `datos = "libro"` (página y número de ejemplo), cotejados con un ejemplar. Es un buen primer aporte para estudiantes.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-13 a las 19:04 UTC ("Apruebo firmar los PR"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Para sumar un ejemplo de libro, leé `verification/README.md` §Ejemplos de libros y copiá el caso más parecido de `verification/libros/`.
- Lo que queda de la Fase 1 es el material didáctico (#10); los cuadernos pueden reutilizar estos cinco casos.
