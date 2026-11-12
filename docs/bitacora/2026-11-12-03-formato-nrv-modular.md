# 2026-11-12-03 · Formato .nrv modular y compatible para siempre

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-mvpen5`
- **Fase de la hoja de ruta:** transversal (antes de congelar el formato con la v0.1.0)

## Qué se pidió

Saber si el `.nrv` es escalable y que el archivo sirva para siempre: que las fases siguientes se agreguen como módulos y que dentro de 5 años la última versión de Nervi siga abriendo un pórtico plano de hoy.

## Qué se hizo

- Manifiesto con `modulos` (`docs/formato-nrv.md` §3.1): cada módulo tiene su versión, sus miembros del ZIP y si es `requerido`. Hoy existe solo `modelo` (versión 1). `version_esquema` pasa a ser la versión del contenedor, que no cambia cuando un módulo agrega datos.
- `python/nervi/formato/contenedor.py`: `MODULOS` con lo que conoce esta versión. Un módulo desconocido o más nuevo y no requerido se conserva byte a byte con su entrada del manifiesto y deja un aviso en `Documento.avisos`. Si es requerido, el archivo no se abre y el error dice qué hace falta. Un manifiesto sin `modulos`, como los que escribía la GUI hasta hoy, se lee como `modelo` versión 1.
- `migraciones.py`: una cadena de migraciones por módulo. `Documento.migrado_desde` es ahora un diccionario `módulo -> versión original`. La GUI lo muestra y también muestra los avisos.
- `tests/datos/nrv/`: archivos de referencia permanentes (`modelo-v1.nrv`, `modelo-v1-sin-modulos.nrv` y `modelo-v1.esperado.json`) y `tests/test_formato_compatibilidad.py`, que los abre, los resuelve y compara con tolerancia relativa 1e-9. También exige un archivo por cada versión de cada módulo conocido.
- `docs/formato-nrv.md` §6.3, "Compromiso de compatibilidad", y dos reglas nuevas en `AGENTS.md`: no se borran ni se regeneran archivos de referencia ni migraciones publicadas, y lo que agrega una fase va en un módulo propio.

## Cómo se verificó

- `pytest`: 107 pruebas en verde y 1 omitida (la de la GUI, porque en este entorno falta `libEGL`; el CI la corre). Son 12 pruebas nuevas de compatibilidad: archivos de referencia, módulo opcional conservado, módulo requerido desconocido, `modelo` de versión futura, manifiestos inválidos y una migración simulada de `modelo` 1 → 2.
- `ruff check` y `ruff format --check` en verde.

## Decisiones tomadas

- Versión por módulo y no una sola versión para todo: así una fase nueva no obliga a migrar ni a romper lo que ya existe.
- Se mantuvo la clave `version_esquema` (ahora versión del contenedor) para no invalidar los archivos ya guardados.
- No se promete que una versión vieja abra archivos nuevos. Sí se promete que lo diga con claridad y que conserve lo que no entiende si no es requerido.
- El 3D entra como otro `tipo` del módulo `modelo`; `portico_2d` sigue siendo válido para siempre. El diseño (Fase 3) va en el módulo `diseno`.

## Pendiente y problemas conocidos

- Firma DCO: el usuario autorizó por escrito, el 2026-11-12 a las 12:59 UTC ("Te doy el ok, firmalo"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.
- El formato sigue en borrador hasta la etiqueta v0.1.0. Desde entonces rige §6.3.

## Para quien siga

- Antes de tocar `modelo.json` o de agregar un módulo, leé `docs/formato-nrv.md` §3.1 y §6.3.
