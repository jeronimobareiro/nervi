# 2026-11-28-05 · Dibujar el edificio con el mouse

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-czjd56`, PR #108
- **Fase de la hoja de ruta:** Fase 7 (#73, segunda parte) y Fase 5 (edición gráfica, #31)

## Qué se pidió

Etapa 3 del plan aprobado el 27/11/2026: dibujar ejes, columnas, vigas, losas y muros en la planta del modo *Edificio* con el mouse, con el enganche de la etapa 2, según la muestra aprobada. Todo en Rust y Python.

## Qué se hizo

- `python/nervi/gui/dibujo.py` (nuevo): `DibujoEdificio` (herramientas, enganche en cada movimiento, vista previa, entrada numérica y creación de elementos con `EstadoEdificio.aplicar`, un Ctrl+Z por elemento), `EntradaNumerica` (largo y ángulo junto al cursor), `PanelHerramienta` (sección, material y espesor, con *Automática* primero) y `OpcionesDibujo` (enganches prendidos, guardados en las preferencias).
  - Eje: dos clics; letras si es más vertical, números si es más horizontal.
  - Columna: un clic, o una ventana que pone una columna en cada cruce de ejes sin columna.
  - Viga y muro: tramos encadenados; la viga se parte en cada columna por la que pasa.
  - Losa: un clic dentro del paño cerrado por vigas y muros, o el contorno a mano.
- `crates/nervi-core/src/planta.rs` (nuevo): `partir`, `cruces` y `pano_en`. `pano_en` corta los segmentos en sus cruces, une vértices con una grilla de dispersión, poda los vértices sueltos, ordena los vecinos por ángulo y recorre la cara que encuentra un rayo desde el punto; descarta la cara exterior y saca los vértices alineados. Expuesto en `nervi._core` y en `nervi.enganche`.
- `python/nervi/gui/ventana.py`: barras *Dibujar* y *Enganche* en el modo *Edificio*, F8 para Orto y el panel de la herramienta en lugar de Propiedades mientras se dibuja.
- `python/nervi/gui/edificio.py`: la planta le pasa el mouse y el teclado al dibujo; clic derecho cancela, Supr borra lo elegido.

## Cómo se verificó

- `crates/nervi-core/tests/planta.rs` (6 pruebas): cortes, cruces sin repetir, paño de un rectángulo, paño con vigas que se cruzan y vigas sueltas, punto fuera de todo paño y paño en L.
- `tests/test_gui_dibujo.py` (7 pruebas, con clics simulados en la planta): ejes, ventana de columnas, vigas encadenadas partidas en columnas, losa con un clic (contorno exacto), muro, Ctrl+Z por elemento, largo escrito con Orto y ángulo, losa a mano, aviso sin piso de abajo, elegir y Supr, y marca del enganche.
- Capturas en los dos temas revisadas a ojo; la clara queda en `docs/img/dibujar-edificio.png`.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test`, `ruff` y 536 pruebas de Python en verde (las de `test_vista3d.py`, que fallan sin pantalla con VTK también sin este cambio, se dejaron afuera).

## Decisiones tomadas

- Los paños se buscan en Rust y en cada movimiento con la herramienta Losa, para mostrar el relleno antes del clic.
- Sección y material *automáticos*: el más usado del modelo, o uno nuevo por defecto (V 20x50, C 30x30, H-25) si no hay; así se puede dibujar sin pasar antes por las tablas.
- Columnas y muros van del piso de abajo al de la planta: sin piso de abajo se avisa y no se crea nada.
- La entrada numérica se abre al escribir un dígito, como en QCAD y FreeCAD, y maneja Enter ella misma para que no termine el tramo.

## Documentación actualizada

- `docs/ESTADO.md`, `README.md`, `sitio/index.md` y sus traducciones (en, pt, ru): el dibujo con el mouse.
- `docs/diseno-interfaz.md`: §Dibujar en la planta, con la captura.
- `docs/hoja-de-ruta.md`: fila de #73.

## Pendiente y problemas conocidos

- Etapa 4: dibujar el modelo de cálculo (nudo, barra, apoyo, cargas) en la vista 2D.
- Etapa 5: paneles acoplables con `QDockWidget` y distribuciones guardadas.
- Mover y estirar elementos con pinzas, copiar y simetría quedan para después.

## Para quien siga

- `DibujoEdificio.geometria()` se vuelve a armar cuando cambia el modelo o el piso; el radio de captura es `RADIO_PX / escala`.
