# 2026-11-16-01 · Memoria de cálculo en PDF

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-3m3kuh`
- **Fase de la hoja de ruta:** Fase 4 (se adelanta sobre el motor 2D), issue [#28](https://github.com/jeronimobareiro/nervi/issues/28)

## Qué se pidió

Implementar el issue #28: memoria de cálculo en PDF, en español, para el análisis 2D que ya existe (modelo, cargas, resultados y diagramas), con dependencias compatibles con GPL-3.0 y pensada para que después se le sumen las verificaciones de diseño de vigas de hormigón armado, que se desarrollan en paralelo.

## Qué se hizo

- Paquete nuevo `python/nervi/memoria/`:
  - `documento.py`: estructura de la memoria independiente del formato (`Memoria`, `Capitulo`, `Parrafo`, `Tabla`, `Figura`, `Trazo`, `Rotulo`), `formatear` (cifras significativas, coma decimal) y `tabla_verificaciones`, la tabla estándar para los módulos de diseño (solicitación, resistencia, relación, cumple y artículo de la norma).
  - `analisis.py`: `memoria_de_calculo(modelo, resultados, ...)` arma los capítulos Alcance y método, Geometría (figura numerada, nudos, apoyos, resortes, barras y liberaciones), Materiales y secciones (agrupa barras con iguales E, A, I), Casos de carga (todos los tipos: uniforme, puntual, trapezoidal, térmica, momento, nodales y asentamientos), Combinaciones, Resultados (para cada caso y combinación: diagramas M, V, N y deformada, desplazamientos, reacciones, esfuerzos de extremo y extremos por barra con su posición) y Envolventes de esfuerzos y reacciones con la combinación que manda.
  - `dibujo.py`: geometría de las figuras en coordenadas del modelo (apoyos, resortes, articulaciones, diagramas del lado traccionado como en la interfaz, deformada con su factor de amplificación).
  - `plantilla.toml` + `plantilla.py`: todos los textos, el título, el pie, los campos de portada, el separador decimal y las cifras están en una plantilla TOML editable; una plantilla propia solo necesita las claves que cambia.
  - `pdf.py`: renderizador A4 con ReportLab: portada con datos del proyecto y aviso, índice con números de página, marcadores del PDF, capítulos numerados, tablas que se parten repitiendo el encabezado y figuras vectoriales en grilla de 2×2.
- Interfaz: acción **Exportar memoria de cálculo (PDF)…** (Ctrl+P, también en el menú y en el buscador de comandos). `Sesion.memoria()` rotula nudos y barras con los `id` de `modelo.json` y toma las unidades del proyecto.
- `examples/portico_simple.py` ahora expone `armar_modelo()` y `COMBINACIONES` (la salida al ejecutarlo es la misma) y `examples/memoria_portico_simple.py` genera su memoria. El CI la genera en cada corrida y la sube como artefacto `memoria-portico-simple` (lo que pide el issue para verificarlo).
- Dependencias: extra nuevo `nervi[memoria]` (`reportlab`, `tomli` en Python 3.10); `reportlab` también en el extra `gui` y en el workflow de publicación (con `--hidden-import nervi.memoria.pdf`); `pypdf` solo en `dev`, para leer el texto del PDF en las pruebas.
- README (es, en, pt, ru), portada y primeros pasos del sitio en los cuatro idiomas, y glosario (memoria de cálculo, plantilla, capítulo).

## Cómo se verificó

- `tests/test_memoria.py` (23 pruebas): formato de números, capítulos completos, que las tablas reproduzcan los resultados del motor (reacciones, M máx = 119,1 kN·m en x = 3 m de la viga del ejemplo con 1.2D+1.6L, desplazamientos), envolvente con la combinación que manda, combinaciones no resueltas con el modelo, todos los tipos de carga, nombres y unidades propios, plantilla propia, `tabla_verificaciones`, agregar un capítulo de diseño antes de Envolventes, momento positivo dibujado del lado traccionado (qL²/8 = 20 en una viga biapoyada), el PDF del ejemplo generado con `examples/memoria_portico_simple.py` y leído con `pypdf`, letras griegas con la fuente Symbol, y el doctest del módulo.
- `tests/test_gui.py`: exportar la memoria desde la ventana. `test_paleta_de_comandos` se ajustó porque "calcul" ahora también encuentra "Exportar memoria de cálculo"; la prueba sigue comprobando que Calcular es el primero.
- `pytest`: 160 pruebas en verde, incluidas las de la interfaz (se instaló `libegl1` en este entorno). `ruff check` y `ruff format --check` en verde. No se tocó Rust.
- Se revisaron a ojo las páginas del PDF del ejemplo (portada, geometría, cargas, resultados, envolventes).

## Decisiones tomadas

- **ReportLab** (BSD, de ReportLab Inc., https://www.reportlab.com/opensource/) para el PDF: es libre, compatible con GPL-3.0, maduro, y trae tablas que se parten entre páginas, índice y gráficos vectoriales sin depender de matplotlib. Alternativas consideradas: fpdf2 (LGPL-3.0, también compatible) y escribir con Qt (`QPdfWriter`), descartado porque obligaría a instalar la interfaz para generar una memoria desde un script.
- **Solo fuentes estándar de PDF** (Helvetica y Symbol): no se incrusta ni se distribuye ninguna fuente. Las letras griegas, flechas y ≤ ≥ se escriben con Symbol. Limitación: texto en alfabetos no latinos (por ejemplo, un nombre de proyecto en cirílico) no se ve; habría que incrustar una fuente libre (DejaVu) más adelante.
- **Estructura separada del formato.** El contenido es una lista de capítulos y bloques; el PDF es solo un renderizador. Así el módulo de diseño de vigas suma su capítulo con `memoria.agregar(Capitulo(...), antes_de=CAPITULOS["envolvente"])` y `tabla_verificaciones(...)` sin tocar este código, y más adelante se puede agregar otro formato (HTML, DOCX) sin rehacer el contenido.
- La clase se llama `Capitulo` y no `Seccion` porque en el glosario "sección" es la sección transversal.
- **Numeración desde 1** (N1, B1…) por defecto, que es lo que espera quien lee una memoria; el texto lo aclara. Desde la interfaz se usan los `id` del proyecto, y desde Python se pueden pasar nombres propios.
- **Coma decimal** por defecto (Paraguay y la mayoría de los países de habla hispana); se cambia en la plantilla con `decimal = "."`. Los datos de entrada se imprimen con 6 cifras significativas y los resultados con 4.
- La memoria no transcribe textos de normas: las verificaciones citan el artículo (`tabla_verificaciones` tiene la columna "Artículo").
- Las envolventes se calculan con los extremos de cada barra sobre las combinaciones, así funcionan también con combinaciones calculadas por superposición después de resolver.

## Pendiente y problemas conocidos

- Revisión del formato por un docente o profesional, como pide el issue.
- Capítulo de verificaciones de diseño: lo agrega el módulo de hormigón armado cuando exista, con `tabla_verificaciones`.
- Figura de cargas (flechas sobre la estructura): hoy las cargas van solo en tablas.
- Incrustar una fuente libre con más alfabetos, y opción de logo o membrete en la portada.
- El instalador con la memoria no se probó: el workflow de publicación instala ReportLab y agrega `nervi.memoria.pdf` como importación oculta, pero hay que comprobarlo en la próxima etiqueta.
- Firma DCO: los commits no están firmados. El usuario tiene que revisarlos y firmarlos (`git rebase --signoff origin/main`) o autorizar por escrito que el agente firme este trabajo en su nombre.

## Para quien siga

- Para sumar verificaciones de diseño a la memoria, mirá `test_agregar_capitulo_de_diseno` en `tests/test_memoria.py`: es el ejemplo mínimo.
- Los textos se cambian en `python/nervi/memoria/plantilla.toml`; el aspecto (colores, tamaños) en `ESTILOS` y `_TRAZOS` de `pdf.py`.
