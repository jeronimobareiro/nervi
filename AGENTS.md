# Instrucciones para agentes de IA

Este archivo es para cualquier IA que trabaje en Nervi (Claude, Gemini, ChatGPT/Codex, Copilot u otra). **Leelo completo antes de tocar el código.**

## 1. Antes de empezar

1. Leé [`docs/ESTADO.md`](docs/ESTADO.md): dónde quedó el proyecto, qué está en curso y qué sigue.
2. Leé las **últimas 3 entradas** de [`docs/bitacora/`](docs/bitacora/) (orden cronológico por nombre de archivo).
3. Si tu tarea toca el motor o la API, leé [`docs/convenciones.md`](docs/convenciones.md) y [`docs/contrato-datos.md`](docs/contrato-datos.md).
4. Las fases están en [`docs/especificacion-tecnica.md`](docs/especificacion-tecnica.md) §7 y el plan con hitos e issues en [`docs/hoja-de-ruta.md`](docs/hoja-de-ruta.md). Si tu tarea corresponde a un issue, citalo en el PR y en la bitácora.

## 2. Mientras trabajás

- No afirmes que algo "está implementado" si no hay código y pruebas que lo demuestren.
- Toda fórmula nueva lleva su **fuente** (norma con artículo, libro o fórmula cerrada) en un comentario y una **prueba de verificación** en `crates/nervi-core/tests/` o `tests/`.
- Antes de terminar, corré y dejá en verde:
  ```
  cargo fmt --all -- --check
  cargo clippy --workspace --all-targets -- -D warnings
  cargo test -p nervi-core
  maturin develop --release && pytest
  ruff check python tests examples scripts && ruff format --check python tests examples scripts
  python scripts/verificar_bitacora.py origin/main
  ```
- No cambies la convención de signos ni el contrato de datos sin subir `VERSION_CONTRATO` y documentarlo.
- Idioma del proyecto: español (código, comentarios, documentación).
- Todo archivo nuevo de código empieza con `// SPDX-License-Identifier: GPL-3.0-or-later` (Rust) o `# SPDX-License-Identifier: GPL-3.0-or-later` (Python).
- Si tu aporte cambia lo que un usuario puede hacer (funciones, instalación, interfaz), actualizá también las páginas públicas de [`sitio/`](sitio/) (portada, descargar, primeros pasos). El sitio es para el público: no publiques ahí pendientes internos ni notas de trabajo.
- Las reglas para personas están en [`CONTRIBUTING.md`](CONTRIBUTING.md) y también valen para vos.

## 3. Al terminar un aporte (obligatorio)

1. **Creá una entrada nueva** en `docs/bitacora/` copiando [`_plantilla.md`](docs/bitacora/_plantilla.md).
   - Nombre: `AAAA-MM-DD-NN-tema-corto.md`, donde `NN` es el número de aporte del día (`01`, `02`, …). Ejemplo: `2026-11-09-02-motor-portico-2d.md`.
   - Una entrada por aporte. **No edites entradas anteriores**: si algo cambió, lo decís en la nueva.
2. **Actualizá [`docs/ESTADO.md`](docs/ESTADO.md)**: es la foto actual, se reescribe; la bitácora es la historia, solo se agrega.
3. Incluí ambos archivos en el mismo commit o PR que el código.
4. **Certificado de origen (DCO).** El CI exige `Signed-off-by` en cada commit. La firma es una declaración de una persona, no de la IA. Por defecto, la persona que pidió el trabajo revisa los commits y los firma con `git rebase --signoff origin/main`; avisale en tu respuesta. **Excepción:** podés agregar la firma de esa persona solo si ella te lo autoriza explícitamente y por escrito para ese trabajo. En ese caso usá exactamente el nombre y correo que indique (o su correo `noreply` de GitHub) y anotá la autorización en la entrada de la bitácora. Nunca firmes en nombre de otra persona ni sin autorización.

El control **"Bitácora de aportes"** del CI (`scripts/verificar_bitacora.py`) deja el PR en rojo si cambia código sin agregar una entrada nueva y sin actualizar `docs/ESTADO.md`, si se edita o borra una entrada existente, si el nombre no sigue el formato o si a la entrada le faltan secciones de la plantilla.

## 4. Lo que no se hace

- No borrar ni desactivar pruebas para que algo pase.
- No subir credenciales, datos de clientes ni modelos de proyectos reales.
- No copiar código de programas comerciales ni de proyectos con licencias incompatibles con GPL-3.0.
- No transcribir textos, tablas ni figuras de normas: implementar el método y citar el artículo. No subir PDFs de normas.
- No leer formatos propietarios por ingeniería inversa ni copiar íconos o capturas de otros programas.
- No agregar dependencias con licencias fuera de la lista de [`deny.toml`](deny.toml).
- Un módulo de diseño según norma no se da por terminado sin revisión de un ingeniero estructural (anotalo como pendiente en la bitácora).
