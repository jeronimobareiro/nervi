# 2026-11-28-07 · Paneles acoplables y distribuciones guardadas

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-czjd56`, PR #108
- **Fase de la hoja de ruta:** interfaz (pedido de personalizar la ventana)

## Qué se pidió

Etapa 5 del plan aprobado el 27/11/2026: poder personalizar la ventana. Acoplar, desacoplar, mover, ocultar y llevar los paneles a otro monitor, y que Nervi recuerde cómo quedó. Con PySide6 y sin bibliotecas de acople en C++ (Qt ADS quedó afuera por el pedido de tener todo en Rust y Python).

## Qué se hizo

- `python/nervi/gui/paneles.py` (nuevo): `crear_panel` (un `QDockWidget` cerrable, movible y flotante), `TituloPanel` (nombre, *Desacoplar* y *Cerrar*; doble clic desacopla), y guardar y recuperar la ventana y las distribuciones con nombre en las preferencias (`VERSION = 1`).
- `python/nervi/gui/ventana.py`:
  - la barra superior, la contextual y el riel pasan a `QToolBar` fijas;
  - la vista queda como widget central;
  - Estructura, Propiedades, Tablas y resultados y Asistente de IA pasan a paneles;
  - las herramientas de dibujo de los dos modos se mudan a una *Barra de dibujo* movible que se pone vertical a los costados;
  - *Ver > Paneles* con las casillas, *Guardar distribución…*, *Distribuciones guardadas* y *Restablecer distribución*;
  - la distribución se guarda al cerrar y se recupera al abrir.
  - El panel de tablas tiene ancho mínimo propio: antes el ancho de sus pestañas obligaba a una ventana de casi 2000 px; ahora alcanzan unos 1210 px.
- Íconos: `cerrar` pasa a en uso y se agrega `desacoplar` (la flecha que sale del recuadro, de la misma familia de trazo), en uso.
- `python/nervi/gui/estilo.py`: estilos de `QToolBar`, separadores de los paneles, título y botones de los paneles.

## Cómo se verificó

- `tests/test_gui_paneles.py` (6 pruebas): distribución de fábrica y ancho mínimo, desacoplar, acoplar, cerrar y volver a abrir desde el menú, asistente como panel con el ícono del riel al día, la distribución que se recupera al abrir otra ventana y *Restablecer*, distribuciones con nombre (guardar, aplicar, nombre vacío, borrar) y la barra de dibujo vertical a un costado.
- Las pruebas de la interfaz que ya había siguen en verde con la ventana nueva; capturas en los dos temas revisadas a ojo (`docs/img/paneles-acoplables.png`).
- `ruff` y la suite de Python en verde (las 2 de `test_vista3d.py` que fallan sin pantalla fallan igual sin este cambio).

## Decisiones tomadas

- `QDockWidget` de Qt en vez de Qt Advanced Docking System: alcanza para acoplar, apilar, desacoplar y llevar a otro monitor, y no suma C++.
- Barras superior, contextual y riel fijas: son la navegación de la aplicación y no tiene sentido perderlas. La barra de dibujo sí se mueve, porque es la que más espacio pide.
- Las tablas quedan abajo solo debajo de la vista (las esquinas son de los paneles laterales), como estaban antes.
- El ícono `desacoplar` es nuevo y se agregó sin muestra aparte, dentro de la muestra del plan; se puede cambiar el dibujo sin tocar nada más.

## Documentación actualizada

- `docs/ESTADO.md`, `README.md`, `sitio/index.md` y sus traducciones (en, pt, ru).
- `docs/diseno-interfaz.md`: §Paneles acoplables, con la captura.
- `docs/iconos.md` y la lámina; `docs/glosario.md`: panel acoplable y distribución.

## Pendiente y problemas conocidos

- La barra superior fija el ancho mínimo de la ventana en unos 1210 px.
- Con Wayland, mover un panel flotante a otro monitor depende del compositor.

## Para quien siga

- Un panel nuevo se crea con `crear_panel(self, clave, título, widget)` y se agrega a `self.paneles` y a la lista de `_llenar_paneles`. Si cambia la lista de paneles de manera que una distribución vieja no sirva, subir `paneles.VERSION`.
