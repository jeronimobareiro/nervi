# 2026-11-09-04 · Control automático de la bitácora en el CI

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `fase-1-portico-2d` (sin subir: cuenta de GitHub suspendida)
- **Fase de la hoja de ruta:** transversal

## Qué se pidió

Que registrar cada aporte en la bitácora no dependa de que la IA se acuerde: un control que lo exija.

## Qué se hizo

- `scripts/verificar_bitacora.py`: compara la rama contra la base y falla si hay cambios de código sin entrada nueva en `docs/bitacora/` o sin actualizar `docs/ESTADO.md`, si se edita o borra una entrada existente, si el nombre no sigue `AAAA-MM-DD-NN-tema.md` o si faltan secciones de la plantilla.
- Trabajo "Bitácora de aportes" en `.github/workflows/ci.yml`, solo en pull requests.
- `tests/test_verificar_bitacora.py`: 6 pruebas de las reglas.
- `AGENTS.md` documenta el control y el comando para correrlo localmente.
- Se agregó la sección "Pendiente y problemas conocidos" a las entradas 01 y 03, que todavía no estaban en `main`.

## Cómo se verificó

- `pytest`: 16 pruebas en verde (10 del motor y 6 del control).
- `python scripts/verificar_bitacora.py origin/main` sobre esta misma rama: pasa.

## Decisiones tomadas

- Solo se exige en PRs que tocan algo fuera de la documentación de seguimiento, para no frenar correcciones de la bitácora misma.
- `docs/bitacora/README.md` y `_plantilla.md` son editables; las entradas fechadas no.

## Pendiente y problemas conocidos

- Para que bloquee el merge hay que marcar el check como obligatorio en la configuración de ramas del repositorio en GitHub.
- No verifica que el contenido sea útil, solo que exista y tenga la estructura.

## Para quien siga

Correr `python scripts/verificar_bitacora.py origin/main` antes de abrir el PR.
