# 2026-11-11-02 · Abrir Nervi a colaboradores de otros idiomas

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-tx48bm`
- **Fase de la hoja de ruta:** transversal (comunidad)

## Qué se pidió

Que personas que no hablan español puedan aportar a Nervi, manteniendo el código en español: README en inglés, portugués y ruso, una sección para colaboradores de otros países en `CONTRIBUTING.md` y un glosario español–inglés–portugués–ruso de términos estructurales.

## Qué se hizo

- `README.en.md`, `README.pt.md` y `README.ru.md`: traducción del README con una sección que explica que el código está en español, que los issues y PR se aceptan en esos idiomas y dónde está el glosario. El ejemplo de uso lleva comentarios con la traducción de cada llamada.
- `README.md`: selector de idioma arriba y una línea en "Contribuir".
- `docs/glosario.md`: glosario es / en / pt / ru con los términos estructurales y los nombres que aparecen en el código (`Modelo`, `agregar_nudo`, `carga_uniforme`, `reacciones`, etiquetas de issues, etc.).
- `CONTRIBUTING.md`: la regla de idioma aclara que issues, PR y conversaciones pueden ser en español, inglés, portugués o ruso; nueva sección "Contributing from other countries" con un párrafo en cada idioma.
- `AGENTS.md`: los agentes responden en el idioma de quien escribe, suman al glosario los términos nuevos y mantienen al día los README traducidos.

## Cómo se verificó

- Revisión de enlaces relativos entre los README, el glosario y `CONTRIBUTING.md` (el ancla `#contributing-from-other-countries` corresponde al título de la sección).
- `scripts/preparar_sitio.py` convierte los enlaces nuevos de `CONTRIBUTING.md` en enlaces a GitHub, porque esos archivos no se publican en el sitio.
- No hay cambios de código; no aplican pruebas nuevas.

## Decisiones tomadas

- El código, los comentarios y la documentación técnica siguen en español (regla de `AGENTS.md`). Renombrar la API a inglés rompería compatibilidad y no hace falta para que otros aporten.
- Los README traducidos indican que, si difieren, prevalece la versión en español.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-11 a las 16:52 UTC ("Te autorizo que firmes por mi todos"), que el agente firme en su nombre. Se usó `bareirojero <345933350+bareirojero@users.noreply.github.com>`, como en la entrada 2026-11-09-09.
- Nombres acordados con el trabajo del sitio multilingüe (en/pt/ru), que enlaza a estos archivos: `README.en.md`, `README.pt.md`, `README.ru.md` y `docs/glosario.md`. Este aporte no toca `sitio/` ni `mkdocs.yml`.

## Pendiente y problemas conocidos

- Las traducciones (sobre todo portugués y ruso) conviene que las revise un hablante nativo con formación en estructuras; algunos términos tienen variantes regionales (por ejemplo "concreto"/"betão" en portugués).
- La interfaz de escritorio y los mensajes de error siguen solo en español.
- La plantilla de issues y PR sigue en español.

## Para quien siga

- Si cambia lo que Nervi hace, actualizá `README.md` y los tres `README.*.md` en el mismo PR.
- Siguientes pasos posibles: plantillas de issues bilingües y traducción de la interfaz (Qt tiene soporte de traducciones).
