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
- `verification/libros/merriman-cercha-fink.toml`: el primer ejemplo transcripto de un libro, el art. 5 de Merriman y Jacoby, *A Text-Book on Roofs and Bridges, Part I*, 6.ª ed. (1907), pp. 10-12, de dominio público. Se compara la reacción y los seis esfuerzos que imprime el libro con tolerancia 1e-3, porque el libro redondea a 5 o 10 libras. El texto se leyó en Internet Archive. La figura no se transcribió: la geometría se reconstruyó de los brazos de palanca impresos (14,44, 5,44, 8,87 y 11,4 pies), y coinciden todos.
- `verification/libros/derivaciones.py`: la solución a mano de cada caso, escrita barra por barra (pendiente-deflexión con desplazamiento lateral, equilibrio de nudos y trabajo virtual) y resuelta con aritmética exacta en `sympy`, sin usar el motor. Los valores esperados de los `.toml` son las fracciones exactas que imprime.
- Tabla `[referencia]` obligatoria en `verification/libros/` (libro, edición, sección y `datos`): con `datos = "libro"` exige página y número de ejemplo; con `datos = "propios"` exige la función de `derivaciones.py` que lo resuelve, y el CI comprueba que exista. Pruebas nuevas en `tests/test_verificacion.py`.
- `verification/README.md`: sección "Ejemplos de libros" con cómo aportar un caso de cada tipo.
- `crates/nervi-core/tests/cargas_termicas.rs`: el clippy de Rust 1.100 del CI marcó `needless_range_loop` en una prueba existente; el bucle ahora recorre las reacciones con un iterador. No cambia lo que se comprueba.

## Cómo se verificó

- `pytest`: 121 pruebas en verde y 1 omitida (la de la GUI, por falta de `libEGL` en este entorno). Los 5 casos con datos propios coinciden con la solución exacta: la cercha con la tolerancia por defecto (1e-9) y los pórticos con 1e-6 (diferencia real de ~5e-8, ver decisiones).
- `cargo fmt --check` y `cargo test -p nervi-core` en verde (no se tocó Rust). `ruff check` y `ruff format --check` en verde, también sobre `derivaciones.py`.

## Decisiones tomadas

- **Dominio público para los ejemplos transcriptos.** Después de hablarlo con el usuario, se buscaron fuentes libres: libros de autores fallecidos hace más de 70 años (Paraguay y Rusia: vida + 70) y obras del gobierno de EE. UU. Los libros de Mir no son de dominio público. Desde este entorno no se llega a la web de la FHWA; Internet Archive se leyó a través de la herramienta de lectura web.
- `test_un_valor_alterado_falla` alteraba los valores en un 0,1 %, lo que no alcanza para un caso con tolerancia 1e-3. Ahora altera 10 veces la tolerancia del caso, con un mínimo de 0,1 %.
- **Datos propios y no transcriptos.** En este entorno no hay ejemplares de los libros, y citar página y número de ejemplo de memoria podía dar referencias falsas. Por eso los cinco casos usan datos propios, se resuelven con el método del capítulo citado y dejan la derivación a la vista. La distinción queda explícita en `datos = "propios"`; los ejemplos transcriptos del libro van con `datos = "libro"` y su página.
- **Rigidez axial en los pórticos.** La pendiente-deflexión supone barras axialmente rígidas. Probando áreas: con `A = 1e2` la diferencia es ~5e-6 (acortamiento de las barras), con `A = 1e4` es ~5e-8 y con `A = 1e6` vuelve a subir a ~5e-6 por redondeo. Se usa `A = 1e4` y tolerancia 1e-6. El caso existente `porticos/portico-carga-lateral.toml` usa `A = 1e6`; pasa, pero cerca del límite de redondeo.

## Pendiente y problemas conocidos

- El issue #6 queda abierto para sumar más ejemplos transcriptos, sobre todo de vigas continuas y pórticos hiperestáticos: Merriman es de cerchas isostáticas. Candidatos: Johnson, Bryan y Turneaure, *Modern Framed Structures*, y manuales de la FHWA o del US Army Corps of Engineers.
- Conviene que un ingeniero confirme las fechas de fallecimiento citadas en `derechos` (Merriman 1925, Jacoby 1955).
- Firma DCO: el usuario autorizó por escrito, el 2026-11-13 a las 19:04 UTC ("Apruebo firmar los PR"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Para sumar un ejemplo de libro, leé `verification/README.md` §Ejemplos de libros y copiá el caso más parecido de `verification/libros/`.
- Lo que queda de la Fase 1 es el material didáctico (#10); los cuadernos pueden reutilizar estos cinco casos.
