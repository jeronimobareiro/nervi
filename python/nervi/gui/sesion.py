# SPDX-License-Identifier: GPL-3.0-or-later
"""Estado de la sesión de trabajo en la interfaz: el proyecto abierto con señales de Qt.

Toda la lógica (documento, cálculo, diseño, dinámica, memoria, selección) está en
:class:`nervi.proyecto.Proyecto`, que no depende de Qt. :class:`Sesion` lo hereda y
convierte cada evento del proyecto en la señal de Qt que escuchan las vistas.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .. import formato
from ..proyecto import (
    Aviso,
    Inestabilidad,
    Proyecto,
    ResultadosDinamica,
    Seleccion,
    documento_ejemplo,
)

__all__ = [
    "Aviso",
    "Inestabilidad",
    "ResultadosDinamica",
    "Seleccion",
    "Sesion",
    "documento_ejemplo",
]

#: Señal de :class:`Sesion` que corresponde a cada evento de ``Proyecto``.
_SENALES = {
    "archivo": "archivo_cambiado",
    "modelo": "modelo_cambiado",
    "resultados": "resultados_cambiados",
    "seleccion": "seleccion_cambiada",
    "diseno": "diseno_cambiado",
    "dinamica": "dinamica_cambiada",
}


class Sesion(Proyecto, QObject):
    """Proyecto abierto en la interfaz. Emite señales para que las vistas se actualicen."""

    modelo_cambiado = Signal()
    resultados_cambiados = Signal()
    seleccion_cambiada = Signal()
    archivo_cambiado = Signal()
    diseno_cambiado = Signal()
    dinamica_cambiada = Signal()

    def __init__(self, doc: formato.Documento | None = None) -> None:
        # Proyecto.__init__ llama a QObject.__init__ por herencia cooperativa.
        super().__init__(doc)

    def _avisar(self, evento: str) -> None:
        getattr(self, _SENALES[evento]).emit()
        super()._avisar(evento)
