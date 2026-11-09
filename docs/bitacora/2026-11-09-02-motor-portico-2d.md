# 2026-11-09-02 · Fase 0 y Fase 1: motor de pórtico plano

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `fase-1-portico-2d`, PR #1, commit `818cd3f`
- **Fase de la hoja de ruta:** 0 (repositorio) y 1 (pórtico plano)

## Qué se pidió

El MVP de la especificación: resolver un pórtico plano lineal elástico desde Python, verificado contra soluciones analíticas.

## Qué se hizo

- `crates/apex-core` (Rust puro): barra Euler-Bernoulli 2D (`elemento.rs`); cargas nodales, uniformes y puntuales en ejes locales o globales; liberaciones por condensación estática; apoyos por partición de GDL; resortes; asentamientos por caso; Cholesky disperso con `faer`; reacciones; diagramas N/V/M y deformada (`analisis.rs`); validación (`modelo.rs`) y errores (`error.rs`).
- `crates/apex-py`: puente PyO3 0.30, contrato de datos v1 con validación de formas, cálculo con el GIL liberado.
- `python/apex`: `Modelo`, `Resultados`, `combinar()`.
- CI de GitHub Actions, licencia GPL-3.0, `docs/convenciones.md`, `docs/contrato-datos.md`, `examples/portico_simple.py`.

## Cómo se verificó

- 6 pruebas unitarias del elemento y 19 casos analíticos en `crates/apex-core/tests/verificacion.rs` (tolerancia relativa 1e-9).
- 10 pruebas de la API Python en `tests/test_portico.py`.
- Pórtico de 8 100 barras en unos 45 ms (release).
- clippy, rustfmt y ruff sin avisos.

## Decisiones tomadas

- `faer` en vez de `nalgebra-sparse`, porque tiene Cholesky disperso con reordenamiento.
- Sin penalización: partición de GDL libres y restringidos, que da reacciones exactas.
- Los GDL sin rigidez y sin carga (giros de nudos de cercha) se fijan solos y se informan en `gdl_sin_rigidez`.
- Mecanismo: error si Cholesky falla, o si `max|u|·max(K_ii)/max|F| > 1e12` (heurística).
- Cargas distribuidas en ejes globales: por unidad de longitud de barra, no proyectada.
- Licencia GPL-3.0, la del documento original; el usuario todavía puede cambiarla.

## Pendiente y problemas conocidos

- La cuenta de GitHub del usuario fue suspendida el 2026-11-09 (motivo desconocido; apelación en curso). El PR #1 no se pudo terminar de verificar en CI: el trabajo de Python 3.10 falló al descargar Python (error 504 de GitHub, no del código) y no se pudo volver a correr.
- Fase 1 incompleta: cargas trapezoidales y parciales, momentos puntuales en el tramo, cargas térmicas.
- La detección de mecanismos es heurística; no indica qué nudo es el inestable.
- `Resultados.combinar()` interpola los diagramas si los casos tienen estaciones distintas (aproximado cerca de los saltos).

## Para quien siga

Siguiente paso natural: completar la Fase 1 (cargas trapezoidales, momentos en el tramo, cargas térmicas) o empezar la Fase 2 (barra 3D 12×12). Leé primero `docs/convenciones.md` y `crates/apex-core/src/analisis.rs`.
