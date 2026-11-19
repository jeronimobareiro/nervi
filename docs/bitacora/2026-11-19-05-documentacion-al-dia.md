# 2026-11-19-05 · Documentación al día y regla de actualizarla en cada aporte

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-oefxsx`
- **Fase de la hoja de ruta:** transversal (documentación y reglas de trabajo)

## Qué se pidió

Revisar si los archivos informativos del repositorio reflejan las directivas del proyecto (rendimiento en Rust y línea de diseño de la interfaz), actualizarlos todos y tomar como regla que se mantengan al día con cada aporte, para que los demás aportantes estén al tanto.

## Qué se hizo

- `README.md` reescrito con el estado actual: análisis plano y espacial, diafragmas y brazos, dinámica, diseño ACI 318-19 de vigas y columnas, interfaz con etapas Diseño y Dinámica y tema claro y oscuro, `.nrv` modular, memoria PDF, rendimiento (diseño de columnas en Rust) y estructura del repositorio con `espacial/` y `diseno/`. Se quitaron afirmaciones viejas ("todavía no hay diseño según normas", "Pendiente de la Fase 1"). Secciones nuevas **Cómo trabajamos** (verificación, rendimiento, sistema de diseño de la interfaz, documentación al día) y **Qué sigue**.
- `README.en.md`, `README.pt.md` y `README.ru.md` con el mismo contenido; antes decían, por ejemplo, que el diseño según norma no existía.
- `CONTRIBUTING.md`: reglas 7 (rendimiento primero, con el banco de tiempos), 8 (interfaz con un único sistema de diseño y muestra visual previa) y 9, y sección nueva **Documentación al día** con una tabla de qué actualizar según el aporte. Los párrafos en inglés, portugués y ruso suman las dos reglas.
- `AGENTS.md`: regla de la interfaz en §2 (temas "A · Claro preciso" y "B · Nocturno Nervi", tirador rectangular, desplegables de esquinas rectas, muestra visual antes de cambiar el diseño) y paso obligatorio §3.3 **Documentación al día**, que absorbe las dos reglas sueltas que había sobre README traducidos y sitio. El DCO pasó a §3.5.
- Control en el CI: `scripts/verificar_bitacora.py` exige la sección nueva **Documentación actualizada** en cada entrada nueva; `docs/bitacora/_plantilla.md` la incluye. Solo afecta a entradas nuevas, las viejas no se tocan.
- `.github/pull_request_template.md`: secciones **Rendimiento** y **Documentación actualizada** y casillas para documentación, cálculo en Rust e interfaz.
- `docs/hoja-de-ruta.md`: punto de partida actualizado, sección de principios para todas las fases, estado de cada issue (hecho, en curso, preliminar o experimental) y fila de servicio y detalle de vigas. `docs/diseno-interfaz.md`: nombres de los temas aprobados y muestra visual previa.
- Sitio: portada y "Participar" en los cuatro idiomas (aviso de versión preliminar, memoria con columnas y dinámica, qué viene y las dos reglas).
- `docs/bitacora/README.md`: el índice llegaba hasta el 2026-11-09-10; ahora lista todas las entradas.

## Cómo se verificó

- `pytest tests/test_verificar_bitacora.py` y `python scripts/verificar_bitacora.py origin/main` en verde, con esta entrada.
- `python scripts/preparar_sitio.py` arma el sitio sin errores (enlaces y nombre anterior).
- Cada afirmación del README se contrastó con `docs/ESTADO.md` y las entradas de la bitácora del 17 al 19 de noviembre.

## Decisiones tomadas

- El control automático exige que la entrada diga qué documentación se actualizó, en lugar de exigir que ciertos archivos cambien: un control por archivos daría falsos positivos (un arreglo interno no tiene por qué tocar el README) y castigaría a quien no puede traducir. Quien revisa el PR juzga si la lista es correcta.
- Quien no pueda traducir actualiza el texto en español y pide ayuda en el PR para las traducciones.
- Firma DCO: Jerónimo Bareiro autorizó en el hilo del proyecto (19/11/2026, decisión explícita para este PR) que el agente agregue su `Signed-off-by` a los commits de este trabajo, con el nombre `bareirojero` y su correo `noreply` de GitHub.

## Documentación actualizada

- `README.md`, `README.en.md`, `README.pt.md`, `README.ru.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/ESTADO.md`, `docs/hoja-de-ruta.md`, `docs/diseno-interfaz.md`, `docs/bitacora/README.md`, `docs/bitacora/_plantilla.md`, `.github/pull_request_template.md`, `sitio/index.md`, `sitio/participar/index.md` y sus traducciones en `sitio/idiomas/`.

## Pendiente y problemas conocidos

- Las traducciones las hizo el agente; conviene que alguien que hable inglés, portugués o ruso las revise.
- El banco de tiempos todavía no corre en el CI.

## Para quien siga

- Antes de abrir un PR, recorré la tabla de `CONTRIBUTING.md` §Documentación al día y completá la sección **Documentación actualizada** de tu entrada.
