# 2026-11-19-06 · Flexión de vigas en Rust (fase 2 del plan de rendimiento)

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-8xjxwp`
- **Fase de la hoja de ruta:** Fase 3 (diseño de hormigón, #22 y #23), rendimiento

## Qué se pidió

Seguir con la migración del diseño a Rust: la fase 2 del plan aprobado (vigas, incluido lo que prepara el servicio), con el mismo método que las columnas (banco de tiempos antes y después, comparación cruzada y la misma API de Python). Después, volver a medir y recomendar si conviene la fase 3.

## Qué se hizo

- Módulo nuevo `nervi_core::diseno::viga` (`crates/nervi-core/src/diseno/viga.rs`): resistencia a flexión por compatibilidad de deformaciones, armadura simple por bisección sobre el área y elección de barras comerciales en una o dos capas. Es el mismo algoritmo que tenía la versión en Python, paso por paso, con el mismo orden de candidatas y de desempates.
- Puente PyO3 en `crates/nervi-py/src/diseno.rs`: `viga_resistencia`, `viga_armadura_simple` y `viga_elegir_barras`. El contrato del diseño sube a `VERSION_CONTRATO_DISENO = 2`; las funciones de columnas no cambian.
- `python/nervi/design/aci318/flexion.py` llama al núcleo en Rust. Las funciones públicas, sus validaciones y mensajes de error y las dataclasses no cambiaron. La armadura doble (fórmula cerrada) sigue en Python.
- Columnas: la búsqueda de armadura arma las posiciones de las barras candidatas sin construir una `SeccionColumna` por candidata (`SeccionColumna._barras_con`); la sección se construye solo para la elegida.
- Cortante, estribos y servicio se midieron y quedan en Python (ver Decisiones).

## Cómo se verificó

- Pórtico de referencia (130 barras), misma máquina de 4 núcleos: diseño **4,8 s antes, 2,4 s después** (132 s antes de la fase 1). Las vigas pasaron de unos 5,8 s a 0,18 s en total, unas 30 veces menos. `scripts/medir_diseno.py --comparar` contra los resultados guardados antes del cambio: las 130 barras dan la misma armadura y las mismas relaciones (tolerancia relativa 1e-6), también en el pórtico de 3 x 4 (0,57 s).
- `tests/test_viga_rust.py` (8 pruebas nuevas): comparación cruzada con la versión en Python anterior, copiada en `tests/_referencia_flexion_python.py`, en 300 resistencias al azar (con y sin armadura comprimida), 200 armaduras (161 simples y 39 que piden armadura doble) y 60 elecciones de barras con una o dos capas (21 con solución y 39 sin ella, que tienen que dar el mismo error), con tolerancia relativa 1e-9; y que los diámetros propios conservan su tipo.
- Pruebas unitarias en Rust: resistencia contra el bloque rectangular cerrado (`Mn = As fy (d − a/2)`, §22.2) y su inversa, y una elección de barras que cumple.
- Las pruebas que ya había pasan sin cambios: 333 en pytest y 96 en Rust. `cargo fmt`, `cargo clippy -D warnings` y `ruff` en verde.

## Decisiones tomadas

- **Cortante y servicio quedan en Python.** Medido en las 60 vigas del pórtico de referencia: `verificar_servicio_viga` tarda 0,5 ms por viga y `elegir_estribos` 0,01 ms; son fórmulas cerradas sin iteraciones pesadas. La regla de rendimiento pasa un cálculo a Rust cuando el banco de tiempos muestra que pesa, y acá no se ganaría nada medible. Lo único que recorre estaciones en servicio es el acceso a los diagramas, que es parte de la fase 3.
- **Recomendación sobre la fase 3: no hacerla como estaba planteada.** En un pórtico de 750 barras (12 x 30) el diseño tarda 12 s: 7,2 s en la búsqueda de armadura de columnas, 1,5 s en su verificación, 0,8 s en vigas y solo 0,1 s en el acceso a los diagramas. El diseño ya usa los 4 núcleos (35 s con uno solo), así que diseñar los elementos en paralelo rendiría poco. Lo que más rinde es acelerar el algoritmo de columnas en Rust: reusar el barrido de 48 inclinaciones entre direcciones con el mismo `Pu` y bajar las bisecciones con un método de raíz más rápido. Eso cambia los resultados en el orden de la tolerancia de las bisecciones, así que la comparación pasaría a ser con tolerancia en vez de exacta.
- La versión en Python de la flexión se guarda solo en `tests/` como referencia; se puede borrar una versión después.
- Firma DCO: Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (19/11/2026) que el agente agregue su `Signed-off-by` a los commits de este trabajo, con el nombre `bareirojero` y su correo `noreply` de GitHub.

## Documentación actualizada

- `docs/contrato-datos.md` §Diseño: funciones de flexión de vigas y versión 2 del contrato.
- `docs/ESTADO.md`: rendimiento del diseño, cantidad de pruebas y próximos pasos.
- `docs/hoja-de-ruta.md`: estado del plan de rendimiento y #22 con el cálculo en Rust.
- `README.md`, `README.en.md`, `README.pt.md` y `README.ru.md`: vigas con la flexión en Rust, el tiempo nuevo del pórtico de referencia y el próximo paso de rendimiento.
- No cambió lo que un usuario puede hacer ni la interfaz, así que `sitio/` no se tocó. No hay términos nuevos para el glosario.

## Pendiente y problemas conocidos

- Decidir la fase 3 (ver la recomendación de arriba) y sumar el banco de tiempos al CI.
- Sigue pendiente la revisión de un ingeniero estructural de la flexión de vigas; conviene hacerla sobre esta versión.

## Para quien siga

- Leé `docs/contrato-datos.md` §Diseño y `crates/nervi-core/src/diseno/viga.rs`. Para medir: `python scripts/medir_diseno.py --guardar antes.json` en `main` y `--comparar antes.json` con tu cambio; `--vanos 12 --pisos 30` da el pórtico de 750 barras.
