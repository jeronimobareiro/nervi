# 2026-11-19-03 · Sistema de diseño de la interfaz con tema claro y oscuro

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-dz1fp5`
- **Fase de la hoja de ruta:** interfaz de escritorio preliminar (en paralelo a las fases)

## Qué se pidió

Saber por qué los desplegables y campos numéricos de la interfaz se veían "como Windows 98" y tener un diseño integral, más actual, de ventanas, desplegables, campos, botones y pestañas, eligiendo entre varias propuestas antes de implementarlo.

## Qué se hizo

- **Causa:** `estilo.py` daba borde y fondo a `QComboBox` y `QDoubleSpinBox` pero no estilaba sus partes (`::drop-down`, `::down-arrow`, `::up-button`, `::down-button`). Con una hoja a medias Qt dibuja esas partes con el relieve biselado de los estilos viejos. Además la hoja se aplicaba solo a la ventana principal.
- Se mostraron cuatro direcciones (claro preciso, nocturno con los colores de la marca, papel técnico y suave) renderizando controles reales de Qt. Se eligió el claro como tema por defecto y el nocturno como tema oscuro.
- `python/nervi/gui/estilo.py` reescrito como sistema de diseño: `Tema` (tokens de color, radio, alto y tamaño de letra), temas `CLARO` y `OSCURO`, `qss(tema)` con la hoja completa (botones primario, secundario, fantasma y peligro, control segmentado, etapas, campos, desplegables abiertos y cerrados, campos numéricos, casillas, opciones, deslizador con tirador rectangular, pestañas, tablas, árboles, barras de desplazamiento, menús, ayudas, avisos y barra de progreso), `iconos(tema)` que genera las flechas y marcas en SVG con los colores del tema, y `aplicar(app, tema)` que instala Fusion, la hoja en toda la aplicación y un filtro de eventos que da a cada desplegable un `QStyledItemDelegate` (el de Fusion ignora la hoja en las opciones) y margen al texto de los campos numéricos.
- Las constantes de módulo (`estilo.PANEL`, `estilo.ACENTO`, `estilo.ESTRUCTURA`…) siguen existiendo y cambian con el tema. `vista2d.py` y `tablas.py` dejaron de usar colores fijos (rayado de apoyos, cajas de valores, ayuda del cursor, colores de las tablas de resultados).
- `ventana.py`: **Tema claro** y **Tema oscuro** en el menú del logo (también en el buscador Ctrl+K), recordados con `QSettings` (`interfaz/tema`); al cambiar se repintan la vista 2D, las tablas, el panel de propiedades y el visor 3D. `app.py` usa `estilo.aplicar`.
- Documentación: línea de diseño en `docs/diseno-interfaz.md` (enlazada desde `AGENTS.md` para que la sigan los próximos aportes), glosario (tema de la interfaz) y "Primeros pasos" del sitio en los cuatro idiomas.

## Cómo se verificó

- `tests/test_estilo.py` (nuevo, 3 pruebas): la hoja estila las partes de los controles compuestos, los íconos se generan con los colores del tema y `aplicar` instala la hoja, el delegado de los desplegables y el margen de los campos numéricos.
- `tests/test_gui.py` (23 pruebas) en verde con el estilo nuevo.
- Capturas de la ventana real sin pantalla en los dos temas (etapas Resultados con el desplegable abierto y Diseño) y de una hoja con todos los controles, revisadas por el usuario.

## Decisiones tomadas

- Hoja de estilos generada desde tokens en lugar de un tema de terceros (qt-material, qdarkstyle): no suma dependencias y deja el diseño en el repositorio.
- Los íconos SVG se escriben en una carpeta temporal por tema porque la hoja de Qt solo toma imágenes de archivos o recursos compilados; así no hace falta compilar recursos ni cambiar el empaquetado.
- La lista abierta del desplegable va con esquinas rectas: es una ventana aparte y con esquinas redondeadas asomaban las de la ventana.
- No se fuerza una tipografía: se usa la del sistema, como antes.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-19 a las 12:31 UTC ("Te doy el ok para firmar", en respuesta al pedido de firma de este PR), que el agente firme los commits de este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Pendiente y problemas conocidos

- El visor 3D cambia de colores con el tema, pero no se pudo probar acá (VTK no está en el entorno).
- La pestaña Dinámica (PR #58, en curso) va a tomar el estilo nuevo sin cambios, porque la hoja se aplica a toda la aplicación; conviene revisarla en los dos temas al integrar ambos.
- Probar el tema oscuro en Windows y macOS reales (diálogos nativos de abrir y guardar archivos no toman la hoja).

## Para quien siga

- Leé `docs/diseno-interfaz.md` antes de tocar la interfaz. Los colores nuevos van como tokens de `Tema`, nunca fijos en los widgets.
