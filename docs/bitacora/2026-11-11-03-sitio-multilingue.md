# 2026-11-11-03 · Sitio web en inglés, portugués y ruso

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-4qkdzd`
- **Fase de la hoja de ruta:** transversal (difusión y comunidad)

## Qué se pidió

Ofrecer el sitio web de Nervi también en inglés, portugués y ruso, con selector de idioma, para que puedan aportar personas de todo el mundo y no solo hispanohablantes.

## Qué se hizo

- Un sitio completo por idioma, sin complementos: `scripts/preparar_sitio.py` arma una carpeta de fuentes por idioma y genera `build/config/mkdocs-<idioma>.yml` a partir de `mkdocs.yml`; `scripts/construir_sitio.py` construye los cuatro con `--strict` y los junta en `build/salida/` (español en la raíz y `/en/`, `/pt/`, `/ru/`). Con `--servir` se ve en local.
- `sitio/idiomas/<en|pt|ru>/`: portada, descargar, primeros pasos, "¿Por qué se llama Nervi?" y la nueva página `participar/index.md`, más `config.yml` con la interfaz (menú, buscador, modo oscuro, aviso, créditos de las fotos). Las páginas de `sitio/` en español siguen siendo el original; el armado falla si a un idioma le falta alguna.
- `sitio/participar/index.md` (en español) y su versión en cada idioma: formas de aportar, que se puede conversar en los cuatro idiomas, que el código y la documentación técnica están en español, y enlaces al glosario y al README de cada idioma (preparados por el hilo de colaboradores internacionales, ver entrada 2026-11-11-02).
- El resto de la documentación (técnica, hoja de ruta, comunidad, bitácora) se publica en español dentro de cada idioma con un aviso al comienzo que lleva al original.
- Selector de idioma en el encabezado (`extra.alternate` de Material) y `sitio/js/idiomas.js`, que al cambiar de idioma deja al lector en la misma página.
- `.github/workflows/sitio.yml`: construye y publica el sitio completo.

## Cómo se verificó

- `python scripts/construir_sitio.py` con los cuatro idiomas y `--strict`, sin advertencias.
- Capturas con Chromium de portada y de una página sin traducir en ruso (el cirílico se ve bien, el aviso lleva al original) y comprobación de que los enlaces del selector conservan la página.
- `ruff check` y `ruff format --check` sobre `scripts/` en verde.

## Decisiones tomadas

- **Un sitio por idioma** en lugar de un complemento de traducción: no agrega dependencias, cada idioma tiene su buscador y su `nav`, y agregar uno es crear su carpeta y sumarlo a `IDIOMAS`.
- Se tradujo solo lo que decide si alguien se queda: portada, instalación, primeros pasos, la página del nombre y cómo participar. La documentación técnica y la bitácora siguen en español, que es el idioma de trabajo del proyecto.
- Las traducciones son del agente y no pasaron por una persona nativa: se agradece su revisión (ruso y portugués en especial).

## Pendiente y problemas conocidos

- Los enlaces a `README.en.md`, `README.pt.md`, `README.ru.md` y `docs/glosario.md` funcionan cuando se integre la entrada 2026-11-11-02.
- Revisión de las traducciones por hablantes nativos.
- Si se compra el dominio propio, actualizar `site_url` y los enlaces de `extra.alternate` en `mkdocs.yml`.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-11 a las 16:52 UTC ("Te autorizo que firmes por mi todos"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Un idioma nuevo: copiar `sitio/idiomas/en/` con su traducción, sumar el código a `IDIOMAS` y a `NOMBRES_IDIOMAS` en `scripts/preparar_sitio.py` y a `extra.alternate` en `mkdocs.yml`.
- Una página nueva en `sitio/` hay que agregarla también a `sitio/idiomas/<idioma>/`.
- Ver el sitio en local: `pip install -r sitio/requirements.txt && python scripts/construir_sitio.py --servir`.
