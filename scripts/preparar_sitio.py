# SPDX-License-Identifier: GPL-3.0-or-later
"""Arma las fuentes del sitio web de Nervi a partir de la documentación del repositorio.

La documentación vive una sola vez, en docs/ y en los archivos de comunidad de la raíz.
Este script la copia a build/sitio/ junto con las páginas propias del sitio (sitio/),
corrige los enlaces relativos y genera el índice de la bitácora. Después:

    mkdocs build --strict      (o mkdocs serve para verla en http://127.0.0.1:8000)

Los enlaces a archivos que no forman parte del sitio (código, LICENSE, plantillas)
se convierten en enlaces a GitHub.

Uso:  python scripts/preparar_sitio.py
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
    "README.md": "guia-rapida.md",
    "docs/ESTADO.md": "estado.md",
    "docs/especificacion-tecnica.md": "especificacion-tecnica.md",
    "docs/hoja-de-ruta.md": "hoja-de-ruta.md",
    "docs/convenciones.md": "convenciones.md",
    "docs/contrato-datos.md": "contrato-datos.md",
    "docs/formato-nrv.md": "formato-nrv.md",
    "docs/bitacora/README.md": "bitacora/index.md",
    "CONTRIBUTING.md": "comunidad/contribuir.md",
    "CODE_OF_CONDUCT.md": "comunidad/codigo-de-conducta.md",
    "GOVERNANCE.md": "comunidad/gobierno.md",
    "SECURITY.md": "comunidad/seguridad.md",
    "AUTHORS.md": "comunidad/autores.md",
    "AGENTS.md": "comunidad/agentes-ia.md",
}
CARPETAS = {"docs/marca": "marca", "docs/esquemas": "esquemas"}
PATRON_ENTRADA = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}-[a-z0-9-]+\.md$")
# Enlaces Markdown en línea: [texto](destino) o ![alt](destino).
PATRON_ENLACE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)\)")
PATRON_SRCSET = re.compile(r'((?:src|srcset)=")([^"]+)(")')


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


def guia_rapida(texto: str) -> str:
    """El README sin el logo ni el título: el sitio ya los muestra."""
    inicio = texto.index("\n## ")
    return "# Guía rápida\n" + texto[inicio:]


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
            if origen_repo == "README.md":
                texto = guia_rapida(texto)
            archivo.write_text(reescribir(texto, origen_repo, origen_sitio, rutas), "utf-8")
        else:
            shutil.copyfile(RAIZ / origen_repo, archivo)
    indice = DESTINO / "bitacora" / "index.md"
    indice.write_text(indice_bitacora(indice.read_text("utf-8"), rutas), "utf-8")
    print(f"Sitio preparado en {DESTINO.relative_to(RAIZ)} ({len(rutas)} archivos de docs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
