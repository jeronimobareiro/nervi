# SPDX-License-Identifier: GPL-3.0-or-later
"""Crea o actualiza las etiquetas y los hitos de la hoja de ruta en GitHub.

Lee .github/hoja-de-ruta.json y, con la CLI `gh` (variable GH_TOKEN):

1. Crea cada etiqueta que falte y actualiza color y descripción de las existentes.
2. Crea cada hito (milestone) que falte.
3. Asigna a cada hito los issues con su etiqueta de fase que todavía no tienen hito.

Es idempotente: se puede correr varias veces. Lo ejecuta el flujo
.github/workflows/hoja-de-ruta.yml a mano (workflow_dispatch).

Uso:  python scripts/organizar_hoja_de_ruta.py OWNER/REPO [--simular]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

PLAN = Path(__file__).resolve().parents[1] / ".github" / "hoja-de-ruta.json"


def cargar_plan(ruta: Path = PLAN) -> dict:
    return json.loads(ruta.read_text("utf-8"))


def validar_plan(plan: dict) -> list[str]:
    """Errores de consistencia del plan (vacío si está bien)."""
    errores = []
    etiquetas = [e["nombre"] for e in plan["etiquetas"]]
    if len(etiquetas) != len(set(etiquetas)):
        errores.append("hay etiquetas repetidas")
    titulos = [h["titulo"] for h in plan["hitos"]]
    if len(titulos) != len(set(titulos)):
        errores.append("hay hitos repetidos")
    for e in plan["etiquetas"]:
        color = e["color"]
        if len(color) != 6 or any(c not in "0123456789ABCDEFabcdef" for c in color):
            errores.append(f"color inválido en la etiqueta {e['nombre']}: {color}")
    for h in plan["hitos"]:
        if h["etiqueta"] not in etiquetas:
            errores.append(f"el hito {h['titulo']} usa una etiqueta inexistente: {h['etiqueta']}")
    return errores


def gh(*args: str, simular: bool = False, escritura: bool = False) -> object:
    """Llama a `gh api` y devuelve el JSON. En modo simulación no escribe nada."""
    if simular and escritura:
        print("[simulación] gh api", " ".join(args))
        return {}
    salida = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(salida) if salida.strip() else {}


def listar(ruta: str) -> list[dict]:
    """GET paginado; `gh --paginate --slurp` devuelve una lista de páginas."""
    paginas = gh("--paginate", "--slurp", ruta)
    return [item for pagina in paginas for item in pagina]


def organizar(repo: str, plan: dict, simular: bool = False) -> None:
    existentes = {e["name"]: e for e in listar(f"repos/{repo}/labels?per_page=100")}
    for e in plan["etiquetas"]:
        campos = ["-f", f"color={e['color']}", "-f", f"description={e['descripcion']}"]
        actual = existentes.get(e["nombre"])
        if actual is None:
            print(f"Etiqueta nueva: {e['nombre']}")
            gh(
                "-X",
                "POST",
                f"repos/{repo}/labels",
                "-f",
                f"name={e['nombre']}",
                *campos,
                simular=simular,
                escritura=True,
            )
        elif (
            actual["color"].lower() != e["color"].lower()
            or (actual.get("description") or "") != e["descripcion"]
        ):
            print(f"Etiqueta actualizada: {e['nombre']}")
            gh(
                "-X",
                "PATCH",
                f"repos/{repo}/labels/{quote(e['nombre'])}",
                *campos,
                simular=simular,
                escritura=True,
            )

    hitos = {h["title"]: h for h in listar(f"repos/{repo}/milestones?state=all&per_page=100")}
    for h in plan["hitos"]:
        if h["titulo"] not in hitos:
            print(f"Hito nuevo: {h['titulo']}")
            hitos[h["titulo"]] = gh(
                "-X",
                "POST",
                f"repos/{repo}/milestones",
                "-f",
                f"title={h['titulo']}",
                "-f",
                f"description={h['descripcion']}",
                simular=simular,
                escritura=True,
            )
        numero = hitos[h["titulo"]].get("number")
        issues = listar(f"repos/{repo}/issues?labels={quote(h['etiqueta'])}&state=all&per_page=100")
        for issue in issues:
            if issue.get("milestone") is None and "pull_request" not in issue:
                print(f"  #{issue['number']} → {h['titulo']}")
                gh(
                    "-X",
                    "PATCH",
                    f"repos/{repo}/issues/{issue['number']}",
                    "-F",
                    f"milestone={numero}",
                    simular=simular,
                    escritura=True,
                )


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    plan = cargar_plan()
    errores = validar_plan(plan)
    if errores:
        for e in errores:
            print(f"error: {e}", file=sys.stderr)
        return 1
    organizar(argv[0], plan, simular="--simular" in argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
