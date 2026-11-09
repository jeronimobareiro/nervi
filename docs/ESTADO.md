# Estado actual del proyecto

_Última actualización: 2026-11-09 · entrada [2026-11-09-09](bitacora/2026-11-09-09-firma-autorizada.md)_

Este archivo es la foto de hoy. Se **reescribe** en cada aporte; la historia está en [`bitacora/`](bitacora/).

## Nombre

El proyecto se llama **Nervi** (antes Apex BIM): crates `nervi-core` y `nervi-py`, paquete Python `nervi`. Repositorio: [github.com/jeronimobareiro/nervi](https://github.com/jeronimobareiro/nervi). Logo e identidad visual en [`marca/`](marca/) (ver especificación §1).

## Fase actual

**Fase 1: pórtico plano lineal elástico**, casi completa. Hoja de ruta en [`especificacion-tecnica.md`](especificacion-tecnica.md) §7.

## Qué funciona

- Análisis de pórticos planos desde Python (`import nervi`): cargas nodales, uniformes y puntuales; articulaciones y cerchas; apoyos rígidos y elásticos; asentamientos; varios casos y combinaciones.
- Reacciones, fuerzas de extremo, diagramas N/V/M y deformada.
- 19 casos de verificación analítica en Rust y 16 pruebas en Python, en verde.
- Registro de aportes: `AGENTS.md`, esta foto y `bitacora/`, con control automático en el CI.
- Apertura a la comunidad: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `SECURITY.md`, `CITATION.cff`, plantillas de issues y PR, encabezados SPDX.
- Controles en el CI: certificado de origen (DCO, `Signed-off-by` obligatorio desde la entrada 07) y licencias de dependencias (`cargo-deny`, `deny.toml`).

## En curso o bloqueado

- **Mudanza al repositorio nuevo** `jeronimobareiro/nervi` (el repositorio `bareirojero/Apex-BIM` y su PR #1 se borraron). El historial está en el PR #1 de ese repositorio (rama `importar-nervi`); falta que pase el CI y hacer el merge.
- Firma DCO: la firma el usuario o, con su autorización explícita, el agente en su nombre (AGENTS.md §3.4).
- Confirmar el correo de contacto de `CODE_OF_CONDUCT.md` y `SECURITY.md`.
- Para que el control de bitácora **bloquee** el merge, el dueño del repo tiene que marcar "Bitácora de aportes" como check obligatorio en Settings → Branches (o Rules) para `main`.

## Próximos pasos sugeridos

1. Completar la Fase 1: cargas trapezoidales y parciales, momentos puntuales en el tramo, cargas térmicas.
2. Fase 2: barra 3D (12×12) con ejes locales y vector de referencia.
3. Registrar la marca Nervi en Paraguay (DINAPI, clases 9 y 42), con abogado.
4. Elegir la norma de hormigón a implementar primero (ACI 318-19 y la que se use en Paraguay) para la Fase 3.

## Decisiones abiertas (las toma el usuario)

- Norma regional prioritaria.
