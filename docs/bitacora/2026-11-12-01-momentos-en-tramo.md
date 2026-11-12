# 2026-11-12-01 · Momentos concentrados en el tramo de una barra

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-tc5x1h`
- **Fase de la hoja de ruta:** Fase 1, cierre del pórtico plano · issue [#3](https://github.com/jeronimobareiro/nervi/issues/3)

## Qué se pidió

Programar lo siguiente después del plan de la semana. Se eligió el issue #3, momentos concentrados en el tramo, porque es el último tipo de carga de la Fase 1 y conviene que entre al esquema 1 del formato `.nrv` antes de congelarlo con la etiqueta `v0.1.0`.

## Qué se hizo

- **Motor** (`elemento.rs`, `modelo.rs`, `analisis.rs`): nuevo `TipoCargaBarra::Momento { a, mz }` y `CargaLocal::Momento`. Cargas equivalentes `mz·dN/dx(a)` con las funciones de Hermite (coinciden con las fórmulas cerradas de la viga biempotrada), flecha en el tramo por Macaulay, salto de `-mz` en el diagrama de momentos con dos estaciones en `a`, y validación `0 ≤ a ≤ L`. El momento no rota con los ejes.
- **Contrato de datos**: tipo 4 en `cargas_barra` (`a`, `vx` = `Mz`), ampliación compatible sin subir `VERSION_CONTRATO` (misma forma de los arreglos, como el tipo 3).
- **Python**: `Modelo.carga_momento(caso, barra, a, mz)`.
- **Formato `.nrv`**: tipo `momento` con `a` (obligatoria) y `mz`, en el esquema JSON, la validación, la lectura y la escritura. Entra al esquema 1 sin migración porque solo agrega un valor de `tipo`.
- **Interfaz**: el tipo `momento` en la tabla de cargas en barras (columna `a` y `qx / … / Mz`) y en el panel de la barra seleccionada. De paso se corrigió el panel con una carga térmica: buscaba la clave `a`, que la térmica no tiene, y fallaba al seleccionar la barra.
- **Biblioteca `verification/`**: tipo `momento` en el ejecutor y caso nuevo `vigas/biempotrada-momento-concentrado.toml`.
- Documentación: `contrato-datos.md`, `convenciones.md`, `formato-nrv.md`, `especificacion-tecnica.md`, `glosario.md` (es/en/pt/ru), `hoja-de-ruta.md`, los cuatro README y la portada del sitio en los cuatro idiomas. El README en español todavía listaba las cargas térmicas como pendientes; ahora lista #6 y #10.

## Cómo se verificó

- `crates/nervi-core/tests/momentos_en_tramo.rs` (6 casos): viga biempotrada con el momento en el centro, en `L/3` y en `0,8 m` contra las fórmulas cerradas (Ghali, Neville y Brown, apéndice D; Roark, tabla 8.1); salto del diagrama igual a `-M0` en una biapoyada; voladizo (flecha y giro en el extremo, flecha en el tramo); barra inclinada comparada punto a punto con el modelo con un nudo en `a` y el momento nodal; momento en `a = 0` y `a = L` igual al nodal; posiciones inválidas. Error relativo menor a 1e-9.
- La prueba de equilibrio global del pórtico de 3 pisos suma ahora un momento en cada columna.
- Python: `tests/test_momentos_en_tramo.py` (4), ida y vuelta y validación en `test_formato.py` (2), tabla y panel en `test_gui.py` (2), y el caso TOML nuevo.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test -p nervi-core` (47), `pytest` (109), `ruff`.

## Decisiones tomadas

- Vector de cargas consistente `mz·N'(a)` en lugar de tabular las fórmulas de empotramiento: es una línea, es exacto para Euler-Bernoulli y sigue el mismo criterio que la trapezoidal.
- En los diagramas el momento aplicado a la izquierda del corte **resta** (`M(a⁺) - M(a⁻) = -Mz`), coherente con el momento de extremo `f3` y con `convenciones.md`.
- `ejes` se ignora: un momento en el plano es el mismo en ejes locales y globales.

## Pendiente y problemas conocidos

- La vista de la interfaz todavía no dibuja las cargas (tampoco las demás).
- Firma DCO: firmado en nombre del usuario con su autorización explícita del 2026-11-12 (12:32 UTC, opción "Sí, firmalos por mí" a "¿Firmo con tu DCO los commits de hoy?"), como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Con esto la Fase 1 tiene todos los tipos de carga de la especificación §3. Lo que falta de la fase es documentación y casos: ejemplos de libros (#6) y material didáctico (#10).
