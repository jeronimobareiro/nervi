# 2026-11-28-06 · Dibujar el modelo de cálculo con el mouse

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-czjd56`, PR #108
- **Fase de la hoja de ruta:** Fase 5 (edición gráfica, #31)

## Qué se pidió

Etapa 4 del plan aprobado el 27/11/2026: dibujar nudos, barras, apoyos y cargas en la vista 2D del modo *Cálculo*, con el enganche de la etapa 2 y la misma forma de trabajo que la planta del edificio. Todo en Rust y Python.

## Qué se hizo

- `python/nervi/edicion.py` (nuevo, sin Qt): `agregar_nudo` (si cae sobre una barra la parte), `agregar_barra` (usa o crea los nudos de los extremos y se parte en cada nudo por el que pasa, sin repetir tramos), `partir_barra` (liberaciones en sus extremos; cargas uniformes y térmicas a los dos tramos, puntuales y momentos al que les toca con `a` medida desde su nudo `i`, trapezoidales cortadas con los valores interpolados), `poner_apoyo` con los tipos de `APOYOS`, `caso`, `agregar_carga_nodal`, `agregar_carga_barra`, `quitar_nudo` y `quitar_barra` (con lo que depende de ellos), `propiedades_por_omision` (30 x 30 cm de hormigón en las unidades del modelo) y `tolerancia`.
- `python/nervi/gui/dibujo.py`: la base común `Dibujo` (enganche, trazo, Orto, entrada numérica, marca y cota) separada de `DibujoEdificio`; la vista se queda quieta desde el primer clic (`fijar_camara`).
- `python/nervi/gui/dibujo_calculo.py` (nuevo): `DibujoCalculo` (Nudo, Barra, Apoyo, Puntual, Repartida, Supr para borrar), `pintar_cargas` (flechas del caso elegido) y `PanelCalculo`.
- `python/nervi/gui/navegacion.py`: `Transformacion` (antes privada de la planta) y `Navegable.transformacion()`.
- `python/nervi/gui/vista2d.py`: encuadre por omisión con el modelo vacío, eventos al dibujo y Supr.
- `python/nervi/gui/ventana.py`: `_barra_dibujo` sirve para los dos lienzos; barras *Dibujar* y *Enganche* en *Cálculo*, F8 según el modo y el panel de la herramienta en lugar de Propiedades.
- Íconos `seleccionar`, `carga_puntual` y `carga_repartida` pasan a en uso (`seleccionar` ya se mostraba en la planta desde la etapa 3 sin estar marcado); `tests/test_iconos.py` suma los íconos de las dos barras *Dibujar*.

## Cómo se verificó

- `tests/test_edicion.py` (6 pruebas): propiedades por omisión en kN·m y N·mm, nudos creados y reusados, barra partida en nudos intermedios, liberaciones al partir, apoyos, cargas y quitar con lo que depende; y una viga simplemente apoyada con carga uniforme, puntual en ejes locales, trapezoidal parcial y momento, que da las mismas reacciones y desplazamientos (a 1e-12) antes y después de partirla.
- `tests/test_gui_dibujo_calculo.py` (6 pruebas, con clics simulados): barra y panel, pórtico dibujado con apoyos, carga repartida y nodal que se calcula y cumple el equilibrio (60 kN verticales, 15 kN horizontales), nudo en el medio que parte la barra y Ctrl+Z, largo escrito con Orto, apoyo que se saca con otro clic, Supr y el mensaje fuera de una barra.
- Capturas en los dos temas revisadas a ojo; la clara queda en `docs/img/dibujar-calculo.png`.
- `ruff`, pruebas de Python en verde (las de `test_vista3d.py` siguen fallando sin pantalla, igual que sin este cambio).

## Decisiones tomadas

- Las ediciones van en `nervi.edicion` y no en la interfaz, para probarlas sin Qt y usarlas desde Python o desde el agente de IA más adelante.
- Una barra se parte en los nudos por los que pasa, pero no donde cruza otra barra sin nudo: en un pórtico dos barras que se cruzan pueden no estar unidas. El enganche *Cruces* deja poner el nudo ahí con un clic.
- Cada lienzo recuerda sus enganches por separado; F8 cambia el Orto del modo que se ve.
- Un modelo inválido después del clic (por ejemplo, una barra que ya está o una carga nula) no cambia nada y deja el motivo en la barra de estado.

## Documentación actualizada

- `docs/ESTADO.md`, `README.md`, `sitio/index.md` y sus traducciones (en, pt, ru).
- `docs/diseno-interfaz.md`: §Dibujar en la vista 2D, con la captura.
- `docs/iconos.md` y la lámina.

## Pendiente y problemas conocidos

- Etapa 5: paneles acoplables con `QDockWidget` y distribuciones guardadas.
- Faltan herramientas para cargas trapezoidales, térmicas, resortes, articulaciones y desplazamientos impuestos (siguen en las tablas), y mover nudos arrastrando.

## Para quien siga

- Una herramienta nueva de la vista 2D es una clave en `HERRAMIENTAS_CALCULO`, una rama en `DibujoCalculo.fijar` que llama a `aplicar` con una función de `nervi.edicion`, y sus filas en `PanelCalculo`.
