# SPDX-License-Identifier: GPL-3.0-or-later
"""Arma el sitio web completo, en todos los idiomas, en build/salida/.

Uso:
    python scripts/construir_sitio.py            # prepara y construye (con --strict)
    python scripts/construir_sitio.py --servir   # además lo sirve en http://localhost:8000/nervi/

El español queda en la raíz y los demás idiomas en /en/, /pt/ y /ru/. Requiere las
dependencias de sitio/requirements.txt.
"""

from __future__ import annotations

import functools
import http.server
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import preparar_sitio  # noqa: E402


def main() -> int:
    if (codigo := preparar_sitio.main()) != 0:
        return codigo
    entorno = {**os.environ, "NO_MKDOCS_2_WARNING": "1"}
    for idioma in preparar_sitio.IDIOMAS:
        config = preparar_sitio.CONFIG / f"mkdocs-{idioma}.yml"
        # --strict: un enlace roto o una página faltante deja el control en rojo.
        resultado = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict", "-q", "-f", str(config)],
            cwd=RAIZ,
            env=entorno,
        )
        if resultado.returncode != 0:
            print(f"Falló la construcción del idioma {idioma}.", file=sys.stderr)
            return resultado.returncode
    # Un solo árbol para publicar: español en la raíz y los demás idiomas en su carpeta.
    salida = preparar_sitio.SALIDA
    if salida.exists():
        shutil.rmtree(salida)
    for idioma in preparar_sitio.IDIOMAS:
        destino = salida if idioma == preparar_sitio.IDIOMAS[0] else salida / idioma
        shutil.copytree(preparar_sitio.HTML / idioma, destino, dirs_exist_ok=True)
    print(f"Sitio construido en {salida.relative_to(RAIZ)}.")
    if "--servir" in sys.argv:
        # El sitio se publica bajo /nervi/, así que se sirve con ese prefijo.
        raiz_local = salida.parent / "local"
        raiz_local.mkdir(exist_ok=True)
        enlace = raiz_local / "nervi"
        if not enlace.is_symlink():
            enlace.symlink_to(salida, target_is_directory=True)
        manejador = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(raiz_local)
        )
        print("Sirviendo en http://localhost:8000/nervi/ (Ctrl+C para salir)")
        http.server.ThreadingHTTPServer(("", 8000), manejador).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
