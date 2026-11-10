# SPDX-License-Identifier: GPL-3.0-or-later
"""Arma las fuentes del sitio web de Nervi a partir de la documentación del repositorio.

El sitio es para el público: quien quiere usar Nervi, aprender con él o sumarse.
Publica las páginas propias de sitio/ y una selección de la documentación técnica
y de comunidad, y la bitácora de aportes. No publica las notas internas de trabajo
(ESTADO.md, con pendientes y decisiones en curso, ni AGENTS.md); los enlaces a esos
archivos y al código llevan a GitHub.

El nombre anterior del proyecto no aparece en el sitio. Las entradas viejas de la
bitácora no se editan en el repositorio, así que se adaptan solo al publicarlas
(ver SUSTITUCIONES); el script falla si el nombre queda en alguna página.

    python scripts/preparar_sitio.py && mkdocs build --strict
    (o mkdocs serve para verlo en http://127.0.0.1:8000)
"""

from __future__ import annotations

import posixpath
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "build" / "sitio"
GITHUB = "https://github.com/jeronimobareiro/nervi"

# Ruta en el repositorio -> ruta en el sitio. Los .md se reescriben; el resto se copia.
PAGINAS = {
    "docs/especificacion-tecnica.md": "tecnica/especificacion.md",
    "docs/convenciones.md": "tecnica/convenciones.md",
    "docs/contrato-datos.md": "tecnica/contrato-datos.md",
    "docs/formato-nrv.md": "tecnica/formato-nrv.md",
    "docs/hoja-de-ruta.md": "hoja-de-ruta.md",
    "CONTRIBUTING.md": "participar/contribuir.md",
    "CODE_OF_CONDUCT.md": "participar/codigo-de-conducta.md",
    "GOVERNANCE.md": "participar/gobierno.md",
    "SECURITY.md": "participar/seguridad.md",
    "AUTHORS.md": "participar/autores.md",
    "docs/bitacora/README.md": "bitacora/index.md",
}
CARPETAS = {"docs/marca": "marca", "docs/esquemas": "esquemas"}
# Partes de mantenimiento interno que no se publican: (patrón, reemplazo) por archivo.
QUITAR = {
    "docs/hoja-de-ruta.md": [
        (r"\n_Plan de desarrollo[^\n]*_\n", "\n"),
        (r"\n- Qué está hecho hoy:[^\n]*", ""),
        (r"\n- Qué se hizo y por qué:[^\n]*", ""),
        (r"\n## Cómo se mantiene este plan\n.*?(?=\n## |\Z)", ""),
    ],
    "CONTRIBUTING.md": [(r" Los agentes de IA siguen además \[`AGENTS\.md`\]\(AGENTS\.md\)\.", "")],
}
# Entradas de la bitácora anteriores al cambio de nombre: se publican sin el nombre viejo.
SUSTITUCIONES = [
    (r'Reemplazar el nombre "Apex BIM" por', "Reemplazar el nombre anterior del proyecto por"),
    (
        r"Crates: `apex-core` → `nervi-core`, `apex-py` → `nervi-py`; "
        r"tipo `ErrorApex` → `ErrorNervi`\.",
        "Crates `nervi-core` y `nervi-py`; tipo de error `ErrorNervi`.",
    ),
    (r"Paquete Python: `apex` → `nervi` \(", "Paquete Python `nervi` ("),
    (r'Búsqueda de "apex" en el repositorio', "Búsqueda del nombre anterior en el repositorio"),
    (r"La URL del repositorio \(`bareirojero/Apex-BIM`\)", "La URL del repositorio anterior"),
    (r" \(`bareirojero/Apex-BIM`\)", ""),
    (r"`apex_bim_repository\.zip`", "archivo comprimido del prototipo"),
    (r"apex-(core|py)", r"nervi-\1"),
    (r"python/apex\b", "python/nervi"),
]
# Nombres que ya no deben aparecer en el sitio.
PROHIBIDOS = re.compile(r"apex", re.I)
# Enlaces Markdown en línea: [texto](destino) o ![alt](destino).
PATRON_ENLACE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)\)")
PATRON_SRCSET = re.compile(r'((?:src|srcset)=")([^"]+)(")')
PATRON_ENTRADA = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}-[a-z0-9-]+\.md$")


def mapa() -> dict[str, str]:
    """Todas las rutas del repositorio que se publican, con su ruta en el sitio."""
    rutas = dict(PAGINAS)
    for entrada in sorted((RAIZ / "docs" / "bitacora").glob("*.md")):
        if PATRON_ENTRADA.match(entrada.name):
            rutas[f"docs/bitacora/{entrada.name}"] = f"bitacora/{entrada.name}"
    for origen, destino in CARPETAS.items():
        for archivo in sorted((RAIZ / origen).iterdir()):
            rutas[f"{origen}/{archivo.name}"] = f"{destino}/{archivo.name}"
    return rutas


