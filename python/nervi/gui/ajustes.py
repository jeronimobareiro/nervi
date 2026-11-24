# SPDX-License-Identifier: GPL-3.0-or-later
"""Preferencias de la persona y configuración del proyecto.

Hay dos lugares para los ajustes, según una sola regla: **si cambiarlo puede
cambiar un número del cálculo o de la memoria, va en el proyecto; si solo cambia
cómo se ve o se usa la aplicación, va en Preferencias.**

* :class:`Preferencias`: se guardan en esta computadora (``QSettings``) y valen
  para todos los proyectos. Cada una se declara una sola vez en
  :data:`PREFERENCIAS` y la ventana se arma sola desde esa lista.
* :class:`ConfiguracionProyecto`: se guarda dentro del ``.nrv`` (módulos
  ``proyecto``, ``modelo`` y ``diseno``) y viaja con el archivo.

Ver ``docs/diseno-interfaz.md`` §Menús y ajustes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import formato
from . import estilo

#: Con un valor, las preferencias se leen y escriben en ese archivo INI en vez del
#: lugar de siempre del sistema. Lo usan las pruebas para no tocar las del usuario.
ARCHIVO: str | None = None


def configuracion() -> QSettings:
    """Donde se guardan las preferencias de esta computadora."""
    if ARCHIVO is not None:
        return QSettings(ARCHIVO, QSettings.IniFormat)
    return QSettings("Nervi", "Nervi")


# --- Registro de preferencias ---------------------------------------------------------
@dataclass(frozen=True)
class Preferencia:
    """Un ajuste de la persona. ``opciones`` son pares ``(valor guardado, texto)``."""

    clave: str
    apartado: str
    etiqueta: str
    opciones: tuple[tuple[str, str], ...]
    defecto: str
    ayuda: str = ""


#: Apartados de Preferencias, en orden. Solo los que ya tienen algo que ajustar.
APARTADOS_PREFERENCIAS = ("General", "Apariencia")

PREFERENCIAS: tuple[Preferencia, ...] = (
    Preferencia(
        "general/inicio",
        "General",
        "Al abrir Nervi",
        (
            ("ejemplo", "Abrir el pórtico de ejemplo"),
            ("ultimo", "Abrir el último proyecto"),
            ("vacio", "Empezar un proyecto vacío"),
        ),
        "ejemplo",
        "Qué se muestra al abrir el programa sin elegir un archivo.",
    ),
    Preferencia(
        "interfaz/tema",
        "Apariencia",
        "Tema",
        (("claro", "A · Claro preciso"), ("oscuro", "B · Nocturno Nervi")),
        "claro",
    ),
    Preferencia(
        "interfaz/tamano",
        "Apariencia",
        "Tamaño de letra",
        (("normal", "Normal (9,5 pt)"), ("grande", "Grande (11 pt)")),
        "normal",
    ),
)

_POR_CLAVE = {p.clave: p for p in PREFERENCIAS}
TAMANOS = {"normal": 9.5, "grande": 11.0}


def leer(clave: str) -> str:
    """Valor guardado de una preferencia; el de por defecto si no hay o no es válido."""
    p = _POR_CLAVE[clave]
    valor = str(configuracion().value(clave, p.defecto))
    return valor if valor in dict(p.opciones) else p.defecto


def guardar(clave: str, valor: str) -> None:
    p = _POR_CLAVE[clave]
    if valor not in dict(p.opciones):
        raise ValueError(f"{valor!r} no es una opción de {p.etiqueta!r}")
    configuracion().setValue(clave, valor)


def tema(clave: str | None = None) -> estilo.Tema:
    """Tema de la interfaz según las preferencias (``clave`` cambia solo el color)."""
    clave = clave or leer("interfaz/tema")
    return estilo.con_tamano(estilo.TEMAS[clave], TAMANOS[leer("interfaz/tamano")])


# --- Proyectos recientes -----------------------------------------------------------------
CLAVE_RECIENTES = "general/recientes"
MAX_RECIENTES = 8


def recientes() -> list[str]:
    """Proyectos abiertos o guardados hace poco, el último primero, solo los que existen."""
    valor = configuracion().value(CLAVE_RECIENTES, [])
    lista = [valor] if isinstance(valor, str) else list(valor or [])
    return [r for r in lista if r and Path(r).is_file()]


def agregar_reciente(ruta: str | Path) -> None:
    ruta = str(Path(ruta).resolve())
    lista = [ruta] + [r for r in recientes() if r != ruta]
    configuracion().setValue(CLAVE_RECIENTES, lista[:MAX_RECIENTES])


# --- Ventana de ajustes ----------------------------------------------------------------
class DialogoAjustes(QDialog):
    """Lista de apartados a la izquierda, contenido a la derecha, buscador arriba y
    *Restablecer este apartado*, *Cancelar*, *Aplicar* y *Aceptar* abajo."""

    aplicado = Signal()

    def __init__(self, titulo: str, nota: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(820, 540)
        self._restablecer: list = []
        self._textos: list[str] = []
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecera = QWidget(objectName="barra")
        cabecera.setAttribute(Qt.WA_StyledBackground)
        c = QHBoxLayout(cabecera)
        c.setContentsMargins(16, 10, 16, 10)
        c.addWidget(QLabel(titulo, objectName="titulo"))
        c.addStretch()
        self.buscador = QLineEdit(placeholderText="Buscar un ajuste…")
        self.buscador.setClearButtonEnabled(True)
        self.buscador.setFixedWidth(240)
        self.buscador.textChanged.connect(self._filtrar)
        c.addWidget(self.buscador)
        raiz.addWidget(cabecera)

        medio = QHBoxLayout()
        medio.setSpacing(0)
        self.lista = QListWidget(objectName="apartados")
        self.lista.setFixedWidth(230)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.paginas = QStackedWidget()
        self.lista.currentRowChanged.connect(self.paginas.setCurrentIndex)
        medio.addWidget(self.lista)
        medio.addWidget(self.paginas, 1)
        raiz.addLayout(medio, 1)

        pie = QWidget(objectName="pie_ajustes")
        pie.setAttribute(Qt.WA_StyledBackground)
        p = QHBoxLayout(pie)
        p.setContentsMargins(16, 10, 16, 10)
        restablecer = QPushButton("Restablecer este apartado", objectName="fantasma")
        restablecer.clicked.connect(lambda: self._restablecer[self.paginas.currentIndex()]())
        p.addWidget(restablecer)
        self.lbl_error = QLabel(objectName="tenue")
        p.addWidget(self.lbl_error, 1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        aplicar = QPushButton("Aplicar")
        aplicar.clicked.connect(self.aplicar)
        aceptar = QPushButton("Aceptar", objectName="primario")
        aceptar.setDefault(True)
        aceptar.clicked.connect(self._aceptar)
        for b in (cancelar, aplicar, aceptar):
            p.addWidget(b)
        raiz.addWidget(pie)
        self._nota = nota

    def agregar_apartado(self, nombre: str, grupos, restablecer) -> None:
        """Agrega una página. ``grupos`` es una lista de ``(título, [(etiqueta, control)])``;
        una etiqueta ``None`` ocupa la fila entera."""
        pagina = QWidget(objectName="pagina_ajustes")
        pagina.setAttribute(Qt.WA_StyledBackground)
        capa = QVBoxLayout(pagina)
        capa.setContentsMargins(24, 18, 24, 18)
        capa.setSpacing(10)
        textos = [nombre]
        for titulo, filas in grupos:
            capa.addWidget(QLabel(titulo.upper(), objectName="seccion"))
            caja = QWidget(objectName="caja_ajustes")
            caja.setAttribute(Qt.WA_StyledBackground)
            form = QFormLayout(caja)
            form.setContentsMargins(16, 12, 16, 12)
            form.setHorizontalSpacing(24)
            form.setVerticalSpacing(10)
            form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
            for etiqueta, control in filas:
                if etiqueta is None:
                    form.addRow(control)
                else:
                    form.addRow(QLabel(etiqueta), control)
                    textos.append(etiqueta)
                if isinstance(control, (QCheckBox, QLabel)):
                    textos.append(control.text())
            capa.addWidget(caja)
            textos.append(titulo)
        capa.addStretch()
        nota = QLabel(self._nota, objectName="tenue")
        nota.setWordWrap(True)
        capa.addWidget(nota)
        self.paginas.addWidget(pagina)
        self.lista.addItem(nombre)
        self._restablecer.append(restablecer)
        self._textos.append(" ".join(textos).lower())
        if self.lista.currentRow() < 0:
            self.lista.setCurrentRow(0)
        # Que el foco empiece en la lista y no en el buscador.
        self.lista.setFocus()

    def elegir_apartado(self, nombre: str) -> None:
        items = self.lista.findItems(nombre, Qt.MatchExactly)
        if items:
            self.lista.setCurrentItem(items[0])

    def _filtrar(self, texto: str) -> None:
        texto = texto.strip().lower()
        primera = None
        for k, contenido in enumerate(self._textos):
            visible = not texto or texto in contenido
            self.lista.item(k).setHidden(not visible)
            if visible and primera is None:
                primera = k
        actual = self.lista.currentRow()
        if primera is not None and (actual < 0 or self.lista.item(actual).isHidden()):
            self.lista.setCurrentRow(primera)

    def _aceptar(self) -> None:
        if self.aplicar():
            self.accept()

    def aplicar(self) -> bool:
        raise NotImplementedError


def _combo(opciones, ancho: int = 260) -> QComboBox:
    c = QComboBox()
    for valor, texto in opciones:
        c.addItem(texto, valor)
    c.setMinimumWidth(ancho)
    return c


def _elegir(combo: QComboBox, valor) -> None:
    combo.setCurrentIndex(max(combo.findData(valor), 0))


class Preferencias(DialogoAjustes):
    """Preferencias de la persona, armadas desde :data:`PREFERENCIAS`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Preferencias",
            "Se guardan en esta computadora y valen para todos los proyectos. "
            "No cambian ningún resultado.",
            parent,
        )
        self.controles: dict[str, QComboBox] = {}
        for apartado in APARTADOS_PREFERENCIAS:
            filas = []
            for p in PREFERENCIAS:
                if p.apartado != apartado:
                    continue
                combo = _combo(p.opciones)
                _elegir(combo, leer(p.clave))
                if p.ayuda:
                    combo.setToolTip(p.ayuda)
                self.controles[p.clave] = combo
                filas.append((p.etiqueta, combo))
            self.agregar_apartado(
                apartado, [(apartado, filas)], lambda a=apartado: self._restablecer_apartado(a)
            )

    def _restablecer_apartado(self, apartado: str) -> None:
        for p in PREFERENCIAS:
            if p.apartado == apartado:
                _elegir(self.controles[p.clave], p.defecto)

    def aplicar(self) -> bool:
        for clave, combo in self.controles.items():
            guardar(clave, combo.currentData())
        self.aplicado.emit()
        return True


