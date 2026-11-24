# 2026-11-24-02 · Resultados a precisión completa (`nervi.resultados`)

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 2

## Qué se pidió

Resolver el redondeo: la memoria de cálculo guarda sus tablas como texto con 4 cifras, así que no sirve como fuente de datos para revisar, comparar ni para que un agente de IA consulte resultados. Se pidió una salida con los números del motor sin redondear.

## Qué se hizo

- `python/nervi/resultados.py` (nuevo): `exportar(proyecto)` arma un diccionario `nervi-resultados` 1 con versión de Nervi y de los contratos del motor, fecha, unidades, `huella_modelo` (SHA-256 de `modelo.json` canónico) y, por caso y por combinación, desplazamientos, reacciones, fuerzas de extremo y diagramas por estación, con los `id` de nudos y barras del usuario. Suma `diseno` (cada verificación con solicitación, resistencia, relación, unidad y artículo) y `dinamica` (periodos, frecuencias, masa participante, factores de participación y espectros) solo si están al día. `guardar` escribe el JSON y rechaza valores no finitos diciendo dónde están; `leer` rechaza otros formatos y versiones más nuevas; `huella(modelo)` recalcula la huella.
- `Proyecto.resultados_completos()` y `Proyecto.exportar_resultados(ruta)`.
- `docs/formato-resultados.md` (nuevo) con el formato, también publicado en el sitio (`mkdocs.yml`, `scripts/preparar_sitio.py`).
- `tests/test_resultados.py` (nuevo, 6 pruebas).

## Cómo se verificó

- Ida y vuelta exacta: se escribe el archivo, se vuelve a leer y cada desplazamiento, reacción, fuerza de extremo y punto de diagrama de cada caso y combinación es igual (`np.array_equal`, sin tolerancia) al que dio el motor. Lo mismo para solicitación y resistencia de cada verificación de diseño y para los periodos.
- El valor guardado de una reacción es el del motor y difiere del texto redondeado de la memoria.
- La huella cambia si cambia el modelo y no depende del orden de las claves.
- Exportar no diseña ni analiza la dinámica por su cuenta (el `.nrv` no gana datos de diseño).
- Tiempos (mejor de 3, Python): pórtico de referencia de 130 barras, armar 0,016 s y escribir 0,087 s (2,7 MB); pórtico de 775 barras, armar 0,12 s y escribir 0,53 s (15,9 MB). Es serialización, no cálculo, por eso queda en Python según la regla de rendimiento.
- Suite completa: 342 pruebas en verde y 4 omitidas; `ruff` en verde.

## Decisiones tomadas

- JSON y no Markdown como fuente de verdad: `json` de Python escribe la representación más corta que identifica cada `float64`, así que vuelve bit a bit igual. Un Markdown legible para agentes puede derivarse después de este archivo o de la `Memoria`.
- Archivo aparte del `.nrv`: los resultados se derivan del modelo; guardarlos en el proyecto permitiría abrir resultados viejos. La huella dice a qué modelo corresponden.
- Combinaciones resueltas junto con el modelo (diagramas exactos con estaciones comunes), las mismas que usa la memoria, y no `Resultados.combinar`.
- La memoria en PDF sigue redondeando a 4 cifras: es para leer, y su formato está pendiente de revisión profesional.
- Firma DCO: Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (24/11/2026) que el agente agregue su `Signed-off-by` a los commits de este trabajo, con el nombre `bareirojero` y su correo `noreply` de GitHub.

## Documentación actualizada

- `README.md` y sus traducciones (`README.en.md`, `README.pt.md`, `README.ru.md`): nueva capacidad en "Qué hace hoy". `docs/formato-resultados.md` (nuevo), `docs/ESTADO.md`, `docs/hoja-de-ruta.md`, `docs/glosario.md`, `mkdocs.yml` y `scripts/preparar_sitio.py` para publicarlo en el sitio. Las páginas de `sitio/` (portada, descargar, primeros pasos) no cambian: todavía no hay comando en la interfaz.

## Pendiente y problemas conocidos

- Comando "Exportar resultados" en la interfaz (menú y buscador Ctrl+K).
- Esquema JSON formal en `docs/esquemas/`, como el de `modelo.json`.
- Pórtico espacial (`Modelo3D`): todavía no tiene proyecto ni interfaz; cuando los tenga, el formato suma sus resultados en una versión nueva.

## Para quien siga

- Siguiente etapa de la integración: deshacer, rehacer y propuestas de cambio en `nervi.proyecto`; después, el servidor MCP de solo lectura, que puede publicar este JSON como recurso.
