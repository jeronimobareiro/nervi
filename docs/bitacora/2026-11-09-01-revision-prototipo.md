# 2026-11-09-01 · Revisión de la especificación y del prototipo de Gemini

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** sin código; documentos en la carpeta del proyecto
- **Fase de la hoja de ruta:** previa a la Fase 0

## Qué se pidió

Revisar la especificación técnica generada por Gemini y el prototipo de código que la acompañaba.

## Qué se hizo

- Revisión crítica de la especificación y versión corregida (hoy `docs/especificacion-tecnica.md`).
- Revisión del prototipo (`apex_bim_repository.zip`, unas 234 líneas).

## Hallazgos principales

- La especificación decía "6 GDL por nudo" en el plano: son 3 por nudo y 6 por barra.
- Faltaban las cargas nodales equivalentes de las cargas en tramo; las fuerzas de extremo eran `k·u`.
- Sin convención de signos; fórmulas LaTeX corruptas; apoyos por penalización 1e20.
- `IfcRebar` no existe (es `IfcReinforcingBar`); el IFC habitual no trae modelo analítico.
- El prototipo devolvía siempre ceros; no compilaba con Python 3.13 (PyO3 0.20). Solo la matriz de rigidez local 6×6 y su transformación eran correctas.
- Las funciones de diseño ACI y EC2 del prototipo eran incorrectas (mezcla de cuantía y área; brazo de palanca `d` en vez de `z`).

## Decisiones tomadas

- Rehacer el motor desde una base verificable en lugar de completar el prototipo.
- Conservar solo la matriz de rigidez local del prototipo.
- Descartar el código de normas del prototipo hasta la Fase 3.

## Pendiente y problemas conocidos

- Ninguno propio de esta revisión; lo pendiente del proyecto está en la entrada siguiente.

## Para quien siga

Ver la entrada `2026-11-09-02`.
