# Instrucciones para agentes de IA

Este archivo es para cualquier IA que trabaje en Apex BIM (Claude, Gemini, ChatGPT/Codex, Copilot u otra). **Leelo completo antes de tocar el código.**

## 1. Antes de empezar

1. Leé [`docs/ESTADO.md`](docs/ESTADO.md): dónde quedó el proyecto, qué está en curso y qué sigue.
2. Leé las **últimas 3 entradas** de [`docs/bitacora/`](docs/bitacora/) (orden cronológico por nombre de archivo).
3. Si tu tarea toca el motor o la API, leé [`docs/convenciones.md`](docs/convenciones.md) y [`docs/contrato-datos.md`](docs/contrato-datos.md).
4. La hoja de ruta y las fases están en [`docs/especificacion-tecnica.md`](docs/especificacion-tecnica.md).

## 2. Mientras trabajás

- No afirmes que algo "está implementado" si no hay código y pruebas que lo demuestren.
- Toda fórmula nueva lleva su **fuente** (norma con artículo, libro o fórmula cerrada) en un comentario y una **prueba de verificación** en `crates/apex-core/tests/` o `tests/`.
- Antes de terminar, corré y dejá en verde:
  ```
  cargo fmt --all -- --check
  cargo clippy --workspace --all-targets -- -D warnings
  cargo test -p apex-core
  maturin develop --release && pytest
  ruff check python tests examples && ruff format --check python tests examples
  ```
- No cambies la convención de signos ni el contrato de datos sin subir `VERSION_CONTRATO` y documentarlo.
- Idioma del proyecto: español (código, comentarios, documentación).

## 3. Al terminar un aporte (obligatorio)

1. **Creá una entrada nueva** en `docs/bitacora/` copiando [`_plantilla.md`](docs/bitacora/_plantilla.md).
   - Nombre: `AAAA-MM-DD-NN-tema-corto.md`, donde `NN` es el número de aporte del día (`01`, `02`, …). Ejemplo: `2026-11-09-02-motor-portico-2d.md`.
   - Una entrada por aporte. **No edites entradas anteriores**: si algo cambió, lo decís en la nueva.
2. **Actualizá [`docs/ESTADO.md`](docs/ESTADO.md)**: es la foto actual, se reescribe; la bitácora es la historia, solo se agrega.
3. Incluí ambos archivos en el mismo commit o PR que el código.

## 4. Lo que no se hace

- No borrar ni desactivar pruebas para que algo pase.
- No subir credenciales, datos de clientes ni modelos de proyectos reales.
- No copiar código de programas comerciales ni de proyectos con licencias incompatibles con GPL-3.0.
- Un módulo de diseño según norma no se da por terminado sin revisión de un ingeniero estructural (anotalo como pendiente en la bitácora).
