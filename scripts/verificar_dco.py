# SPDX-License-Identifier: GPL-3.0-or-later
"""Verifica que los commits de un cambio estén firmados con el DCO (ver CONTRIBUTING.md).

Cada commit nuevo debe tener una línea ``Signed-off-by: Nombre <correo>``. Los commits
anteriores a la adopción del DCO (los que no tienen este script en su commit padre)
quedan exceptuados, para no exigir firma retroactiva.

Uso:  python scripts/verificar_dco.py [BASE]        (por defecto origin/main)
Salida distinta de cero si algún commit no está firmado.
"""

from __future__ import annotations

import re
import subprocess
import sys

ESTE_SCRIPT = "scripts/verificar_dco.py"
FIRMA = re.compile(r"^Signed-off-by: .+ <[^<>@\s]+@[^<>\s]+>\s*$", re.MULTILINE)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def tiene_script(commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}:{ESTE_SCRIPT}"], capture_output=True
        ).returncode
        == 0
    )


def exigible(commit: str) -> bool:
    """El DCO se exige a los commits cuyo padre ya incluía este control."""
    padres = git("rev-list", "--parents", "-n", "1", commit).split()[1:]
    return any(tiene_script(p) for p in padres)


def firmado(mensaje: str) -> bool:
    return bool(FIRMA.search(mensaje))


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    commits = git("rev-list", "--no-merges", f"{base}..HEAD").split()
    faltan = []
    for c in commits:
        if exigible(c) and not firmado(git("log", "-1", "--format=%B", c)):
            faltan.append(git("log", "-1", "--format=%h %s", c).strip())
    if faltan:
        print("Commits sin 'Signed-off-by' (firmalos con: git rebase --signoff " + base + "):")
        for f in faltan:
            print(f"  - {f}")
        print("Ver la sección 'Certificado de origen (DCO)' de CONTRIBUTING.md.")
        return 1
    print(f"DCO: {len(commits)} commit(s) revisados, todo en orden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
