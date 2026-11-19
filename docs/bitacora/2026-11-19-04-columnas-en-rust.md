# 2026-11-19-04 · Flexocompresión de columnas en Rust y banco de tiempos del diseño

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-8xjxwp`
- **Fase de la hoja de ruta:** Fase 3 (diseño de hormigón, #24), rendimiento

## Qué se pidió

Aplicar la regla nueva del proyecto (todo cálculo pesado en Rust, Python solo como capa de uso) al diseño ACI. Se midió dónde se va el tiempo, se aprobó un plan por fases y se pidió hacer ahora las fases 0 (banco de tiempos) y 1 (columnas en Rust), sin cambiar la API de Python.

## Qué se hizo

- Banco de tiempos `scripts/medir_diseno.py`: pórtico plano de referencia de 6 vanos y 10 pisos (130 barras, cargas D, L y W, 6 combinaciones de ACI 318-19) que mide `proyecto.disenar` y guarda o compara armaduras y relaciones de cada elemento (`--guardar`, `--comparar`).
- Módulo nuevo `nervi_core::diseno::columna` (`crates/nervi-core/src/diseno/`): recorte exacto del bloque comprimido, resultantes de la sección para un eje neutro, profundidad por bisección logarítmica, capacidad en una dirección con `Pu` fijo, razones demanda/capacidad y búsqueda de la armadura de menor área. Es el mismo algoritmo que tenía la versión NumPy, paso por paso. Las solicitaciones y las candidatas se reparten entre núcleos con `rayon` (MIT o Apache-2.0, ya estaba en el árbol por `faer`).
- Puente PyO3 `crates/nervi-py/src/diseno.rs` con contrato propio `VERSION_CONTRATO_DISENO = 1` (`docs/contrato-datos.md` §Diseño): `columna_seccion_en`, `columna_capacidad`, `columna_razones` y `columna_elegir_armadura`. Suelta el GIL mientras calcula.
- `python/nervi/design/aci318/columna.py` llama al núcleo en Rust. Las funciones públicas y las dataclasses no cambiaron; las privadas `_geo` y `_seccion_en` conservan su firma porque las usan las pruebas.
- Fase 0: `disenar_columna` toma los diagramas de las combinaciones resueltas junto con el modelo (exactos) en vez de recombinar los casos con `Resultados.combinar`, que interpolaba y costaba unos 5 s en el pórtico de referencia. Con combinaciones que no se resolvieron con el modelo sigue recombinando como antes.
- `SeccionColumna` comprueba que todas las barras estén dentro del hormigón de una vez, no barra por barra (la búsqueda arma miles de secciones candidatas).
- `AGENTS.md` suma la regla de rendimiento tal como quedó en las instrucciones del proyecto; tres términos nuevos en `docs/glosario.md`.

## Cómo se verificó

- Pórtico de referencia, misma máquina (4 núcleos): diseño **132 s antes, 4,6 s después**. Las columnas pasaron de unos 2 s a unos 0,03 s cada una; lo que queda son sobre todo las vigas (unos 3 s), que son la fase 2. `--comparar` contra los resultados guardados antes del cambio: las 130 barras dan la misma armadura y las mismas relaciones (tolerancia relativa 1e-6), también en el pórtico de 3 vanos y 4 pisos (30 s → 1,5 s).
- `tests/test_columna_rust.py` (7 pruebas nuevas): comparación cruzada con la versión NumPy anterior, copiada sin cambios en `tests/_referencia_columna_numpy.py`, en 20 secciones rectangulares y circulares al azar (resultantes con tolerancia 1e-9 relativa al mayor valor), 240 solicitaciones (capacidad y razones, 1e-6), el diagrama de interacción con zuncho en cuatro direcciones y la elección de armadura con tres semillas; y el control de versión del contrato.
- Pruebas unitarias en Rust del recorte del bloque, la flexión simple contra el bloque rectangular cerrado (`Mn = As fy (d − a/2)`, §22.2) y la simetría de una sección cuadrada.
- Las pruebas que ya había (columnas contra concreteproperties y contra fibras, etapa Diseño, memoria) pasan sin cambios: 325 en pytest y 94 en Rust, en verde. `cargo fmt`, `cargo clippy -D warnings` y `ruff` en verde.

## Decisiones tomadas

- Se portó el algoritmo tal cual, con los mismos números de iteraciones (48 inclinaciones, 42 y 22 bisecciones) y el mismo orden de decisiones, para que los resultados no cambien y la comparación cruzada sea estricta. Mejorar el algoritmo (menos iteraciones, Newton) queda para después, ya en Rust y con estas pruebas.
- Se dejaron en Python la geometría de la sección, las candidatas, la esbeltez y el armado de los resultados: no pesan y son la parte que más cambia.
- La versión NumPy se guarda solo en `tests/` como referencia; se puede borrar una versión después.
- En un caso degenerado (`φPn` pedido igual a la compresión máxima con zuncho) el redondeo de Rust y de NumPy decide distinto si hay solución; el momento resistente es nulo en los dos. `diagrama_interaccion` nunca evalúa ese extremo, así que no cambia nada.
- Firma DCO: Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (19/11/2026) que el agente agregue su `Signed-off-by` a los commits de este trabajo, con el nombre `bareirojero` y su correo `noreply` de GitHub.

## Pendiente y problemas conocidos

- Fase 2 del plan: vigas (flexión, cortante y servicio) a Rust. Hoy son lo más lento del diseño. Fases 3 y 4 (envolventes, acceso por barra y detalle) solo si el banco de tiempos lo muestra.
- El banco de tiempos todavía no corre en el CI.
- Armar en Python las secciones candidatas cuesta todavía alrededor de 1 s en el pórtico de referencia; se puede llevar a Rust junto con la fase 2.
- Sigue pendiente la revisión de un ingeniero estructural del diseño de columnas; conviene hacerla sobre esta versión.

## Para quien siga

- Leé `docs/contrato-datos.md` §Diseño y `crates/nervi-core/src/diseno/columna.rs`. Para medir: `python scripts/medir_diseno.py --guardar antes.json` en `main` y `--comparar antes.json` con tu cambio.
