# 2026-11-09-05 · Cambio de nombre a Nervi

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `fase-1-portico-2d` (sin subir: cuenta de GitHub suspendida)
- **Fase de la hoja de ruta:** transversal

## Qué se pidió

Reemplazar el nombre "Apex BIM" por **Nervi** en todo el proyecto.

## Qué se hizo

- Crates: `apex-core` → `nervi-core`, `apex-py` → `nervi-py`; tipo `ErrorApex` → `ErrorNervi`.
- Paquete Python: `apex` → `nervi` (`import nervi`, módulo nativo `nervi._core`); paquete de distribución `nervi`.
- README, AGENTS.md, especificación, contrato de datos, ESTADO, CI, pruebas y ejemplo.

## Cómo se verificó

- `cargo test -p nervi-core`: 25 pruebas en verde. `pytest`: 16 pruebas en verde. clippy, rustfmt y ruff sin avisos.
- Búsqueda de "apex" en el repositorio: solo queda la URL del repositorio de GitHub y las entradas anteriores de la bitácora.

## Decisiones tomadas

- Las entradas 01 a 04 de la bitácora conservan el nombre viejo: son historia y no se editan.
- La URL del repositorio (`bareirojero/Apex-BIM`) no se cambia hasta que el usuario renombre el repo en GitHub.

## Pendiente y problemas conocidos

- Renombrar el repositorio en GitHub (Settings → General → Repository name) cuando se recupere la cuenta, y actualizar `repository` en `Cargo.toml`.
- El logo y la maqueta con el nombre nuevo se trabajan aparte.

## Para quien siga

El código de Python ahora se importa con `import nervi`.
