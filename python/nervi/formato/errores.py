# SPDX-License-Identifier: GPL-3.0-or-later
"""Error de formato con archivo y ruta JSON (``docs/formato-nrv.md`` §4.1)."""

from __future__ import annotations


class FormatoError(ValueError):
    """El archivo no es un proyecto de Nervi válido.

    ``miembro`` es el archivo dentro del ZIP (por ejemplo ``modelo.json``) y
    ``ruta`` la ruta JSON del dato (por ejemplo ``barras[3].j``)."""

    def __init__(self, motivo: str, miembro: str = "", ruta: str = "") -> None:
        self.motivo = motivo
        self.miembro = miembro
        self.ruta = ruta
        lugar = ": ".join(p for p in (miembro, ruta) if p)
        super().__init__(f"{lugar}: {motivo}" if lugar else motivo)
