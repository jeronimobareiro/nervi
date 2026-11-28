# 2026-11-28-03 · Zoom, paneo y grilla en metros en la planta y la vista 2D

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-czjd56`
- **Fase de la hoja de ruta:** Fase 5 (edición gráfica, #31) y Fase 7 (#73, segunda parte)

## Qué se pidió

Etapa 1 del plan para dibujar con el mouse, aprobado el 27/11/2026: poder moverse por la planta del edificio y por la vista 2D del pórtico. Hasta ahora la vista se reacomodaba sola para mostrar todo, así que una viga mal cargada (50 m en la prueba del instalador) achicaba el resto hasta no verse.

## Qué se hizo

- `python/nervi/gui/navegacion.py` (nuevo): `Camara` (zoom hacia el cursor y paneo, o encuadre automático mientras no se navegó), `paso_grilla` (serie 1-2-5 con al menos 14 px entre líneas finas), `dibujar_grilla` (grilla en unidades del modelo, fina y gruesa), `escala_papel` (1:N en pantalla según los ppp) y `dibujar_coordenadas`. La mezcla `Navegable` da la rueda, el botón del medio, espacio + arrastre, doble clic del medio, `F`, `Inicio`, `+` y `-`, y los botones Acercar, Alejar y Encuadrar arriba a la derecha.
- `PlantaEdificio` (`edificio.py`) y `Vista2D` (`vista2d.py`) usan `Navegable`: el encuadre automático pasa a `ajuste()` y la cámara decide la vista. La grilla deja de ser de píxeles y pasa a estar en unidades del modelo. Abajo a la derecha se ven las coordenadas del cursor y la escala. El clic izquierdo sigue eligiendo; el del medio ya no elige.
- `ventana.py`: un proyecto nuevo, el ejemplo o un archivo abierto se encuadran enteros; los botones de navegación cambian de color con el tema.
- Íconos `acercar`, `alejar` y `encuadrar` del catálogo pasan a en uso (29 en uso, 94 reservados) y se regeneró la lámina.

## Cómo se verificó

- `tests/test_gui_navegacion.py` (nuevo, 7 pruebas): serie de la grilla, escala 1:N, que el punto bajo el cursor no se mueva al hacer zoom, rueda, paneo con el botón del medio, `F` y los botones en la planta y en la vista 2D, elección con clic después del zoom y encuadre al abrir otro proyecto.
- `tests/test_gui.py`, `test_gui_edificio.py`, `test_gui_cargas.py` y `test_iconos.py` en verde.
- Capturas de la planta con zoom en los dos temas.

## Decisiones tomadas

- La navegación queda en Python: solo cambia cómo se mira el modelo, no recorre sus elementos. El enganche, que sí los recorre en cada movimiento del mouse, va en Rust (etapa 2).
- Mientras no se toca el zoom, la vista sigue encuadrando sola, como antes; al navegar queda fija hasta que se encuadra. Cambiar de planta no mueve la vista, para comparar pisos en el mismo lugar.
- El paneo va en el botón del medio y en espacio + arrastre, para no quitarle al botón izquierdo la elección ni, más adelante, el dibujo.

## Documentación actualizada

- `docs/ESTADO.md`: navegación de las vistas, conteo de íconos y el plan aprobado.
- `docs/iconos.md` y la lámina `docs/img/iconos-*.png`: tres íconos pasan a en uso.
- README y sitio no cambian todavía: la navegación sola no cambia lo que se puede hacer; se actualizan cuando se pueda dibujar con el mouse.

## Pendiente y problemas conocidos

- Etapa 2: motor de enganche en Rust (`nervi_core::enganche`), con el algoritmo de `gui_snapper.py` de FreeCAD Draft (LGPL-2.1-or-later) como referencia y su atribución.
- El visor 3D tiene su propia navegación (VTK) y no cambia.

## Para quien siga

- Leé `python/nervi/gui/navegacion.py`. Una vista nueva que dibuje en planta hereda `Navegable`, implementa `ajuste()` y llama a `navegacion_presionar`, `navegacion_mover` y `navegacion_soltar` desde sus eventos del mouse.
