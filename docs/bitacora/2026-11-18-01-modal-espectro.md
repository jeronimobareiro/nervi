# 2026-11-18-01 · Masas, análisis modal y espectro de respuesta del pórtico espacial

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-k5h479`
- **Fase de la hoja de ruta:** Fase 2b, dinámica y sismo · issues [#16](https://github.com/jeronimobareiro/nervi/issues/16) (masas), [#17](https://github.com/jeronimobareiro/nervi/issues/17) (modal) y [#18](https://github.com/jeronimobareiro/nervi/issues/18) (espectro)

## Qué se pidió

Empezar la Fase 2b sobre el pórtico espacial que ya funciona: masas (nodales y a partir del peso propio y las cargas), análisis modal (periodos, modos y masa participante) y análisis por espectro de respuesta con combinación SRSS y CQC, con casos de verificación contra soluciones cerradas. P-Δ queda para un paso posterior. Antes de empezar se confirmó que #16, #17 y #18 estaban abiertos y sin PR en curso.

## Qué se hizo

- `crates/nervi-core/src/espacial/dinamica.rs` (nuevo):
  - `Masas3d`: masas nodales `[mx, my, mz, Jx, Jy, Jz]`, masa por unidad de longitud de las barras y masa desde las cargas verticales de los casos (`m = -Fz · factor / g`, cargas en barras repartidas por estática). `TipoMasa::Concentrada` (`m L/2` traslacional, sin inercia rotacional) o `Consistente` (`masa_consistente_local`, Przemieniecki cap. 11). `ensamblar_masa` da la matriz global dispersa. Las masas van aparte del `Modelo3d`, así que el análisis estático y su contrato no cambian.
  - `analizar_modal_3d`: `K φ = ω² M φ` en los GDL libres, modos normalizados a masa con signo fijo, factores de participación y masas efectivas en X, Y y Z y masa total. Dos métodos con el mismo resultado: **denso exacto** (condensación exacta de los GDL sin masa con la factorización dispersa de `K` y problema simétrico `M½ F M½`) hasta 1500 GDL con masa, y **Lanczos** con transformación espectral (`σ = 0`), reortogonalización completa y bloqueo de modos hallados por encima. El bloqueo hace falta porque el Lanczos de un solo vector encuentra una sola copia de cada frecuencia repetida (pasaba con un edificio simétrico; hay una prueba).
  - `analizar_espectro_3d`: espectro `(T, Sa)` interpolado, dirección de excitación cualquiera, respuesta de cada modo como una estática y combinación SRSS o CQC (`coeficiente_cqc`, Der Kiureghian) de desplazamientos, reacciones, fuerzas de extremo, cortante basal y esfuerzos en cada sección (`seccion`, `diagrama`).
- `espacial/analisis.rs`: se separó `recuperar_caso` (fuerzas de extremo y reacciones desde los desplazamientos) y `gdl_barra` para usarlos también en la respuesta modal. Los resultados estáticos no cambian (las pruebas del pórtico espacial siguen en verde).
- Python: `Modelo3D.masa_nodal`, `masa_lineal`, `masa_desde_casos` y `modal(n_modos, masa, metodo)`; módulo nuevo `nervi.dinamica` con `ResultadosModal3D` (periodos, modos, masa participante y acumulada, `tabla()`) y `ResultadoEspectro3D` (con la forma de un caso de carga, más cortante basal, `Sa` y `Γ` por modo y correlaciones). Puente PyO3: `resolver_modal_3d` y `espectro_3d` con su propio contrato (`VERSION_CONTRATO_DINAMICA = 1`), que reciben el modelo como el diccionario de `Modelo3D.arreglos()`.
- `examples/modal_espectro_3d.py`: edificio de tres pisos con masa desde D + 0.25 L y peso propio, tabla modal y respuesta en X e Y con un espectro ilustrativo.
- Documentación: `convenciones.md` §Dinámica, `contrato-datos.md` (contrato de dinámica), glosario (es, en, pt, ru), README en los cuatro idiomas y portada del sitio en los cuatro idiomas.

## Cómo se verificó

- `crates/nervi-core/tests/dinamica_3d.rs` (12 casos):
  - Viga simplemente apoyada con masa consistente: tres primeras frecuencias contra `(nπ/L)² √(EI/m)` (error menor a 0.05 % con 12 elementos), modos verticales, normalización a masa y ortogonalidad `φᵢᵀ M φⱼ = δᵢⱼ`.
  - Voladizo: masa consistente contra `(βₙL)² √(EI/mL⁴)` (0.1 % con 10 elementos, y siempre por encima, como corresponde) y masa concentrada que converge al refinar (0.5 % con 40 elementos).
  - Edificio de cortante de dos pisos con vigas prácticamente rígidas: `ω² = (k/m)(3 ∓ √5)/2`, formas modales con el número de oro, `Γ` y masa efectiva cerrados; con todos los modos, la suma de masas efectivas es la masa total en X, Y y Z.
  - Piso con cuatro columnas: modos de traslación en X, en Y y de torsión contra `Kθ = Σ(kx y² + ky x²) + Σ GJ/h` sobre `m (a² + b²)`.
  - Lanczos contra el método denso en un pórtico de 2 × 2 vanos y 4 pisos con masa consistente (ocho frecuencias, 1e-8) y en una columna de sección cuadrada con frecuencias dobles.
  - Espectro de un grado de libertad: `u = Sa/ω²`, `V = M Sa`, momento en la base `M Sa h` y diagrama, con `Sa` interpolado en un tramo inclinado. Espectro del edificio de dos pisos con SRSS y con CQC contra la combinación cerrada de sus dos modos.
  - Coeficiente CQC calculado a mano (`β = 0.5`, `ζ = 5 %`), simetría, `ρ = 1` con frecuencias iguales y `ρ = 0` sin amortiguamiento.
  - Masa desde cargas nodales, uniformes, puntuales y trapezoidales en ejes locales contra las reacciones de viga simple; masa consistente que suma `m L` en cada dirección y es simétrica; errores (sin masa, masa negativa, mecanismo con los dos métodos, espectro mal definido).
- `tests/test_dinamica_3d.py` (7 pruebas): API, un grado de libertad por dirección y su respuesta espectral, espectro interpolado con dirección oblicua, edificio de dos pisos (denso y Lanczos), CQC frente a SRSS, viga con masa consistente, masa desde casos y errores.
- `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test -p nervi-core`, `pytest`, `ruff check`, `ruff format --check` y `verificar_bitacora.py`, en verde (detalle en el PR).

## Decisiones tomadas

- **Masas fuera del `Modelo3d`** (`Masas3d` y un contrato propio), para no tocar el análisis estático ni el contrato 3D versión 1.
- **Denso exacto más Lanczos** en lugar de solo Lanczos, como pedía #17: el denso sobre los GDL con masa es exacto, sin parámetros de convergencia, y alcanza para edificios de varios cientos de nudos con masa concentrada; Lanczos queda para modelos más grandes y se verifica contra el denso. Implementación propia sobre `faer`; sin dependencias nuevas.
- **Bloqueo de modos en Lanczos** en lugar de Lanczos por bloques: es más simple y resuelve las frecuencias repetidas con una corrida más por multiplicidad. No hay todavía control de Sturm (conteo de autovalores por debajo de un corrimiento).
- **Masa desde casos repartida por estática** y como masa traslacional en las tres direcciones, como se suele hacer con la masa sísmica; las cargas en barras no generan inercia rotacional.
- **Espectro dado por quien diseña**: Nervi no trae espectros normativos hasta decidir la norma (#20). Las magnitudes combinadas son valores absolutos y no se mezclan con los casos estáticos con signo.
- Los diagramas combinados van en estaciones equidistantes, porque la combinación no es lineal entre estaciones. Con masa consistente, la inercia distribuida dentro de la barra no se dibuja en el diagrama (los extremos sí son exactos).

## Pendiente y problemas conocidos

- **Diafragma rígido** (#14): sin él, las vigas con masa propia tienen modos locales verticales que aparecen en la tabla (con masa participante nula) y hay que pedir más modos para llegar al 90 %. Masa y centro de masa de piso, excentricidad accidental y torsión accidental llegan con el diafragma.
- Espectros normativos, factor de reducción `R`, combinación de direcciones (100 %/30 % o SRSS) y escalado del cortante basal al estático: dependen de la norma (#20).
- Combinar la respuesta espectral con las cargas gravitatorias para el diseño (envolventes `D ± E`) y llevar el sismo a `nervi.design`.
- P-Δ (#19), control de Sturm en Lanczos, análisis modal del pórtico plano, interfaz y módulo `.nrv` para la dinámica.
- #16 pide masa consistente también para el pórtico plano: no se hizo (el plano se puede modelar en 3D).
- Comparar con un ejemplo espectral publicado (criterio de salida de la Fase 2b).
- Firma DCO: el usuario autorizó por escrito, el 2026-11-19 a las 11:30 UTC ("Esta ok, firmalo", en respuesta al pedido de firma de este PR), que el agente firme los commits de este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Empezar por el docstring de `crates/nervi-core/src/espacial/dinamica.rs`, `docs/convenciones.md` §Dinámica y `examples/modal_espectro_3d.py`.
- Lo natural después: diafragma rígido por piso con masa de piso (#14), espectro de la norma elegida (#20) y combinación con las cargas gravitatorias para diseñar.
