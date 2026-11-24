# 2026-11-24-10 · Importar DXF con vista previa

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 6

## Qué se pidió

Importar la geometría de un pórtico desde un DXF, con vista previa antes de aplicar. Jerónimo aclaró que la importación tiene que funcionar sin ninguna IA conectada: es una función de Nervi, y la IA solo puede usarla como una herramienta más.

## Qué se hizo

- `python/nervi/importar/dxf.py` (nuevo, sin Qt, sin IA y sin bibliotecas externas): lee un DXF en texto (`LINE`, `LWPOLYLINE`, `POLYLINE`, la unidad de `$INSUNITS`, UTF-8 o Windows-1252) por capa, y arma nudos y barras sobre el modelo abierto. Une los puntos a menos de una tolerancia (en metros, con una grilla para que sea rápido), corta donde una línea llega a otra o la cruza, y también donde pasa por un nudo que el modelo ya tiene, reusa esos nudos y descarta las líneas repetidas, superpuestas o más cortas que la tolerancia. Las barras nuevas toman la sección de la última barra o, con el modelo vacío, una de hormigón de 30 x 30 cm en las unidades del modelo. Lo que no es línea (textos, cotas, círculos, bloques…) se cuenta en los avisos, igual que los tramos curvos de polilíneas, que se toman rectos.
- `python/nervi/gui/importar.py` (nuevo) y `ventana.py`: *Archivo › Importar DXF…* abre un diálogo con las capas y sus cantidades, la unidad (la del DXF o la que elija la persona), la tolerancia, llevar al origen y empotrar la base. A la derecha, el modelo que quedaría, con lo nuevo resaltado si ya había barras, cuánto se agrega y los avisos. *Importar* lo aplica con `Sesion.editar`: se deshace con Ctrl+Z y queda en el historial con origen `importador: DXF`.
- `python/nervi/ia/herramientas.py` y `servidor.py`: herramienta de la ventana `proponer_dxf`, que usa el mismo importador y deja el resultado como propuesta. No es de solo lectura.

## Cómo se verificó

- `tests/test_importar_dxf.py` (15): doctest, unidades declaradas y elegidas, sin unidad, T y cruces, tolerancia, cortas y repetidas, polilíneas cerradas y con arcos, `POLYLINE` con vértices, capas, base empotrada, suma a un modelo en otras unidades reusando nudos, corte en un nudo existente, sección por omisión convertida, DXF binario y Windows-1252.
- `tests/test_gui.py`: el diálogo sobre el ejemplo (resumen, resaltado, capas, botón inactivo sin líneas, importar, historial y deshacer) y el aviso con un DXF binario. `tests/test_ia.py`: `proponer_dxf` deja una propuesta y no cambia el modelo; también con el SDK de MCP 1.x.
- Capturas del diálogo en los dos temas con un pórtico de dos vanos y dos pisos en milímetros, con ejes, textos, cotas y círculos.
- Suite completa: 436 en verde y 4 omitidas.

## Decisiones tomadas

- Lector propio en vez de `ezdxf`: solo hacen falta líneas, y así no se suma una dependencia al instalador. Los DXF binarios se rechazan con un mensaje que dice cómo guardarlos en texto.
- La importación es una función de Nervi que no depende de la IA. El agente la puede pedir con `proponer_dxf`, pero solo deja una propuesta.
- El dibujo se toma como una elevación (X horizontal, Y vertical). Lo importado se **suma** al modelo abierto: para empezar de cero, se importa sobre un proyecto nuevo.
- La tolerancia por omisión es de 10 mm: une los extremos que no quedaron bien enganchados en el dibujo sin juntar nudos reales.

## Documentación actualizada

- `docs/agentes-ia.md` (`proponer_dxf`), `docs/diseno-interfaz.md` §Importar DXF, `docs/hoja-de-ruta.md` (etapa 6 hecha), `docs/glosario.md`, `docs/ESTADO.md` y los cuatro README.

## Pendiente y problemas conocidos

- Arcos, bloques (`INSERT`) y plantas en 3D no se importan. Tampoco secciones por capa: todas las barras nuevas llevan la misma sección.

## Para quien siga

- Una sección por capa (por ejemplo COLUMNAS y VIGAS) sería la mejora más útil. Iría como opción del diálogo y argumento de `importar`.
