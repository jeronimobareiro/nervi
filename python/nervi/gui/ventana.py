# SPDX-License-Identifier: GPL-3.0-or-later
"""Ventana principal: todo el trabajo en una sola ventana.

Arriba, el flujo de trabajo (Geometría › Cargas › Análisis › Resultados) y la
barra contextual; a la izquierda, el explorador del proyecto; al centro, la
vista del pórtico; a la derecha, las propiedades de la selección; abajo, tablas,
revisión del modelo y consola.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import MecanismoError, formato
from . import estilo
from .consola import Consola
from .paleta import Entrada, Paleta
from .sesion import Seleccion, Sesion, documento_ejemplo
from .tablas import LISTAS, EditorLista, TablaResultados, vista_tabla
from .vista2d import DIAGRAMAS, Vista2D

RECURSOS = Path(__file__).resolve().parent / "recursos"
ETAPAS = ("Geometría", "Cargas", "Análisis", "Resultados", "Diseño", "Memoria")
AVISO_PRELIMINAR = "Versión preliminar · no apta para proyecto"


def icono() -> QIcon:
    return QIcon(str(RECURSOS / "nervi.svg"))


class Ventana(QMainWindow):
    def __init__(self, sesion: Sesion | None = None) -> None:
        super().__init__()
        self.sesion = sesion or Sesion()
        self.setWindowIcon(icono())
        self.resize(1440, 900)
        self.setStyleSheet(estilo.QSS)
        self._acciones()

        raiz = QWidget(objectName="raiz")
        capa = QVBoxLayout(raiz)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(self._barra_superior())
        capa.addWidget(self._barra_contextual())

        self.vista = Vista2D(self.sesion)
        self.panel_inferior = self._panel_inferior()
        centro = QSplitter(Qt.Vertical)
        centro.addWidget(self.vista)
        centro.addWidget(self.panel_inferior)
        centro.setStretchFactor(0, 3)
        centro.setStretchFactor(1, 1)
        centro.setSizes([560, 250])

        horizontal = QSplitter(Qt.Horizontal)
        horizontal.addWidget(self._explorador())
        horizontal.addWidget(centro)
        horizontal.addWidget(self._propiedades())
        horizontal.setStretchFactor(1, 1)
        horizontal.setSizes([240, 900, 290])
        capa.addWidget(horizontal, 1)
        self.setCentralWidget(raiz)
        self._barra_estado()

        s = self.sesion
        s.archivo_cambiado.connect(self._actualizar_titulo)
        s.modelo_cambiado.connect(self._actualizar_explorador)
        s.modelo_cambiado.connect(self._actualizar_etapas)
        s.resultados_cambiados.connect(self._actualizar_resultados)
        s.seleccion_cambiada.connect(self._actualizar_propiedades)
        self.vista.diagrama_cambiado.connect(self._marcar_diagrama)
        self._actualizar_todo()

    # --- Acciones y menú ------------------------------------------------------------
    def _accion(self, texto: str, funcion, atajo: str | QKeySequence | None = None) -> QAction:
        a = QAction(texto, self)
        if atajo:
            a.setShortcut(QKeySequence(atajo))
        a.triggered.connect(funcion)
        self.addAction(a)
        return a

    def _acciones(self) -> None:
        self.a_nuevo = self._accion("Nuevo proyecto", self.nuevo, QKeySequence.New)
        self.a_ejemplo = self._accion("Abrir ejemplo: pórtico simple", self.abrir_ejemplo)
        self.a_abrir = self._accion("Abrir…", self.abrir_dialogo, QKeySequence.Open)
        self.a_guardar = self._accion("Guardar", self.guardar, QKeySequence.Save)
        self.a_guardar_como = self._accion("Guardar como…", self.guardar_como, QKeySequence.SaveAs)
        self.a_calcular = self._accion("Calcular", self.calcular, "F5")
        self.a_buscar = self._accion("Buscar comando o elemento", self.abrir_paleta, "Ctrl+K")
        self.a_salir = self._accion("Salir", self.close, QKeySequence.Quit)
        self.a_diagramas = {}
        for clave, nombre in DIAGRAMAS.items():
            atajo = {"M": "M", "V": "V", "N": "N", "D": "D"}[clave]
            self.a_diagramas[clave] = self._accion(
                f"Mostrar {nombre.lower()}",
                lambda _=False, c=clave: self.vista.elegir_diagrama(c),
                atajo,
            )
            self.a_diagramas[clave].setShortcutContext(Qt.WidgetWithChildrenShortcut)

    def _barra_superior(self) -> QWidget:
        barra = QWidget(objectName="barra")
        capa = QHBoxLayout(barra)
        capa.setContentsMargins(8, 6, 10, 6)
        capa.setSpacing(10)
        menu = QMenu(self)
        for a in (
            self.a_nuevo,
            self.a_abrir,
            self.a_ejemplo,
            None,
            self.a_guardar,
            self.a_guardar_como,
            None,
            self.a_salir,
        ):
            menu.addSeparator() if a is None else menu.addAction(a)
        boton_menu = QToolButton()
        boton_menu.setIcon(icono())
        boton_menu.setIconSize(QSize(16, 22))
        boton_menu.setMenu(menu)
        boton_menu.setPopupMode(QToolButton.InstantPopup)
        boton_menu.setToolTip("Archivo")
        capa.addWidget(boton_menu)
        self.lbl_titulo = QLabel(objectName="titulo")
        self.lbl_guardado = QLabel(objectName="tenue")
        capa.addWidget(self.lbl_titulo)
        capa.addWidget(self.lbl_guardado)
        capa.addStretch()

        self.etapas = QButtonGroup(self)
        self.botones_etapa: list[QPushButton] = []
        for n, nombre in enumerate(ETAPAS):
            if n:
                sep = QLabel("›", objectName="tenue")
                capa.addWidget(sep)
            b = QPushButton(nombre, objectName="etapa", checkable=True)
            if nombre in ("Diseño", "Memoria"):
                b.setEnabled(False)
                b.setToolTip("Llega con la Fase 3 (diseño) y la Fase 4 (memoria de cálculo)")
            self.etapas.addButton(b, n)
            self.botones_etapa.append(b)
            capa.addWidget(b)
        self.etapas.idClicked.connect(self.ir_a_etapa)
        capa.addStretch()

        buscar = QPushButton("Buscar comando o elemento      Ctrl K", objectName="buscar")
        buscar.clicked.connect(self.abrir_paleta)
        calcular = QPushButton("Calcular   F5", objectName="primario")
        calcular.clicked.connect(self.calcular)
        capa.addWidget(buscar)
        capa.addWidget(calcular)
        return barra

    def _barra_contextual(self) -> QWidget:
        barra = QWidget(objectName="contexto")
        capa = QHBoxLayout(barra)
        capa.setContentsMargins(12, 5, 12, 5)
        capa.setSpacing(10)
        capa.addWidget(QLabel("Diagrama", objectName="tenue"))
        grupo = QWidget(objectName="grupo")
        g = QHBoxLayout(grupo)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        self.segmentos = QButtonGroup(self)
        self.botones_diagrama: dict[str, QPushButton] = {}
        for clave, nombre in DIAGRAMAS.items():
            b = QPushButton(nombre, objectName="segmento", checkable=True)
            b.setToolTip(f"Atajo: {clave}")
            b.clicked.connect(lambda _=False, c=clave: self.vista.elegir_diagrama(c))
            self.segmentos.addButton(b)
            self.botones_diagrama[clave] = b
            g.addWidget(b)
        capa.addWidget(grupo)
        capa.addSpacing(8)
        capa.addWidget(QLabel("Combinación", objectName="tenue"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(170)
        self.combo.currentTextChanged.connect(
            lambda t: self.sesion.elegir_combinacion(t) if t else None
        )
        capa.addWidget(self.combo)
        self.b_valores = QPushButton("Valores", checkable=True, checked=True)
        self.b_valores.toggled.connect(self._valores)
        capa.addWidget(self.b_valores)
        capa.addStretch()
        return barra

    def _explorador(self) -> QWidget:
        panel = QWidget(objectName="panel")
        capa = QVBoxLayout(panel)
        capa.setContentsMargins(6, 8, 6, 8)
        self.arbol = QTreeWidget()
        self.arbol.setHeaderHidden(True)
        self.arbol.setIndentation(14)
        self.arbol.itemClicked.connect(self._item_explorador)
        capa.addWidget(self.arbol)
        panel.setMinimumWidth(200)
        return panel

    def _propiedades(self) -> QWidget:
        panel = QWidget(objectName="panel")
        self.capa_prop = QVBoxLayout(panel)
        self.capa_prop.setContentsMargins(14, 12, 14, 12)
        self.capa_prop.setSpacing(8)
        self.lbl_tipo_sel = QLabel(objectName="seccion")
        self.lbl_sel = QLabel(objectName="titulo")
        self.lbl_sel.setStyleSheet("font-size: 12pt;")
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(6)
        self.lbl_res = QLabel("RESULTADOS", objectName="seccion")
        self.form_res = QFormLayout()
        self.form_res.setVerticalSpacing(6)
        for w in (self.lbl_tipo_sel, self.lbl_sel):
            self.capa_prop.addWidget(w)
        self.capa_prop.addLayout(self.form)
        self.capa_prop.addSpacing(6)
        self.capa_prop.addWidget(self.lbl_res)
        self.capa_prop.addLayout(self.form_res)
        self.capa_prop.addStretch()
        panel.setMinimumWidth(240)
        return panel

    def _panel_inferior(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.tabs_modelo = QTabWidget()
        self.tabs_modelo.setDocumentMode(True)
        for lista, (titulo, _cols) in LISTAS.items():
            self.tabs_modelo.addTab(EditorLista(self.sesion, lista), titulo)
        tabs.addTab(self.tabs_modelo, "Modelo")

        self.tabs_res = QTabWidget()
        self.tabs_res.setDocumentMode(True)
        for tipo, titulo in (
            ("reacciones", "Reacciones"),
            ("fuerzas_extremo", "Fuerzas de extremo"),
            ("desplazamientos", "Desplazamientos"),
        ):
            self.tabs_res.addTab(vista_tabla(TablaResultados(self.sesion, tipo)), titulo)
        tabs.addTab(self.tabs_res, "Resultados")

        self.revision = QListWidget()
        tabs.addTab(self.revision, "Revisión del modelo")
        self.consola = Consola(self.sesion)
        tabs.addTab(self.consola, "Consola")
        return tabs

    def _barra_estado(self) -> None:
        barra = self.statusBar()
        barra.setSizeGripEnabled(False)
        self.lbl_estado = QLabel()
        self.lbl_unidades = QLabel()
        self.lbl_tamano = QLabel()
        barra.addWidget(self.lbl_estado)
        barra.addWidget(self.lbl_unidades)
        barra.addWidget(self.lbl_tamano)
        aviso = QLabel(AVISO_PRELIMINAR, objectName="etiqueta")
        aviso.setToolTip(
            "Análisis lineal elástico verificado contra soluciones analíticas. "
            "El diseño según norma todavía no está disponible."
        )
        barra.addPermanentWidget(aviso)

    # --- Actualización de la vista ---------------------------------------------------
    def _actualizar_todo(self) -> None:
        self._actualizar_titulo()
        self._actualizar_explorador()
        self._actualizar_resultados()
        self._actualizar_propiedades()
        self._marcar_diagrama(self.vista.diagrama)
        self.botones_etapa[0].setChecked(True)

    def _actualizar_titulo(self) -> None:
        s = self.sesion
        self.lbl_titulo.setText(s.titulo)
        self.lbl_guardado.setText("Sin guardar" if s.modificado or s.ruta is None else "Guardado")
        self.setWindowTitle(f"{'• ' if s.modificado else ''}{s.titulo} — Nervi")

    def _actualizar_etapas(self) -> None:
        m = self.sesion.modelo
        listos = (
            bool(m["nudos"] and m["barras"] and m.get("apoyos")),
            bool(m["casos"]),
            self.sesion.al_dia,
            self.sesion.al_dia,
        )
        for b, listo, nombre in zip(self.botones_etapa, listos, ETAPAS, strict=False):
            b.setText(f"✓ {nombre}" if listo else nombre)
        u = m["unidades"]
        self.lbl_unidades.setText(f"{u['fuerza']} · {u['longitud']}")
        n, b = len(m["nudos"]), len(m["barras"])
        self.lbl_tamano.setText(f"{n} nudos · {b} barras · {3 * n} GDL")

    def _actualizar_explorador(self) -> None:
        m = self.sesion.modelo
        self.arbol.clear()

        def grupo(titulo: str) -> QTreeWidgetItem:
            item = QTreeWidgetItem(self.arbol, [titulo])
            item.setFlags(Qt.ItemIsEnabled)
            item.setExpanded(True)
            f = item.font(0)
            f.setBold(True)
            item.setFont(0, f)
            return item

        modelo = grupo("Modelo")
        nudos = QTreeWidgetItem(modelo, [f"Nudos  ({len(m['nudos'])})"])
        nudos.setData(0, Qt.UserRole, ("tabla", "nudos"))
        barras = QTreeWidgetItem(modelo, [f"Barras  ({len(m['barras'])})"])
        barras.setData(0, Qt.UserRole, ("tabla", "barras"))
        for b in m["barras"]:
            hijo = QTreeWidgetItem(barras, [f"B{b['id']}   N{b['i']} → N{b['j']}"])
            hijo.setData(0, Qt.UserRole, ("barra", b["id"]))
        apoyos = QTreeWidgetItem(modelo, [f"Apoyos  ({len(m.get('apoyos', []))})"])
        apoyos.setData(0, Qt.UserRole, ("tabla", "apoyos"))
        cargas = grupo("Cargas")
        for c in m["casos"]:
            item = QTreeWidgetItem(cargas, [f"{c['nombre']}"])
            item.setData(0, Qt.UserRole, ("resultado", c["nombre"]))
        combos = QTreeWidgetItem(cargas, [f"Combinaciones  ({len(m.get('combinaciones', []))})"])
        combos.setData(0, Qt.UserRole, ("tabla", "combinaciones"))
        for c in m.get("combinaciones", []):
            item = QTreeWidgetItem(combos, [c["nombre"]])
            item.setData(0, Qt.UserRole, ("resultado", c["nombre"]))
        self.arbol.expandAll()
        self._actualizar_etapas()
        self._actualizar_revision()

    def _actualizar_revision(self) -> None:
        self.revision.clear()
        marcas = {"ok": "✓", "info": "ⓘ", "error": "✕"}
        colores = {"ok": estilo.OK, "info": estilo.ACENTO, "error": estilo.NEGATIVO}
        for aviso in self.sesion.avisos:
            item = QListWidgetItem(f"{marcas[aviso.nivel]}   {aviso.texto}")
            item.setForeground(
                QColor(colores[aviso.nivel] if aviso.nivel != "info" else estilo.TEXTO)
            )
            self.revision.addItem(item)

    def _actualizar_resultados(self) -> None:
        s = self.sesion
        nombres = s.nombres_resultado()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(nombres)
        if s.combinacion in nombres:
            self.combo.setCurrentText(s.combinacion)
        self.combo.blockSignals(False)
        if not s.modelo["barras"]:
            estado = "Modelo vacío"
        elif s.al_dia:
            estado = "● Resultados al día"
        elif s.resultados is not None:
            estado = "● Resultados desactualizados: calculá de nuevo (F5)"
        else:
            estado = "Sin calcular"
        self.lbl_estado.setText(estado)
        color = (
            estilo.OK
            if s.al_dia
            else estilo.NEGATIVO
            if s.resultados is not None
            else estilo.TEXTO_2
        )
        self.lbl_estado.setStyleSheet(f"color: {color};")
        self._actualizar_etapas()
        self._actualizar_revision()
        self._actualizar_propiedades()

    def _actualizar_propiedades(self) -> None:
        for form in (self.form, self.form_res):
            while form.rowCount():
                form.removeRow(0)
        sel = self.sesion.seleccion
        m = self.sesion.modelo
        u = m["unidades"]
        f, l = u["fuerza"], u["longitud"]
        self.lbl_res.setVisible(False)
        if sel is None:
            self.lbl_tipo_sel.setText("PROPIEDADES")
            self.lbl_sel.setText("Nada seleccionado")
            self.form.addRow(_tenue("Hacé clic en una barra o un nudo de la vista."))
            return
        if sel.tipo == "nudo":
            nudo = next((n for n in m["nudos"] if n["id"] == sel.id), None)
            if nudo is None:
                return
            self.lbl_tipo_sel.setText("NUDO")
            self.lbl_sel.setText(f"N{nudo['id']}")
            self.form.addRow("x", _valor(f"{nudo['x']:.3f} {l}"))
            self.form.addRow("y", _valor(f"{nudo['y']:.3f} {l}"))
            apoyo = next((a for a in m.get("apoyos", []) if a["nudo"] == sel.id), None)
            if apoyo:
                gdl = [g for g in ("ux", "uy", "rz") if apoyo.get(g)]
                self.form.addRow("Apoyo", _valor(", ".join(gdl) or "libre"))
            res = self.sesion.resultado()
            if res is not None and self.sesion.indices is not None:
                k = self.sesion.indices.nudos[sel.id]
                self.lbl_res.setVisible(True)
                ux, uy, rz = res.desplazamientos[k]
                self.form_res.addRow("ux", _valor(_num(ux, ".4g") + f" {l}"))
                self.form_res.addRow("uy", _valor(_num(uy, ".4g") + f" {l}"))
                self.form_res.addRow("rz", _valor(_num(rz, ".4g") + " rad"))
                if apoyo:
                    rx, ry, mz = res.reacciones[k]
                    self.form_res.addRow("Rx", _valor(_num(rx) + f" {f}"))
                    self.form_res.addRow("Ry", _valor(_num(ry) + f" {f}"))
                    self.form_res.addRow("Mz", _valor(_num(mz) + f" {f}·{l}"))
            return
        barra = next((b for b in m["barras"] if b["id"] == sel.id), None)
        if barra is None:
            return
        nudos = {n["id"]: n for n in m["nudos"]}
        ni, nj = nudos.get(barra["i"]), nudos.get(barra["j"])
        self.lbl_tipo_sel.setText("BARRA")
        self.lbl_sel.setText(f"B{barra['id']}")
        self.form.addRow("Nudos", _valor(f"N{barra['i']} → N{barra['j']}"))
        if ni and nj:
            largo = ((nj["x"] - ni["x"]) ** 2 + (nj["y"] - ni["y"]) ** 2) ** 0.5
            self.form.addRow("Longitud", _valor(f"{largo:.3f} {l}"))
        self.form.addRow("E", _valor(f"{barra['E']:.4g}"))
        self.form.addRow("A", _valor(f"{barra['A']:.4g}"))
        self.form.addRow("I", _valor(f"{barra['I']:.4g}"))
        lib = barra.get("liberaciones") or [False] * 6
        extremos = [e for e, libre in (("i", lib[2]), ("j", lib[5])) if libre]
        self.form.addRow("Articulada", _valor(" y ".join(extremos) or "no"))
        casos = {c["id"]: c["nombre"] for c in m["casos"]}
        for c in m.get("cargas_barra", []):
            if c["barra"] == barra["id"]:
                if c["tipo"] == "uniforme":
                    texto = f"q = {_num(c.get('qy', 0.0))} {f}/{l} ({c['ejes']})"
                elif c["tipo"] == "trapezoidal":
                    fin = f"{c['b']:g}" if "b" in c else "L"
                    texto = (
                        f"q = {_num(c.get('qy1', 0.0))} → {_num(c.get('qy2', 0.0))} {f}/{l} "
                        f"en [{c.get('a', 0.0):g}, {fin}] ({c['ejes']})"
                    )
                elif c["tipo"] == "momento":
                    texto = f"M = {_num(c.get('mz', 0.0))} {f}·{l} en a = {c['a']:g}"
                elif c["tipo"] == "termica":
                    texto = (
                        f"ΔT = {_num(c.get('dt', 0.0))}, ΔTg = {_num(c.get('gradiente', 0.0))} "
                        f"(α = {c['alfa']:g})"
                    )
                else:
                    texto = f"P = {_num(c.get('py', 0.0))} {f} en a = {c['a']:g} ({c['ejes']})"
                self.form.addRow(casos.get(c["caso"], "?"), _valor(texto))
        res = self.sesion.resultado()
        if res is not None and self.sesion.indices is not None:
            d = res.diagrama(self.sesion.indices.barras[sel.id])
            self.lbl_res.setVisible(True)
            self.lbl_res.setText(f"RESULTADOS · {res.nombre}")
            self.form_res.addRow("M máx +", _valor(_num(max(d["M"].max(), 0.0)) + f" {f}·{l}"))
            self.form_res.addRow("M máx −", _valor(_num(min(d["M"].min(), 0.0)) + f" {f}·{l}"))
            self.form_res.addRow("|V| máx", _valor(_num(abs(d["V"]).max()) + f" {f}"))
            self.form_res.addRow("N", _valor(_num(d["N"][0]) + f" {f}"))
            self.form_res.addRow("|v| máx", _valor(_num(abs(d["v"]).max(), ".4g") + f" {l}"))

    def _marcar_diagrama(self, clave: str) -> None:
        self.botones_diagrama[clave].setChecked(True)

    def _valores(self, activo: bool) -> None:
        self.vista.mostrar_valores = activo
        self.vista.update()

    def _item_explorador(self, item: QTreeWidgetItem) -> None:
        dato = item.data(0, Qt.UserRole)
        if not dato:
            return
        tipo, valor = dato
        if tipo == "barra":
            self.sesion.seleccionar(Seleccion("barra", valor))
        elif tipo == "tabla":
            self.mostrar_tabla(valor)
        elif tipo == "resultado":
            self.combo.setCurrentText(valor)

    def mostrar_tabla(self, lista: str) -> None:
        self.panel_inferior.setCurrentWidget(self.tabs_modelo)
        self.tabs_modelo.setCurrentIndex(list(LISTAS).index(lista))

    def ir_a_etapa(self, n: int) -> None:
        self.botones_etapa[n].setChecked(True)
        if n == 0:
            self.mostrar_tabla("nudos")
        elif n == 1:
            self.mostrar_tabla("cargas_barra")
        elif n == 2:
            self.panel_inferior.setCurrentWidget(self.revision)
        elif n == 3:
            self.panel_inferior.setCurrentWidget(self.tabs_res)

    # --- Comandos --------------------------------------------------------------------
    def _seguir_si_hay_cambios(self) -> bool:
        if not self.sesion.modificado:
            return True
        r = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "Hay cambios sin guardar. ¿Descartarlos?",
            QMessageBox.Discard | QMessageBox.Cancel,
        )
        return r == QMessageBox.Discard

    def nuevo(self) -> None:
        if self._seguir_si_hay_cambios():
            self.sesion.nuevo()
            self.ir_a_etapa(0)

    def abrir_ejemplo(self) -> None:
        if self._seguir_si_hay_cambios():
            self.sesion.nuevo(documento_ejemplo())
            self.ir_a_etapa(0)

    def abrir_dialogo(self) -> None:
        if not self._seguir_si_hay_cambios():
            return
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", "Proyectos de Nervi (*.nrv)"
        )
        if ruta:
            self.abrir(ruta)

    def abrir(self, ruta: str | Path) -> bool:
        try:
            self.sesion.abrir(ruta)
        except (formato.FormatoError, OSError) as e:
            QMessageBox.warning(self, "No se pudo abrir el proyecto", str(e))
            return False
        doc = self.sesion.doc
        if doc.migrado_desde:
            partes = ", ".join(
                f"{nombre} {v} → {formato.MODULOS[nombre].version}"
                for nombre, v in doc.migrado_desde.items()
            )
            QMessageBox.information(
                self,
                "Formato actualizado",
                f"El archivo usaba versiones anteriores del formato ({partes}). Al guardarlo "
                "se actualiza y se deja una copia .bak.",
            )
        if doc.avisos:
            QMessageBox.information(self, "Partes del proyecto sin leer", "\n\n".join(doc.avisos))
        return True

    def guardar(self) -> bool:
        if self.sesion.ruta is None:
            return self.guardar_como()
        return self._guardar_en(self.sesion.ruta)

    def guardar_como(self) -> bool:
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar proyecto", self.sesion.titulo, "Proyectos de Nervi (*.nrv)"
        )
        return self._guardar_en(ruta) if ruta else False

    def _guardar_en(self, ruta) -> bool:
        try:
            self.sesion.guardar(ruta)
        except (formato.FormatoError, OSError) as e:
            QMessageBox.warning(self, "No se pudo guardar", str(e))
            return False
        return True

    def calcular(self) -> bool:
        try:
            self.sesion.calcular()
        except formato.FormatoError as e:
            self._error_calculo(f"El modelo tiene un error: {e}")
            return False
        except MecanismoError as e:
            # El mensaje del motor usa índices internos; la sesión lo traduce a los
            # id de los nudos que ve el usuario.
            ines = self.sesion.inestabilidad
            self._error_calculo(ines.texto() if ines else f"La estructura es inestable: {e}")
            return False
        except ValueError as e:
            self._error_calculo(str(e))
            return False
        self.ir_a_etapa(3)
        return True

    def _error_calculo(self, texto: str) -> None:
        self._actualizar_revision()
        self.panel_inferior.setCurrentWidget(self.revision)
        self.statusBar().showMessage(texto, 8000)

    def entradas_paleta(self) -> list[Entrada]:
        entradas = [
            Entrada(a.text().replace("&", ""), "Comando", a.shortcut().toString(), a.trigger)
            for a in self.actions()
        ]
        for n, nombre in enumerate(ETAPAS[:4]):
            entradas.append(Entrada(f"Ir a {nombre}", "Etapa", "", lambda n=n: self.ir_a_etapa(n)))
        for lista, (titulo, _c) in LISTAS.items():
            entradas.append(
                Entrada(
                    f"Editar {titulo.lower()}", "Tabla", "", lambda l=lista: self.mostrar_tabla(l)
                )
            )
        for nombre in self.sesion.nombres_resultado():
            entradas.append(
                Entrada(
                    f"Ver resultados de {nombre}",
                    "Combinación",
                    "",
                    lambda t=nombre: self.combo.setCurrentText(t),
                )
            )
        m = self.sesion.modelo
        for b in m["barras"]:
            entradas.append(
                Entrada(
                    f"B{b['id']}  N{b['i']} → N{b['j']}",
                    "Barra",
                    "Ir a",
                    lambda i=b["id"]: self.sesion.seleccionar(Seleccion("barra", i)),
                )
            )
        for n in m["nudos"]:
            entradas.append(
                Entrada(
                    f"N{n['id']}  ({n['x']:g}, {n['y']:g})",
                    "Nudo",
                    "Ir a",
                    lambda i=n["id"]: self.sesion.seleccionar(Seleccion("nudo", i)),
                )
            )
        return entradas

    def abrir_paleta(self) -> Paleta:
        paleta = Paleta(self.entradas_paleta(), self)
        geo = self.geometry()
        paleta.move(geo.x() + (geo.width() - paleta.width()) // 2, geo.y() + 110)
        paleta.show()
        paleta.campo.setFocus()
        return paleta

    def closeEvent(self, evento) -> None:
        if self._seguir_si_hay_cambios():
            evento.accept()
        else:
            evento.ignore()


def _num(v: float, fmt: str = ".2f") -> str:
    return format(float(v), fmt).replace("-", "−")


def _valor(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lbl


def _tenue(texto: str) -> QLabel:
    lbl = QLabel(texto, objectName="tenue")
    lbl.setWordWrap(True)
    return lbl
