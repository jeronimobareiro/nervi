# 2026-11-24-01 · Capa de proyecto sin Qt (`nervi.proyecto`)

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-jxpob7`
- **Fase de la hoja de ruta:** línea transversal "Integración con agentes de IA, API y complementos", etapa 1

## Qué se pidió

Jerónimo Bareiro pidió evaluar cómo conectar el agente de IA de cada persona a Nervi y, después del análisis sobre el código, hacer la primera etapa: sacar la lógica de la sesión de la interfaz a una capa sin Qt, para que la interfaz, los scripts, un servidor MCP y los complementos usen el mismo código.

## Qué se hizo

- `python/nervi/proyecto.py` (nuevo): `Proyecto` con todo lo que hacía `gui/sesion.py` (archivo, edición, revisión, cálculo, dinámica, diseño, memoria, combinación activa y selección) y los tipos `Seleccion`, `Inestabilidad`, `ResultadosDinamica`, `Aviso` y `documento_ejemplo`. En lugar de señales de Qt, avisa cada cambio con un evento (`"archivo"`, `"modelo"`, `"resultados"`, `"seleccion"`, `"diseno"`, `"dinamica"`) a quien se suscriba con `suscribir(oyente)`, que devuelve la función para cancelar.
- `python/nervi/gui/sesion.py`: `Sesion(Proyecto, QObject)` hereda el proyecto y solo traduce cada evento a su señal, en el mismo orden que antes. Sigue exportando los mismos nombres, así que el resto de la interfaz no cambió.
- `tests/test_proyecto.py` (nuevo, 7 pruebas).

## Cómo se verificó

- Suite completa antes del cambio: 329 pruebas en verde y 4 omitidas. Después, con las pruebas nuevas de esta entrada y de la siguiente: 342 en verde y 4 omitidas, sin tocar ninguna prueba existente.
- `tests/test_proyecto.py`: importar y calcular con `nervi.proyecto` no carga PySide6 (en un proceso aparte); `calcular` da arreglos idénticos (`np.array_equal`) a llamar al motor directamente; `disenar` da la misma armadura, relación, solicitación y resistencia que `nervi.design.proyecto.disenar`; los eventos salen en el mismo orden que las señales; el mecanismo selecciona su nudo; guardar, abrir y memoria funcionan sin interfaz; y `Sesion` da exactamente los mismos resultados que `Proyecto` y emite la señal junto con el evento.
- Banco de tiempos: `python scripts/medir_diseno.py --guardar` en `main` y `--comparar` con el cambio da "igual a la referencia" (diseño 2,14 s antes y 2,12 s después en el pórtico de referencia de 130 barras). El cambio no toca ningún cálculo.
- Herencia cooperativa: se comprobó que `Proyecto.__init__` corre una sola vez al crear una `Sesion` (con `QObject` primero en la herencia, PySide6 6.12 llama a `Proyecto.__init__` dos veces, por eso `Proyecto` va primero y llama a `super().__init__()`).

## Decisiones tomadas

- Herencia y no composición: la interfaz lee y asigna atributos de la sesión (`sesion.doc`, `sesion.resultados`, `sesion.combinacion`…) en muchos lugares; heredando, ninguna vista cambió y la sesión sigue siendo un `Proyecto` para las integraciones.
- La combinación activa y la selección quedan en `Proyecto`: un agente de IA necesita saber qué está mirando la persona ("explicame la barra seleccionada").
- Nombre `nervi.proyecto`, distinto de `nervi.design.proyecto` (diseño de los elementos de un proyecto); el docstring del módulo lo aclara.

## Documentación actualizada

- `docs/ESTADO.md` (qué funciona, cantidad de pruebas, próximos pasos), `docs/hoja-de-ruta.md` (línea transversal de integración con sus etapas) y `docs/glosario.md` (proyecto sin interfaz, evento). No cambió lo que el usuario ve en la interfaz, así que no se tocaron los README por esta entrada ni el sitio (los README cambian por la entrada siguiente).

## Pendiente y problemas conocidos

- Deshacer y rehacer, y las propuestas de cambio con su origen (etapa 3 de la línea de integración).
- `Proyecto._resolver_con_combinaciones` sigue siendo privado; lo usan la memoria y los resultados completos.

## Para quien siga

- Toda lógica nueva de la sesión va en `nervi/proyecto.py`, no en `gui/sesion.py`, y avisa con `self._avisar(evento)`. Si hace falta un evento nuevo, sumalo a `Proyecto.EVENTOS` y a `_SENALES` de `gui/sesion.py`.
- El análisis completo de la propuesta (memoria bruta, API, MCP, panel de IA, DXF, complementos) está en el documento compartido en el hilo del proyecto; las etapas, en `docs/hoja-de-ruta.md`.
