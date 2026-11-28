# Archivos de referencia del formato `.nrv`

Estos archivos garantizan que un proyecto guardado con una versión vieja de Nervi se siga abriendo y dé los mismos resultados (`docs/formato-nrv.md` §6.3). Los usa `tests/test_formato_compatibilidad.py`.

**No se borran, no se regeneran y no se editan.** Si una prueba falla, el error está en el cambio nuevo.

| Archivo | Qué es |
|---|---|
| `modelo-v1.nrv` | Módulo `modelo` versión 1: pórtico plano de 5 nudos y 4 barras con todos los tipos de carga de la versión 1, resorte, asentamiento, articulación y dos combinaciones. Guardado el 2026-11-12. |
| `modelo-v1-sin-modulos.nrv` | El mismo proyecto con el manifiesto que escribía Nervi antes de que existiera `modulos` (GUI del 2026-11-10 al 2026-11-12). |
| `modelo-v1.esperado.json` | Desplazamientos, reacciones y fuerzas de extremo de cada caso, calculados con el motor del 2026-11-12. |
| `diseno-v1.nrv` | Módulo `diseno` versión 1 junto con `modelo` 1: el pórtico de ejemplo de la interfaz con H-21, estribos Ø8, B1 marcada como columna, B2 con sección propia de 250 × 550 mm y B3 sin diseñar. Guardado el 2026-11-17. |
| `diseno-v1.esperado.json` | Resultados de cada caso (motor del 2026-11-17) y, en `diseno`, el tipo y la sección de cada barra y los materiales que se tienen que leer. |
| `dinamica-v1.nrv` | Módulo `dinamica` versión 1 junto con `modelo` 1: el pórtico de ejemplo de la interfaz con masa desde D + 0,25 L, 4 modos y dos espectros (`Sismo X` en X con CQC y `Vertical` en Y con SRSS y 2 % de amortiguamiento). Guardado el 2026-11-19. |
| `dinamica-v1.esperado.json` | Resultados de cada caso y, en `dinamica`, los datos que se tienen que leer, los periodos, la masa total y efectiva y el cortante basal de cada espectro (motor del 2026-11-19). |
| `diseno-v2.nrv` | Módulo `diseno` versión 2 junto con `modelo` 1: el pórtico de ejemplo de la interfaz con H-25, estribos Ø8, B1 como columna de 350 × 350 mm con la búsqueda de armadura limitada a Ø16 (`diametros_columna`), B2 viga de 250 × 550 mm y B3 sin diseñar. Guardado el 2026-11-24. |
| `diseno-v2.esperado.json` | Resultados de cada caso (motor del 2026-11-24) y, en `diseno`, los datos que se tienen que leer y la armadura de B1 (8 barras Ø16; con todos los diámetros saldría 4Ø20). |
| `proyecto-v1.nrv` | Módulo `proyecto` versión 1 junto con `modelo` 1: el pórtico de ejemplo de la interfaz con los seis datos de la carátula cargados. Guardado el 2026-11-24. |
| `proyecto-v1.esperado.json` | Resultados de cada caso y, en `proyecto`, el contenido de `proyecto.json` que se tiene que leer. |
| `historial-v1.nrv` | Módulo `historial` versión 1 junto con `modelo` 1: el pórtico de ejemplo de la interfaz con dos propuestas aplicadas (`ia: Claude` cambia la sección de B2; `importador: planilla` agrega viento en N3) y la segunda deshecha. Guardado el 2026-11-24. |
| `historial-v1.esperado.json` | Resultados de cada caso (motor del 2026-11-24) y, en `historial`, los tres cambios que se tienen que leer. |
| `fisico-v1.nrv` | Módulo `fisico` versión 1 junto con `modelo` 1: el pórtico de ejemplo de la interfaz y, como modelo físico, el edificio de `examples/edificio_fisico.py` (4 niveles, 5 ejes, H-25, 18 columnas de 40 x 40, 21 vigas de 25 x 50, 6 losas macizas de 12 cm y un muro de 20 cm). Guardado el 2026-11-25. |
| `fisico-v1.esperado.json` | Resultados de cada caso (motor del 2026-11-25) y, en `fisico`, el contenido de `fisico.json` que se tiene que leer. |
| `fisico-v2.nrv` | Módulo `fisico` versión 2 junto con `modelo` 1: el edificio de `examples/edificio_fisico.py` con cargas por planta (1,5 kN/m² de permanente en los tres pisos, 2 kN/m² de sobrecarga en los pisos 1 y 2 y 1 kN/m² en la azotea) y la primera losa con 5 kN/m² de sobrecarga propia y un hormigón de 20 kN/m³ (`H-25 liviano`). Guardado el 2026-11-27. |
| `fisico-v2.esperado.json` | Resultados de cada caso (motor del 2026-11-27), en `fisico` el contenido de `fisico.json` y, en `reparto`, la carga total por caso y la resultante de cada viga y muro en cada caso (reparto del 2026-11-27). |

Cuando un módulo sube de versión, se **agrega** su archivo (`modelo-v2.nrv`, `modelo-v2.esperado.json`) y se anota acá. Los anteriores se quedan.
