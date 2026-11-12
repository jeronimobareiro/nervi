# 2026-11-12-02 · Resaltar en la interfaz el nudo que hace inestable el modelo

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-tc5x1h` · PR [#47](https://github.com/jeronimobareiro/nervi/pull/47)
- **Fase de la hoja de ruta:** Fase 1, interfaz preliminar · continúa el issue [#9](https://github.com/jeronimobareiro/nervi/issues/9)

## Qué se pidió

Segundo punto de la jornada: el pendiente que dejó la entrada 2026-11-11-01, mostrar en el dibujo el nudo del mecanismo usando `MecanismoError.nudo` y `modos`.

## Qué se hizo

- `python/nervi/gui/sesion.py`: nueva clase `Inestabilidad` (nudo, GDL y nudos que se mueven, con los `id` de `modelo.json`). Al fallar el cálculo por mecanismo, la sesión traduce los índices del motor a `id`, guarda la inestabilidad, selecciona el nudo y escribe un aviso como "N2 se puede mover en ux sin que nada lo impida (también se mueven N1, N3, N4)". La marca se borra al editar, abrir o calcular con éxito.
- `python/nervi/gui/vista2d.py`: el nudo inestable lleva un aro rojo y la etiqueta "inestable en ux"; los demás nudos del modo, un aro rojo punteado.
- `python/nervi/gui/ventana.py`: la barra de estado usa el mismo texto. Antes mostraba el mensaje del motor, que numera los nudos por índice interno (desde 0), así que no coincidía con los `N…` de la pantalla.

## Cómo se verificó

- `tests/test_gui.py`: el caso sin apoyos ahora comprueba la marca, la selección y que se borra al editar. Hay una prueba nueva con `id` 10, 20 y 30 distintos de los índices: una viga con rótula de más marca N20 en `uy` y los nudos {10, 20, 30}.
- Captura de la ventana con un pórtico biarticulado de viga articulada: aro en N2 y aros punteados en N1, N3 y N4.
- `pytest` (110), `ruff`.

## Decisiones tomadas

- La traducción de índice a `id` se hace en la sesión, no en el motor, porque los `id` son del formato `.nrv` y el motor no los conoce.
- Se selecciona el nudo para que el panel de la derecha muestre sus datos sin otro clic.

## Pendiente y problemas conocidos

- Todavía no se anima el modo de mecanismo; los valores están en `modos`.
- Firma DCO: firmado en nombre del usuario con la misma autorización de la entrada 2026-11-12-01.

## Para quien siga

- Animar o dibujar el modo con `MecanismoError.modos`, igual que la deformada.
