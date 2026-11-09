# SPDX-License-Identifier: GPL-3.0-or-later
"""Verifica que un cambio registre su aporte en la bitácora (ver AGENTS.md).

Reglas, comparando la rama actual contra una base (por ejemplo origin/main):

1. Si cambió algo fuera de la documentación de seguimiento, el cambio debe
   *agregar* al menos una entrada nueva en docs/bitacora/ con nombre
   AAAA-MM-DD-NN-tema.md y debe modificar docs/ESTADO.md.
2. Las entradas existentes de la bitácora no se modifican ni se borran.
3. Cada entrada nueva tiene las secciones de la plantilla.

Uso:  python scripts/verificar_bitacora.py [BASE]        (por defecto origin/main)
Salida distinta de cero si alguna regla no se cumple.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BITACORA = "docs/bitacora/"
ESTADO = "docs/ESTADO.md"
PATRON_ENTRADA = re.compile(r"^docs/bitacora/\d{4}-\d{2}-\d{2}-\d{2}-[a-z0-9-]+\.md$")
# Archivos de la bitácora que sí se pueden editar.
EDITABLES = {"docs/bitacora/README.md", "docs/bitacora/_plantilla.md", ESTADO}
SECCIONES = [
    "## Qué se pidió",
    "## Qué se hizo",
    "## Pendiente y problemas conocidos",
    "## Para quien siga",
]


def cambios(base: str) -> list[tuple[str, str]]:
    """Lista de (estado, ruta) entre la base común y HEAD."""
    salida = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    resultado = []
    for linea in salida.splitlines():
        estado, ruta = linea.split("\t", 1)
        resultado.append((estado[0], ruta))
    return resultado


def verificar(lista: list[tuple[str, str]], leer=lambda r: Path(r).read_text("utf-8")) -> list[str]:
    errores: list[str] = []
    seguimiento = {r for _, r in lista if r.startswith(BITACORA) or r in EDITABLES}
    codigo = [r for _, r in lista if r not in seguimiento]

    nuevas = [r for e, r in lista if e == "A" and PATRON_ENTRADA.match(r)]
    for e, r in lista:
        if r.startswith(BITACORA) and r not in EDITABLES:
            if e in ("M", "D"):
                errores.append(
                    f"{r}: las entradas de la bitácora no se editan ni se borran; "
                    "agregá una entrada nueva con la corrección"
                )
            elif e == "A" and not PATRON_ENTRADA.match(r):
                errores.append(
                    f"{r}: el nombre debe ser docs/bitacora/AAAA-MM-DD-NN-tema.md "
                    "(minúsculas, números y guiones)"
                )

    if codigo:
        if not nuevas:
            errores.append(
                "el cambio modifica código o configuración pero no agrega una entrada en "
                "docs/bitacora/ (copiá docs/bitacora/_plantilla.md; ver AGENTS.md)"
            )
        if ESTADO not in seguimiento:
            errores.append(
                "el cambio modifica código o configuración pero no actualiza docs/ESTADO.md"
            )

    for r in nuevas:
        texto = leer(r)
        faltan = [s for s in SECCIONES if s not in texto]
        if faltan:
            errores.append(f"{r}: faltan las secciones {', '.join(faltan)}")
    return errores


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    errores = verificar(cambios(base))
    if errores:
        print("Bitácora incompleta (ver AGENTS.md, sección 3):")
        for e in errores:
            print(f"  - {e}")
        return 1
    print("Bitácora en orden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
