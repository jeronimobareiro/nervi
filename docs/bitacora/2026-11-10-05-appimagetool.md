# 2026-11-10-05 · Arreglar el armado del AppImage

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-isqnl8`
- **Fase de la hoja de ruta:** vía paralela de interfaz (instaladores)

## Qué se pidió

Saber si Nervi ya es instalable. Para responder se lanzó a mano por primera vez el workflow de publicación sobre `main`.

## Qué se hizo

- `.github/workflows/publicacion.yml`: `appimagetool` se descarga ahora del repositorio `AppImage/appimagetool`, versión fija 1.9.1. La descarga anterior (`AppImageKit`, versión 13) devolvía 404 porque ese archivo ya no existe.

## Cómo se verificó

- Primera corrida manual (run 42872372597): el job de Windows terminó bien (motor, PyInstaller, prueba de arranque e instalador Inno Setup) y el de Linux falló en el paso AppImage con `curl: (22) ... 404`.
- La URL nueva responde 200. El workflow se volvió a correr sobre esta rama antes de abrir el PR.

## Decisiones tomadas

- Versión fija (1.9.1) y no `continuous`, para que el armado sea reproducible.

## Pendiente y problemas conocidos

- Probar el `.exe` en un Windows real y el AppImage en un Linux de escritorio antes de la etiqueta `v0.1.0`.

## Para quien siga

- Si `appimagetool` vuelve a cambiar de lugar, la URL está en la variable `APPIMAGETOOL` al principio del workflow.
