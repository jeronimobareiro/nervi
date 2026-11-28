# 2026-11-28-02 · Modelo de cálculo generado desde el edificio (motor)

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-pv0njt`
- **Fase de la hoja de ruta:** Fase 7, issue #74 (primera parte: motor y API de Python), sobre el modelo físico (#73) y las cargas por planta (#78)

## Qué se pidió

Jerónimo Bareiro notó que los modos *Edificio* y *Cálculo* de la interfaz parecen dos estructuras distintas y preguntó cómo unificarlos. Se le mostró una propuesta con muestras en los dos temas (un solo modelo: el edificio genera el de cálculo; sin el selector *Edificio | Cálculo*; las etapas al mando de la ventana) y el 28/11/2026 la aprobó con la opción "el edificio manda, el pórtico aparte": si el proyecto tiene edificio, el modelo de cálculo se genera solo; un proyecto sin edificio sigue siendo un pórtico de nudos y barras cargado a mano. Este aporte es la primera parte: la generación del modelo de cálculo.

## Qué se hizo

- `crates/nervi-core/src/idealizacion.rs` (nuevo): idealización del edificio en un pórtico espacial.
  - Nudos en los extremos de columnas y vigas, en los cruces de vigas del mismo nivel y en el centro de cada muro en cada piso que alcanza, unidos con una tolerancia (grilla de celdas).
  - Cada columna, muro y viga se parte en los nudos que caen sobre su eje.
  - Brazos rígidos de las vigas hasta la cara de la columna o del muro: el semiancho de la sección en la dirección de la viga, con columnas giradas y circulares. Si los brazos ocupan toda la luz, el tramo va sin brazos y se avisa.
  - Empotramientos en la base y un diafragma por cada nivel pedido.
  - Muros como columna ancha equivalente; una viga apoyada en todo su largo sobre un muro no es barra y su carga pasa al muro.
  - Cargas lineales por estática exacta: la parte flexible queda como carga trapezoidal, y lo que cae sobre un brazo o sobre una viga apoyada en un muro pasa al nudo con el momento de su excentricidad.
  - Cruces de vigas y partición de vigas en paralelo con rayon.
- `crates/nervi-py/src/idealizacion.rs` (nuevo): `idealizar_edificio`, contrato `VERSION_CONTRATO_IDEALIZACION = 1` (`docs/contrato-datos.md` §Modelo de cálculo generado).
- `python/nervi/idealizacion.py` (nuevo): `generar(mf)` y `ModeloCalculo`.
  - Arma los datos desde el modelo físico (con el reparto de las losas de #78 y el peso propio de las barras), en la unidad de longitud del modelo.
  - Pone secciones, `E` y `G` de cada material (`E` de la norma si el material no lo da) y arma el `Modelo3D` con los casos `D` y `L`.
  - Cada barra guarda de qué elemento físico sale (`OrigenBarra`); `barras_de` y `diagrama` devuelven los resultados a la viga, columna o muro.
  - Las cargas se pasan en bloque y las de los nudos se suman por nudo y caso antes de pasarlas.
- `python/nervi/fisico.py`: `ModeloFisico.modelo_calculo()`.
- `examples/edificio_fisico.py`: genera el modelo de cálculo, lo resuelve y muestra los momentos de la viga V102.
- `scripts/medir_modelo_calculo.py` (nuevo): banco de tiempos.

## Cómo se verificó

- Criterio de salida del issue, `tests/test_idealizacion.py::test_mismo_resultado_que_a_mano`: el edificio de referencia del #73 (3 pisos, 2 × 1 vanos de 6 y 5 m) generado da los mismos desplazamientos y reacciones en cada nudo y las mismas fuerzas de extremo en cada barra que el mismo modelo armado a mano con `Modelo3D` (columnas, vigas con brazos de 0,20 m, diafragmas, empotramientos y las cargas tributarias a 45° calculadas a mano, con lo que cae sobre los brazos pasado al nudo), con una diferencia menor que 1e-9 del valor máximo.
- `tests/test_idealizacion.py` (7 pruebas en total): además, el equilibrio vertical exacto con peso propio y muro (1616,625 kN en D); las vigas sobre el muro; la misma respuesta en cm y en m; la viga partida por una columna intermedia con sus brazos y la simetría de sus momentos; columna girada de dos pisos, cruces y viga apoyada en otra; `E` y peso de los materiales por omisión; y el ejemplo de referencia.
- `crates/nervi-core/tests/idealizacion.rs` (8 casos): pórtico de un vano, brazo de columna girada 30° y circular, partición en cruces, apoyos y pisos, nudos unidos por la tolerancia, estática exacta de las cargas (fuerza y momentos totales contra la integral a mano), viga sobre muro con su carga y la del muro, brazos sin luz y datos inválidos.
- `cargo test -p nervi-core`, `cargo clippy -D warnings`, `cargo fmt --check`, `pytest` completo (538 pasan en este entorno, con pytest-qt), `ruff check` y `ruff format --check`: en verde.
- Rendimiento (`scripts/medir_modelo_calculo.py`, 20 pisos de 10 × 10 vanos: 2420 columnas, 4400 vigas y 2000 losas, que dan 2541 nudos y 6820 barras): 0,14 s en total, de los que 18 ms son la idealización en Rust y 20 ms el reparto de las losas; el resto es armar el `Modelo3D`. Una primera versión que pasaba las cargas una por una tardaba 0,48 s. No hay versión anterior con la que comparar resultados: es código nuevo. `scripts/medir_diseno.py` no cambia, porque el diseño no se tocó.

## Decisiones tomadas

- La geometría, la partición y el paso de las cargas van en Rust, como pide la regla de rendimiento; Python arma los datos, las secciones y el `Modelo3D`.
- El modelo de cálculo no se guarda en el `.nrv`: se genera cuando se pide, como el reparto, para que nunca quede desactualizado. Por eso no cambia el formato.
- Las vigas van en el nivel del piso (sin la excentricidad de medio canto) y las columnas sin brazos, como el ejemplo armado a mano `examples/edificio_diafragma_3d.py`.
- Los muros son una columna ancha equivalente hasta que haya láminas (Fase 6). Una viga apoyada en todo su largo sobre un muro no se modela como barra (quedaría sin luz flexible): su carga pasa al muro con estática exacta y se avisa.
- Un diafragma por cada piso que tiene losas, con todos los nudos de su nivel.
- Casos `D` (peso propio de losas y barras más permanente) y `L` (sobrecarga), los que ya usan las combinaciones de la interfaz.
- `E` por omisión: 4700 √f'c en hormigón (ACI 318-19 §19.2.2.1(b)) y 200 000 MPa en acero; ν = 0,2 y 0,3. Peso del acero 78,5 kN/m³ (EN 1991-1-1, Tabla A.4).
- En la sección de las columnas, `h` va sobre el eje `y` local girado con la columna, para que el ancho y el alto coincidan con la planta.
- **Firma DCO:** Jerónimo Bareiro autorizó por escrito, en el hilo del proyecto el 28/11/2026 a las 13:02 UTC ("firmalo por mi"), firmar este trabajo a su nombre. Se usó su correo `noreply` de GitHub, `Jerónimo Bareiro <345933350+bareirojero@users.noreply.github.com>` (AGENTS.md §3.5).

## Documentación actualizada

- `README.md` y sus traducciones (`README.en.md`, `README.pt.md`, `README.ru.md`): el modelo físico ya genera el modelo de cálculo desde Python.
- `docs/ESTADO.md`: nueva línea del modelo de cálculo generado, conteos de pruebas y próximos pasos.
- `docs/hoja-de-ruta.md`: #74 en curso.
- `docs/contrato-datos.md`: contrato nuevo §Modelo de cálculo generado.
- `docs/convenciones.md`: §Modelo de cálculo generado desde el edificio.
- `docs/glosario.md`: idealización, `ModeloCalculo` y columna ancha equivalente.
- `AGENTS.md` y `CONTRIBUTING.md`: el banco de tiempos nuevo.
- El sitio público no se tocó: la interfaz todavía no usa el modelo generado.

## Pendiente y problemas conocidos

- La interfaz: quitar el selector *Edificio | Cálculo*, el conmutador *Mostrar: Edificio · Cálculo · Ambos*, las etapas al mando de la ventana, calcular el edificio en 3D y mostrar los resultados por elemento (muestras aprobadas en `nervi/gui/modelo-unico/` de los archivos del proyecto). Coordinar con el visor único (hilo "Unificar el visor 2D y 3D") y la barra de título propia.
- Ajustes del modelo generado (apoyos articulados, liberaciones), que se guardarán aparte del modelo físico.
- Losas y muros como láminas (Fase 6); mientras tanto, la columna ancha equivalente no toma bien un muro largo con vigas que llegan fuera de su centro.
- Vigas que cruzan un muro fuera de su centro no se conectan con él.
- Falta comparar contra un edificio publicado (#15).

## Para quien siga

- Empezá por `python/nervi/idealizacion.py` y la documentación de `crates/nervi-core/src/idealizacion.rs`. El criterio de salida está en `tests/test_idealizacion.py`.
- Para la interfaz, mirá las muestras aprobadas y la propuesta en el hilo del proyecto: el edificio manda; si un proyecto no tiene edificio, se sigue trabajando con el pórtico plano de siempre.
