# 2026-11-09-08 · Mudanza al repositorio jeronimobareiro/nervi

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `fase-1-portico-2d`, para subir como `main` del repositorio nuevo
- **Fase de la hoja de ruta:** transversal

## Qué se pidió

Usar el repositorio nuevo `https://github.com/jeronimobareiro/nervi` como hogar del proyecto. El repositorio anterior (`bareirojero/Apex-BIM`) y su PR #1 se borraron.

## Qué se hizo

- Enlaces actualizados al repositorio nuevo en `Cargo.toml` y en la especificación.
- `docs/ESTADO.md` ya no menciona la suspensión ni el PR #1; indica la mudanza pendiente.

## Cómo se verificó

- Búsqueda de referencias al repositorio viejo: solo quedan en entradas anteriores de la bitácora, que son historia.
- Pruebas locales sin cambios de comportamiento (solo cambian enlaces y documentación).

## Decisiones tomadas

- Subir el historial completo a `main` del repositorio nuevo en vez de abrir un PR, porque el repositorio empieza vacío y no hay revisión pendiente contra otra base.

## Pendiente y problemas conocidos

- El agente no tiene permiso de escritura en `jeronimobareiro/nervi`: el usuario sube el bundle, firmando los commits (`Signed-off-by`) como pide el DCO.
- Verificar el primer CI en el repositorio nuevo; el trabajo de Python 3.10 nunca llegó a correr completo.
- Marcar como obligatorios los checks de bitácora y DCO en la configuración de ramas de `main`.

## Para quien siga

Si el CI del primer push falla, empezá por ahí antes de cualquier funcionalidad nueva.
