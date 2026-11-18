# 2026-11-17-07 · Etapa Diseño en la interfaz

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-wdt9nv`
- **Fase de la hoja de ruta:** Fase 3, diseño de hormigón armado · issues [#22](https://github.com/jeronimobareiro/nervi/issues/22) y [#23](https://github.com/jeronimobareiro/nervi/issues/23) en la interfaz, y columnas de [#24](https://github.com/jeronimobareiro/nervi/issues/24) conectadas · capítulo de diseño de la memoria [#28](https://github.com/jeronimobareiro/nervi/issues/28)

## Qué se pidió

Habilitar la etapa "Diseño" de la interfaz, que estaba desactivada: elegir hormigón y acero, diseñar las vigas con las envolventes, mostrar armadura y estribos de cada viga con cumple/no cumple y el artículo de la norma, mostrar el aviso de módulo experimental y sumar el capítulo de diseño a la memoria en PDF. Las columnas (#24) se hacen en paralelo en otro trabajo, así que la etapa tiene que dejarlas enchufar sin tocar la interfaz. Se revisó `main` antes de empezar: el diseño de vigas (entrada 2026-11-17-02) y la memoria (`Memoria.agregar`, `tabla_verificaciones`) ya estaban.

## Qué se hizo

- `python/nervi/design/proyecto.py` (nuevo): diseño de todas las barras de un proyecto a partir de `modelo.json` y `diseno.json`.
  - Clasifica cada barra en viga o columna por su orientación (o lo que elija el usuario, incluido "no diseñar") y toma como sección el rectángulo con el mismo `A` e `I` (`h = √(12 I/A)`, `b = A/h`), que el usuario puede cambiar.
  - Ancho de apoyo de cada viga: el canto de las columnas que llegan a ese nudo, para ubicar la cara del apoyo de §9.4.3.2.
  - Registro `DISENADORES` por tipo de elemento, con `"viga"` y `"columna"`; un tipo sin diseñador queda "pendiente" con el motivo.
  - Columnas: después de integrar `main` con el diseño de columnas (#24, entrada 2026-11-17-04) se agregó el adaptador `disenar_columna`, que llama a `aci318.disenar_columna` con la sección rectangular del elemento, barras de 16 mm de arranque y búsqueda de la armadura de menor área. Verificaciones: flexocompresión (§10.5.1.1, §22.4), compresión axial máxima (§22.4.2) y cuantías mínima y máxima (§10.6.1.1), más la esbeltez en el plano (§6.2.5.1, §6.6.4.5). Supone `k = 1`, `lu` igual al largo de la barra, pórtico no desplazable y `βdns = 1`; no revisa fuera del plano ni diseña estribos de columnas. Solo con el modelo en kN y m; en otras unidades queda pendiente con el motivo.
  - Cada resultado trae estado (cumple, no cumple, pendiente, error), armadura en texto y una lista de `Verificacion` (solicitación, resistencia, unidad y artículo): flexión M+ y M− (§9.5.1.1, §22.2), armadura mínima con la excepción de 4/3 (§9.6.1.2 y §9.6.1.3), ancho para las barras (§25.2.1), cortante (§9.5.1.1, §22.5), separación de estribos (§9.7.6.2.2) y límite de la sección (§22.5.1.2).
  - `capitulo_memoria`: capítulo "Diseño de hormigón armado (ACI 318-19)" con el aviso de experimental, materiales y criterios, tabla de armaduras, `tabla_verificaciones` y los motivos de lo pendiente.
- `nervi.design.aci318.disenar_viga`: acepta las unidades del modelo (`fuerza` y `longitud`, por ejemplo tf y cm) y convierte a kN y m; devuelve además `d_cortante` y la verificación a cortante aunque no hagan falta estribos. Lo que ya existía no cambia.
- Formato `.nrv`: módulo nuevo `diseno` versión 1 (`diseno.json`, no requerido), en `python/nervi/formato/diseno.py`. Guarda norma, materiales, criterios y los datos propios de cada barra, nunca resultados. Solo se escribe si el proyecto tiene datos de diseño. Lleva el SHA-256 de `modelo.json`: si otro programa cambió el modelo, al abrir se avisa. Documentado en `docs/formato-nrv.md` §4b y §9. Archivo de referencia `tests/datos/nrv/diseno-v1.nrv` con su `diseno-v1.esperado.json`.
- Interfaz:
  - `python/nervi/gui/diseno.py` (nuevo): pestaña "Diseño" con el aviso de experimental, f'c, fy, fyt, recubrimiento, estribo, agregado, sección crítica a `d`, botón **Diseñar**, tabla de barras (tipo y sección editables, armadura inferior, superior y estribos, estado con la relación que gobierna) y tabla de verificaciones de la barra elegida con su artículo.
  - `ventana.py`: el botón de etapa **Diseño** queda habilitado y se marca ✓ cuando el diseño está al día; comando "Diseñar elementos de hormigón armado" en Ctrl+K; el panel de propiedades suma la armadura de la barra; en la etapa Diseño la vista 2D pinta cada barra según su estado. La etapa "Memoria" sigue desactivada con una ayuda que remite a Ctrl+P.
  - `sesion.py`: `diseno`, `editar_diseno`, `disenar` y `resultado_diseno`; editar el modelo deja el diseño desactualizado. La memoria (Ctrl+P) suma el capítulo de diseño y el aviso en la portada si el proyecto tiene datos de diseño.
- README en los cuatro idiomas, sitio (portada y primeros pasos en los cuatro idiomas) y glosario.
- Capturas: `docs/img/etapa-diseno.png`, `docs/img/etapa-diseno-columna.png` y `docs/img/etapa-diseno-no-cumple.png`.

## Cómo se verificó

- `tests/test_diseno_proyecto.py` (24 pruebas): sección equivalente y tipo automático; elementos con datos del usuario y ancho de apoyo; el diseño del pórtico da lo mismo que llamar a `aci318.disenar_viga` con esos datos (armadura y cada verificación); armadura mínima exigida con la excepción de 4/3, calculada a mano; el mismo pórtico en tf y cm da la misma armadura que en kN y m; sección chica (no cumple, con el motivo) e imposible (error); registro de diseñadores; el diseño de una columna da lo mismo que `aci318.disenar_columna`; una columna en otras unidades queda pendiente; sin combinaciones no se diseña; capítulo de la memoria; guardar y abrir `diseno.json`; aviso cuando otro programa cambió el modelo; diez casos de `diseno.json` inválido con su ruta.
- `tests/test_formato_compatibilidad.py`: el archivo de referencia nuevo se abre y da los mismos resultados (prueba general) y sus datos de diseño se leen igual (prueba nueva); un módulo `diseno` de una versión futura se conserva sin leer.
- `tests/test_gui.py` (7 pruebas nuevas): etapa habilitada y diseño del ejemplo, verificaciones de la barra elegida y selección desde la tabla, edición de sección, tipo y materiales (dato inválido rechazado), diseño desactualizado al editar el modelo, aviso sin combinaciones, guardar y abrir, memoria con el capítulo de diseño en PDF.
- `pytest`: 286 en verde (después de integrar `main` con las columnas y con servicio y detalle de vigas, entrada 2026-11-17-06), con `NERVI_EXIGIR_3D=1`. `ruff check` y `ruff format --check` en verde. `cargo fmt --check`, `cargo clippy -D warnings` y `cargo test -p nervi-core` en verde (no se tocó Rust).
- Ventana real bajo `QT_QPA_PLATFORM=offscreen` a 1920 × 1080 para las capturas, y lectura del PDF de la memoria con `pypdf`.

## Decisiones tomadas

- **Datos de diseño en un módulo propio** (`diseno`), como pide `AGENTS.md` y anticipaba `formato-nrv.md` §3.1, y no dentro de `modelo.json`. Unidades fijas (MPa y mm) para que no dependan de las del modelo.
- **Sin resultados en el archivo:** la armadura se recalcula, igual que los esfuerzos. Así un cambio en el algoritmo nunca deja un proyecto con resultados viejos.
- **Sección por defecto desde `A` e `I`** de la barra, porque el modelo de la versión 1 no tiene secciones con nombre. Es exacta para rectángulos; para otras secciones el usuario la escribe.
- **Ancho de apoyo automático** con el canto de las columnas del nudo. Se puede desactivar la sección crítica a `d` desde la interfaz.
- **Registro de diseñadores** en vez de un `if` por tipo en la interfaz, para que #24 entrara sin tocar la memoria. Como #24 se integró primero, el adaptador de columnas se hizo en este mismo aporte.
- La prueba `test_modulo_desconocido_opcional_se_conserva` usaba `"diseno"` como ejemplo de módulo desconocido; ahora usa `"resultados"`, que sigue siendo desconocido, y se agregó otra para un `diseno` de versión futura. No se quitó ninguna comprobación.
- `ruff`: se permite `×` y `−` (RUF001) en `design/proyecto.py` y su prueba, igual que en la interfaz y la memoria, porque son textos para el usuario.
- Sin dependencias nuevas. Implementación propia; no se copió código de otros programas ni se transcribió texto de la norma (solo se citan artículos).

## Pendiente y problemas conocidos

- Flechas, fisuración y anclajes de vigas (`aci318.servicio` y `aci318.detalle`, entrada 2026-11-17-06) todavía no están en la etapa Diseño ni en su capítulo de la memoria.

- **Revisión de un ingeniero estructural** de todo `nervi.design` antes de quitar la marca de experimental, ahora también de: el ancho de apoyo tomado del canto de la columna, la sección equivalente desde `A` e `I`, y qué verificaciones van en la memoria.
- **Columnas en la etapa Diseño:** el supuesto de pórtico no desplazable no es conservador si el pórtico se desplaza con cargas laterales; falta pedir `k`, `lu` y `δs` por barra, revisar fuera del plano y diseñar los estribos. Las barras de arranque (16 mm) son fijas por ahora. Que lo revise un ingeniero.
- La etapa no revisa torsión ni estribos por zonas. La vista 2D no muestra todavía la envolvente ni dibuja la armadura.
- El módulo `diseno` se congela junto con el resto del formato en la etiqueta `v0.1.0`.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-17 a las 00:39 UTC (opción "Sí, firmá con mi nombre" a "¿Firmo los commits de este PR (DCO) con tu nombre?"), que el agente firme los commits de este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Para sumar otro tipo de elemento: leé el docstring de `nervi/design/proyecto.py` y `disenar_viga` o `disenar_columna` de ese archivo como modelo; `Contexto` trae resultados, combinaciones, materiales y unidades.
- Las pruebas de la interfaz están al final de `tests/test_gui.py`; el formato del módulo, en `docs/formato-nrv.md` §4b.
