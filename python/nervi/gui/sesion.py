# SPDX-License-Identifier: GPL-3.0-or-later
"""Estado de la sesión de trabajo: documento abierto, cálculo y selección.

La interfaz no guarda datos propios: todo cambio pasa por el diccionario de
``modelo.json`` del documento (``nervi.formato``), y el cálculo se hace con
``nervi.formato.construir_modelo`` + ``Modelo.resolver``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .. import MecanismoError, formato
from ..modelo import ResultadoCaso, Resultados


@dataclass(frozen=True)
class Seleccion:
    tipo: str  # "barra" o "nudo"
    id: int


@dataclass
class Aviso:
    nivel: str  # "ok", "info", "error"
    texto: str


def documento_ejemplo() -> formato.Documento:
    """Pórtico de una crujía de ``examples/portico_simple.py`` (kN, m)."""
    from ..modelo import Modelo

    E = 2.5e7
    columna = dict(E=E, A=0.30 * 0.30, I=0.30 * 0.30**3 / 12)
    viga = dict(E=E, A=0.25 * 0.50, I=0.25 * 0.50**3 / 12)
    m = Modelo()
    a, b = m.agregar_nudo(0.0, 0.0), m.agregar_nudo(0.0, 3.0)
    c, d = m.agregar_nudo(6.0, 3.0), m.agregar_nudo(6.0, 0.0)
    m.agregar_barra(a, b, **columna)
    v = m.agregar_barra(b, c, **viga)
    m.agregar_barra(d, c, **columna)
    m.apoyar(a)
    m.apoyar(d)
    m.carga_uniforme("D", v, qy=-20.0)
    m.carga_uniforme("L", v, qy=-10.0)
    m.carga_nodal("W", b, fx=15.0)
    return formato.Documento.desde_modelo(
        m,
        {
            "1.4D": {"D": 1.4},
            "1.2D+1.6L": {"D": 1.2, "L": 1.6},
            "1.2D+1.0L+1.0W": {"D": 1.2, "L": 1.0, "W": 1.0},
        },
    )


class Sesion(QObject):
    """Documento abierto y su estado. Emite señales para que las vistas se actualicen."""

    modelo_cambiado = Signal()
    resultados_cambiados = Signal()
    seleccion_cambiada = Signal()
    archivo_cambiado = Signal()

    def __init__(self, doc: formato.Documento | None = None) -> None:
        super().__init__()
        self.doc = doc or formato.Documento.nuevo()
        self.ruta: Path | None = None
        self.modificado = False
        self.resultados: Resultados | None = None
        self.indices: formato.modelo.Indices | None = None
        self.al_dia = False
        self.combinacion = ""
        self.seleccion: Seleccion | None = None
        self.avisos: list[Aviso] = []
        self.revisar()

    # --- Archivo ---------------------------------------------------------------
    @property
    def titulo(self) -> str:
        return self.ruta.name if self.ruta else "Sin título.nrv"

    def nuevo(self, doc: formato.Documento | None = None) -> None:
        self.doc = doc or formato.Documento.nuevo()
        self.ruta = None
        self._reiniciar()

    def abrir(self, ruta: str | Path) -> None:
        """Abre un ``.nrv``. Lanza ``formato.FormatoError`` si no es válido."""
        doc = formato.abrir(ruta)
        self.doc = doc
        self.ruta = Path(ruta)
        self._reiniciar()

    def guardar(self, ruta: str | Path | None = None) -> None:
        ruta = Path(ruta) if ruta else self.ruta
        if ruta is None:
            raise ValueError("falta la ruta del archivo")
        if ruta.suffix.lower() != ".nrv":
            ruta = ruta.with_suffix(".nrv")
        formato.guardar(self.doc, ruta, copia_bak=self.doc.migrado_desde is not None)
        self.doc.migrado_desde = None
        self.ruta = ruta
        self.modificado = False
        self.archivo_cambiado.emit()

    def _reiniciar(self) -> None:
        self.modificado = False
        self.resultados = None
        self.indices = None
        self.al_dia = False
        self.combinacion = ""
        self.seleccion = None
        self.revisar()
        self.archivo_cambiado.emit()
        self.modelo_cambiado.emit()
        self.resultados_cambiados.emit()
        self.seleccion_cambiada.emit()

    # --- Edición -----------------------------------------------------------------
    @property
    def modelo(self) -> dict:
        return self.doc.modelo

    def editar(self, nuevo_modelo: dict) -> None:
        """Reemplaza ``modelo.json`` por una versión editada. Los resultados quedan
        desactualizados hasta volver a calcular."""
        self.doc.modelo = nuevo_modelo
        self.modificado = True
        self.al_dia = False
        self.revisar()
        self.archivo_cambiado.emit()
        self.modelo_cambiado.emit()
        self.resultados_cambiados.emit()

    def copia_modelo(self) -> dict:
        return copy.deepcopy(self.doc.modelo)

    def seleccionar(self, sel: Seleccion | None) -> None:
        if sel != self.seleccion:
            self.seleccion = sel
            self.seleccion_cambiada.emit()

    # --- Revisión y cálculo ------------------------------------------------------
    def revisar(self) -> list[Aviso]:
        """Revisión del modelo (lo que muestra el panel "Revisión del modelo")."""
        avisos: list[Aviso] = []
        m = self.modelo
        try:
            formato.validar(m)
        except formato.FormatoError as e:
            avisos.append(Aviso("error", f"{e.ruta or e.miembro}: {e.motivo}"))
            self.avisos = avisos
            return avisos
        if not m["nudos"] or not m["barras"]:
            avisos.append(Aviso("info", "El modelo todavía no tiene nudos y barras."))
        if not m.get("apoyos"):
            avisos.append(Aviso("error", "No hay apoyos: la estructura es un mecanismo."))
        if not m["casos"]:
            avisos.append(Aviso("info", "No hay casos de carga."))
        usados = {n for b in m["barras"] for n in (b["i"], b["j"])}
        sueltos = [n["id"] for n in m["nudos"] if n["id"] not in usados]
        if sueltos:
            lista = ", ".join(f"N{i}" for i in sueltos)
            avisos.append(Aviso("error", f"Nudos sin barras: {lista}."))
        pares = {}
        for b in m["barras"]:
            par = frozenset((b["i"], b["j"]))
            if par in pares:
                avisos.append(Aviso("error", f"B{b['id']} se superpone con B{pares[par]}."))
            pares[par] = b["id"]
        en_comb = {n for c in m.get("combinaciones", []) for n in c["factores"]}
        for c in m["casos"]:
            if m.get("combinaciones") and c["nombre"] not in en_comb:
                avisos.append(
                    Aviso("info", f"El caso {c['nombre']} no entra en ninguna combinación.")
                )
        if not any(a.nivel == "error" for a in avisos):
            avisos.insert(0, Aviso("ok", "Datos completos y referencias válidas."))
        self.avisos = avisos
        return avisos

    def nombres_resultado(self) -> list[str]:
        """Casos y combinaciones disponibles para mostrar."""
        m = self.modelo
        return [c["nombre"] for c in m.get("combinaciones", [])] + [c["nombre"] for c in m["casos"]]

    def calcular(self) -> None:
        """Resuelve el modelo. Lanza ``FormatoError``, ``ValueError`` o ``MecanismoError``."""
        try:
            modelo, indices = formato.construir_modelo(self.modelo)
            resultados = modelo.resolver()
        except MecanismoError as e:
            self.avisos = [Aviso("error", f"Estructura inestable: {e}")]
            self.resultados_cambiados.emit()
            raise
        self.resultados = resultados
        self.indices = indices
        self.al_dia = True
        nombres = self.nombres_resultado()
        if self.combinacion not in nombres:
            self.combinacion = nombres[0] if nombres else ""
        self.revisar()
        self.avisos.insert(
            1 if self.avisos and self.avisos[0].nivel == "ok" else 0,
            Aviso("ok", "Estructura estable: el sistema de ecuaciones se resolvió."),
        )
        self.resultados_cambiados.emit()

    def resultado(self) -> ResultadoCaso | None:
        """Resultado del caso o la combinación activa, si está al día."""
        if not self.al_dia or self.resultados is None or not self.combinacion:
            return None
        for c in self.modelo.get("combinaciones", []):
            if c["nombre"] == self.combinacion:
                return self.resultados.combinar(c["nombre"], c["factores"])
        if self.combinacion in self.resultados.casos:
            return self.resultados[self.combinacion]
        return None

    def elegir_combinacion(self, nombre: str) -> None:
        if nombre != self.combinacion:
            self.combinacion = nombre
            self.resultados_cambiados.emit()
