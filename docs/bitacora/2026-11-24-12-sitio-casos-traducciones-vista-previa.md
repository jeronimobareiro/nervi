# 2026-11-24-12 · Sitio: casos verificados, vista previa al compartir y más páginas traducidas

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-4qkdzd`
- **Fase de la hoja de ruta:** transversal (difusión y comunidad)

## Qué se pidió

De la lista de lo que le falta al sitio: la imagen para compartir en redes y la página de casos verificados (punto 4), y más traducciones con revisión de nativos (punto 5).

## Qué se hizo

- **Vista previa al compartir un enlace**: `sitio/img/social.png` (1200×630, logotipo, lema y captura de la interfaz en tema nocturno) y `overrides/main.html`, que agrega las etiquetas Open Graph y Twitter a todas las páginas con su título y descripción. La imagen se indica en `extra.imagen_social` de `mkdocs.yml`. `scripts/preparar_sitio.py` apunta cada idioma a esa carpeta de plantillas.
- **Página "Casos verificados"** en los cuatro idiomas, dentro de Documentación técnica: cómo se verifica (fuente, tolerancia, CI) y la tabla de todos los casos de `verification/` por carpeta, con su fuente. La tabla y la cantidad se generan al armar el sitio a partir de los `.toml`, así que no hay que mantenerlas a mano. Los títulos y las fuentes quedan en español. Enlazada desde la tarjeta "Verificable" de la portada.
- **Más páginas traducidas** al inglés, portugués y ruso: Seguridad de los resultados, Gobierno del proyecto y Código de conducta (resumen, con enlace al Contributor Covenant 2.1 y a sus traducciones oficiales). El armado usa la versión traducida en lugar de la copia en español y todas llevan un aviso que lleva al original, que es el texto de referencia.

## Cómo se verificó

- `python scripts/construir_sitio.py` con los cuatro idiomas y `--strict`; `ruff check` y `ruff format --check` sobre `scripts/`.
- Se comprobó que cada página lleva las etiquetas `og:` con la imagen absoluta, y que la tabla de casos sale con todas las carpetas.
- `python scripts/verificar_bitacora.py origin/main`.

## Decisiones tomadas

- El Código de conducta no se traduce completo: es el Contributor Covenant 2.1 y conviene remitir a sus traducciones oficiales en vez de mantener una nuestra. Gobierno y Seguridad sí se tradujeron enteros, y todas dicen que el texto de referencia es el español.
- No se tradujeron la documentación técnica ni la hoja de ruta (unas 16 000 palabras que cambian en cada aporte): quedarían desactualizadas enseguida. Conviene hacerlo con voluntarios cuando se estabilicen.
- La revisión por hablantes nativos no la puede hacer el agente; queda abierta.

## Documentación actualizada

- `docs/ESTADO.md` (sitio). README, `CONTRIBUTING.md`, `AGENTS.md` y la hoja de ruta no cambian.

## Firma DCO

- Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (24/11/2026, "Autorizo") que el agente agregue su firma a este aporte. Se usó `bareirojero <345933350+bareirojero@users.noreply.github.com>` (AGENTS.md §3.5).

## Pendiente y problemas conocidos

- Revisión de las traducciones (ruso y portugués sobre todo) por hablantes nativos.
- Si se compra el dominio propio, cambiar `site_url`, `extra.alternate` y `extra.imagen_social` en `mkdocs.yml`.
- Las tablas de casos muestran títulos y fuentes en español.
- No pude abrir el sitio de Contributor Covenant desde el entorno: el enlace de traducciones es el que figura en el propio texto del código de conducta.

## Para quien siga

- Una página traducida nueva va en `sitio/idiomas/<idioma>/` con el mismo nombre que su ruta en el sitio; si existe, reemplaza a la copia en español.
- La imagen para compartir se rehace a mano (HTML de 1200×630 con el logotipo y la captura) cuando cambie la interfaz.
