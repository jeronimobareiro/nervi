# 2026-11-24-08 · Sitio: captura nueva de la interfaz y metas al día

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-4qkdzd`
- **Fase de la hoja de ruta:** transversal (difusión y comunidad)

## Qué se pidió

Actualizar la imagen del programa que se ve en el sitio web con la aplicación actual y ajustar los apartados de metas e hitos al estado real del proyecto.

## Qué se hizo

- `sitio/img/interfaz-claro.png` e `interfaz-oscuro.png` reemplazan a `interfaz.png`: capturas de la ventana actual (panel Estructura, barra lateral con el asistente, Preferencias y Configuración, etapas Geometría a Diseño) del pórtico de ejemplo con la combinación 1.2D+1.6L, en el tema claro y en el nocturno. La portada muestra la que corresponde al tema del lector (clases `nv-claro` y `nv-oscuro`).
- Portada en español, inglés, portugués y ruso: "Qué hace hoy" y "Qué viene" reescritos con lo que ya hay (pórtico espacial preliminar, dinámica, diseño de hormigón armado experimental, memoria PDF, asistente de IA) y el aviso de versión preliminar actualizado.
- `docs/hoja-de-ruta.md`: "Punto de partida" al 24/11/2026 y una columna **Estado** en la tabla de hitos.

## Cómo se verificó

- Las capturas se generaron con la ventana real (`nervi.gui.Ventana`) en modo sin pantalla y se miraron una por una.
- `python scripts/construir_sitio.py` con los cuatro idiomas y `--strict`.
- `python scripts/verificar_bitacora.py origin/main`.

## Decisiones tomadas

- Dos capturas, una por tema, en lugar de una sola: la portada respeta el modo claro u oscuro del sitio, como ya hacen los logotipos.
- Las capturas se redujeron a 1600 px de ancho y 128 colores para que pesen unos 70 KB cada una.
- Los horizontes de la hoja de ruta no se tocaron: siguen siendo tentativos y los decide el responsable del proyecto.

## Documentación actualizada

- `sitio/index.md` y `sitio/idiomas/{en,pt,ru}/index.md`, `docs/hoja-de-ruta.md` y `docs/ESTADO.md`. README, `CONTRIBUTING.md` y `AGENTS.md` no cambian: no hay reglas ni instalación nuevas.

## Firma DCO

- Jerónimo Bareiro autorizó por escrito en el hilo del proyecto (24/11/2026, "firmalo") que el agente agregue su firma a este aporte. Se usó `bareirojero <345933350+bareirojero@users.noreply.github.com>` (AGENTS.md §3.5).

## Pendiente y problemas conocidos

- La captura se rehace a mano cuando cambie mucho la interfaz; conviene un script que la genere (hoy se arma con `Ventana(Sesion(documento_ejemplo()))` y `grab()`).
- Las traducciones de la portada siguen sin revisión de hablantes nativos.

## Para quien siga

- Para regenerar las capturas: abrir el ejemplo, `elegir_tema("claro"|"oscuro")`, `calcular()`, `elegir_combinacion("1.2D+1.6L")`, `ir_a_etapa(3)` y `grab()` con `QT_QPA_PLATFORM=offscreen`.
