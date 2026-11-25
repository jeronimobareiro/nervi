# 2026-11-25-01 · Modelo físico del edificio: datos, módulo `.nrv` y API de Python

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-du9lvx`
- **Fase de la hoja de ruta:** Fase 7, issue #73 (primera parte)

## Qué se pidió

Empezar el modelo físico (#73): que Nervi represente la estructura como pisos, ejes, vigas, columnas, losas y muros con su sección, material y contorno, con módulo propio en el `.nrv` y API de Python. La edición en la interfaz queda para después porque depende de #31.

## Qué se hizo

- `python/nervi/formato/fisico.py`: módulo `fisico` 1 del `.nrv` (`fisico.json`) con su validación: `id` y referencias, pisos en distinto nivel, columnas y muros con el piso de arriba más alto que el de abajo, materiales de hormigón (`fc`) y acero (`fy`, `fu ≥ fy`), secciones rectangulares y circulares, losas con contorno simple (prueba exacta de cruce de segmentos) y con área, losas y muros solo de hormigón, nombres únicos en pisos, ejes, materiales y secciones. Cada error dice archivo, ruta y motivo.
- `python/nervi/formato/contenedor.py`, `__init__.py` y `migraciones.py`: el módulo `fisico` (no requerido) se lee, se valida y se escribe solo si el proyecto lo tiene; `Documento.fisico`. Se sumaron a `MIGRACIONES` las entradas vacías de `historial` y `fisico`.
- `python/nervi/fisico.py`: `ModeloFisico`, con `agregar_piso`, `agregar_eje`, `agregar_material`, `agregar_seccion`, `agregar_columna`, `agregar_viga`, `agregar_losa`, `agregar_muro` y `quitar` (que no quita un piso, material o sección en uso); consultas `pisos_ordenados`, `en_piso`, `nivel`, `altura_columna`, `largo_viga` y `area_losa`; `a_json` y `desde_json` con ida y vuelta exacta. Un elemento inválido no cambia el modelo.
- `python/nervi/proyecto.py`: `Proyecto.fisico` y `editar_fisico`, con deshacer y rehacer. Por ahora lo edita solo la persona; las propuestas de agentes e importadores siguen siendo del modelo analítico (el módulo `historial` no admite la parte `fisico` todavía).
- `examples/edificio_fisico.py`: el edificio de `edificio_diafragma_3d.py` (2 × 1 vanos, 3 pisos) como modelo físico, con 18 columnas, 21 vigas, 6 losas macizas y un muro; se guarda y se vuelve a abrir igual.
- Archivo de referencia nuevo `tests/datos/nrv/fisico-v1.nrv` y su `fisico-v1.esperado.json` (§6.3).
- Issues nuevos por decisión de Jerónimo Bareiro de hoy: #100 (perfiles conformados en frío, AISI S100, Fase 9), #101 (losas nervadas) y #102 (losas pretensadas), Fase 10.

## Cómo se verificó

- `tests/test_fisico.py` (43 pruebas): criterio de salida de #73 (edificio de 3 pisos con losas y muros que se guarda y se vuelve a abrir igual, con los mismos bytes de `fisico.json` al guardar otra vez), consultas, elementos inválidos que no cambian el modelo, rutas de error de `validar`, archivo con referencia rota que no se abre, `quitar` con referencias, deshacer y rehacer en `Proyecto` y el ejemplo.
- `tests/test_formato_compatibilidad.py`: `fisico-v1.nrv` se abre, da los mismos resultados del modelo analítico y su `fisico.json` es el esperado.
- `pytest` completo: 481 pasan y 4 se saltean. `ruff check` y `ruff format --check` en verde.
- No cambia Rust ni ningún cálculo que recorra barras, nudos o combinaciones (la validación y las consultas son de datos), así que no se corrió `cargo` ni el banco de tiempos.

## Decisiones tomadas

- Módulo propio `fisico`, separado de `modelo.json` (regla de `AGENTS.md`: lo que agrega una fase nueva va en un módulo propio). Los dos modelos no se refieren uno al otro hasta #74.
- Unidades: coordenadas y niveles en la unidad de longitud del modelo físico (`m`, `cm` o `mm`); secciones y espesores en mm y resistencias en MPa, como en `diseno.json`.
- El nivel de un piso es la cota de la cara superior de su losa; las vigas cuelgan de ese nivel.
- La versión 1 tiene solo losas macizas y secciones rectangulares y circulares. Nervadas, steel deck, pretensadas y perfiles de acero entran subiendo la versión del módulo, con su migración.
- La validación del formato no controla superposiciones entre elementos (una losa que se sale de sus vigas): eso corresponde a la revisión del modelo.
- Losas después de las macizas: nervadas, mixtas con steel deck y pretensadas; los perfiles conformados en frío entran en la Fase 9 después de los laminados. Decisiones de Jerónimo Bareiro del 25/11/2026 en el hilo del proyecto.
- **Firma DCO:** Jerónimo Bareiro autorizó por escrito, en el hilo del proyecto el 25/11/2026, firmar este trabajo a su nombre; se usó su correo `noreply` de GitHub (AGENTS.md §3.5).

## Documentación actualizada

- `docs/formato-nrv.md`: título, árbol del contenedor, tabla de módulos, §4f nueva, §8 e historial del esquema (§9).
- `docs/ESTADO.md`: modelo físico en "Qué funciona", visión, cantidad de pruebas, hoja de ruta con los hitos confirmados, #5 y #9 por cerrar, próximos pasos y decisiones abiertas.
- `docs/hoja-de-ruta.md`: #73 en curso, #100, #101 y #102 en sus tablas, decisiones de losas y conformados en frío fuera de "Decisiones abiertas".
- `docs/glosario.md`: modelo físico, modelo analítico, nivel, eje de replanteo, losa, muro, contorno y espesor.
- `README.md` y sus traducciones: el modelo físico en "Qué hace hoy".
- `tests/datos/nrv/README.md`: archivo de referencia nuevo.
- El sitio no cambia: el modelo físico es solo una API preliminar, sin nada que una persona pueda usar desde la interfaz todavía.

## Pendiente y problemas conocidos

- Edición del modelo físico en la interfaz (#73 con #31), con muestra visual antes.
- Generar el modelo de cálculo desde el físico (#74); ahí la generación de barras y nudos va en Rust según la regla de rendimiento.
- Huecos en losas, perfiles de acero, más formas de sección y tipos de losa (suben la versión del módulo).
- Propuestas de agentes sobre el modelo físico: necesitan sumar `fisico` a las partes del módulo `historial` (sube su versión).
- #5 y #9 están hechos pero siguen abiertos en GitHub.

## Para quien siga

- Leé `docs/formato-nrv.md` §4f y `python/nervi/fisico.py`. Para #74 conviene empezar por columnas y vigas (barras entre nudos en cada nivel y punto de planta) y dejar losas y muros para cuando estén las láminas (#32).
