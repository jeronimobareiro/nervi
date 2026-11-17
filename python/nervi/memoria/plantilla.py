# SPDX-License-Identifier: GPL-3.0-or-later
"""Plantilla editable de la memoria: títulos, textos y formato de los números.

La plantilla por defecto es ``plantilla.toml`` (junto a este archivo). Una
plantilla propia solo necesita las claves que cambia; el resto se toma de la
plantilla por defecto.
"""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10
    import tomli as tomllib


class _Faltantes(dict):
    """Deja ``{clave}`` tal cual si no hay valor para esa clave."""

    def __missing__(self, clave: str) -> str:
        return "{" + clave + "}"


def _fusionar(base: dict, propia: dict) -> dict:
    salida = dict(base)
    for k, v in propia.items():
        if isinstance(v, dict) and isinstance(salida.get(k), dict):
            salida[k] = _fusionar(salida[k], v)
        else:
            salida[k] = v
    return salida


class Plantilla:
    """Textos de la memoria con sus variables ya reemplazadas."""

    def __init__(self, datos: dict[str, Any], variables: dict[str, str]) -> None:
        self.datos = datos
        self.variables = _Faltantes(variables)

    @classmethod
    def cargar(
        cls, ruta: str | Path | dict | None = None, variables: dict[str, str] | None = None
    ) -> Plantilla:
        """Plantilla por defecto fusionada con ``ruta`` (archivo TOML o diccionario)."""
        texto = resources.files(__package__).joinpath("plantilla.toml").read_text("utf-8")
        datos = tomllib.loads(texto)
        if isinstance(ruta, dict):
            datos = _fusionar(datos, ruta)
        elif ruta is not None:
            with open(ruta, "rb") as f:
                datos = _fusionar(datos, tomllib.load(f))
        return cls(datos, variables or {})

    def texto(self, clave: str) -> str:
        """Texto de ``[textos]`` (o de la raíz si la clave tiene un punto, como
        ``"portada.aviso"``), con las variables reemplazadas."""
        if "." in clave:
            seccion, nombre = clave.split(".", 1)
            valor = self.datos.get(seccion, {}).get(nombre, "")
        else:
            valor = self.datos.get("textos", {}).get(clave, self.datos.get(clave, ""))
        return str(valor).format_map(self.variables).strip()

    @property
    def decimal(self) -> str:
        return str(self.datos.get("decimal", ","))

    @property
    def cifras(self) -> int:
        return int(self.datos.get("cifras", 4))

    @property
    def campos_portada(self) -> list[str]:
        return list(self.datos.get("portada", {}).get("campos", []))
