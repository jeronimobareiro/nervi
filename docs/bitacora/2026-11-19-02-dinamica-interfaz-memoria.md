# 2026-11-19-02 · Modos y espectros en la interfaz y en la memoria de cálculo

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-be257p`
- **Fase de la hoja de ruta:** Fase 2b, dinámica y sismo · issues [#16](https://github.com/jeronimobareiro/nervi/issues/16), [#17](https://github.com/jeronimobareiro/nervi/issues/17) y [#18](https://github.com/jeronimobareiro/nervi/issues/18) (llevar a la interfaz lo que hizo la entrada 2026-11-18-01)

## Qué se pidió

Que el análisis modal y espectral de la entrada 2026-11-18-01 se vea: periodos, masa participante y formas modales (dibujadas y animadas) y resultados de espectros en la interfaz, y un capítulo de análisis dinámico en la memoria PDF. En el mismo hilo se pidió una muestra en PNG de una carátula nueva para la memoria, que se entregó aparte y no entra en este aporte hasta que el usuario la apruebe.

## Qué se hizo

- `python/nervi/dinamica_plana.py` (nuevo): la interfaz trabaja con el pórtico plano, así que el plano se lleva al plano XZ de un `Modelo3D` (`modelo_espacial`) y se usa el motor de `nervi.dinamica`. `modal(modelo, masas, gravedad, n_modos)` devuelve `ResultadosModalPlano` (periodos, masa total, efectiva y participante en X e Y, `formas()`, `modos()` como resultados del plano y `espectro()`), y `ResultadoEspectroPlano` es un resultado del plano con cortante basal, `Sa` y `Γ` por modo. Cada modo se dibuja como el resultado de cargar el modelo con `ω² M φ` (con masa concentrada da exactamente `φ` y sus diagramas), escalado a traslación máxima 1.
- `python/nervi/formato/dinamica.py` (nuevo): módulo `dinamica` versión 1 del `.nrv` (`dinamica.json`, §4c de `formato-nrv.md`): casos de masa con su factor, cantidad de modos y espectros con nombre, dirección X o Y, CQC o SRSS, amortiguamiento y puntos `[T, Sa/g]`. `contenedor.py` lo lee, lo valida y lo escribe solo si el proyecto lo tiene, como `diseno`.
- Interfaz:
  - `gui/sesion.py`: `dinamica`, `editar_dinamica`, `analizar_dinamica` y `ResultadosDinamica`. Los modos (`Modo 1`, `Modo 2`…) y los espectros se suman al selector de resultados, así que las vistas 2D y 3D, el inspector y las tablas los muestran como cualquier caso. Editar el modelo los desactualiza.
  - `gui/dinamica.py` (nuevo): pestaña **Dinámica** con la tabla de masa por caso, la cantidad de modos, el editor de espectros (nombre, dirección, combinación, amortiguamiento y puntos, con un gráfico de `Sa/g` y los periodos de los modos), la tabla de modos (T, f y masa participante y acumulada en X e Y, en rojo si no llega al 90 %) y el cortante basal de cada espectro. Elegir un modo muestra su deformada; elegir un espectro, su momento. **Animar modo** hace oscilar la forma en la vista 2D (`Vista2D.fase`).
  - `gui/ventana.py`: la pestaña, el comando "Análisis modal y espectral" en el buscador y la animación.
- `python/nervi/memoria/dinamica.py` (nuevo): capítulo "Análisis dinámico" con el método, los casos de masa y la masa total, la tabla de periodos y masa participante (con aviso si no llega al 90 %), las formas de hasta 6 modos y, por espectro, sus datos, la curva `Sa/g` con `T1` marcado, la tabla de puntos, el cortante basal por modo y combinado, los diagramas `|M|`, `|V|`, `|N|` y los desplazamientos, reacciones y esfuerzos máximos. La sesión lo agrega a la memoria antes del capítulo de diseño si el proyecto tiene datos de dinámica con masa.
- Documentación: `formato-nrv.md` (§4c, módulo en la tabla y en el historial), `convenciones.md` (§Dinámica, pórtico plano), glosario, `tests/datos/nrv/README.md`, README en los cuatro idiomas y portada y primeros pasos del sitio en los cuatro idiomas.

## Cómo se verificó

- `tests/test_dinamica_plana.py` (10 pruebas):
  - Voladizo con masa en la punta: `T = 2π √(m h³ / 3EI)`, modo axial `2π √(m h / EA)`, masa participante 100 % en X y en Y, y espectro con `V = m Sa`, `M = V h` en la base y en el diagrama, y `u = Sa / ω²`.
  - Edificio de cortante de dos pisos con vigas casi rígidas: `ω²` cerradas, formas con el número de oro, `Γ²` cerrado, SRSS con espectro constante igual a `Sa √(Σ Mef²)` y CQC cerca de SRSS.
  - Cada modo como resultado del plano: traslación máxima 1, misma forma que el modo normalizado y reacciones que equilibran `ω² M u`.
  - La conversión al plano XZ resuelta con el motor espacial da los mismos desplazamientos, reacciones, fuerzas de extremo y diagramas que el motor plano, con articulación, resorte, barra dibujada de derecha a izquierda y cargas locales y globales, uniformes, puntuales, trapezoidales y nodales con momento.
  - Masa desde cargas en una viga inclinada de derecha a izquierda (local, global y puntual axial; la térmica no aporta) contra la resultante vertical / g.
  - Formato: errores de validación con su ruta, ida y vuelta, y el archivo de referencia nuevo `tests/datos/nrv/dinamica-v1.nrv` (con su `esperado.json`), que también corre en `test_formato_compatibilidad.py`.
  - Capítulo de la memoria: subcapítulos, texto del PDF y aviso de masa insuficiente.
- `tests/test_gui.py` (4 pruebas nuevas): sin masa avisa; flujo completo desde el panel (factores, modos, espectro, análisis, elegir modo y espectro, animación y desactualización al editar); guardar, abrir y memoria con el capítulo antes del de diseño; el modo en la escena 3D.
- Capturas de la interfaz con un pórtico de tres pisos y dos vanos (en el PR).
- `pytest`: 308 pruebas en verde. `ruff check` y `ruff format --check`, en verde. El motor Rust no cambió (`cargo fmt`, `clippy` y `cargo test -p nervi-core` se corrieron igual; detalle en el PR).

## Decisiones tomadas

- **El pórtico plano usa el motor espacial** en lugar de un modal plano propio: el motor 3D ya está verificado y la equivalencia de ejes la prueba `portico_plano_en_xz_coincide_con_el_motor_plano` (Rust) y ahora también la prueba de conversión en Python. Un modal plano en Rust queda como mejora de rendimiento si hace falta.
- **Módulo `.nrv` propio (`dinamica`)** en lugar de subir la versión de `modelo`, como pide AGENTS.md para lo que agrega una fase nueva. `formato-nrv.md` §4.2 decía que masas y espectros irían en `modelo`; se corrigió.
- **Espectros en `Sa/g`** en el archivo y en la interfaz (así se dan los espectros de diseño); la API de Python sigue en unidades de aceleración del modelo, como `nervi.dinamica`.
- **Masa solo desde los casos**, concentrada en los nudos y en X e Y: es lo habitual para la masa sísmica y no pide datos nuevos. Las masas nodales sueltas están en la API (`masas_nodales`) pero no en la interfaz todavía.
- La forma modal se escala a traslación máxima 1 para dibujarla; sus esfuerzos se muestran pero solo indican la forma.
- La animación solo está en la vista 2D: en la 3D, redibujar VTK en cada cuadro es caro; ahí se ve la forma fija.
- La carátula nueva de la memoria se mostró como PNG en el hilo y no se integró hasta tener la aprobación del usuario.

## Pendiente y problemas conocidos

- Sin diafragma rígido (#14, en otro hilo), las vigas con masa repartida a sus extremos tienen modos verticales que aparecen en la tabla; en el pórtico plano la masa vertical va en los nudos, así que también salen modos axiales de las columnas.
- Espectros normativos, `R`, combinación de direcciones y escalado del cortante basal (#20); combinar el sismo con las cargas gravitatorias para diseñar.
- Pórtico espacial en la interfaz (el panel trabaja con el plano), masas nodales en la interfaz, animación en el visor 3D.
- La carátula de la memoria: muestra entregada, falta la aprobación del usuario.
- Firma DCO: pendiente; se pidió al usuario que confirme si autoriza firmar en su nombre, como en el PR #57.

## Para quien siga

- Empezar por el docstring de `python/nervi/dinamica_plana.py`, `docs/convenciones.md` §Dinámica (pórtico plano) y `formato-nrv.md` §4c.
- Lo natural después: espectro de la norma elegida (#20) sobre `formato.dinamica` (por ejemplo un generador de puntos por zona y suelo), y la dinámica del pórtico espacial cuando el visor 3D muestre `Modelo3D`.
