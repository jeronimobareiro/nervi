# SPDX-License-Identifier: GPL-3.0-or-later
"""Tablas del edificio en las etapas Análisis y Resultados (issue #74).

- :class:`PanelModeloCalculo`: las barras del modelo de cálculo generado desde el
  edificio, de qué elemento sale cada una y sus brazos rígidos. Es de solo lectura:
  se cambia el edificio y el modelo se vuelve a generar.
- :class:`PanelResultadosEdificio`: *Por elemento* (los esfuerzos devueltos a cada
  viga, columna y muro del edificio, aunque el cálculo los haya partido en barras),
  *Reacciones*, *Desplazamientos* y *Derivas* de piso.

Todo sale de :meth:`nervi.proyecto.Proyecto.modelo_calculo` y
:meth:`~nervi.proyecto.Proyecto.resultado_edificio`; los números se arman en
bloque con ``numpy`` (:meth:`nervi.idealizacion.ModeloCalculo.resumen`).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import estilo
from .sesion import Sesion
from .tablas import vista_tabla

#: Tipo de barra del modelo de cálculo según la lista de la que sale.
TIPO_BARRA = {"columnas": "Columna", "vigas": "Viga", "muros": "Muro"}
#: Listas de *Por elemento*, con el nombre del botón.
LISTAS_RESULTADO = {"vigas": "Vigas", "columnas": "Columnas", "muros": "Muros"}


def _nombre(mf, lista: str, id: int) -> str:
    return mf.elemento(lista, id).get("nombre") or f"{lista[0].upper()}{id}"


class TablaNumeros(QAbstractTableModel):
    """Tabla de solo lectura: unas columnas de texto y después números.

    ``formatos`` da el formato de cada columna numérica (``".2f"``, ``".6g"``…). Los
    números negativos llevan el signo menos tipográfico y el color de su signo, como
    las demás tablas de resultados."""

    def __init__(self) -> None:
        super().__init__()
        self.titulos: list[str] = []
        self.textos: list[list[str]] = []
        self.valores = np.zeros((0, 0))
        self.formatos: list[str] = []
        self.colores = True
        self._n_texto = 0

    def poner(
        self,
        titulos: list[str],
        textos: list[list[str]],
        valores: np.ndarray | None = None,
        formatos: list[str] | None = None,
        colores: bool = True,
    ) -> None:
        self.beginResetModel()
        self.titulos = titulos
        self.textos = textos
        n_texto = len(titulos) - (0 if valores is None else valores.shape[1])
        self.valores = (
            np.zeros((len(textos), 0)) if valores is None else np.asarray(valores, dtype=float)
        )
        self._n_texto = n_texto
        self.formatos = formatos or [".2f"] * self.valores.shape[1]
        self.colores = colores
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.textos)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.titulos)

    def headerData(self, seccion, orientacion, rol=Qt.DisplayRole):
        if rol == Qt.DisplayRole and orientacion == Qt.Horizontal:
            return self.titulos[seccion]
        return None

    def data(self, indice: QModelIndex, rol=Qt.DisplayRole):
        if not indice.isValid():
            return None
        f, c = indice.row(), indice.column()
        if c < self._n_texto:
            return self.textos[f][c] if rol == Qt.DisplayRole else None
        v = float(self.valores[f, c - self._n_texto])
        if rol == Qt.DisplayRole:
            if np.isnan(v):
                return "—"
            return format(v, self.formatos[c - self._n_texto]).replace("-", "−")
        if rol == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if rol == Qt.ForegroundRole and self.colores:
            if np.isnan(v) or abs(v) < 1e-12:
                return QColor(estilo.TEXTO_3)
            return QColor(estilo.POSITIVO if v > 0 else estilo.NEGATIVO)
        return None


def _con_nota(tabla_widget: QWidget) -> tuple[QWidget, QLabel]:
    """Una tabla con una nota tenue arriba a la derecha."""
    w = QWidget()
    capa = QVBoxLayout(w)
    capa.setContentsMargins(0, 4, 0, 0)
    capa.setSpacing(4)
    nota = QLabel(objectName="tenue")
    nota.setAlignment(Qt.AlignRight)
    capa.addWidget(nota)
    capa.addWidget(tabla_widget)
    return w, nota


class PanelModeloCalculo(QWidget):
    """Las barras del modelo de cálculo generado (Análisis › Modelo de cálculo)."""

    def __init__(self, sesion: Sesion) -> None:
        super().__init__()
        self.sesion = sesion
        self.modelo = TablaNumeros()
        self.tabla = vista_tabla(self.modelo)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        w, self.nota = _con_nota(self.tabla)
        capa.addWidget(w)
        sesion.fisico_cambiado.connect(self.recargar)
        sesion.archivo_cambiado.connect(self.recargar)
        self.recargar()

    def recargar(self) -> None:
        s = self.sesion
        titulos = ["Barra", "Nudos", "Tipo", "Sale de", "Tramo", "Brazos rígidos"]
        if not s.es_edificio:
            self.modelo.poner(titulos, [])
            self.nota.setText("El proyecto no tiene edificio")
            return
        try:
            mc = s.modelo_calculo()
        except (ValueError, KeyError) as e:
            self.modelo.poner(titulos, [])
            self.nota.setText(f"No se pudo generar el modelo de cálculo: {e}")
            return
        from ..fisico import ModeloFisico

        mf = ModeloFisico.desde_json(s.fisico)
        conect = [b["nudos"] for b in mc.modelo._barras]
        u = mc.longitud
        filas = []
        for k, (o, (i, j)) in enumerate(zip(mc.origenes, conect, strict=True)):
            brazos = (
                "—" if not (o.brazo_i or o.brazo_j) else f"{o.brazo_i:.2f} · {o.brazo_j:.2f} {u}"
            )
            filas.append(
                [
                    f"B{k + 1}",
                    f"N{i + 1} → N{j + 1}",
                    TIPO_BARRA[o.lista],
                    _nombre(mf, o.lista, o.id),
                    f"{o.s0:.2f} – {o.s1:.2f} {u}",
                    brazos,
                ]
            )
        self.modelo.poner(titulos, filas)
        self.nota.setText(
            f"Generado del edificio · {len(mc.nudos)} nudos · {mc.n_barras} barras · "
            f"{len(mc.maestros)} diafragmas · solo lectura"
        )


class PanelResultadosEdificio(QTabWidget):
    """Resultados del edificio: Por elemento, Reacciones, Desplazamientos y Derivas."""

    #: Clic en una fila de *Por elemento*: ``(lista, id)`` del elemento.
    elemento_elegido = Signal(str, int)

    def __init__(self, sesion: Sesion) -> None:
        super().__init__()
        self.sesion = sesion
        self.setDocumentMode(True)
        self.lista = "vigas"

        # Por elemento: Vigas · Columnas · Muros y su tabla.
        por_elemento = QWidget()
        capa = QVBoxLayout(por_elemento)
        capa.setContentsMargins(0, 6, 0, 0)
        capa.setSpacing(4)
        fila = QHBoxLayout()
        fila.setContentsMargins(6, 0, 6, 0)
        grupo = QWidget(objectName="grupo")
        g = QHBoxLayout(grupo)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        botones = QButtonGroup(self)
        self.botones_lista: dict[str, QPushButton] = {}
        for clave, texto in LISTAS_RESULTADO.items():
            b = QPushButton(texto, objectName="segmento", checkable=True)
            b.clicked.connect(lambda _=False, c=clave: self.elegir_lista(c))
            botones.addButton(b)
            self.botones_lista[clave] = b
            g.addWidget(b)
        self.botones_lista[self.lista].setChecked(True)
        fila.addWidget(grupo)
        fila.addStretch()
        self.nota = QLabel(objectName="tenue")
        fila.addWidget(self.nota)
        capa.addLayout(fila)
        self.por_elemento = TablaNumeros()
        self.tabla_elementos = vista_tabla(self.por_elemento)
        self.tabla_elementos.clicked.connect(self._fila_elegida)
        capa.addWidget(self.tabla_elementos)
        self.addTab(por_elemento, "Por elemento")
        self._ids: list[int] = []

        self.reacciones = TablaNumeros()
        self.desplazamientos = TablaNumeros()
        self.derivas = TablaNumeros()
        for modelo, titulo in (
            (self.reacciones, "Reacciones"),
            (self.desplazamientos, "Desplazamientos"),
            (self.derivas, "Derivas"),
        ):
            self.addTab(vista_tabla(modelo), titulo)

        sesion.resultados_cambiados.connect(self.recargar)
        sesion.fisico_cambiado.connect(self.recargar)
        self.recargar()

    def elegir_lista(self, lista: str) -> None:
        self.lista = lista
        self.botones_lista[lista].setChecked(True)
        self._recargar_elementos()

    def _fila_elegida(self, indice: QModelIndex) -> None:
        if indice.isValid() and indice.row() < len(self._ids):
            self.elemento_elegido.emit(self.lista, self._ids[indice.row()])

    def recargar(self) -> None:
        self._recargar_elementos()
        self._recargar_nudos()

    def _datos(self):
        """(modelo de cálculo, modelo físico, resultado) o ``None`` sin resultados."""
        s = self.sesion
        if not s.es_edificio:
            return None
        res = s.resultado_edificio()
        if res is None:
            return None
        from ..fisico import ModeloFisico

        return s.modelo_calculo(), ModeloFisico.desde_json(s.fisico), res

    def _recargar_elementos(self) -> None:
        datos = self._datos()
        viga = self.lista == "vigas"
        nombre = {"vigas": "Viga", "columnas": "Columna", "muros": "Muro"}[self.lista]
        if viga:
            titulos = [nombre, "Barras", "M izq [kN·m]", "M+ máx [kN·m]", "M− máx [kN·m]"]
            titulos += ["M der [kN·m]", "|V| máx [kN]"]
        else:
            titulos = [nombre, "Barras", "N base [kN]", "N mín [kN]", "|Mz| máx [kN·m]"]
            titulos += ["|My| máx [kN·m]", "|V| máx [kN]", "T máx [kN·m]"]
        self._ids = []
        if datos is None:
            self.por_elemento.poner(titulos, [])
            self.nota.setText("Sin resultados: calculá con F5")
            return
        mc, mf, res = datos
        r = mc.resumen(res, self.lista)
        en_r = {int(i): k for k, i in enumerate(r["id"])}
        filas, valores = [], []
        n = len(titulos) - 2
        for el in mf.lista(self.lista):
            k = en_r.get(el["id"])
            barras = mc.barras_de(self.lista, el["id"])
            texto_barras = " + ".join(f"B{b + 1}" for b in barras) if barras else "sobre muro"
            self._ids.append(el["id"])
            filas.append([_nombre(mf, self.lista, el["id"]), texto_barras])
            if k is None:
                valores.append([np.nan] * n)
            elif viga:
                valores.append(
                    [
                        r["Mz_i"][k],
                        max(r["Mz_max"][k], 0.0),
                        min(r["Mz_min"][k], 0.0),
                        r["Mz_j"][k],
                        r["V_max"][k],
                    ]
                )
            else:
                valores.append(
                    [
                        r["N_i"][k],
                        r["N_min"][k],
                        max(abs(r["Mz_max"][k]), abs(r["Mz_min"][k])),
                        max(abs(r["My_max"][k]), abs(r["My_min"][k])),
                        r["V_max"][k],
                        max(abs(r["T_max"][k]), abs(r["T_min"][k])),
                    ]
                )
        self.por_elemento.poner(titulos, filas, np.array(valores, dtype=float).reshape(-1, n))
        self.nota.setText(
            f"{res.nombre} · esfuerzos de las barras devueltos a cada {nombre.lower()} del edificio"
        )

    def _recargar_nudos(self) -> None:
        datos = self._datos()
        cab_r = ["Nudo", "x", "y", "z", "Rx [kN]", "Ry [kN]", "Rz [kN]"]
        cab_r += ["Mx [kN·m]", "My [kN·m]", "Mz [kN·m]"]
        cab_d = ["Nudo", "x", "y", "z", "ux", "uy", "uz", "rx [rad]", "ry [rad]", "rz [rad]"]
        cab_p = ["Piso", "Nivel", "Altura", "ux", "uy", "Deriva x", "Deriva y"]
        if datos is None:
            for modelo, cab in (
                (self.reacciones, cab_r),
                (self.desplazamientos, cab_d),
                (self.derivas, cab_p),
            ):
                modelo.poner(cab, [])
            return
        mc, mf, res = datos
        u = mc.longitud
        cab_d[4:7] = [f"ux [{u}]", f"uy [{u}]", f"uz [{u}]"]
        cab_p[1:5] = [f"Nivel [{u}]", f"Altura [{u}]", f"ux [{u}]", f"uy [{u}]"]
        apoyos = np.array(mc.apoyos, dtype=np.int64)
        nudos = mc.nudos
        self.reacciones.poner(
            cab_r,
            [[f"N{n + 1}"] for n in apoyos],
            np.hstack([nudos[apoyos], res.reacciones[apoyos]]),
            [".3f"] * 3 + [".2f"] * 6,
        )
        n = len(nudos)
        self.desplazamientos.poner(
            cab_d,
            [[f"N{k + 1}"] for k in range(n)],
            np.hstack([nudos, res.desplazamientos[:n]]),
            [".3f"] * 3 + [".4g"] * 6,
        )
        pisos = {nudo: piso for piso, nudo in mc.maestros.items()}
        try:
            dv = self.sesion.resultados_edificio.derivas(res)
        except ValueError:
            self.derivas.poner(cab_p, [])
            return
        nombres = [
            [mf.elemento("pisos", pisos[int(m)])["nombre"] if int(m) in pisos else f"N{m + 1}"]
            for m in dv["maestro"]
        ]
        self.derivas.poner(
            cab_p,
            nombres,
            np.column_stack([dv["z"], dv["h"], dv["ux"], dv["uy"], dv["deriva_x"], dv["deriva_y"]]),
            [".3f", ".3f", ".4g", ".4g", ".3g", ".3g"],
            colores=False,
        )
