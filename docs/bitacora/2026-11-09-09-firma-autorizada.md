# 2026-11-09-09 · Firma DCO autorizada por el usuario

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `importar-nervi`, PR #1 de `jeronimobareiro/nervi`
- **Fase de la hoja de ruta:** transversal

## Qué se pidió

El usuario no sabía cómo firmar el commit pendiente y autorizó por escrito, el 2026-11-09 a las 16:55 UTC, que el agente lo firme en su nombre como "bareirojero".

## Qué se hizo

- Se agregó `Signed-off-by: bareirojero <345933350+bareirojero@users.noreply.github.com>` al commit "Apuntar al repositorio nuevo jeronimobareiro/nervi" y a este commit. Se usó el correo `noreply` de GitHub de esa cuenta porque el usuario no indicó un correo.
- `AGENTS.md` §3.4: el agente puede agregar la firma de quien pidió el trabajo solo con autorización explícita y por escrito, y debe anotarla en la bitácora.

## Cómo se verificó

- `scripts/verificar_dco.py main` en verde sobre la rama.

## Decisiones tomadas

- Se firmó solo lo que el control exige (commits posteriores a la adopción del DCO); el commit de merge no lo requiere según el script.

## Pendiente y problemas conocidos

- Si el usuario prefiere otro correo en la firma, hay que volver a firmar estos commits.

## Para quien siga

Sin autorización explícita y escrita del usuario, no firmes en su nombre.
