# SPDX-License-Identifier: GPL-3.0-or-later
"""Arma las fuentes del sitio web de Nervi, una carpeta por idioma, en build/sitio/.

El sitio es para el público: quien quiere usar Nervi, aprender con él o sumarse.
Publica las páginas propias de sitio/ y una selección de la documentación técnica
y de comunidad, y la bitácora de aportes. No publica las notas internas de trabajo
(ESTADO.md, con pendientes y decisiones en curso, ni AGENTS.md); los enlaces a esos
archivos y al código llevan a GitHub.

Idiomas: español (completo) e inglés, portugués y ruso (ver IDIOMAS). Cada idioma
traduce las páginas de sitio/idiomas/<idioma>/ (portada, descargar, primeros pasos,
por qué Nervi y participar); el resto de la documentación se publica en español con
un aviso al comienzo. Para agregar un idioma: crear sitio/idiomas/<código>/ con esas
páginas y un config.yml, y sumarlo a IDIOMAS.

El nombre anterior del proyecto no aparece en el sitio. Las entradas viejas de la
bitácora no se editan en el repositorio, así que se adaptan solo al publicarlas
(ver SUSTITUCIONES); el script falla si el nombre queda en alguna página.

Genera además la configuración de MkDocs de cada idioma (build/config/). Para
armar y ver el sitio completo: python scripts/construir_sitio.py [--servir].
"""

from __future__ import annotations

import copy
import posixpath
import re
import shutil
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "build" / "sitio"
CONFIG = RAIZ / "build" / "config"
HTML = RAIZ / "build" / "html"  # una carpeta por idioma
SALIDA = RAIZ / "build" / "salida"  # el sitio final, con todos los idiomas
IDIOMAS = ("es", "en", "pt", "ru")  # el primero es el idioma de origen y vive en la raíz
NOMBRES_IDIOMAS = {"es": "Español", "en": "English", "pt": "Português", "ru": "Русский"}
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


def indice_bitacora(texto: str, rutas: dict, destino: Path) -> str:
    """Reemplaza la tabla escrita a mano por la lista completa de entradas."""
    entradas = sorted(
        (r for r in rutas.values() if r.startswith("bitacora/") and PATRON_ENTRADA.match(r[9:])),
        reverse=True,
    )
    lineas = []
    for ruta in entradas:
        titulo = (destino / ruta).read_text("utf-8").splitlines()[0].lstrip("# ").strip()
        lineas.append(f"- [{titulo}]({posixpath.basename(ruta)})")
    tabla = re.compile(r"\n\| Entrada \|.*?(?=\n\n|\Z)", re.S)
    lista = "\n## Entradas\n\nDe la más reciente a la más antigua.\n\n" + "\n".join(lineas)
    return tabla.sub(lambda _: lista, texto) if tabla.search(texto) else texto + "\n" + lista


def aviso_solo_espanol(texto: str, origen_sitio: str, aviso: dict) -> str:
    """Agrega, debajo del título, el aviso de que la página solo existe en español."""
    partes = origen_sitio.removesuffix(".md").split("/")
    if partes[-1] == "index":
        partes = partes[:-1]
    # La página vive en <idioma>/<partes>/; el original en español, un nivel más arriba.
    destino = "../" * (len(partes) + 1) + "/".join(partes) + ("/" if partes else "")
    bloque = (
        f'\n!!! info "{aviso["titulo"]}"\n'
        f'    {aviso["texto"]} <a href="{destino}">{aviso["enlace"]}</a>.\n'
    )
    return re.sub(r"^(# [^\n]*\n)", lambda m: m[1] + bloque, texto, count=1, flags=re.M)


def leer_idioma(idioma: str) -> dict:
    return yaml.safe_load((RAIZ / "sitio" / "idiomas" / idioma / "config.yml").read_text("utf-8"))


def paginas_propias(idioma: str) -> list[Path]:
    carpeta = RAIZ / "sitio" / "idiomas" / idioma
    return sorted(p for p in carpeta.rglob("*.md"))


