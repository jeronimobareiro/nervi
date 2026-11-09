# 2026-11-09-03 · Reglas para agentes y bitácora

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `fase-1-portico-2d` (sin subir: cuenta de GitHub suspendida)
- **Fase de la hoja de ruta:** transversal

## Qué se pidió

Una sección del repositorio donde cada IA deje sus aportes en orden cronológico, para que la siguiente sepa dónde quedó el trabajo.

## Qué se hizo

- `AGENTS.md`: reglas para cualquier IA (qué leer antes, qué verificar, cómo registrar el aporte). `CLAUDE.md` y `GEMINI.md` apuntan a él.
- `docs/ESTADO.md`: foto actual del proyecto, que se reescribe en cada aporte.
- `docs/bitacora/`: una entrada por aporte, con plantilla e índice. Entradas 01 y 02 reconstruidas a partir del trabajo del mismo día.

## Decisiones tomadas

- Un archivo por entrada en vez de un único archivo largo: evita conflictos cuando dos IAs trabajan en ramas distintas, y el nombre con fecha y número da el orden.
- Separar historia (bitácora, solo se agrega) de foto actual (`ESTADO.md`, se reescribe), para que quien llegue no tenga que leer toda la historia.
- `AGENTS.md` porque es el nombre que buscan por defecto varias herramientas de IA para programar.

## Pendiente y problemas conocidos

- El registro depende de que cada IA cumpla `AGENTS.md`; se resuelve con el control automático de la entrada 04.

## Para quien siga

Empezá por `docs/ESTADO.md`.
