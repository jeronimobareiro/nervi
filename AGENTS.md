# Instrucciones para agentes de IA

Este archivo es para cualquier IA que trabaje en Nervi (Claude, Gemini, ChatGPT/Codex, Copilot u otra). **Leelo completo antes de tocar el código.**

## 1. Antes de empezar

1. Leé [`docs/ESTADO.md`](docs/ESTADO.md): dónde quedó el proyecto, qué está en curso y qué sigue.
2. Leé las **últimas 3 entradas** de [`docs/bitacora/`](docs/bitacora/) (orden cronológico por nombre de archivo).
3. Si tu tarea toca el motor o la API, leé [`docs/convenciones.md`](docs/convenciones.md) y [`docs/contrato-datos.md`](docs/contrato-datos.md).
   Si toca la interfaz de escritorio, seguí la línea de diseño de [`docs/diseno-interfaz.md`](docs/diseno-interfaz.md).
4. Las fases están en [`docs/especificacion-tecnica.md`](docs/especificacion-tecnica.md) §7 y el plan con hitos e issues en [`docs/hoja-de-ruta.md`](docs/hoja-de-ruta.md). Si tu tarea corresponde a un issue, citalo en el PR y en la bitácora.

## 2. Mientras trabajás

- No afirmes que algo "está implementado" si no hay código y pruebas que lo demuestren.
- **Rendimiento (regla prioritaria).** Todo cálculo que recorra barras, nudos, combinaciones, estaciones o iteraciones numéricas (análisis, combinaciones y envolventes, diseño y verificación según norma, diagramas de interacción, búsqueda de armaduras) va en Rust (`nervi-core`) y se expone a Python por `nervi-py` con la misma API pública. Python queda para la interfaz, la memoria PDF, el formato `.nrv`, la orquestación, los ejemplos y los prototipos. Un prototipo en Python pasa a Rust antes de entrar en la interfaz o en la memoria, o en cuanto el banco de tiempos (`scripts/medir_diseno.py`; para el reparto de las losas, `scripts/medir_reparto.py`) muestre que pesa, con las mismas pruebas de verificación más una comparación cruzada contra la versión anterior. Todo cambio que toque cálculo informa en el PR el tiempo del pórtico de referencia antes y después.
- **Exactitud (regla prioritaria, por encima del rendimiento).** Nunca se bajan tolerancias, iteraciones de convergencia ni exactitud para ganar tiempo. Toda migración u optimización da exactamente los mismos resultados que la versión anterior: la misma armadura y el mismo estado en cada elemento y los mismos números salvo el redondeo de la aritmética de doble precisión. Se comprueba con `python scripts/medir_diseno.py --comparar antes.json` con su tolerancia por defecto (1e-12 relativa) y con una comparación cruzada contra la versión anterior. Si una mejora no puede dar los mismos resultados, no se hace sin que lo decida quien mantiene el proyecto.
- **Interfaz.** Todo control nuevo toma su estilo del sistema de [`python/nervi/gui/estilo.py`](python/nervi/gui/estilo.py) según [`docs/diseno-interfaz.md`](docs/diseno-interfaz.md): tema por defecto "A · Claro preciso" (fondo claro, azul Nervi de acento, botón primario negro) y "B · Nocturno Nervi" como oscuro; deslizadores con tirador rectangular y listas desplegables con esquinas rectas y borde en los cuatro lados; nada de aspecto nativo antiguo ni colores sueltos. Los **íconos** salen del catálogo [`python/nervi/gui/iconos.py`](python/nervi/gui/iconos.py) ([`docs/iconos.md`](docs/iconos.md)): usá el que corresponda (muchos ya están reservados para las fases de la hoja de ruta) y no dibujes íconos sueltos en tu módulo; si falta uno, sumalo al catálogo con su muestra. **Antes de implementar un cambio de diseño, mostrá una muestra visual** (captura o maqueta, en los dos temas) y esperá el acuerdo.
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
- **Formato `.nrv`:** cualquier cambio en lo que se guarda de un módulo (`modelo`, `diseno`…) sube la versión de ese módulo, trae su migración y agrega su archivo de referencia en `tests/datos/nrv/` ([`docs/formato-nrv.md`](docs/formato-nrv.md) §6.3). Lo que agrega una fase nueva va en un módulo propio, no dentro de `modelo.json`.
- Idioma del proyecto: español (código, comentarios, documentación técnica). En issues y PR respondé en el idioma de quien escribe (español, inglés, portugués o ruso). Si agregás un término nuevo al código, sumalo a [`docs/glosario.md`](docs/glosario.md).
- Todo archivo nuevo de código empieza con `// SPDX-License-Identifier: GPL-3.0-or-later` (Rust) o `# SPDX-License-Identifier: GPL-3.0-or-later` (Python).
- Las reglas para personas están en [`CONTRIBUTING.md`](CONTRIBUTING.md) y también valen para vos.

