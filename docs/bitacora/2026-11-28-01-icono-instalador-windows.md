# 2026-11-28-01 · Arreglar el ícono del instalador de Windows

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-isqnl8`
- **Fase de la hoja de ruta:** vía paralela de interfaz (instaladores)

## Qué se pidió

Generar un instalador de Windows desde el `main` del día para probarlo.

## Qué se hizo

- `packaging/pyinstaller/nervi.spec`: la ruta de `NERVI_ICONO` se pasa a absoluta antes de dársela a PyInstaller.

## Cómo se verificó

- La corrida manual 46090870625 del workflow de publicación falló en Windows con `FileNotFoundError: Icon input file D:\a\nervi\nervi\packaging\pyinstaller\build/iconos/nervi.ico not found`. PyInstaller resolvió la ruta relativa `build/iconos/nervi.ico` contra la carpeta de la receta (`packaging/pyinstaller/`). Linux no pasa ícono y salió bien.
- Se volvió a correr el workflow sobre esta rama antes de abrir el PR.

## Decisiones tomadas

- El arreglo va en la receta y no en el workflow, para que también funcione al generar el instalador a mano.

## Documentación actualizada

- `docs/ESTADO.md` (fecha y entrada). No hizo falta tocar README ni la documentación técnica: el cambio es interno a la receta de empaquetado.

## Pendiente y problemas conocidos

- Probar el instalador en un Windows real antes de la etiqueta `v0.1.0`.

## Para quien siga

- Cualquier ruta que llegue a la receta por variable de entorno conviene pasarla a absoluta.