def convertir_enlace(destino: str, origen_repo: str, origen_sitio: str, rutas: dict) -> str:
    """Convierte un enlace relativo del repositorio en uno válido dentro del sitio."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", destino) or destino.startswith(("#", "/")):
        return destino
    ruta, _, ancla = destino.partition("#")
    if not ruta:
        return destino
    en_repo = posixpath.normpath(posixpath.join(posixpath.dirname(origen_repo), ruta))
    es_carpeta = ruta.endswith("/") or (RAIZ / en_repo).is_dir()
    if es_carpeta and f"{en_repo}/README.md" in rutas:
        en_repo = f"{en_repo}/README.md"
    if en_repo in rutas:
        nuevo = posixpath.relpath(rutas[en_repo], posixpath.dirname(origen_sitio) or ".")
    elif es_carpeta and en_repo in CARPETAS:
        nuevo = f"{GITHUB}/tree/main/{en_repo}"
    else:
        tipo = "tree" if es_carpeta else "blob"
        nuevo = f"{GITHUB}/{tipo}/main/{en_repo}"
    return f"{nuevo}#{ancla}" if ancla else nuevo


def reescribir(texto: str, origen_repo: str, origen_sitio: str, rutas: dict) -> str:
    def enlace(m: re.Match) -> str:
        return f"{m[1]}({convertir_enlace(m[2], origen_repo, origen_sitio, rutas)})"

    def atributo(m: re.Match) -> str:
        return f"{m[1]}{convertir_enlace(m[2], origen_repo, origen_sitio, rutas)}{m[3]}"

    return PATRON_SRCSET.sub(atributo, PATRON_ENLACE.sub(enlace, texto))


def indice_bitacora(texto: str, rutas: dict) -> str:
    """Reemplaza la tabla escrita a mano por la lista completa de entradas."""
    entradas = sorted(
        (r for r in rutas.values() if r.startswith("bitacora/") and PATRON_ENTRADA.match(r[9:])),
        reverse=True,
    )
    lineas = []
    for ruta in entradas:
        titulo = (DESTINO / ruta).read_text("utf-8").splitlines()[0].lstrip("# ").strip()
        lineas.append(f"- [{titulo}]({posixpath.basename(ruta)})")
    tabla = re.compile(r"\n\| Entrada \|.*?(?=\n\n|\Z)", re.S)
    lista = "\n## Entradas\n\nDe la más reciente a la más antigua.\n\n" + "\n".join(lineas)
    return tabla.sub(lambda _: lista, texto) if tabla.search(texto) else texto + "\n" + lista


def main() -> int:
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    shutil.copytree(RAIZ / "sitio", DESTINO, ignore=shutil.ignore_patterns("requirements.txt"))
    rutas = mapa()
    for origen_repo, origen_sitio in rutas.items():
        archivo = DESTINO / origen_sitio
        archivo.parent.mkdir(parents=True, exist_ok=True)
        if origen_repo.endswith(".md"):
            texto = (RAIZ / origen_repo).read_text("utf-8")
            for patron, reemplazo in QUITAR.get(origen_repo, []):
                texto, n = re.subn(patron, reemplazo, texto, flags=re.S)
                if n == 0:
                    print(f"{origen_repo}: no se encontró {patron!r}", file=sys.stderr)
                    return 1
            if PATRON_ENTRADA.match(posixpath.basename(origen_repo)):
                for patron, reemplazo in SUSTITUCIONES:
                    texto = re.sub(patron, reemplazo, texto)
            archivo.write_text(reescribir(texto, origen_repo, origen_sitio, rutas), "utf-8")
        else:
            shutil.copyfile(RAIZ / origen_repo, archivo)
    indice = DESTINO / "bitacora" / "index.md"
    indice.write_text(indice_bitacora(indice.read_text("utf-8"), rutas), "utf-8")
    errores = [
        f"{md.relative_to(DESTINO)}: contiene {m[0]!r}"
        for md in sorted(DESTINO.rglob("*.md"))
        if (m := PROHIBIDOS.search(md.read_text("utf-8")))
    ]
    for error in errores:
        print(error, file=sys.stderr)
    if errores:
        return 1
    print(f"Sitio preparado en {DESTINO.relative_to(RAIZ)} ({len(rutas)} archivos de docs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