# --- Configuración del proyecto ----------------------------------------------------------
def _spin(minimo: float, maximo: float, sufijo: str, decimales: int = 0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(minimo, maximo)
    s.setDecimals(decimales)
    s.setSuffix(f" {sufijo}")
    s.setKeyboardTracking(False)
    s.setMinimumWidth(130)
    return s


class ConfiguracionProyecto(DialogoAjustes):
    """Datos del proyecto, unidades, materiales y criterios de diseño del ``.nrv`` abierto.

    Edita los mismos datos que la etapa Diseño: los dos lugares muestran siempre
    lo mismo porque los dos pasan por la sesión."""

    def __init__(self, sesion, parent: QWidget | None = None) -> None:
        nombre = sesion.ruta.stem if sesion.ruta else "Sin título"
        super().__init__(
            f"Configuración del proyecto · {nombre}",
            "Se guarda dentro del archivo .nrv. Cambiar unidades, materiales o criterios "
            "deja los resultados desactualizados hasta calcular de nuevo.",
            parent,
        )
        self.sesion = sesion

        # Datos del proyecto (carátula de la memoria)
        self.datos: dict[str, QLineEdit] = {}
        filas = []
        for clave, etiqueta in formato.proyecto.CAMPOS.items():
            campo = QLineEdit()
            campo.setMaxLength(formato.proyecto.MAX_CARACTERES)
            campo.setMinimumWidth(320)
            if clave == "nombre":
                campo.setPlaceholderText(nombre)
            self.datos[clave] = campo
            filas.append((etiqueta, campo))
        self.agregar_apartado(
            "Datos del proyecto",
            [("Carátula de la memoria", filas)],
            lambda: [c.clear() for c in self.datos.values()],
        )

        # Unidades
        validos = formato.modelo._UNIDADES
        self.fuerza = _combo([(u, u) for u in validos["fuerza"]], 120)
        self.longitud = _combo([(u, u) for u in validos["longitud"]], 120)
        self.aviso_unidades = QLabel(objectName="tenue")
        self.aviso_unidades.setWordWrap(True)
        self.agregar_apartado(
            "Unidades",
            [
                (
                    "Unidades del modelo",
                    [
                        ("Fuerza", self.fuerza),
                        ("Longitud", self.longitud),
                        (None, self.aviso_unidades),
                    ],
                )
            ],
            self._unidades_por_defecto,
        )

        # Materiales
        self.fc = _spin(17, 100, "MPa", 1)
        self.fy = _spin(240, 550, "MPa")
        self.fyt = _spin(240, 420, "MPa")
        self.agregar_apartado(
            "Materiales",
            [
                ("Hormigón", [("f'c", self.fc)]),
                ("Acero", [("fy (longitudinal)", self.fy), ("fyt (estribos)", self.fyt)]),
            ],
            self._materiales_por_defecto,
        )

        # Diseño
        self.recubrimiento = _spin(0, 100, "mm")
        self.agregado = _spin(5, 50, "mm")
        self.estribo = _combo([(d, f"Ø {d}") for d in formato.diseno.DIAMETROS_ESTRIBO], 130)
        self.a_d = QCheckBox("Cortante de vigas en la sección crítica a d del apoyo")
        self.diametros: dict[int, QCheckBox] = {}
        casillas = QWidget()
        h = QHBoxLayout(casillas)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)
        for d in formato.diseno.DIAMETROS_COLUMNA:
            cb = QCheckBox(f"Ø{d}")
            self.diametros[d] = cb
            h.addWidget(cb)
        h.addStretch()
        ayuda_diametros = QLabel(
            "El programa elige solo la armadura de menor área que cumple, entre los "
            "diámetros marcados.",
            objectName="tenue",
        )
        ayuda_diametros.setWordWrap(True)
        self.agregar_apartado(
            "Diseño",
            [
                (
                    "Criterios",
                    [
                        ("Recubrimiento libre", self.recubrimiento),
                        ("Estribo", self.estribo),
                        ("Tamaño máximo del agregado", self.agregado),
                        (None, self.a_d),
                    ],
                ),
                (
                    "Columnas",
                    [("Diámetros permitidos", casillas), (None, ayuda_diametros)],
                ),
            ],
            self._diseno_por_defecto,
        )
        self.cargar()

    # --- Leer y escribir ------------------------------------------------------------
    def cargar(self) -> None:
        s = self.sesion
        datos = s.proyecto["datos"]
        for clave, campo in self.datos.items():
            campo.setText(datos.get(clave, ""))
        u = s.modelo["unidades"]
        _elegir(self.fuerza, u["fuerza"])
        _elegir(self.longitud, u["longitud"])
        vacio = not s.modelo["nudos"] and not s.modelo["barras"]
        self.fuerza.setEnabled(vacio)
        self.longitud.setEnabled(vacio)
        self.aviso_unidades.setText(
            "Se eligen al empezar el modelo."
            if vacio
            else "El modelo ya tiene datos en estas unidades. Para cambiarlas hace falta "
            "convertir todos los valores, algo que Nervi todavía no hace."
        )
        self._cargar_diseno(s.diseno)

    def _cargar_diseno(self, d: dict) -> None:
        c = d["criterios"]
        self.fc.setValue(d["hormigon"]["fc"])
        self.fy.setValue(d["acero"]["fy"])
        self.fyt.setValue(d["acero"].get("fyt", d["acero"]["fy"]))
        self.recubrimiento.setValue(c["recubrimiento"])
        self.agregado.setValue(c["d_agregado"])
        _elegir(self.estribo, int(c["d_estribo"]))
        self.a_d.setChecked(c["seccion_critica_a_d"])
        elegidos = c.get("diametros_columna", formato.diseno.DIAMETROS_COLUMNA)
        for d_b, cb in self.diametros.items():
            cb.setChecked(d_b in elegidos)

    def _unidades_por_defecto(self) -> None:
        if self.fuerza.isEnabled():
            u = formato.modelo.nuevo()["unidades"]
            _elegir(self.fuerza, u["fuerza"])
            _elegir(self.longitud, u["longitud"])

    def _materiales_por_defecto(self) -> None:
        d = formato.diseno.nuevo()
        self.fc.setValue(d["hormigon"]["fc"])
        self.fy.setValue(d["acero"]["fy"])
        self.fyt.setValue(d["acero"]["fyt"])

    def _diseno_por_defecto(self) -> None:
        d = formato.diseno.nuevo()
        c = d["criterios"]
        self.recubrimiento.setValue(c["recubrimiento"])
        self.agregado.setValue(c["d_agregado"])
        _elegir(self.estribo, int(c["d_estribo"]))
        self.a_d.setChecked(c["seccion_critica_a_d"])
        for cb in self.diametros.values():
            cb.setChecked(True)

    def aplicar(self) -> bool:
        s = self.sesion
        elegidos = [d for d, cb in self.diametros.items() if cb.isChecked()]
        if not elegidos:
            self.elegir_apartado("Diseño")
            self.lbl_error.setText("Marcá al menos un diámetro para las columnas.")
            return False
        self.lbl_error.clear()

        proyecto = copy.deepcopy(s.proyecto)
        textos = {clave: campo.text().strip() for clave, campo in self.datos.items()}
        proyecto["datos"] = {clave: texto for clave, texto in textos.items() if texto}
        if proyecto != s.proyecto:
            s.editar_proyecto(proyecto)

        u = {"fuerza": self.fuerza.currentData(), "longitud": self.longitud.currentData()}
        if u != s.modelo["unidades"]:
            modelo = s.copia_modelo()
            modelo["unidades"] = u
            s.editar(modelo)

        d = copy.deepcopy(s.diseno)
        d["hormigon"]["fc"] = self.fc.value()
        d["acero"]["fy"] = self.fy.value()
        d["acero"]["fyt"] = self.fyt.value()
        c = d["criterios"]
        c["recubrimiento"] = self.recubrimiento.value()
        c["d_agregado"] = self.agregado.value()
        c["d_estribo"] = float(self.estribo.currentData())
        c["seccion_critica_a_d"] = self.a_d.isChecked()
        c["diametros_columna"] = elegidos
        # Un proyecto sin datos de diseño solo los suma si algo cambió.
        if d != s.diseno:
            s.editar_diseno(d)
        self.aplicado.emit()
        return True
