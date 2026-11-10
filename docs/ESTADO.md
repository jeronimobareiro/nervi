# Estado actual del proyecto

_Última actualización: 2026-11-10 · entrada [2026-11-10-02](bitacora/2026-11-10-02-cargas-trapezoidales.md)_

Este archivo es la foto de hoy. Se **reescribe** en cada aporte; la historia está en [`bitacora/`](bitacora/).

## Nombre

El proyecto se llama **Nervi** (antes Apex BIM): crates `nervi-core` y `nervi-py`, paquete Python `nervi`. Repositorio: [github.com/jeronimobareiro/nervi](https://github.com/jeronimobareiro/nervi). Logo e identidad visual en [`marca/`](marca/) (ver especificación §1).

## Fase actual

**Fase 1: pórtico plano lineal elástico**, casi completa. Fases en [`especificacion-tecnica.md`](especificacion-tecnica.md) §7; plan con hitos e issues (#2 a #32) en [`hoja-de-ruta.md`](hoja-de-ruta.md).

## Qué funciona

- Análisis de pórticos planos desde Python (`import nervi`): cargas nodales, uniformes, puntuales y trapezoidales o uniformes parciales en un tramo `[a, b]` (#2); articulaciones y cerchas; apoyos rígidos y elásticos; asentamientos; varios casos y combinaciones.
- Reacciones, fuerzas de extremo, diagramas N/V/M y deformada.
- 27 casos de verificación analítica en Rust y 28 pruebas en Python, en verde. Contrato de datos Rust ↔ Python en la versión 2.
- Registro de aportes: `AGENTS.md`, esta foto y `bitacora/`, con control automático en el CI.
- Apertura a la comunidad: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `SECURITY.md`, `CITATION.cff`, plantillas de issues y PR, encabezados SPDX.
- Controles en el CI: certificado de origen (DCO, `Signed-off-by` obligatorio desde la entrada 07) y licencias de dependencias (`cargo-deny`, `deny.toml`).
- Sitio web con toda la documentación (MkDocs + GitHub Pages, `mkdocs.yml`, `sitio/`), publicado automáticamente desde `main` en https://jeronimobareiro.github.io/nervi/.
- Hoja de ruta para colaborar: 31 issues en GitHub con etiquetas de fase, tamaño (`buen-primer-aporte`, `proyecto-academico`, `tesis-posible`) y área; el flujo "Organizar hoja de ruta" crea los hitos y asigna los issues.

## En curso o bloqueado

- **Sitio web**: falta activar GitHub Pages una vez (Settings → Pages → Source: "GitHub Actions").
- **Cargas trapezoidales en `.nrv` y la GUI**: si el PR #35 entra después que las trapezoidales, hay que adaptar `nervi.formato` al contrato v2 (10 columnas en `cargas_barra`) y sumar el tipo `trapezoidal` al esquema.
- **Formato de archivo `.nrv`**: especificación en [`formato-nrv.md`](formato-nrv.md) (ZIP + JSON versionado; IFC solo para importar y exportar). Aprobada por el usuario el 2026-11-09; falta el módulo `nervi.formato`. Se congela con la primera versión de la GUI.
- **Hitos de GitHub**: se crean al integrar el PR de la hoja de ruta (flujo `.github/workflows/hoja-de-ruta.yml`). Hay que confirmar en Actions que corrió bien.
- Firma DCO: la firma el usuario o, con su autorización explícita para cada trabajo, el agente en su nombre (AGENTS.md §3.4).
- Confirmar el correo de contacto de `CODE_OF_CONDUCT.md` y `SECURITY.md`.
- Para que los controles **bloqueen** el merge, el dueño del repo tiene que marcarlos como obligatorios en Settings → Branches (o Rules) para `main`.

## Próximos pasos sugeridos

1. Cerrar la Fase 1: momentos en el tramo (#3), cargas térmicas (#4) y la biblioteca `verification/` (#5). Las trapezoidales (#2) ya están.
2. Difundir los issues `buen-primer-aporte` y `proyecto-academico` entre cátedras (ver `hoja-de-ruta.md` §Colaboración con universidades).
3. Fase 2a: barra 3D 12×12 (#11), que destraba casi todo lo demás.
4. Decidir la norma regional (#20) para ordenar la Fase 3 y el espectro sísmico.
5. Registrar la marca Nervi en Paraguay (DINAPI, clases 9 y 42), con abogado.

## Decisiones abiertas (las toma el usuario)

- Norma regional prioritaria ([#20](https://github.com/jeronimobareiro/nervi/issues/20)).
