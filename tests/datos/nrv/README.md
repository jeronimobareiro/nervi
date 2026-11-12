# Archivos de referencia del formato `.nrv`

Estos archivos garantizan que un proyecto guardado con una versión vieja de Nervi se siga abriendo y dé los mismos resultados (`docs/formato-nrv.md` §6.3). Los usa `tests/test_formato_compatibilidad.py`.

**No se borran, no se regeneran y no se editan.** Si una prueba falla, el error está en el cambio nuevo.

| Archivo | Qué es |
|---|---|
| `modelo-v1.nrv` | Módulo `modelo` versión 1: pórtico plano de 5 nudos y 4 barras con todos los tipos de carga de la versión 1, resorte, asentamiento, articulación y dos combinaciones. Guardado el 2026-11-12. |
| `modelo-v1-sin-modulos.nrv` | El mismo proyecto con el manifiesto que escribía Nervi antes de que existiera `modulos` (GUI del 2026-11-10 al 2026-11-12). |
| `modelo-v1.esperado.json` | Desplazamientos, reacciones y fuerzas de extremo de cada caso, calculados con el motor del 2026-11-12. |

Cuando un módulo sube de versión, se **agrega** su archivo (`modelo-v2.nrv`, `modelo-v2.esperado.json`) y se anota acá. Los anteriores se quedan.
