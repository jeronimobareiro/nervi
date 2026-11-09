# 2026-11-09-07 · Archivos de comunidad, DCO y control de licencias

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `fase-1-portico-2d` (sin subir: cuenta de GitHub suspendida)
- **Fase de la hoja de ruta:** 0 (repositorio, guía de contribución)

## Qué se pidió

Preparar Nervi para recibir aportes de universidades y de cualquier persona, y reducir riesgos de propiedad intelectual, siguiendo el informe "Nervi: apertura open source y propiedad intelectual".

## Qué se hizo

- `CONTRIBUTING.md`: cómo aportar, reglas de código, qué no se puede subir (código ajeno, texto de normas, formatos propietarios), DCO, bitácora y uso de IA.
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1 en español, con contacto jerobareiro@gmail.com.
- `GOVERNANCE.md`: roles (contribuyente, revisor técnico, mantenedor, responsable), cómo se decide, revisión obligatoria de módulos normativos, camino a un comité técnico y uso de la marca.
- `SECURITY.md`: reporte privado de resultados incorrectos que afecten la seguridad y límite de responsabilidad.
- `CITATION.cff` y `AUTHORS.md`; aviso de copyright y de normas en el README.
- Plantillas de issues (error, propuesta) y de PR en `.github/`.
- Encabezado `SPDX-License-Identifier: GPL-3.0-or-later` en todos los archivos `.rs` y `.py`.
- `deny.toml` y trabajo "Licencias de dependencias" en el CI (`cargo-deny`): solo licencias compatibles con GPL-3.0 y solo crates.io.
- `scripts/verificar_dco.py` (con pruebas en `tests/test_verificar_dco.py`) y trabajo "Certificado de origen (DCO)" en el CI.
- `AGENTS.md`: SPDX, DCO para agentes y nuevas prohibiciones (texto de normas, ingeniería inversa, licencias fuera de `deny.toml`).
- Especificación §1.1: la licencia queda decidida como GPL-3.0-or-later.

## Cómo se verificó

- `cargo deny check licenses bans sources` en verde con el `Cargo.lock` actual.
- `cargo fmt`, `clippy`, `cargo test -p nervi-core`, `pytest` y `ruff` en verde.
- `verificar_dco.py` contra la rama: exceptúa los commits anteriores a su adopción y exige firma a los siguientes.

## Decisiones tomadas

- Licencia: GPL-3.0-or-later para todo; se descartó MPL-2.0/LGPL para el núcleo.
- DCO en lugar de CLA: más simple para estudiantes y no exige cesión de derechos. Si algún día se quiere licencia dual, hará falta un CLA (consultar abogado).
- El DCO se exige solo a commits cuyo padre ya incluye `verificar_dco.py`, para no firmar historia retroactivamente. Este commit queda exceptuado.
- Una IA no firma el DCO: lo firma la persona que pidió el trabajo antes de subir (`git rebase --signoff origin/main`).

## Pendiente y problemas conocidos

- Confirmar el correo de contacto de `CODE_OF_CONDUCT.md` y `SECURITY.md`, o reemplazarlo por uno del proyecto.
- Al recuperar GitHub o mudarse a GitLab: actualizar `repository` en `Cargo.toml` y `pyproject.toml`; en GitLab, portar el CI a `.gitlab-ci.yml`.
- Crear las etiquetas `buen-primer-aporte` y `tesis-posible` en el gestor de issues.
- Publicar la primera versión en Zenodo y agregar el DOI a `CITATION.cff`.
- README en inglés y notebooks didácticos.
- Búsqueda y registro de la marca Nervi (DINAPI, clases 9 y 42).

## Para quien siga

Los commits nuevos necesitan `Signed-off-by` de una persona. Leé `CONTRIBUTING.md` además de `AGENTS.md`.
