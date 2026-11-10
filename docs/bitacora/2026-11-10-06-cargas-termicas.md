# 2026-11-10-06 · Cargas térmicas en barras

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-40bfxu`
- **Fase de la hoja de ruta:** Fase 1, cierre del pórtico plano · issue [#4](https://github.com/jeronimobareiro/nervi/issues/4)

## Qué se pidió

Segundo punto del plan de la semana: acciones térmicas por barra y por caso, con variación uniforme `ΔT` y gradiente entre caras (issue #4). El número 03 del día queda para la entrada de la interfaz de escritorio (PR #35), que tenía repetido el 01.

## Qué se hizo

- `nervi-core`: nuevo `TipoCargaBarra::Termica { alfa, dt, gradiente, h }` y `CargaLocal::Termica { eps0, kappa0 }`, con `ε₀ = α·ΔT` y `κ₀ = α·ΔT_g/h`, `ΔT_g = T(cara -y) - T(cara +y)`. Se valida `h > 0` cuando hay gradiente.
- `elemento.rs`: cargas equivalentes `[-EAε₀, 0, -EIκ₀, EAε₀, 0, EIκ₀]`; sin fuerzas en el tramo y flecha biempotrada nula (la deformación térmica queda impedida por completo). `cargas_equivalentes` ahora recibe `EA` y `EI`.
- Contrato: tipo 3 en `cargas_barra` (`a` = α, `vx` = ΔT, `vy` = ΔT_g, `b` = h). No cambia la forma de ningún arreglo, así que `VERSION_CONTRATO` sigue en 2 (documentado en el historial).
- Python: `Modelo.carga_termica(caso, barra, alfa, dt=0, gradiente=0, h=None)`.
- `docs/convenciones.md`, `docs/contrato-datos.md`, `docs/especificacion-tecnica.md`.
- Formato `.nrv` y GUI (integrados en `main` con el PR #35): tipo `termica` en el esquema 1 (`alfa`, `dt`, `gradiente`, `h`), en `nervi.formato` (lectura, escritura y validación: `alfa` obligatoria, `h > 0` si hay gradiente) y en la tabla de cargas en barras de la GUI (columnas `a / α`, `b / h`, `ΔT`, `ΔTg`). Se completó también `docs/esquemas/nrv-modelo-v1.schema.json`, que todavía no tenía el tipo `trapezoidal`.

## Cómo se verificó

- `crates/nervi-core/tests/cargas_termicas.rs`, 7 casos con error relativo < 1e-9:
  - barra biempotrada con `ΔT`: `N = -EAαΔT`, desplazamientos nulos;
  - viga isostática con `ΔT` y gradiente: sin esfuerzos ni reacciones, alargamiento `αΔT·L`, giros `∓κ₀L/2` y flecha `-αΔT_g·L²/8h`;
  - viga biempotrada con gradiente: momento constante `-EIαΔT_g/h`;
  - empotrada y apoyada con gradiente (método de las fuerzas): `R = 3EIκ₀/2L`, `M(0) = -3EIκ₀/2`;
  - barra biarticulada entre apoyos fijos: el gradiente no genera momento y el `ΔT` sí genera axil;
  - pórtico biempotrado con el dintel calentado: equilibrio, simetría y compatibilidad del dintel;
  - rechazo de gradiente sin canto.
- `tests/test_cargas_termicas.py`: 4 pruebas en Python, incluida una combinación con carga gravitatoria. `tests/test_formato.py`: ida y vuelta de una carga térmica por un `.nrv` y rechazo de térmicas inválidas. `tests/test_gui.py`: edición de una carga térmica en la tabla.
- Fuentes: Ghali, Neville y Brown, *Structural Analysis*, 6.ª ed., §4.6 y §6.4; Weaver y Gere, *Matrix Analysis of Framed Structures*, 3.ª ed., §3.5; Przemieniecki, *Theory of Matrix Structural Analysis*, §5.6.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test -p nervi-core`, `maturin develop --release && pytest` (71, con la GUI), `ruff`: en verde.

## Decisiones tomadas

- **`α` en la carga y no en la barra.** El issue pedía proponerlo: ponerlo en la carga no toca `props` ni el contrato de las barras y permite casos con materiales distintos sin agregar columnas. Cuando lleguen los materiales con nombre (formato `.nrv`, Fase 2), la API puede tomar `α` del material por defecto.
- El gradiente se da como diferencia de temperatura entre caras más el canto `h`, que es como lo dan las normas y los libros, en lugar de pedir la curvatura directamente.
- `N, V, M` informan solo los esfuerzos mecánicos (los que dimensionan); la deformada sí incluye la parte térmica.

## Pendiente y problemas conocidos

- Firma DCO: el usuario autorizó por escrito, el 2026-11-10 a las 13:30 UTC ("firmalo todo por mi, te autorizo"), que el agente firme en su nombre los aportes de este plan de trabajo, como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Siguiente en el plan: biblioteca `verification/` en el CI (#5). Los casos de `cargas_trapezoidales.rs` y `cargas_termicas.rs` pueden migrarse ahí.