## 3. Al terminar un aporte (obligatorio)

1. **Creá una entrada nueva** en `docs/bitacora/` copiando [`_plantilla.md`](docs/bitacora/_plantilla.md).
   - Nombre: `AAAA-MM-DD-NN-tema-corto.md`, donde `NN` es el número de aporte del día (`01`, `02`, …). Ejemplo: `2026-11-09-02-motor-portico-2d.md`.
   - Una entrada por aporte. **No edites entradas anteriores**: si algo cambió, lo decís en la nueva.
2. **Actualizá [`docs/ESTADO.md`](docs/ESTADO.md)**: es la foto actual, se reescribe; la bitácora es la historia, solo se agrega.
3. **Documentación al día (obligatorio).** En el mismo PR, actualizá los archivos informativos que tu aporte deja desactualizados, para que los demás aportantes estén al tanto. Usá la tabla de [`CONTRIBUTING.md`](CONTRIBUTING.md) §Documentación al día; como mínimo revisá:
   - [`README.md`](README.md) y sus traducciones (`README.en.md`, `README.pt.md`, `README.ru.md`), si cambia lo que Nervi hace, cómo se instala o cómo se trabaja.
   - [`docs/hoja-de-ruta.md`](docs/hoja-de-ruta.md), si avanza una fase o un issue.
   - [`CONTRIBUTING.md`](CONTRIBUTING.md), este archivo y [`.github/pull_request_template.md`](.github/pull_request_template.md), si cambia una regla o un control.
   - Las páginas públicas de [`sitio/`](sitio/) y sus traducciones en `sitio/idiomas/` (portada, descargar, primeros pasos), si cambia lo que un usuario puede hacer. El sitio es para el público: no publiques ahí pendientes internos ni notas de trabajo.
   - La documentación técnica que corresponda (convenciones, contratos, formato `.nrv`, glosario, línea de diseño de la interfaz).

   Listá lo que actualizaste en la sección **Documentación actualizada** de la entrada de la bitácora (o explicá por qué no hizo falta). No afirmes en esos archivos nada que el código no haga.
4. Incluí la entrada, `docs/ESTADO.md` y la documentación en el mismo commit o PR que el código.
5. **Certificado de origen (DCO).** El CI exige `Signed-off-by` en cada commit. La firma es una declaración de una persona, no de la IA. Por defecto, la persona que pidió el trabajo revisa los commits y los firma con `git rebase --signoff origin/main`; avisale en tu respuesta. **Excepción:** podés agregar la firma de esa persona solo si ella te lo autoriza explícitamente y por escrito para ese trabajo. En ese caso usá exactamente el nombre y correo que indique (o su correo `noreply` de GitHub) y anotá la autorización en la entrada de la bitácora. Nunca firmes en nombre de otra persona ni sin autorización.

El control **"Bitácora de aportes"** del CI (`scripts/verificar_bitacora.py`) deja el PR en rojo si cambia código sin agregar una entrada nueva y sin actualizar `docs/ESTADO.md`, si se edita o borra una entrada existente, si el nombre no sigue el formato o si a la entrada le faltan secciones de la plantilla (entre ellas **Documentación actualizada**).

## 4. Lo que no se hace

- No borrar ni desactivar pruebas para que algo pase.
- No borrar, regenerar ni editar los archivos de referencia de `tests/datos/nrv/`, ni borrar o cambiar una migración publicada del formato `.nrv`: un proyecto guardado con cualquier versión de Nervi se tiene que poder abrir siempre.
- No subir credenciales, datos de clientes ni modelos de proyectos reales.
- No copiar código de programas comerciales ni de proyectos con licencias incompatibles con GPL-3.0.
- No transcribir textos, tablas ni figuras de normas: implementar el método y citar el artículo. No subir PDFs de normas.
- No leer formatos propietarios por ingeniería inversa ni copiar íconos o capturas de otros programas.
- No agregar dependencias con licencias fuera de la lista de [`deny.toml`](deny.toml).
- Un módulo de diseño según norma no se da por terminado sin revisión de un ingeniero estructural (anotalo como pendiente en la bitácora).