def creditos(idioma: str) -> str:
    """Créditos de las fotos de 'Por qué Nervi', traducidos desde la versión en español."""
    texto = (RAIZ / "sitio" / "por-que-nervi.md").read_text("utf-8")
    lineas = [ln for ln in texto.splitlines() if ln.startswith("    - ") and "Commons" in ln]
    if idioma == "es":
        return "\n".join(lineas)
    t = leer_idioma(idioma)["creditos"]
    resultado = []
    for linea in lineas:
        for original, traducido in t.items():
            linea = linea.replace(original, traducido)
        resultado.append(linea)
    return "\n".join(resultado)


def preparar_idioma(idioma: str, rutas: dict) -> int:
    destino = DESTINO / idioma
    ignorar = shutil.ignore_patterns("requirements.txt", "idiomas")
    shutil.copytree(RAIZ / "sitio", destino, ignore=ignorar)
    config = None if idioma == "es" else leer_idioma(idioma)
    if config:
        # Páginas traducidas: reemplazan a las de sitio/.
        traducidas = set()
        for origen in paginas_propias(idioma):
            relativa = origen.relative_to(RAIZ / "sitio" / "idiomas" / idioma).as_posix()
            texto = origen.read_text("utf-8").replace("{{CREDITOS}}", creditos(idioma))
            archivo = destino / relativa
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(texto, "utf-8")
            traducidas.add(relativa)
        esperadas = {p.name for p in (RAIZ / "sitio").glob("*.md")} | {"participar/index.md"}
        faltan = sorted(esperadas - traducidas)
        if faltan:
            print(f"{idioma}: faltan páginas traducidas: {faltan}", file=sys.stderr)
            return 1
    for origen_repo, origen_sitio in rutas.items():
        archivo = destino / origen_sitio
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
            texto = reescribir(texto, origen_repo, origen_sitio, rutas)
            if config:
                texto = aviso_solo_espanol(texto, origen_sitio, config["aviso"])
            archivo.write_text(texto, "utf-8")
        else:
            shutil.copyfile(RAIZ / origen_repo, archivo)
    indice = destino / "bitacora" / "index.md"
    indice.write_text(indice_bitacora(indice.read_text("utf-8"), rutas, destino), "utf-8")
    return 0


def escribir_configuracion(idioma: str) -> None:
    """Escribe build/config/mkdocs-<idioma>.yml a partir de mkdocs.yml (español) y del idioma."""
    cfg = copy.deepcopy(yaml.safe_load((RAIZ / "mkdocs.yml").read_text("utf-8")))
    cfg["docs_dir"] = str(DESTINO / idioma)
    cfg["site_dir"] = str(HTML / idioma)
    if idioma != "es":
        t = leer_idioma(idioma)
        cfg["site_description"] = t["descripcion"]
        cfg["copyright"] = t["copyright"]
        cfg["site_url"] = cfg["site_url"].rstrip("/") + f"/{idioma}/"
        cfg["theme"]["language"] = t["tema"]
        claro, oscuro = cfg["theme"]["palette"]
        claro["toggle"]["name"] = t["modo_oscuro"]
        oscuro["toggle"]["name"] = t["modo_claro"]
        for plugin in cfg["plugins"]:
            if isinstance(plugin, dict) and "search" in plugin:
                plugin["search"]["lang"] = t["busqueda"]
        cfg["nav"] = t["nav"]
    CONFIG.mkdir(parents=True, exist_ok=True)
    (CONFIG / f"mkdocs-{idioma}.yml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), "utf-8"
    )


def main() -> int:
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    rutas = mapa()
    for idioma in IDIOMAS:
        if (codigo := preparar_idioma(idioma, rutas)) != 0:
            return codigo
        escribir_configuracion(idioma)
    errores = [
        f"{md.relative_to(DESTINO)}: contiene {m[0]!r}"
        for md in sorted(DESTINO.rglob("*.md"))
        if (m := PROHIBIDOS.search(md.read_text("utf-8")))
    ]
    for error in errores:
        print(error, file=sys.stderr)
    if errores:
        return 1
    print(f"Sitio preparado en {DESTINO.relative_to(RAIZ)}: {', '.join(IDIOMAS)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
