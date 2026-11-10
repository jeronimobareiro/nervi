# Cómo contribuir a Nervi

Gracias por querer aportar. Nervi es software libre (GPL-3.0-or-later) y está pensado para que estudiantes, docentes, investigadores e ingenieros lo mejoren entre todos. Este documento explica cómo.

Al participar aceptás el [Código de conducta](CODE_OF_CONDUCT.md). Las reglas de decisión están en [`GOVERNANCE.md`](GOVERNANCE.md).

## Formas de aportar

- **Reportar un error.** Si un resultado te parece incorrecto, abrí un issue con el modelo mínimo que lo reproduce y el valor que esperabas, con su fuente. Si el error puede afectar una estructura real, seguí [`SECURITY.md`](SECURITY.md).
- **Agregar un caso de verificación.** Un ejemplo resuelto de un libro o una solución analítica es un aporte valioso aunque no toques el motor: es un archivo de texto en [`verification/`](verification/README.md).
- **Implementar una funcionalidad.** Mirá los issues marcados `buen-primer-aporte` (tareas acotadas), `proyecto-academico` (del tamaño de un trabajo práctico, final o práctica profesional) o `tesis-posible` (temas para una tesis de grado o posgrado). El plan con hitos y tareas está en [`docs/hoja-de-ruta.md`](docs/hoja-de-ruta.md).
- **Mejorar la documentación o el material didáctico.** Ejemplos, notebooks y traducciones son bienvenidos.
- **Revisar un módulo normativo.** Si sos ingeniero estructural o docente, tu revisión es la condición para que un módulo de diseño deje de ser experimental.

Antes de un cambio grande, abrí un issue para conversarlo; así evitamos trabajo duplicado.

## Preparar el entorno

Requisitos: Rust estable y Python ≥ 3.10.

```bash
python -m venv .venv && source .venv/bin/activate
pip install maturin pytest ruff
maturin develop --release
pytest
cargo test -p nervi-core
```

## Reglas para el código

1. **Toda fórmula lleva su fuente** en un comentario: norma con edición y artículo, libro con página, o la derivación. Ejemplo: `// ACI 318-19 §9.6.1.2`.
2. **Toda funcionalidad llega con su prueba de verificación** en `verification/`, `crates/nervi-core/tests/` o `tests/`, comparada contra una solución cerrada o un ejemplo publicado.
3. **No se borran ni se desactivan pruebas** para que algo pase.
4. **No se cambia la convención de signos ni el contrato de datos** sin subir `VERSION_CONTRATO` y documentarlo ([`docs/convenciones.md`](docs/convenciones.md), [`docs/contrato-datos.md`](docs/contrato-datos.md)).
5. **Idioma:** español en código, comentarios y documentación.
6. **Encabezado de licencia** en cada archivo nuevo de código:
   - Rust: `// SPDX-License-Identifier: GPL-3.0-or-later`
   - Python: `# SPDX-License-Identifier: GPL-3.0-or-later`

Antes de enviar, corré y dejá en verde:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test -p nervi-core
maturin develop --release && pytest
ruff check python tests examples scripts && ruff format --check python tests examples scripts
```

## Propiedad intelectual: lo que no se puede subir

- **Código de programas comerciales** ni de proyectos con licencias incompatibles con GPL-3.0. Tampoco código obtenido por ingeniería inversa de programas propietarios ni lectores de sus formatos cerrados; para intercambiar modelos usamos IFC.
- **Textos, tablas o figuras copiados de normas** (ACI, AISC, Eurocódigos, ABNT, CIRSOC, etc.). Se implementa el método y se cita el artículo; no se transcriben párrafos ni se suben PDFs de normas.
- **Íconos, capturas o elementos gráficos** de otros programas.
- **Datos de clientes o modelos de proyectos reales** sin permiso, ni credenciales.
- Las dependencias nuevas deben tener una licencia de la lista de [`deny.toml`](deny.toml); el CI lo controla con `cargo-deny`.

No digas que Nervi está "certificado" o "aprobado" por un organismo normativo: decí que "implementa disposiciones de" la norma.

## Certificado de origen (DCO)

Cada commit tiene que estar firmado con el [Developer Certificate of Origin](https://developercertificate.org/): con la firma declarás que escribiste el aporte o que tenés derecho a donarlo bajo la licencia del proyecto. Se agrega con `git commit -s`, que añade la línea:

```
Signed-off-by: Tu Nombre <tu@correo>
```

El CI rechaza los PR con commits sin firma. Si sos estudiante o trabajás en una empresa o universidad, confirmá que tu reglamento o contrato te permite donar el código.

## Bitácora de aportes

Los cambios de código o configuración agregan una entrada en [`docs/bitacora/`](docs/bitacora/) (copiando `_plantilla.md`) y actualizan [`docs/ESTADO.md`](docs/ESTADO.md). El CI lo controla. Si es tu primer aporte y no sabés qué poner, abrí el PR igual y pedí ayuda: un mantenedor la completa con vos. Los agentes de IA siguen además [`AGENTS.md`](AGENTS.md).

## Usar IA para contribuir

Se puede. Quien envía el PR es responsable de lo que contiene: revisalo, entendelo y verificá que no reproduzca código o texto con derechos de terceros. Indicá en la bitácora qué agente usaste.

## Licencia de tus aportes

Al enviar un aporte aceptás que se distribuya bajo GPL-3.0-or-later, la licencia del proyecto. Conservás el derecho de autor sobre lo que escribiste; el proyecto no pide cesión de derechos.
