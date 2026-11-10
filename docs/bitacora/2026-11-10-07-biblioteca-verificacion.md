# 2026-11-10-05 · Biblioteca de casos de verificación

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-40bfxu`
- **Fase de la hoja de ruta:** Fase 1, cierre del pórtico plano · issue [#5](https://github.com/jeronimobareiro/nervi/issues/5)

## Qué se pidió

Tercer punto del plan de la semana: la carpeta `verification/` con casos de referencia (modelo, resultado esperado y fuente) que corren en el CI y que se puedan aportar sin saber Rust (issue #5).

## Qué se hizo

- `verification/`: formato de caso en TOML con título, fuente, parámetros, modelo, cargas y valores esperados con tolerancia. Los números pueden ser expresiones con los parámetros (`"-q*L**2/12"`), así el valor esperado queda escrito como la fórmula del libro.
- `tests/test_verificacion.py`: ejecutor `pytest` parametrizado que lee todos los `.toml`, arma el modelo con la API Python, lo resuelve y compara reacciones, desplazamientos y esfuerzos o flechas en una sección (o su máximo y mínimo en la barra). Las expresiones se evalúan recorriendo el árbol sintáctico con una lista cerrada de operaciones y funciones, sin `eval`.
- 11 casos migrados de `crates/nervi-core/tests/`: voladizo con puntual y con uniforme, biapoyada y biempotrada con uniforme, biempotrada con puntual excéntrica (incluido el salto de cortante), continua de dos tramos, biempotrada y biapoyada con triangular, asentamiento, pórtico con carga lateral y cercha triangular; además un caso nuevo de cargas térmicas (empotrada y apoyada con gradiente).
- `verification/README.md`: cómo agregar un caso y referencia completa del formato.
- CI y `pyproject.toml`: `tomli` en Python 3.10 (desde 3.11 viene `tomllib`).
- `CONTRIBUTING.md` apunta a `verification/` para aportar casos; `docs/especificacion-tecnica.md` dice TOML en lugar de JSON.

## Cómo se verificó

- `pytest`: los 11 casos en verde, más una prueba que altera los valores esperados de tres casos y comprueba que fallan (lo que pide el issue) y otra de las expresiones (incluido el rechazo de `__import__`, atributos y nombres desconocidos).
- El primer intento del pórtico con carga lateral falló por el signo de la reacción de momento: el ejecutor lo detectó y mostró calculado y esperado. Se corrigió el signo del archivo (en la prueba de Rust se comparaba el valor absoluto).
- `ruff` y el resto de las pruebas en verde.

## Decisiones tomadas

- **TOML en lugar de JSON**: admite comentarios y se lee mejor para quien escribe un caso a mano; Python lo lee sin dependencias desde 3.11. La especificación decía JSON y se actualizó.
- **Un formato propio y no `.nrv`**: el `.nrv` (PR #35) es un ZIP pensado para la GUI; un caso de verificación tiene que ser un texto chico que se lea en el diff del PR. Si conviene, más adelante un caso puede apuntar a un `.nrv`.
- Las secciones se comparan en estaciones del diagrama (no se interpola), para no introducir error; si `x` no es estación, el ejecutor lo dice.
- Los casos de Rust se mantienen: prueban el motor sin pasar por Python y son más rápidos de depurar.

## Pendiente y problemas conocidos

- Issue #6 (ejemplos resueltos de libros): ya se puede hacer sobre este formato.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-10 a las 13:30 UTC ("firmalo todo por mi, te autorizo"), que el agente firme en su nombre los aportes de este plan de trabajo, como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Siguiente en el plan: combinaciones de carga y envolventes (#21).
