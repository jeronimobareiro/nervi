# 2026-11-24-11 · Hoja de ruta: fechas ajustadas y estados con íconos

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-4qkdzd`
- **Fase de la hoja de ruta:** transversal (difusión y comunidad)

## Qué se pidió

Ajustar las fechas previstas a lo que ya se hizo y mostrar con un sistema de checks el estado de cada cosa: hecho, hecho pero experimental, en desarrollo y pendiente.

## Qué se hizo

- `docs/hoja-de-ruta.md`: leyenda de cuatro estados (✅ hecho, 🧪 hecho pero experimental o preliminar, 🚧 en desarrollo, ⬜ pendiente) y una columna **Estado** con el ícono en cada tabla de tareas; el ícono también encabeza el estado de cada hito y cada paso de la línea de agentes de IA.
- Horizontes de los hitos ajustados a lo hecho en noviembre de 2026: las fases 2a, 2b y 3 ya tienen su primera versión (preliminar o experimental), así que su horizonte pasa a lo que falta (verificación con ejemplos publicados, P-Δ y espectros normativos, revisión de un ingeniero y norma regional).
- El sitio publica la hoja de ruta tal cual, así que los cambios se ven en los cuatro idiomas (en español dentro de cada uno).

## Cómo se verificó

- `python scripts/construir_sitio.py` con los cuatro idiomas y `--strict`, y revisión de la página en Chromium.
- `python scripts/verificar_bitacora.py origin/main`.

## Decisiones tomadas

- Los estados salen de lo que dicen `ESTADO.md` y las entradas de la bitácora; una tarea es 🧪 mientras no la revise un ingeniero o no se compare con ejemplos publicados.
- Las fechas nuevas son una propuesta del agente, siguen siendo tentativas y las confirma el responsable del proyecto.

## Documentación actualizada

- `docs/hoja-de-ruta.md` y `docs/ESTADO.md`. El sitio no necesita cambios propios porque publica la hoja de ruta. README, `CONTRIBUTING.md` y `AGENTS.md` no cambian.

## Firma DCO

- Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (24/11/2026, "Firmalo") que el agente agregue su firma a este aporte. Se usó `bareirojero <345933350+bareirojero@users.noreply.github.com>` (AGENTS.md §3.5).

## Pendiente y problemas conocidos

- Hay que mover el ícono de una tarea cuando cambie su estado; la regla de documentación al día ya obliga a tocar este archivo en cada aporte.

## Para quien siga

- Al terminar una tarea, cambiar su ícono en la tabla y actualizar el estado del hito.
