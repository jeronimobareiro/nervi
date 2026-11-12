# SPDX-License-Identifier: GPL-3.0-or-later
"""Tablas editables de ``modelo.json`` y tablas de resultados.

Las tablas usan el modelo/vista de Qt: solo se dibujan las filas visibles, así
que escalan a modelos grandes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from . import estilo
from .sesion import Seleccion, Sesion


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    tipo: str = "num"  # num, id, bool, texto, opcion, lib
    opciones: tuple[str, ...] = ()
    defecto: object = 0.0


#: lista de modelo.json -> (título de la pestaña, columnas, fila nueva)
LISTAS: dict[str, tuple[str, tuple[Columna, ...]]] = {
    "nudos": ("Nudos", (Columna("id", "Id", "id"), Columna("x", "x"), Columna("y", "y"))),
    "barras": (
        "Barras",
        (
            Columna("id", "Id", "id"),
            Columna("i", "Nudo i", "id"),
            Columna("j", "Nudo j", "id"),
            Columna("E", "E", defecto=2.5e7),
            Columna("A", "A", defecto=0.09),
            Columna("I", "I", defecto=6.75e-4),
            Columna("liberaciones", "Articulada en", "lib"),
        ),
    ),
    "apoyos": (
        "Apoyos",
        (
            Columna("nudo", "Nudo", "id"),
            Columna("ux", "ux", "bool", defecto=True),
            Columna("uy", "uy", "bool", defecto=True),
            Columna("rz", "rz", "bool", defecto=True),
        ),
    ),
    "casos": ("Casos", (Columna("id", "Id", "id"), Columna("nombre", "Nombre", "texto"))),
    "cargas_nodales": (
        "Cargas en nudos",
        (
            Columna("caso", "Caso", "id"),
            Columna("nudo", "Nudo", "id"),
            Columna("fx", "Fx"),
            Columna("fy", "Fy"),
            Columna("mz", "Mz"),
        ),
    ),
    "cargas_barra": (
        "Cargas en barras",
        (
            Columna("caso", "Caso", "id"),
            Columna("barra", "Barra", "id"),
            Columna(
                "tipo",
                "Tipo",
                "opcion",
                ("uniforme", "puntual", "trapezoidal", "termica", "momento"),
                "uniforme",
            ),
            Columna("ejes", "Ejes", "opcion", ("local", "global"), "local"),
            Columna("a", "a / α"),
            Columna("b", "b (vacío = L) / h"),
            Columna("qx", "qx / px / qx1 / ΔT / Mz"),
            Columna("qy", "qy / py / qy1 / ΔTg"),
            Columna("qx2", "qx2"),
            Columna("qy2", "qy2"),
        ),
    ),
    "combinaciones": (
        "Combinaciones",
        (
            Columna("nombre", "Nombre", "texto"),
            Columna("factores", "Factores (caso=factor, …)", "factores"),
        ),
    ),
}

_LIB = {
    "": [False] * 6,
    "i": [False, False, True, False, False, False],
    "j": [False, False, False, False, False, True],
    "i y j": [False, False, True, False, False, True],
}


#: tipo de carga en barra -> columna de la tabla -> clave en modelo.json
_CLAVES_CARGA: dict[str, dict[str, str]] = {
    "uniforme": {"qx": "qx", "qy": "qy"},
    "puntual": {"a": "a", "qx": "px", "qy": "py"},
    "trapezoidal": {"a": "a", "b": "b", "qx": "qx1", "qy": "qy1", "qx2": "qx2", "qy2": "qy2"},
    # dt uniforme y gradiente = T(cara -y) - T(cara +y); alfa: coef. de dilatación; h: canto.
    "termica": {"a": "alfa", "b": "h", "qx": "dt", "qy": "gradiente"},
    # Momento concentrado antihorario Mz a la distancia a del nudo i.
    "momento": {"a": "a", "qx": "mz"},
}
_COLUMNAS_CARGA = ("a", "b", "qx", "qy", "qx2", "qy2")


def _clave_carga(fila: dict, columna: str) -> str | None:
    """Clave de ``modelo.json`` que muestra la columna, o ``None`` si el tipo no la usa."""
    return _CLAVES_CARGA.get(fila.get("tipo", ""), {}).get(columna)


def _texto_lib(lib: list[bool] | None) -> str:
    lib = lib or [False] * 6
    for texto, valor in _LIB.items():
        if lib == valor:
            return texto or "—"
    return "otra"


class TablaModelo(QAbstractTableModel):
    """Una lista de ``modelo.json`` (nudos, barras, …) como tabla editable."""

    def __init__(self, sesion: Sesion, lista: str) -> None:
        super().__init__()
        self.sesion = sesion
        self.lista = lista
        self.columnas = LISTAS[lista][1]
        sesion.modelo_cambiado.connect(self._recargar)

    def _recargar(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def _filas(self) -> list[dict]:
        return self.sesion.modelo.get(self.lista, [])

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._filas())

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.columnas)

    def headerData(self, seccion, orientacion, rol=Qt.DisplayRole):
        if rol == Qt.DisplayRole and orientacion == Qt.Horizontal:
            return self.columnas[seccion].titulo
        return None

    def _valor(self, fila: dict, col: Columna):
        if self.lista == "cargas_barra" and col.clave in _COLUMNAS_CARGA:
            clave = _clave_carga(fila, col.clave)
            if clave is None or (clave == "b" and "b" not in fila):
                return None
            return fila.get(clave, 0.0)
        if col.tipo == "bool":
            return fila.get(col.clave, False)
        if col.tipo == "lib":
            return _texto_lib(fila.get("liberaciones"))
        if col.tipo == "factores":
            return ", ".join(f"{k}={v:g}" for k, v in fila.get("factores", {}).items())
        return fila.get(col.clave, 0.0 if col.tipo == "num" else "")

    def data(self, indice: QModelIndex, rol=Qt.DisplayRole):
        if not indice.isValid():
            return None
        fila, col = self._filas()[indice.row()], self.columnas[indice.column()]
        valor = self._valor(fila, col)
        if col.tipo == "bool":
            if rol == Qt.CheckStateRole:
                return Qt.Checked if valor else Qt.Unchecked
            return None
        if rol in (Qt.DisplayRole, Qt.EditRole):
            if valor is None:
                return "" if rol == Qt.DisplayRole else None
            if col.tipo == "num" and rol == Qt.DisplayRole:
                return f"{valor:.6g}"
            return valor
        if rol == Qt.TextAlignmentRole and col.tipo in ("num", "id"):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if rol == Qt.ForegroundRole and valor is None:
            return QColor(estilo.TEXTO_3)
        return None

    def flags(self, indice: QModelIndex):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        col = self.columnas[indice.column()]
        fila = self._filas()[indice.row()]
        if col.tipo == "bool":
            return base | Qt.ItemIsUserCheckable
        if (
            self.lista == "cargas_barra"
            and col.clave in _COLUMNAS_CARGA
            and _clave_carga(fila, col.clave) is None
        ):
            return base
        return base | Qt.ItemIsEditable

    def setData(self, indice: QModelIndex, valor, rol=Qt.EditRole) -> bool:
        if not indice.isValid():
            return False
        col = self.columnas[indice.column()]
        modelo = self.sesion.copia_modelo()
        fila = modelo[self.lista][indice.row()]
        clave_carga = (
            _clave_carga(fila, col.clave)
            if self.lista == "cargas_barra" and col.clave in _COLUMNAS_CARGA
            else None
        )
        if clave_carga == "b" and not str(valor if valor is not None else "").strip():
            fila.pop("b", None)  # vacío: hasta el nudo j
            self.sesion.editar(modelo)
            return True
        try:
            convertido = self._convertir(col, valor, rol)
        except ValueError:
            return False
        if clave_carga is not None:
            fila[clave_carga] = convertido
        elif self.lista == "cargas_barra" and col.clave == "tipo":
            _cambiar_tipo_carga(fila, convertido)
        elif col.tipo == "lib":
            if convertido == _LIB[""]:
                fila.pop("liberaciones", None)
            else:
                fila["liberaciones"] = convertido
        else:
            fila[col.clave] = convertido
        self.sesion.editar(modelo)
        return True

    @staticmethod
    def _convertir(col: Columna, valor, rol):
        if col.tipo == "bool":
            return (valor == Qt.Checked.value) or (valor == Qt.Checked) or valor is True
        if col.tipo == "id":
            v = int(str(valor).strip())
            if v < 1:
                raise ValueError
            return v
        if col.tipo == "num":
            return float(str(valor).replace(",", ".").replace("−", "-"))
        if col.tipo == "opcion":
            if valor not in col.opciones:
                raise ValueError
            return valor
        if col.tipo == "factores":
            factores = {}
            for parte in str(valor).split(","):
                nombre, _, factor = parte.partition("=")
                if not nombre.strip() or not factor.strip():
                    raise ValueError
                factores[nombre.strip()] = float(factor.replace("−", "-"))
            if not factores:
                raise ValueError
            return factores
        if col.tipo == "lib":
            texto = str(valor).strip().lower().replace("—", "")
            if texto not in _LIB:
                raise ValueError
            return list(_LIB[texto])
        texto = str(valor).strip()
        if not texto:
            raise ValueError
        return texto

    def fila_nueva(self) -> dict:
        filas = self._filas()
        nueva = {}
        for col in self.columnas:
            if col.tipo == "lib" or (
                self.lista == "cargas_barra" and col.clave in ("a", "b", "qx2", "qy2")
            ):
                continue
            if col.clave == "id":
                nueva["id"] = max((f["id"] for f in filas), default=0) + 1
            elif col.tipo == "id":
                origen = {
                    "i": "nudos",
                    "j": "nudos",
                    "nudo": "nudos",
                    "barra": "barras",
                    "caso": "casos",
                }
                ids = [f["id"] for f in self.sesion.modelo.get(origen[col.clave], [])]
                nueva[col.clave] = (
                    ids[min(len(ids) - 1, 1 if col.clave == "j" else 0)] if ids else 1
                )
            elif col.tipo == "texto":
                nueva[col.clave] = f"C{nueva.get('id', len(filas) + 1)}"
            elif col.tipo == "factores":
                casos = self.sesion.modelo.get("casos", [])
                nueva["factores"] = {casos[0]["nombre"]: 1.0} if casos else {}
            else:
                nueva[col.clave] = col.defecto
        return nueva


def _cambiar_tipo_carga(fila: dict, tipo: str) -> None:
    if fila["tipo"] == tipo:
        return
    # Se conservan los valores que se ven en las columnas qx/qy y a.
    valores = {col: fila.pop(clave, 0.0) for col, clave in _CLAVES_CARGA[fila["tipo"]].items()}
    fila["tipo"] = tipo
    for col, clave in _CLAVES_CARGA[tipo].items():
        if col == "b":
            continue  # sin b: hasta el nudo j
        if col in ("qx2", "qy2"):
            fila[clave] = valores.get(col, valores.get(col[:2], 0.0))
        else:
            fila[clave] = valores.get(col, 0.0)


class EditorLista(QWidget):
    """Tabla editable con botones para agregar y eliminar filas."""

    def __init__(self, sesion: Sesion, lista: str) -> None:
        super().__init__()
        self.sesion = sesion
        self.lista = lista
        self.modelo = TablaModelo(sesion, lista)
        self.tabla = QTableView()
        self.tabla.setModel(self.modelo)
        self.tabla.verticalHeader().hide()
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setSelectionBehavior(QTableView.SelectRows)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.clicked.connect(self._fila_elegida)
        agregar, eliminar = QPushButton("Agregar"), QPushButton("Eliminar")
        agregar.clicked.connect(self.agregar)
        eliminar.clicked.connect(self.eliminar)
        botones = QHBoxLayout()
        botones.setContentsMargins(0, 0, 0, 0)
        botones.addWidget(agregar)
        botones.addWidget(eliminar)
        botones.addStretch()
        capa = QVBoxLayout(self)
        capa.setContentsMargins(10, 6, 10, 6)
        capa.setSpacing(6)
        capa.addLayout(botones)
        capa.addWidget(self.tabla)

    def agregar(self) -> None:
        modelo = self.sesion.copia_modelo()
        modelo.setdefault(self.lista, []).append(self.modelo.fila_nueva())
        self.sesion.editar(modelo)
        self.tabla.scrollToBottom()

    def eliminar(self) -> None:
        filas = sorted({i.row() for i in self.tabla.selectionModel().selectedRows()}, reverse=True)
        if not filas:
            return
        modelo = self.sesion.copia_modelo()
        for f in filas:
            del modelo[self.lista][f]
        self.sesion.editar(modelo)

    def _fila_elegida(self, indice: QModelIndex) -> None:
        fila = self.sesion.modelo[self.lista][indice.row()]
        if self.lista == "barras":
            self.sesion.seleccionar(Seleccion("barra", fila["id"]))
        elif self.lista == "nudos":
            self.sesion.seleccionar(Seleccion("nudo", fila["id"]))


class TablaResultados(QAbstractTableModel):
    """Reacciones, fuerzas de extremo o desplazamientos del resultado activo."""

    TIPOS: ClassVar[dict[str, tuple[str, tuple[str, ...]]]] = {
        "reacciones": ("Nudo", ("Rx [{f}]", "Ry [{f}]", "Mz [{f}·{l}]")),
        "fuerzas_extremo": (
            "Barra",
            ("Ni [{f}]", "Vi [{f}]", "Mi [{f}·{l}]", "Nj [{f}]", "Vj [{f}]", "Mj [{f}·{l}]"),
        ),
        "desplazamientos": ("Nudo", ("ux [{l}]", "uy [{l}]", "rz [rad]")),
    }

    def __init__(self, sesion: Sesion, tipo: str) -> None:
        super().__init__()
        self.sesion = sesion
        self.tipo = tipo
        self._filas: list[tuple[str, np.ndarray]] = []
        sesion.resultados_cambiados.connect(self.recargar)
        sesion.modelo_cambiado.connect(self.recargar)
        self.recargar()

    def recargar(self) -> None:
        self.beginResetModel()
        self._filas = []
        res = self.sesion.resultado()
        if res is not None:
            datos = getattr(res, self.tipo)
            m = self.sesion.modelo
            if self.tipo == "fuerzas_extremo":
                ids = [f"B{b['id']}" for b in m["barras"]]
                self._filas = list(zip(ids, datos, strict=True))
            else:
                apoyados = {a["nudo"] for a in m.get("apoyos", [])} | {
                    r["nudo"] for r in m.get("resortes", [])
                }
                for k, n in enumerate(m["nudos"]):
                    if self.tipo == "desplazamientos" or n["id"] in apoyados:
                        self._filas.append((f"N{n['id']}", datos[k]))
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._filas)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else 1 + len(self.TIPOS[self.tipo][1])

    def headerData(self, seccion, orientacion, rol=Qt.DisplayRole):
        if rol != Qt.DisplayRole or orientacion != Qt.Horizontal:
            return None
        cab, cols = self.TIPOS[self.tipo]
        if seccion == 0:
            return cab
        u = self.sesion.modelo["unidades"]
        return cols[seccion - 1].format(f=u["fuerza"], l=u["longitud"])

    def data(self, indice: QModelIndex, rol=Qt.DisplayRole):
        if not indice.isValid():
            return None
        nombre, valores = self._filas[indice.row()]
        c = indice.column()
        if rol == Qt.DisplayRole:
            if c == 0:
                return nombre
            v = float(valores[c - 1])
            texto = f"{v:.6g}" if self.tipo == "desplazamientos" else f"{v:.2f}"
            return texto.replace("-", "−")
        if rol == Qt.TextAlignmentRole and c > 0:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if rol == Qt.ForegroundRole and c > 0:
            v = float(valores[c - 1])
            if abs(v) < 1e-12:
                return QColor("#9CA3AF")
            return QColor("#1E40AF" if v > 0 else "#9A3412")
        return None


def vista_tabla(modelo: QAbstractTableModel) -> QTableView:
    t = QTableView()
    t.setModel(modelo)
    t.verticalHeader().hide()
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.setSelectionBehavior(QTableView.SelectRows)
    return t
