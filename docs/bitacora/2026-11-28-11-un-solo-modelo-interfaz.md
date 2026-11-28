# 2026-11-28-11 · Un solo modelo en la interfaz: el edificio manda

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-pv0njt`
- **Fase de la hoja de ruta:** Fase 7, issue #74 (segunda parte: interfaz)

## Qué se pidió

Que *Edificio* y *Cálculo* dejen de parecer dos sesiones de dos estructuras distintas, y que la barra de etapas y las pestañas del panel inferior no se repitan. Se aprobó el 28/11/2026, con muestras en los dos temas, la opción "edificio manda, pórtico aparte": si el proyecto tiene edificio, el modelo de cálculo se genera solo y es de solo lectura; un proyecto sin edificio sigue siendo un pórtico plano armado a mano. Las etapas mandan sobre la ventana y Calcular resuelve el edificio en 3D y devuelve los resultados a cada viga y columna.

## Qué se hizo

- **Proyecto** (`nervi.proyecto`): `es_edificio` (el proyecto tiene modelo físico), `modelo_calculo()` (generado y guardado hasta que el edificio cambie), `calcular_edificio()` y `resultado_edificio()`. `calcular()` y `nombres_resultado()` siguen al edificio cuando lo hay; la revisión del modelo informa el modelo generado y sus avisos. Las combinaciones del edificio son `1.4D` y `1.2D+1.6L` (`idealizacion.COMBINACIONES`, ACI 318-19 §5.3.1).
- **Esfuerzos por elemento** (`ModeloCalculo.resumen`): por viga, columna o muro, cada esfuerzo al principio y al final del elemento y su máximo y mínimo sobre todas sus barras, más el cortante resultante máximo. Agrupa las estaciones de todas las barras con `numpy` (`lexsort` y `reduceat`), sin bucles por barra. `ResultadoCaso3D.diagramas` da las estaciones de todas las barras juntas.
- **Ventana** (`nervi.gui.ventana`): sin el selector *Edificio | Cálculo*; el modo sale del proyecto al abrir, al crear y con el ejemplo. *Archivo › Nuevo edificio* (Ctrl+N) y *Nuevo pórtico plano*. Selector *Vista*: *Planta* | *3D* en un edificio, *Frente* | *3D* en un pórtico. El panel inferior no tiene fila de pestañas de primer nivel: la etapa elegida muestra su página y solo sus pestañas (Geometría y Cargas reparten las tablas del pórtico; Análisis: Revisión, Modelo de cálculo y Dinámica; Resultados del edificio o del pórtico; Diseño). La Consola Python es un panel acoplable propio, desde Herramientas.
- **Tablas del edificio** (`nervi.gui.resultados_edificio`, nuevo): *Modelo de cálculo* (barras generadas, nudos, tipo, de qué elemento salen, tramo y brazos rígidos; solo lectura) y *Resultados* con *Por elemento* (Vigas · Columnas · Muros), Reacciones, Desplazamientos y Derivas de piso. Clic en una fila elige el elemento.
- **Visor 3D** (`nervi.gui.escena3d`, `nervi.gui.vista3d`): escena del edificio con *Mostrar* *Edificio* · *Cálculo* · *Ambos* (piezas con volumen, modelo de cálculo con brazos rígidos, diafragmas y empotramientos, o los dos), diagramas y deformada de todas las barras armados en bloque, y un clic en una barra que elige el elemento del edificio y lo resalta. `_lineas` y `_franjas` arman sus celdas en bloque (mismas mallas que antes, comprobado).

## Cómo se verificó

- `tests/test_idealizacion.py`: `resumen` da, elemento por elemento, exactamente lo que se lee con `ModeloCalculo.diagrama` (igualdad, sin tolerancia).
- `tests/test_proyecto.py`: con edificio, `calcular` da lo mismo que resolver el modelo generado a mano (desplazamientos con `rtol` 1e-12, reacciones de `L` bit a bit), cambiar el edificio invalida resultados y modelo, deshacer hasta sin edificio vuelve al pórtico.
- `tests/test_vista3d.py`: escena según *Mostrar*, cajas de columnas y vigas, estaciones del diagrama en el lugar del motor (corridas el brazo rígido, del lado del valor), dibujo con PyVista y la ventana: 3D del edificio, cálculo, *Mostrar*, clic que elige el elemento y brújula.
- `tests/test_gui_edificio.py`: el proyecto dice si es edificio o pórtico, *Nuevo edificio* y *Nuevo pórtico plano*, etapas al mando del panel inferior, cálculo del edificio con *Por elemento* igual al diagrama de la viga, reacciones, derivas y resultados desactualizados al cambiar el edificio. Las pruebas que miraban la pestaña de Revisión o de Dinámica en el panel inferior ahora la buscan dentro de Análisis.
- Tiempos: `resumen` y la escena 3D del edificio grande de `scripts/medir_modelo_calculo.py` se midieron aparte (ver el PR). El cálculo del pórtico plano no cambió.

## Decisiones tomadas

- El modo sale de que el proyecto tenga modelo físico, no de un control. Un proyecto viejo con edificio y pórtico a mano abre como edificio; el pórtico queda guardado en el archivo.
- Combinaciones fijas del edificio (`1.4D`, `1.2D+1.6L`) mientras el modelo físico no guarde las suyas; se dicen en la revisión y en la documentación.
- Diagramas 3D del plano `x-y` local (en vigas, la flexión vertical); el segundo plano queda para después. Números solo en vigas (M, V) o columnas y muros (N) y nunca con más de 300 barras, para que se lean.
- La dinámica y el diseño siguen siendo del pórtico plano: en un edificio, Análisis no muestra Dinámica y Diseño dice que llega después.

## Documentación actualizada

- `docs/diseno-interfaz.md` §Un solo modelo (nueva), §Modelo físico y §Visor.
- `docs/convenciones.md` §Modelo de cálculo generado: combinaciones del edificio, esfuerzos por elemento y diagramas en 3D.
- `docs/glosario.md`: esfuerzos por elemento, proyecto con edificio, mostrar edificio, cálculo o ambos.
- `docs/hoja-de-ruta.md` (#74), `docs/ESTADO.md`.
- `README.md` y sus traducciones (`README.en.md`, `README.pt.md`, `README.ru.md`) y la portada del sitio en los cuatro idiomas (`sitio/index.md`, `sitio/idiomas/*/index.md`).
- `CONTRIBUTING.md`, `AGENTS.md` y la plantilla del PR no cambian: no hay reglas ni controles nuevos.

## Pendiente y problemas conocidos

- Ajustes del modelo generado (apoyos y liberaciones), combinaciones propias del edificio, su análisis modal y su diseño.
- *Frente* y *Lateral* de un pórtico del edificio; diagramas del segundo plano local (`My`, `Vz`) en 3D.
- Las propiedades del elemento elegido todavía no muestran sus resultados (están en *Por elemento*).
- Las columnas circulares se dibujan en 3D como un prisma de lado `d`.
- Firma DCO: los commits van con `Signed-off-by` de Jerónimo, que lo autorizó por escrito para este PR ("firmalo", 28/11/2026; AGENTS.md §3.5).

## Para quien siga

- Leer `docs/diseno-interfaz.md` §Un solo modelo y `nervi.gui.ventana.ir_a_etapa` / `_mostrar_etapa`: la etapa decide la página del panel inferior.
- El cálculo del edificio pasa por `Proyecto.calcular_edificio`; lo que muestra la interfaz sale de `resultado_edificio()` y `ModeloCalculo.resumen`.
