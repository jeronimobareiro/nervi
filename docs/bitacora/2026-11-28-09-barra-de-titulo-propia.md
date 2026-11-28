# 2026-11-28-09 · Barra de título propia

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-fkwaml`, PR #110, sobre la rama del PR #108 (que ya incluye el visor único, entrada 2026-11-28-08)
- **Fase de la hoja de ruta:** interfaz de escritorio (pulido, sin issue propio)

## Qué se pidió

Que la barra de título gris del sistema deje de verse de otro color y que toda la ventana sea de Nervi, con los controles del sistema dentro de la ventana, en Windows y Linux. Se mostró una muestra en los dos temas y Jerónimo eligió la barra propia, acordando Buscar y Calcular con el hilo que unifica los modos Edificio y Cálculo.

## Qué se hizo

- `python/nervi/gui/marco.py` (nuevo): `BotonesVentana` (*Minimizar*, *Maximizar* / *Restaurar*, *Cerrar*) y `Marco`, que quita el marco del sistema y hace de la fila superior la barra de título. En Windows atiende `WM_NCCALCSIZE`, `WM_NCHITTEST` y los mensajes del mouse fuera del cliente con `ctypes` para conservar Snap, el menú de Snap sobre *Maximizar*, la sombra y las esquinas redondeadas. En Linux usa `startSystemMove` y `startSystemResize` con un margen de 5 px y una línea de 1 px.
- `ventana.py`: la fila superior mide 40 px y lleva los botones de la ventana; `nativeEvent` y `paintEvent` delegan en el marco. Buscar pasa a "Buscar…  Ctrl K" (180 px), con el nombre completo en la ayuda y el texto accesible.
- `estilo.py`: tokens `cerrar_ventana`, `cerrar_ventana_presionado` y `sobre_cerrar_ventana`, y estilos `boton_ventana`, `boton_cerrar_ventana` y `separador_ventana`.
- `iconos.py`: íconos `minimizar`, `maximizar` y `restaurar` (en uso); `cerrar` suma el uso en la barra.
- `ajustes.py`: preferencia *Apariencia › Barra de título* (la de Nervi o la del sistema), que se aplica al volver a abrir.

## Cómo se verificó

- `tests/test_gui_marco.py` (7): barra propia por defecto y del sistema, maximizar y restaurar, cerrar, bordes, qué partes arrastran y la respuesta a `WM_NCHITTEST` simulada (bordes, `HTMAXBUTTON`, `HTCAPTION`, `HTCLIENT`).
- `pytest` sin `test_vista3d.py`: 581 pasan (ya con el visor único de la rama base). Ese archivo no corre en este entorno sin VTK. `ruff check` y `ruff format --check` en verde. No toca Rust ni el cálculo.

## Decisiones tomadas

- En Windows la ventana sigue siendo una ventana con marco para el sistema (no un `FramelessWindowHint` puro), porque así se conservan Snap, la sombra y las animaciones sin reimplementarlos. Sin bibliotecas en C++.
- El rojo de *Cerrar* es un token del tema, igual en los dos temas, porque es la señal que la persona ya conoce del sistema.
- Se descartó teñir la barra del sistema (solo Windows 11, y la fila extra seguía).
- **Firma DCO:** Jerónimo Bareiro autorizó por escrito en el hilo del proyecto, el 2026-11-28 a las 12:50 UTC ("firmalo por mi y mergea esta"), que el agente firme en su nombre el commit de este PR. Se firmó como `Jerónimo Bareiro <345933350+bareirojero@users.noreply.github.com>`, su correo `noreply` de GitHub, como en el PR #108.

## Documentación actualizada

- `docs/diseno-interfaz.md` §Barra de título propia, con captura `docs/img/barra-titulo.png`.
- `docs/iconos.md` y la lámina (`docs/img/iconos-claro.png` y `-oscuro.png`), `docs/glosario.md`, `docs/ESTADO.md`.
- README, sitio y hoja de ruta no cambian: no cambia lo que Nervi calcula ni cómo se instala.

## Pendiente y problemas conocidos

- Falta probar en Windows 10 y 11 reales: arrastre, Snap, el menú de Snap sobre *Maximizar*, la sombra y maximizar con pantallas de distinta escala.
- En Linux, sin compositor, la ventana sin marco no tiene sombra.
- Cambiar la preferencia se aplica al volver a abrir Nervi.

## Para quien siga

- Todo está en `nervi.gui.marco`. Si una zona nueva de la fila superior tiene que arrastrar la ventana, pasala a `Marco` en `*arrastre`; las etiquetas ya arrastran solas.
