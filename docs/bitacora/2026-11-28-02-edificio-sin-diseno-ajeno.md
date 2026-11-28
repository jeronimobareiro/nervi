# 2026-11-28-02 · El modo Edificio deja de mostrar el diseño del pórtico de cálculo

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-czjd56`
- **Fase de la hoja de ruta:** Fase 5 (interfaz) y Fase 7 (#73, modelo físico)

## Qué se pidió

Al probar el instalador de Windows, la pestaña Diseño en el modo *Edificio* mostraba las barras B1 a B3 del pórtico de cálculo y no las vigas del edificio. Es la etapa 0 del plan para dibujar con el mouse y tener paneles acoplables.

## Qué se hizo

- `python/nervi/gui/ventana.py`: en el modo *Edificio* se ocultan las pestañas Resultados, Diseño y Dinámica del panel inferior, que trabajan sobre el modelo de cálculo. Si una de ellas estaba a la vista, pasa a las tablas del edificio.
- Ir a las etapas Análisis, Resultados o Diseño, o a Dinámica, desde *Edificio* pasa a *Cálculo* y avisa en la barra de estado que el edificio todavía no genera su modelo de cálculo.

## Cómo se verificó

- Prueba nueva `test_edificio_no_muestra_resultados_ni_diseno_del_calculo` en `tests/test_gui_edificio.py`.
- `pytest tests/test_gui.py tests/test_gui_edificio.py tests/test_gui_cargas.py`: 59 pruebas en verde.

## Decisiones tomadas

- Ocultar las pestañas en vez de mostrarlas vacías: el mismo criterio que ya se usa para cambiar las tablas del modelo por las del edificio. Cuando exista el modelo de cálculo generado desde el edificio (#74), estas pestañas vuelven a mostrarse en *Edificio* con sus vigas y columnas.

## Documentación actualizada

- `docs/ESTADO.md`: el modo *Edificio* oculta Resultados, Diseño y Dinámica, y el plan del dibujo con el mouse espera el visto bueno de su muestra.
- README, sitio y hoja de ruta no cambian: no cambia lo que Nervi hace, solo deja de mostrar datos que no corresponden.

## Pendiente y problemas conocidos

- El plan por etapas (navegación con zoom y paneo, enganche en Rust, herramientas de dibujo del edificio y del cálculo, paneles acoplables) y su muestra visual esperan el visto bueno de quien mantiene el proyecto.

## Para quien siga

- La muestra visual del dibujo con el mouse se armó con una maqueta sobre la ventana real (no es código del producto). La etapa 1 (zoom, paneo y grilla en metros) es la que sigue.
