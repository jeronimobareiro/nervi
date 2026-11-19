# 2026-11-19-01 · Diafragma rígido por piso y brazos rígidos en el pórtico espacial

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-i7olr2`
- **Fase de la hoja de ruta:** Fase 2a, pórtico espacial · issues [#13](https://github.com/jeronimobareiro/nervi/issues/13) (brazos rígidos) y [#14](https://github.com/jeronimobareiro/nervi/issues/14) (diafragma rígido)

## Qué se pidió

Poder modelar edificios reales con el pórtico espacial: diafragma rígido por piso (restricción maestro-esclavo) y brazos rígidos en los extremos de las barras, aprovechando el análisis modal y espectral del aporte anterior (la masa del piso tiene que quedar en el nudo maestro), con verificación contra soluciones cerradas o de libro. Antes de empezar se confirmó que #13 y #14 estaban abiertos y sin PR en curso.

## Qué se hizo

- **Brazos rígidos** (`crates/nervi-core/src/espacial/elemento.rs` y `modelo.rs`): `Barra3d.brazo_i` y `brazo_j` (vectores globales del nudo a la cara, `Barra3d::con_brazos`). La parte flexible va entre las caras: de ella salen `L`, los ejes locales, las cargas en el tramo, los diagramas y la masa lineal. Transformación de cuerpo rígido `u_cara = u_nudo + θ × r` (`a_caras`), su traspuesta para las fuerzas (`a_nudos`) y `Bᵀ k B` para la rigidez y la masa (`matriz_a_nudos`); `BarraAnalisis3d` guarda los brazos y su `k_global` ya está referida a los nudos. Fuerzas de extremo y diagramas en las caras; reacciones en los nudos. Los brazos pueden ser excéntricos (ejes que no se cruzan).
- **Diafragma rígido** (`espacial/restricciones.rs`, nuevo): `Modelo3d.diafragmas` y `agregar_diafragma(nudos, maestro)`, que sin maestro crea un nudo en el centroide con `uz, rx, ry` restringidos. Restricción por transformación `u = T û` (sin penalización): `ux = ux_m - dy rz_m`, `uy = uy_m + dx rz_m`, `rz = rz_m`; rigidez, masa y cargas con `Tᵀ K T`, `Tᵀ M T` y `Tᵀ F`. Validación: cada nudo en un solo diafragma y `ux, uy, rz` restringidos solo en el maestro.
- `espacial/analisis.rs`: el ensamble pasa por `rigidez_reducida` (barras y resortes llevados a los GDL independientes) y `recuperar_caso` reconstruye los esclavos y suma en el maestro las reacciones del piso. Sin diafragmas ni brazos los resultados son los de antes (las pruebas anteriores siguen iguales).
- `espacial/dinamica.rs`: modal con la rigidez y la masa reducidas; la masa horizontal del piso queda concentrada en el maestro con su inercia de rotación. `ResultadosModal3d.diafragmas` (`MasaDiafragma`) da masa, **centro de masa** e inercia de cada piso. La masa desde los casos de una barra con brazos se reparte según dónde cae la resultante.
- Python: `Modelo3D.agregar_barra(..., brazo_i=, brazo_j=)` (un número es el largo sobre el eje de la barra; un vector, el brazo global), `Modelo3D.diafragma(nudos, maestro=None)` y `Modelo3D.diafragmas`; `Resultados3D.derivas(caso)` y `ResultadoEspectro3D.derivas()` (derivas de piso en los maestros; en el espectro se combinan las derivas de cada modo); `ResultadosModal3D.diafragmas`; función `nervi.modelo3d.derivas_de_piso`.
- Puente PyO3: contrato 3D **versión 2** (arreglos opcionales `brazos`, `diafragmas`, `maestros`) y contrato de dinámica **versión 2** (salida `diafragmas`; `inercias` en los GDL independientes). Un modelo sin brazos ni diafragmas da lo mismo que en la versión 1.
- `examples/edificio_diafragma_3d.py`: el edificio de tres pisos del ejemplo modal con diafragma por piso y vigas con brazos de media columna; masa y centro de masa por piso, tabla modal, derivas del sismo en X e Y y momento de una viga a la cara.
- Documentación: `convenciones.md` (§Brazos rígidos, §Diafragma rígido y masas con diafragma), `contrato-datos.md` (versiones 2), glosario (brazo rígido, cara de la unión, diafragma rígido, nudo maestro/esclavo, piso, centro de masa y de rigidez, deriva de piso, en los cuatro idiomas), README en los cuatro idiomas y portada del sitio en los cuatro idiomas.

## Cómo se verificó

- `crates/nervi-core/tests/diafragma_brazos.rs` (9 casos):
  - Voladizo con brazo rígido en el empotramiento: flecha `P Lf³/(3EI)`, giro, momento `P Lf` en la cara y `P L` en el nudo (1e-12).
  - Barra oblicua con brazos excéntricos en los dos extremos, articulada en `j`, con carga uniforme local y puntual global, contra el mismo pórtico con la barra partida en tres y los brazos 10⁶ veces más rígidos (criterio del issue #13): desplazamientos, reacciones, fuerzas de extremo y esfuerzos en el tramo (1e-5).
  - Equilibrio global (fuerzas y momentos de cargas y reacciones) y equilibrio de la unión con brazos (1e-10).
  - Piso de 2 × 1 vanos con seis columnas distintas y carga excéntrica: diafragma contra la losa modelada con bielas diagonales y vigas 10⁶ veces más rígidas en su plano (criterio del issue #14), en desplazamientos, reacciones y fuerzas de las columnas (1e-5); relación cinemática maestro-esclavo exacta.
  - Torsión en planta con excentricidad conocida: cuatro columnas en voladizo de rigideces distintas unidas solo por el diafragma; centro de rigidez, traslación `F/Σk`, giro `T/Kθ` y cortante de cada columna contra la solución cerrada (1e-9).
  - Modos del piso con la masa en los nudos esclavos: `ω² = Σk/M` en X e Y y `Kθ/J` en torsión con `J = Σ m r²`, masa e inercia del diafragma, inercias en el maestro, Lanczos igual al denso y cortante basal `M Sa` con espectro constante.
  - Centro de masa e inercia respecto de él con masas desiguales; suma de masas efectivas igual a la masa total.
  - Masa de una barra con brazos (concentrada y consistente) igual a `m Lf`; errores (brazos que se tocan, esclavo con `ux` restringido, nudo en dos diafragmas).
- `tests/test_diafragma_brazos.py` (6 pruebas): brazo como número o vector, voladizo cerrado, viga biempotrada con brazos y trapezoidal hasta la cara (`q Lf²/12` en la cara y más el brazo en el nudo), maestro en el centroide, derivas estáticas de dos pisos, derivas espectrales como combinación de las de cada modo, masa y centro de masa por piso, modos del piso y errores.
- `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test -p nervi-core` (91 pruebas), `pytest` (299), `ruff check`, `ruff format --check` y `verificar_bitacora.py`, en verde. El ejemplo `edificio_diafragma_3d.py` corre (9 modos con 100 % de masa en X e Y, sin modos locales de vigas).

## Decisiones tomadas

- **Transformación y no penalización**, como pide #14: los GDL esclavos desaparecen del sistema y no hay rigideces artificiales que empeoren el condicionamiento. Se implementó de forma general (`u = T û`), así que más adelante sirve para otras restricciones (nudos iguales, cuerpos rígidos).
- **Diafragma horizontal (plano XY)** solamente, que es el caso de las losas de edificio; los nudos no necesitan estar a la misma altura. Diafragmas inclinados quedan para cuando hagan falta.
- **Maestro opcional**: si no se da, se crea un nudo en el centroide geométrico. El resultado no depende de dónde esté el maestro (la restricción es de cuerpo rígido); el centro de masa se informa aparte porque depende de las masas, que van fuera del modelo estático.
- **Masa al maestro por `Tᵀ M T`** en lugar de sumarla a mano: es exacto, incluye la inercia de rotación `Σ m r²` y funciona igual con masa consistente o desde casos.
- **Brazos como vector global** en el motor (cubre brazos excéntricos) y, en Python, también como largo sobre el eje, que es el caso común (media columna).
- **Todo lo de la barra se refiere a la parte flexible**: cargas, diagramas, masa lineal y fuerzas de extremo, para que el diseño use los esfuerzos a la cara. Las cargas sobre los brazos se dan como nodales.
- Contratos 3D y de dinámica a la **versión 2** con los arreglos nuevos opcionales, en lugar de una función aparte.

## Pendiente y problemas conocidos

- Excentricidad accidental (desplazar el centro de masa ±5 % y su torsión) y fuerzas estáticas equivalentes por piso: dependen de la norma (#20).
- Las derivas se miden en el maestro de cada piso; falta la deriva máxima en las esquinas (importante con torsión) y los límites de la norma.
- Diafragmas semirrígidos o inclinados; cargas aplicadas sobre los brazos (hoy se dan como nodales); `.nrv`, interfaz y visor 3D para diafragmas y brazos; brazos en el pórtico plano (#13 pedía también 2D: el plano se puede modelar en 3D).
- Verificación contra un ejemplo 3D publicado con diafragma (#15).
- Firma DCO: el usuario autorizó por escrito, el 2026-11-19 a las 11:44 UTC (opción «Sí, firmalo en mi nombre» a la pregunta «¿Firmo los commits de este PR (DCO) en tu nombre, como en el modal?»), que el agente firme los commits de este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Empezar por `crates/nervi-core/src/espacial/restricciones.rs`, `docs/convenciones.md` §Brazos rígidos y §Diafragma rígido y `examples/edificio_diafragma_3d.py`.
- Lo natural después: espectro de la norma elegida (#20) con excentricidad accidental y escalado del cortante basal, verificación contra un edificio 3D publicado (#15) y llevar diafragmas y brazos al `.nrv` y a la interfaz.
