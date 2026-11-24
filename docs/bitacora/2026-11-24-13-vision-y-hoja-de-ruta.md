# 2026-11-24-13 · Visión ampliada y hoja de ruta con hormigón, acero y mixtas

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-8b41c7`
- **Fase de la hoja de ruta:** todas (planificación); fases nuevas 7 a 12

## Qué se pidió

Reescribir la visión y la hoja de ruta para que Nervi sea un programa de diseño y cálculo de estructuras de hormigón, acero y mixtas: del plano de arquitectura (DXF) al predimensionado, cálculo y dimensionado, con cómputos, planillas de armaduras y planos de detalle de hormigón y de acero, y la memoria de cálculo. Crear los issues que correspondan.

## Qué se hizo

- `docs/hoja-de-ruta.md`: sección **Visión** con el recorrido de un proyecto; Fase 6 (láminas) como objetivo firme con fecha; fases nuevas 7 (del plano al modelo), 8 (cargas y predimensionado), 9 (acero), 10 (losas, muros, fundaciones y elementos especiales), 11 (mixtas) y 12 (documentación de obra) en la tabla de hitos, el diagrama y las tablas de tareas; sección **Etapas propuestas** en cuatro etapas ordenadas por dependencias; los planos DXF (#29) pasan de la Fase 4 a la 12; decisiones abiertas nuevas.
- `.github/hoja-de-ruta.json`: etiquetas `fase-7` a `fase-12` y de área `planos`, hitos nuevos y descripciones de las fases 4 y 6. Los títulos de hitos existentes no cambian, porque el flujo los busca por título.
- Issues nuevos #73 a #98 en GitHub, con su fase, tamaño y área; #29 reetiquetado a `fase-12` y `planos`.
- `docs/especificacion-tecnica.md` §1 (visión), §5.2 (AISC 360-22) y §7 (fases 6 a 12).
- README y traducciones, `docs/ESTADO.md` y portada del sitio en los cuatro idiomas.

## Cómo se verificó

- `validar_plan` de `scripts/organizar_hoja_de_ruta.py` sin errores sobre el JSON nuevo; `pytest tests/test_hoja_de_ruta.py` y `python scripts/verificar_bitacora.py origin/main`.
- No cambia código ni cálculo, así que no hace falta el banco de tiempos.

## Decisiones tomadas

- El DWG queda fuera del alcance: se recibe y se entrega en DXF (y PDF), decisión de Jerónimo Bareiro del 24/11/2026.
- Se mantiene la numeración de las fases 1 a 6 para no romper etiquetas ni hitos; las nuevas siguen desde la 7 aunque algunas (7, 8, 9) puedan empezar antes que la 6.
- Las fechas de las etapas son una propuesta para que el responsable las revise.
- **Firma DCO:** Jerónimo Bareiro autorizó por escrito, en el hilo del proyecto el 24/11/2026, firmar este trabajo a su nombre; se usó su correo `noreply` de GitHub (AGENTS.md §3.5).

## Documentación actualizada

- `README.md`, `README.en.md`, `README.pt.md`, `README.ru.md`: descripción y "Qué sigue".
- `docs/hoja-de-ruta.md`, `docs/ESTADO.md`, `docs/especificacion-tecnica.md`.
- `sitio/index.md` y `sitio/idiomas/{en,pt,ru}/index.md`: "Qué viene". La tabla de hitos con estados del sitio es la propia hoja de ruta.

## Pendiente y problemas conocidos

- Decidir tipos de losa después de las macizas y si los perfiles conformados en frío (AISI) entran en la Fase 9.
- Al integrar, confirmar en Actions que "Organizar hoja de ruta" creó los hitos 7 a 12 y asignó los issues.

## Para quien siga

- El bloque que destraba casi todo es el modelo físico (#73) y el modelo de cálculo generado desde él (#74). En paralelo se pueden empezar #82, #83, #84 y #93.
