# 2026-11-10-09 · Página "¿Por qué se llama Nervi?"

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-4qkdzd`
- **Fase de la hoja de ruta:** transversal (difusión y comunidad)

## Qué se pidió

Una pestaña del sitio que explique el nombre del proyecto a partir de la vida y la obra del ingeniero Pier Luigi Nervi, con imágenes de uso libre, que inspire a participar, y un enlace "¿Por qué se llama Nervi?" en la portada debajo de los botones.

## Qué se hizo

- `sitio/por-que-nervi.md`: portada con retrato, "Quién fue", "Cómo pensaba" (nervaduras isostáticas y su relación con el cálculo por elementos finitos), galería de diez obras con año, lugar y descripción, cierre con llamado a participar, nota de independencia y créditos de las imágenes.
- Trece fotos de Wikimedia Commons, enlazadas desde `commons.wikimedia.org/wiki/Special:FilePath` con ancho de 1200 px.
- `sitio/index.md` y `mkdocs.yml`: enlace en la portada y pestaña "Por qué Nervi" en el menú.
- `sitio/estilos/nervi.css`: estilos de la página (retrato, columnas, galería en grilla con dos obras destacadas y versión móvil).

## Cómo se verificó

- Licencias leídas de los metadatos de cada archivo en Commons (API `imageinfo`, `extmetadata`): dominio público, CC0, CC BY 3.0 y CC BY-SA 3.0/4.0. Autor, licencia y enlace de cada una figuran en los créditos de la página.
- `python scripts/preparar_sitio.py && mkdocs build --strict` sin advertencias; capturas en escritorio y móvil.
- El usuario revisó y aprobó el texto en un borrador antes de armar la página.

## Decisiones tomadas

- El texto es propio, no copiado de Wikipedia, para no depender de su licencia.
- Las fotos se enlazan desde Commons y no se guardan en el repositorio: Wikimedia limitó las descargas desde el entorno de trabajo (HTTP 429, esperas de 10 minutos). Enlazar es una práctica permitida con atribución; a cambio, el sitio depende de que Commons siga alojando cada archivo y los visitantes cargan las fotos de ese servidor.
- No se incluyó foto de la sede de la UNESCO: no se encontró una con licencia libre clara; la obra se menciona en el texto.
- Las fotos CC BY-SA se publican sin modificar su contenido (solo reducidas) y con su atribución; la licencia no se extiende al resto del sitio.

## Pendiente y problemas conocidos

- Firma DCO: el usuario autorizó por escrito, el 2026-11-10 a las 23:01 UTC ("firmalo, te autorizo"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.
- Algunas fotos de edificios italianos pueden verse afectadas por la falta de libertad de panorama en Italia; Commons las aloja con su licencia, pero si alguna se retira de Commons conviene reemplazarla.
- Faltan fotos de la fábrica Gatti y de los hangares: no hay en Commons con licencia libre.

## Para quien siga

- Conviene guardar copias reducidas en `sitio/img/nervi/` y apuntar la página a ellas, para no depender de Commons.
- Para cambiar una foto, reemplazá su enlace en `sitio/por-que-nervi.md` y actualizá su línea en los créditos.
