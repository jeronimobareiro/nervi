# 2026-11-28-04 · Motor de enganche en Rust para dibujar en planta

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-czjd56`
- **Fase de la hoja de ruta:** Fase 5 (edición gráfica, #31) y Fase 7 (#73, segunda parte)

## Qué se pidió

Etapa 2 del plan para dibujar con el mouse: el enganche a la grilla, los ejes y los extremos. El pedido fue traer lo que ya resolvieron los programas libres y dejarlo todo en Rust y Python, sin dependencias en C++.

## Qué se hizo

- `crates/nervi-core/src/enganche.rs` (nuevo): `IndiceEnganche` (índice de grilla uniforme de puntos y segmentos), `Opciones` y `Enganche`. Prioridades: puntos notables (punto, extremo, cruce, medio, perpendicular y cruce de una línea polar con un segmento; gana el más cercano), Orto, el punto más cercano sobre un segmento, guías (cruce de guías, línea polar, prolongación de un segmento reciente) y la grilla. `enganchar_sin_indice` recorre todo, para comprobar el índice.
- Adaptado del `Snapper` de FreeCAD Draft (`src/Mod/Draft/draftguitools/gui_snapper.py`, LGPL-2.1-or-later, compatible con GPL-3.0): de ahí salen los tipos de enganche y su orden (`snapToObject`, `snapToPolar`, `snapToExtensions`, `snapToCrossExtensions`, `snapToGrid`). No se copió código: el de FreeCAD depende de la escena 3D (Coin) y de las formas de OpenCASCADE, así que se reescribió para segmentos en planta, con la atribución en el encabezado del módulo.
- `crates/nervi-py/src/enganche.rs` (nuevo): clase `nervi._core.IndiceEnganche`.
- `python/nervi/enganche.py` (nuevo): `IndiceEnganche`, `Enganche` y `geometria_planta(mf, piso)`, que arma lo enganchable de una planta del modelo físico (columnas, vigas, muros, bordes de losas y ejes) y dice de qué elemento sale cada enganche.
- `scripts/medir_enganche.py` (nuevo): banco de tiempos.

## Cómo se verificó

- `crates/nervi-core/tests/enganche.rs` (9 pruebas): cada tipo de enganche con su resultado exacto, prioridades, Orto con grilla, prolongación y cruce de guías, y 3000 consultas al azar iguales con índice y sin índice.
- `tests/test_enganche.py` (4 pruebas): la API de Python, entradas inválidas, la planta del ejemplo y 800 consultas iguales con índice y sin índice.
- `python scripts/medir_enganche.py`: planta de 70 × 70 vanos (5041 puntos y 14 910 segmentos), índice en 7,5 ms y 2,0 µs por consulta; 300 consultas iguales al recorrido completo.
- `cargo fmt`, `cargo clippy -D warnings`, `ruff` en verde.

## Decisiones tomadas

- En Rust desde el principio, por la regla de rendimiento: el enganche recorre los elementos en cada movimiento del mouse.
- Índice de grilla uniforme propio en vez de un árbol R (`rstar`): no suma dependencias y da 2 µs por consulta.
- La prolongación usa solo los segmentos "recientes" (los que pasó el mouse), como FreeCAD, porque una recta infinita no se puede ubicar en el índice.
- Dos reglas propias que FreeCAD no tiene igual: el cruce de una línea polar con un segmento cuenta como punto notable, y Orto redondea la distancia al paso de la grilla (cómo se cargan vigas de largos redondos).
- LibreCAD es GPL-2.0 sin "o posterior", no compatible con GPL-3.0: no se usó. QCAD 3 (GPL-3.0) se consultó solo como idea de interfaz.

## Documentación actualizada

- `docs/ESTADO.md`: enganche y avance del plan.
- `AGENTS.md` y `CONTRIBUTING.md`: el banco de tiempos nuevo.
- `docs/glosario.md`: enganche y navegación.
- README y sitio no cambian todavía: la interfaz no lo usa hasta la etapa 3.

## Pendiente y problemas conocidos

- Etapa 3: herramientas de dibujo del edificio en la planta, con este enganche, la cota dinámica y la entrada de largo y ángulo de la muestra aprobada.

## Para quien siga

- La interfaz arma `geometria_planta` cuando cambia el modelo o el piso, y en cada movimiento del mouse llama a `enganchar` con `radio = 10 px / escala`.
