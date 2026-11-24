# 2026-11-24-01 · Barra lateral de menús, Preferencias y Configuración del proyecto

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-13lahw`
- **Fase de la hoja de ruta:** Fase 5 (interfaz gráfica, vía paralela); formato `.nrv`

## Qué se pidió

Definir qué menús y qué ajustes tiene la aplicación, de modo que cualquier parámetro que se quiera incorporar tenga su lugar, e implementar la primera parte. Se discutió con muestras en los dos temas (barra arriba, barra abajo y barra lateral de íconos) y Jerónimo Bareiro eligió la barra lateral de íconos (23/11/2026). También pidió que el diámetro de las barras de columnas no lo elija el usuario sino el programa.

## Qué se hizo

- **Barra lateral de menús** (`gui/ventana.py`): columna de íconos de 52 px a la izquierda con Archivo, Modelo, Calcular, Ver y Herramientas arriba, y Ayuda y Preferencias abajo. Cada ícono abre su menú hacia la derecha. Los menús solo tienen acciones que ya existen; *Editar* no está porque todavía no hay Deshacer. Archivo suma **Abrir reciente** y **Configuración del proyecto**; Ayuda, *Código fuente y documentación*, *Informar un error* y *Acerca de Nervi*. El menú del logo se conserva y suma Configuración del proyecto y Preferencias.
- **Íconos propios** de trazo fino en `estilo.ICONOS_MENU` y `estilo.iconos_menu`, en el color del texto secundario o del acento. Estilos nuevos en `estilo.qss`: `riel`, `menu_riel`, `apartados`, `caja_ajustes`, `pagina_ajustes`, `pie_ajustes`.
- **`gui/ajustes.py`** (nuevo): registro de preferencias (`PREFERENCIAS`), lectura y escritura en `QSettings` (`ajustes.ARCHIVO` permite aislarlas en las pruebas), proyectos recientes y las dos ventanas con la misma forma (`DialogoAjustes`): apartados, buscador, *Restablecer este apartado*, *Cancelar*, *Aplicar* y *Aceptar*.
  - **Preferencias:** General (qué abrir al iniciar: ejemplo, último proyecto o vacío) y Apariencia (tema y tamaño de letra Normal 9,5 pt o Grande 11 pt, con `estilo.con_tamano`).
  - **Configuración del proyecto:** Datos del proyecto (carátula de la memoria), Unidades (solo con el modelo vacío), Materiales (f'c, fy, fyt) y Diseño (recubrimiento, estribo, agregado, sección crítica a d y **diámetros permitidos para columnas**). Edita los mismos datos que la etapa Diseño a través de la sesión.
- **Formato `.nrv`:** módulo `diseno` versión 2 con `criterios.diametros_columna` y su migración `diseno_1_a_2`, que agrega los cinco diámetros (12, 16, 20, 25 y 32 mm). Módulo nuevo `proyecto` versión 1 (`formato/proyecto.py`, `proyecto.json`) con nombre, ubicación, comitente, autor, fecha y revisión. Archivos de referencia nuevos `diseno-v2.nrv` y `proyecto-v1.nrv` con sus `*.esperado.json`.
- **Diseño de columnas** (`design/proyecto.py`): `diametros_columna(criterios)` pasa los diámetros elegidos a la búsqueda de armadura, que ya elegía sola la armadura de menor área. El Ø16 que estaba en el código es solo la sección de arranque de esa búsqueda y no influye en el resultado. La memoria nombra los diámetros solo si se limitaron.
- **Sesión y memoria** (`gui/sesion.py`): `proyecto` y `editar_proyecto`; la carátula de la memoria toma los datos del proyecto.
- **Arranque** (`gui/app.py`): sin archivo en la línea de comandos, hace lo que dice la preferencia *Al abrir Nervi*.

## Cómo se verificó

- `pytest`: 348 pruebas en verde (324 antes de este cambio). Nuevas en `tests/test_gui.py`: cada menú de la barra lateral se abre a la derecha de su ícono y solo tiene acciones habilitadas; Preferencias cambia tema y tamaño y restablece; el buscador de ajustes; Configuración del proyecto guarda datos, recubrimiento y diámetros en el `.nrv` y la etapa Diseño muestra lo mismo; sin ningún diámetro no se aplica; sin cambios no agrega módulos; unidades de un modelo vacío; proyectos recientes y *Abrir el último proyecto*. En `tests/test_formato.py`: validación de `diametros_columna` y de `proyecto.json`, ida y vuelta. En `tests/test_formato_compatibilidad.py`: `diseno-v1.nrv` se migra con los cinco diámetros, `diseno-v2.nrv` da 8 barras Ø16 en la columna limitada a Ø16 (con todos los diámetros saldría 4Ø20) y `proyecto-v1.nrv` se lee igual.
- **Exactitud:** `python scripts/medir_diseno.py --guardar antes.json` en `main` y `--comparar antes.json` con este cambio, con la tolerancia por defecto: "igual a la referencia" en las 130 barras. Tiempo del pórtico de referencia: 1,92 s antes y 1,95 s después (el cálculo no cambió; la diferencia es ruido).
- `ruff check` y `ruff format --check` en verde. No se tocó Rust.
- Capturas de la ventana con el menú Archivo abierto y de las dos ventanas de ajustes, en tema claro y oscuro, revisadas a ojo.

## Decisiones tomadas

- **Regla para ubicar un ajuste:** si cambiarlo puede cambiar un número del cálculo o de la memoria, va en Configuración del proyecto y en el `.nrv`; si solo cambia cómo se ve o se usa la aplicación, va en Preferencias. Escrita en `docs/diseno-interfaz.md` §Menús y ajustes.
- **Barra lateral de íconos** en vez de barra de menús arriba o abajo (decisión de Jerónimo Bareiro). Cada ícono abre un menú; no cambia el panel izquierdo como en VS Code, para no tocar lo que ya funciona.
- **Íconos propios** en vez de un juego externo, para que tengan el trazo de la marca.
- **Sin opciones grises:** las acciones y apartados que todavía no existen no se muestran.
- **Preferencias por persona** en esta etapa; exportarlas e importarlas en un archivo queda para más adelante.
- **Factores de norma no editables** por ahora; cuando se habiliten, la memoria marcará cada valor cambiado.
- **Unidades:** solo se eligen con el modelo vacío, porque cambiarlas en un modelo con datos exige convertir todos los valores. La conversión queda pendiente.
- **Diámetros de columnas:** se guardan como lista de diámetros permitidos y no como un diámetro fijo, porque el programa ya elige la armadura óptima. Con todos marcados el resultado es idéntico al anterior.
- Firma DCO: Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (23/11/2026, hora de Asunción) que el agente agregue su `Signed-off-by` a los commits de este trabajo, con el nombre `bareirojero` y su correo `noreply` de GitHub.
- La prueba `test_diseno_de_version_futura_se_conserva` usaba la versión 2 de `diseno` como "versión futura"; desde este cambio la 2 es la que escribe Nervi, así que pasó a usar la 3. La prueba comprueba lo mismo.

## Documentación actualizada

- `docs/diseno-interfaz.md` (§Menús y ajustes, tema y tamaño de letra), `docs/formato-nrv.md` (título, §3.1, §4b versión 2, §4d nuevo, §8 y §9), `tests/datos/nrv/README.md`, `docs/ESTADO.md`, `docs/hoja-de-ruta.md` (Fase 5), `docs/glosario.md` (preferencias, configuración del proyecto, apartado, barra lateral, recientes, diámetros permitidos, datos del proyecto), los cuatro README (dónde se eligen el tema y los ajustes) y `sitio/primeros-pasos.md` con sus traducciones en `sitio/idiomas/`.

## Pendiente y problemas conocidos

- Próximos apartados, cuando exista lo que ajustan: Unidades con conversión, Normas, Análisis, Cargas y combinaciones, Memoria, Empresa y firma, Atajos de teclado, Asistente IA y complementos, y Valores por defecto de proyectos nuevos.
- Menú *Editar* cuando haya Deshacer y Rehacer.
- El diseño de columnas sigue experimental y pendiente de revisión de un ingeniero estructural.

## Para quien siga

- Para sumar una preferencia: una entrada en `ajustes.PREFERENCIAS` (y su apartado en `APARTADOS_PREFERENCIAS` si es nuevo). Para sumar un ajuste del proyecto: el dato en el módulo del `.nrv` que corresponda, con su versión y migración, y su control en `ConfiguracionProyecto`.
- Leer `docs/diseno-interfaz.md` §Menús y ajustes antes de agregar menús o apartados.
