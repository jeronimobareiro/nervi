# 2026-11-26-01 · Modelo físico en la interfaz: modo Edificio, tablas y gestor de plantas

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-du9lvx`
- **Fase de la hoja de ruta:** Fase 7, issue #73 (segunda parte, primera de dos entregas de la interfaz)

## Qué se pidió

Editar el modelo físico (#73) desde la interfaz, en dos PR: en este, el selector Edificio | Cálculo, la planta por piso, el árbol, tablas y propiedades editables, un gestor de plantas y flechas para subir y bajar de nivel en la vista 2D; en el siguiente, las herramientas de dibujo con el mouse (con #31).

## Qué se hizo

- `python/nervi/gui/edificio.py` (nuevo):
  - `EstadoEdificio`: piso que se ve, elemento elegido y `aplicar`, la única puerta de los cambios. Valida el modelo físico entero sobre una copia y lo guarda en la sesión con deshacer. Si algo no vale, avisa el motivo y no cambia nada.
  - `PlantaEdificio`: la planta de un piso con ejes, losas, vigas, muros y columnas, y elección con un clic.
  - `filas_arbol`, `TablasEdificio` (con `TablaFisico` y `EditorFisico`), `PropiedadesEdificio` y `GestorPlantas`.
- `python/nervi/gui/ventana.py`:
  - Segmento *Edificio | Cálculo* en la barra contextual. En *Edificio* se ven *Planta*, un botón con ícono de edificio que abre el gestor de plantas y chevrones en grupo para subir y bajar (Re Pág y Av Pág, activas solo en ese modo); ícono y chevrones elegidos por Jerónimo Bareiro el 26/11/2026 entre muestras (pedido de Jerónimo Bareiro el 26/11/2026, en lugar de un botón con texto).
  - Pilas para la vista, el árbol y las propiedades, y una pestaña *Edificio* en el panel inferior que reemplaza a *Modelo*.
  - *Plantas* en el menú Modelo y los dos modos en el menú Ver.
  - Barra de estado con las cantidades del edificio.
- `python/nervi/gui/arbol.py`:
  - Íconos de pisos, ejes, columnas, vigas, losas, muros y materiales.
  - `Fila.ref` y `mostrar_filas`.
  - Los eventos `edificio` y `tabla_edificio`.
- `python/nervi/proyecto.py` y `gui/sesion.py`: evento `fisico` y señal `fisico_cambiado`, también al abrir, al empezar un proyecto nuevo, al deshacer y al rehacer.
- `python/nervi/fisico.py`:
  - `editar`, `elementos_en_piso`, `quitar_piso` (que quita lo que usa el piso), `cambiar_nivel` (con `mover_arriba`), `piso_de_abajo` y `copiar_piso`.
  - Cada uno valida todo el modelo y, si falla, no cambia nada.
- `examples/edificio_fisico.py`: las vigas tienen nombres únicos (V101 a V307). Antes, las de cada piso se llamaban igual.

## Cómo se verificó

- `tests/test_fisico_edicion.py` (7 pruebas): cubre los métodos nuevos de `ModeloFisico`, que un cambio inválido no modifique el modelo y la ida y vuelta después de copiar.
- `tests/test_gui_edificio.py` (10 pruebas):
  - el cambio de modo y la planta inicial;
  - ▲▼, Av Pág y el desplegable;
  - la elección con clic en la planta (viga, columna, losa y vacío) y desde el árbol;
  - editar, agregar y eliminar en la tabla, con deshacer;
  - agregar el primer piso y la primera columna en un proyecto vacío;
  - las propiedades editables, con un contorno inválido que se rechaza;
  - el gestor de plantas completo (agregar, entrepiso con mover arriba, copiar y quitar con y sin confirmar), con *Aceptar* como un solo Ctrl+Z y *Cancelar* sin cambios.
- `pytest` completo: 498 pasan y 4 se saltean. `ruff check` y `ruff format --check` en verde.
- Capturas reales de la ventana y del gestor en los dos temas, revisadas antes del PR.
- No cambia Rust ni ningún cálculo que recorra barras, nudos o combinaciones, así que no se corrió `cargo` ni el banco de tiempos.

## Decisiones tomadas

- La edición va en dos PR: este con tablas, propiedades y gestor de plantas; el siguiente con las herramientas de dibujo y la referencia a objetos (#31). Decisión de Jerónimo Bareiro del 25/11/2026.
- El gestor de plantas y las flechas ▲▼ fueron pedidos y aprobados por Jerónimo Bareiro el 25 y el 26/11/2026, con muestras en los dos temas (`docs/diseno-interfaz.md` §Modelo físico).
- Las plantas tipo (pisos vinculados que cambian juntos) se dejan para después porque cambian el formato `.nrv`.
- Copiar una planta lleva las columnas y los muros del piso de abajo del destino al destino. Por eso no se copian columnas a la planta más baja.
- El gestor trabaja sobre una copia del modelo. *Aceptar* lo aplica todo como un solo paso de deshacer.
- Quitar un piso quita lo que lo usa (vigas y losas del piso, y columnas y muros que nacen o terminan en él), después de confirmarlo. En la API, `quitar` sigue sin quitar un piso en uso.
- Sin tres puntos ("…") en los nombres de menús y botones que abren una ventana: van solo con su nombre (*Abrir*, *Guardar como*, *Preferencias*, *Plantas*). Decisión de Jerónimo Bareiro del 26/11/2026; se aplicó a las 9 entradas que los tenían. Los textos de ejemplo de los campos de búsqueda conservan el "…".
- Re Pág y Av Pág cambian de planta solo en el modo *Edificio*. En *Cálculo* quedan para las tablas.
- **Firma DCO:** Jerónimo Bareiro autorizó por escrito, en el hilo del proyecto el 26/11/2026 ("Cuando tengas todo hecho, firmalo a mi nombre"), firmar este trabajo a su nombre. Se usó su correo `noreply` de GitHub (AGENTS.md §3.5).

## Documentación actualizada

- `docs/diseno-interfaz.md`: sección nueva *Modelo físico*, con la captura `docs/img/modelo-fisico.png`.
- `docs/ESTADO.md`: el modelo físico en "Qué funciona", la visión, la cantidad de pruebas y los próximos pasos.
- `docs/hoja-de-ruta.md`: avance de #73.
- `docs/glosario.md`: planta y altura de entrepiso.
- `README.md` y sus traducciones: el modo *Edificio* en "Qué hace hoy".
- `sitio/index.md` y sus traducciones (en, pt, ru): el modelo físico en "Qué hace hoy".

## Pendiente y problemas conocidos

- Dibujo con el mouse: ejes, columnas, vigas, losas y muros, con referencia a objetos (segundo PR, con #31).
- Un muro que atraviesa varios pisos se dibuja solo en la planta de su piso de arriba (`en_piso`). Conviene mostrarlo también, más tenue, en las plantas intermedias.
- Plantas tipo, el modelo de cálculo generado desde el físico (#74) y las propuestas de agentes sobre el modelo físico (módulo `historial`).

## Para quien siga

- Leé `docs/diseno-interfaz.md` §Modelo físico y `python/nervi/gui/edificio.py`. Para las herramientas de dibujo conviene sumar un modo de herramienta a `PlantaEdificio` (usando `transformacion().a_modelo`) y crear cada elemento con `EstadoEdificio.aplicar`, como hacen las tablas.
