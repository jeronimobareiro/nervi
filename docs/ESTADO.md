# Estado actual del proyecto

_Última actualización: 2026-11-12 · entradas [2026-11-12-01](bitacora/2026-11-12-01-momentos-en-tramo.md) y [2026-11-12-02](bitacora/2026-11-12-02-gui-nudo-inestable.md)_

Este archivo es la foto de hoy. Se **reescribe** en cada aporte; la historia está en [`bitacora/`](bitacora/).

## Nombre

El proyecto se llama **Nervi**: crates `nervi-core` y `nervi-py`, paquete Python `nervi`. Repositorio: [github.com/jeronimobareiro/nervi](https://github.com/jeronimobareiro/nervi). Logo e identidad visual en [`marca/`](marca/) (ver especificación §1).

## Fase actual

**Fase 1: pórtico plano lineal elástico**, casi completa, con una **interfaz de escritorio preliminar** que crece en paralelo. Fases en [`especificacion-tecnica.md`](especificacion-tecnica.md) §7; plan con hitos e issues (#2 a #32) en [`hoja-de-ruta.md`](hoja-de-ruta.md).

## Qué funciona

- Análisis de pórticos planos desde Python (`import nervi`): cargas nodales, uniformes, puntuales, trapezoidales o uniformes parciales en un tramo `[a, b]` (#2) térmicas, uniformes y con gradiente (#4), y momentos concentrados en el tramo (#3); articulaciones y cerchas; apoyos rígidos y elásticos; asentamientos; varios casos y combinaciones.
- Reacciones, fuerzas de extremo, diagramas N/V/M y deformada.
- Si el modelo es un mecanismo, el error dice qué nudo y qué GDL se mueven sin rigidez y da el modo de mecanismo (#9); en Python, `MecanismoError.nudo`, `.gdl` y `.modos`. La interfaz marca ese nudo en el dibujo, junto con los demás nudos del modo.
- Formato de proyecto `.nrv` (`nervi.formato`): abrir, guardar, validar y migrar según [`formato-nrv.md`](formato-nrv.md), con cargas uniformes, puntuales, trapezoidales, térmicas y momentos en el tramo.
- Interfaz de escritorio `nervi.gui` (PySide6, `nervi-gui`): una sola ventana con tablas editables del modelo, cálculo, diagramas N/V/M y deformada, lectura de esfuerzos con el cursor, revisión del modelo, consola Python y buscador de comandos (Ctrl+K). Aviso permanente de versión preliminar.
- Workflow de publicación: con una etiqueta `v*` genera el instalador `.exe` de Windows (Inno Setup, asocia `.nrv`) y el AppImage de Linux, sin firma, como versión preliminar en Releases.
- 47 casos de verificación analítica en Rust (6 de mecanismos y 6 de momentos en el tramo) y 110 pruebas en Python (formato e interfaz incluidos), en verde. Contrato de datos Rust ↔ Python en la versión 2.
- Biblioteca de casos de verificación en `verification/` (#5): 13 casos en TOML con su fuente, que corren en el CI y se pueden aportar sin saber Rust (`verification/README.md`).
- Combinaciones de carga ACI 318-19 y envolventes por sección en `nervi.design` (#21), **experimental** hasta la revisión de un ingeniero. Las combinaciones se resuelven junto con el modelo y sus diagramas son exactos.
- Registro de aportes: `AGENTS.md`, esta foto y `bitacora/`, con control automático en el CI.
- Colaboradores de otros idiomas: README en inglés, portugués y ruso (`README.en.md`, `README.pt.md`, `README.ru.md`), glosario es/en/pt/ru en [`glosario.md`](glosario.md) y sección multilingüe en `CONTRIBUTING.md`. El código sigue en español; issues y PR se aceptan en esos cuatro idiomas.
- Apertura a la comunidad: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `SECURITY.md`, `CITATION.cff`, plantillas de issues y PR, encabezados SPDX.
- Controles en el CI: certificado de origen (DCO, `Signed-off-by` obligatorio desde la entrada 07) y licencias de dependencias (`cargo-deny`, `deny.toml`).
- Sitio web público en https://jeronimobareiro.github.io/nervi/ (MkDocs + GitHub Pages, publicado solo desde `main`), en español, inglés (`/en/`), portugués (`/pt/`) y ruso (`/ru/`) con selector de idioma; el resto de la documentación se muestra en español con un aviso. Páginas: portada, por qué Nervi (homenaje a Pier Luigi Nervi con fotos libres de Commons), descargar, primeros pasos, documentación técnica, hoja de ruta, participar y bitácora. No publica `ESTADO.md` ni `AGENTS.md`, y el armado falla si aparece el nombre anterior del proyecto.
- Hoja de ruta para colaborar: 31 issues en GitHub con etiquetas de fase, tamaño (`buen-primer-aporte`, `proyecto-academico`, `tesis-posible`) y área; el flujo "Organizar hoja de ruta" crea los hitos y asigna los issues.

## En curso o bloqueado

- **Instaladores**: el workflow de publicación ya genera el `.exe` de Windows y el AppImage de Linux (la descarga de `appimagetool` se arregló en la entrada 2026-11-10-05). Falta probarlos en equipos reales antes de la primera etiqueta `v0.1.0`. El formato `.nrv` (esquema 1) se congela con esa etiqueta.
- Firma de código de los instaladores: pendiente (SignPath Foundation o certificado).
- **Hitos de GitHub**: se crean al integrar el PR de la hoja de ruta (flujo `.github/workflows/hoja-de-ruta.yml`). Hay que confirmar en Actions que corrió bien.
- Firma DCO: la firma el usuario o, con su autorización explícita para cada trabajo, el agente en su nombre (AGENTS.md §3.4).
- Confirmar el correo de contacto de `CODE_OF_CONDUCT.md` y `SECURITY.md`.
- Para que los controles **bloqueen** el merge, el dueño del repo tiene que marcarlos como obligatorios en Settings → Branches (o Rules) para `main`.

## Próximos pasos sugeridos

0. Interfaz: dibujar cargas, crear barras con el mouse y deshacer/rehacer; después, visor 3D con la Fase 2a.
1. Cerrar la Fase 1: ejemplos de libros en `verification/` (#6) y material didáctico (#10). Ya están todos los tipos de carga (trapezoidales #2, térmicas #4 y momentos en el tramo #3), también en `.nrv` y la GUI, igual que la biblioteca de verificación (#5) y el diagnóstico de mecanismos (#9).
2. Difundir los issues `buen-primer-aporte` y `proyecto-academico` entre cátedras (ver `hoja-de-ruta.md` §Colaboración con universidades).
3. Fase 2a: barra 3D 12×12 (#11), que destraba casi todo lo demás. En paralelo, Fase 3: revisión de ingeniería de `nervi.design` y diseño de vigas a flexión y cortante (#22, #23) sobre las envolventes.
4. Decidir la norma regional (#20) para ordenar la Fase 3 y el espectro sísmico.
5. Registrar la marca Nervi en Paraguay (DINAPI, clases 9 y 42), con abogado.

## Decisiones abiertas (las toma el usuario)

- Dominio propio para el sitio (por ejemplo `nervi.lat`).

- Norma regional prioritaria ([#20](https://github.com/jeronimobareiro/nervi/issues/20)).
