# 2026-11-10-04 · Sitio web pensado para el público

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-4qkdzd`
- **Fase de la hoja de ruta:** transversal (difusión y comunidad)

## Qué se pidió

Actualizar la información del sitio web, que no aparezca más el nombre anterior del proyecto y que no se publiquen las notas internas sin pulir, para que cualquier persona lo entienda. La bitácora se mantiene.

## Qué se hizo

- Páginas nuevas para usuarios en `sitio/`: portada renovada con una captura de la interfaz (`sitio/img/interfaz.png`), "Descargar" (instaladores, aviso de Windows sin firma, instalación desde el código fuente) y "Primeros pasos" (una viga resuelta con la interfaz y con Python).
- `scripts/preparar_sitio.py` y `mkdocs.yml`: menú nuevo (Inicio, Descargar, Primeros pasos, Documentación técnica, Hoja de ruta, Participar, Bitácora). Ya no se publican `docs/ESTADO.md` (pendientes y decisiones en curso) ni `AGENTS.md`, y en la hoja de ruta se omiten las notas de mantenimiento. Los enlaces a esos archivos llevan a GitHub.
- El nombre anterior no aparece en el sitio: se quitó del README, de `ESTADO.md` y de la especificación; las entradas viejas de la bitácora, que no se editan, se adaptan solo al publicarlas (`SUSTITUCIONES`), y el armado falla si el nombre queda en alguna página.
- Información puesta al día con lo que ya está en `main`: cargas trapezoidales, interfaz de escritorio y formato `.nrv` en README, especificación y hoja de ruta (#2 marcado como hecho).
- `AGENTS.md`: quien cambie lo que un usuario puede hacer actualiza también las páginas de `sitio/`.

## Cómo se verificó

- `python scripts/preparar_sitio.py && mkdocs build --strict` sin advertencias; búsqueda del nombre anterior en el HTML generado sin resultados.
- Capturas en Chromium de la portada (escritorio y móvil), "Descargar" y una entrada de la bitácora adaptada.
- `ruff check` y `ruff format --check` sobre `scripts/` en verde.

## Decisiones tomadas

- Las páginas de inicio, descargar y primeros pasos se escriben a mano en lenguaje llano en lugar de publicar el README, que está pensado para quien programa.
- La bitácora se publica, a pedido del usuario; `ESTADO.md` no, porque mezcla pendientes internos.

## Pendiente y problemas conocidos

- Firma DCO: el usuario autorizó por escrito, el 2026-11-10 a las 18:39 UTC ("Firmalo, te autorizo"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.
- "Descargar" apunta a Releases, que todavía está vacío hasta la primera versión `v0.1.0`.
- `nervi` no está publicado en PyPI; la instalación con Python es desde el código fuente.
- Dominio propio: a decidir por el usuario.

## Para quien siga

- Las páginas públicas están en `sitio/`; la lista de documentos que se publican, en `PAGINAS` de `scripts/preparar_sitio.py`.
