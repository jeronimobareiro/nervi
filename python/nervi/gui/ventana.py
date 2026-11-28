# SPDX-License-Identifier: GPL-3.0-or-later
"""Ventana principal: todo el trabajo en una sola ventana.

Arriba, el flujo de trabajo (Geometría › Cargas › Análisis › Resultados › Diseño) y la
barra contextual; a la izquierda, la barra lateral de menús (íconos) y el
explorador del proyecto; al centro, la vista del pórtico; a la derecha, las
propiedades de la selección; abajo, tablas, revisión del modelo y consola.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QByteArray, QElapsedTimer, QPoint, QPointF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import MecanismoError, formato
from ..design import proyecto
from . import ajustes, camara3d, estilo, iconos, marco, paneles, vista3d
from .ajustes import ConfiguracionProyecto, Preferencias
from .arbol import ArbolModelo
from .asistente import PanelAsistente
from .canal import CanalVentana
from .consola import Consola
from .dibujo import ENGANCHES, HERRAMIENTAS, PASO_GRILLA_M, PanelHerramienta
from .dibujo_calculo import ENGANCHES_CALCULO, HERRAMIENTAS_CALCULO, PanelCalculo
from .dinamica import PanelDinamica, fase
from .diseno import PanelDiseno, color_estado
from .edificio import (
    CASOS_VISTA,
    EstadoEdificio,
    GestorPlantas,
    PlantaEdificio,
    PropiedadesEdificio,
    TablasEdificio,
    filas_arbol,
    nombre_elemento,
)
from .paleta import Entrada, Paleta
from .paneles import crear_panel
from .resultados_edificio import PanelModeloCalculo, PanelResultadosEdificio
from .sesion import Seleccion, Sesion, documento_ejemplo
from .tablas import LISTAS, EditorLista, TablaResultados, vista_tabla
from .vista2d import DIAGRAMAS, Vista2D
from .vista3d import Vista3D

RECURSOS = Path(__file__).resolve().parent / "recursos"
#: Ícono del gestor de plantas del modo Edificio: el edificio con sus losas y el terreno
#: (elegido el 26/11/2026), y chevrones para subir y bajar de planta. Salen del catálogo
#: :mod:`nervi.gui.iconos`.
ICONO_PLANTAS = iconos.CATALOGO["plantas"].cuerpo
ICONO_SUBIR = iconos.CATALOGO["subir"].cuerpo
ICONO_BAJAR = iconos.CATALOGO["bajar"].cuerpo
ICONO_CARGAS = iconos.CATALOGO["cargas_planta"].cuerpo  # botón Cargas (#78)


def icono_trazo(cuerpo: str, color: str, lado: int, escala: float) -> QPixmap:
    """Ícono de trazo de la familia de la barra lateral (``viewBox`` de 24), de ``lado`` px."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{cuerpo}</svg>'
    )
    pix = QPixmap(round(lado * escala), round(lado * escala))
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pix.setDevicePixelRatio(escala)
    return pix


ETAPAS = ("Geometría", "Cargas", "Análisis", "Resultados", "Diseño", "Memoria")
#: Tablas del pórtico plano que van en la etapa Cargas (las demás, en Geometría).
LISTAS_CARGAS = ("casos", "cargas_nodales", "cargas_barra", "combinaciones")
AVISO_PRELIMINAR = "Versión preliminar · no apta para proyecto"


CLAVE_TEMA = "interfaz/tema"
URL_REPOSITORIO = "https://github.com/jeronimobareiro/nervi"

#: Menús de la barra lateral: clave del ícono y nombre, arriba y abajo.
MENUS_RIEL = (
    ("archivo", "Archivo"),
    ("editar", "Editar"),
    ("modelo", "Modelo"),
    ("calcular", "Calcular"),
    ("ver", "Ver"),
    ("herramientas", "Herramientas"),
    ("ia", "Asistente de IA"),
)
MENUS_RIEL_ABAJO = (("ayuda", "Ayuda"), ("preferencias", "Preferencias"))


def tema_guardado() -> str:
    """Tema elegido la última vez ("claro" u "oscuro")."""
    return ajustes.leer(CLAVE_TEMA)


def icono() -> QIcon:
    return QIcon(str(RECURSOS / "nervi.svg"))


#: Nombres viejos de las vistas (antes había una vista 2D y una 3D separadas).
ALIAS_VISTAS = {"2D": "frente", "2d": "frente", "3D": "3d"}


class Ventana(QMainWindow):
    def __init__(self, sesion: Sesion | None = None) -> None:
        super().__init__()
        self.sesion = sesion or Sesion()
        self.canal = CanalVentana(self.sesion, self)
        self.setWindowIcon(icono())
        self.resize(1440, 900)
        estilo.aplicar(tema=ajustes.tema())
        # Modelo físico del edificio (#73): piso que se ve y elemento elegido.
        self.edificio = EstadoEdificio(self.sesion)
        # La planta y la vista 2D se crean antes que las barras: la barra contextual
        # lleva sus herramientas de dibujo.
        self.planta = PlantaEdificio(self.edificio)
        self.vista = Vista2D(self.sesion)
        self.vista.brujula.show()
        self.vista.brujula.vista_pedida.connect(self._vista_desde_brujula)
        self.vista.giro_pedido.connect(self._girar_desde_frente)
        self.vista.giro_arrastre.connect(self._seguir_giro)
        self.vista.giro_terminado.connect(self._terminar_giro)
        self.modo = "calculo"
        self._acciones()

        # Barras fijas: arriba la superior y la contextual, a la izquierda el riel de
        # menús. Van en QToolBar para que los paneles se acoplen entre ellas y la vista.
        barra_superior = self._barra_fija("superior", self._barra_superior(), Qt.TopToolBarArea)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self._barra_fija("contextual", self._barra_contextual(), Qt.TopToolBarArea)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.barra_dibujo = self._barra_herramientas_dibujo()
        self._barra_fija("riel", self._riel(), Qt.LeftToolBarArea)

        # El visor 3D se crea la primera vez que se lo pide: VTK tarda en arrancar
        # y es una dependencia opcional (nervi[visor3d]).
        self.vista3d: QWidget | None = None
        self.vistas = QStackedWidget(objectName="raiz")
        self.vistas.addWidget(self.vista)
        self.vistas.addWidget(self.planta)
        self.setCentralWidget(self.vistas)

        # Paneles acoplables (nervi.gui.paneles): se mueven, se apilan, se desacoplan
        # y se cierran; el menú Ver > Paneles los vuelve a abrir.
        self.setDockOptions(
            QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks
        )
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.panel_inferior = self._panel_inferior()
        # Sin esto, el ancho de las pestañas y las tablas fija el ancho mínimo de la
        # ventana; las pestañas que no entran se recorren con flechas.
        self.panel_inferior.setMinimumWidth(360)
        # Panel del asistente de IA: junto a la barra lateral, se abre con su ícono.
        self.asistente = PanelAsistente(self.sesion, self.canal)
        self.paneles = {
            "asistente": crear_panel(self, "asistente", "Asistente de IA", self.asistente),
            "estructura": crear_panel(self, "estructura", "Estructura", self._explorador()),
            "propiedades": crear_panel(self, "propiedades", "Propiedades", self._propiedades()),
            "inferior": crear_panel(self, "inferior", "Tablas y resultados", self.panel_inferior),
            "consola": crear_panel(self, "consola", "Consola Python", self.consola),
        }
        d = self.paneles
        self.addDockWidget(Qt.LeftDockWidgetArea, d["estructura"])
        self.addDockWidget(Qt.RightDockWidgetArea, d["propiedades"])
        self.addDockWidget(Qt.BottomDockWidgetArea, d["inferior"])
        self.addDockWidget(Qt.LeftDockWidgetArea, d["asistente"])
        self.addDockWidget(Qt.BottomDockWidgetArea, d["consola"])
        self.tabifyDockWidget(d["inferior"], d["consola"])
        d["consola"].hide()
        self.splitDockWidget(d["asistente"], d["estructura"], Qt.Horizontal)
        d["asistente"].hide()
        self.resizeDocks([d["estructura"], d["propiedades"]], [240, 290], Qt.Horizontal)
        self.resizeDocks([d["inferior"]], [250], Qt.Vertical)
        d["asistente"].toggleViewAction().toggled.connect(
            lambda v: self.botones_riel["ia"].setChecked(v)
        )
        #: Distribución de fábrica, para *Restablecer*.
        self._distribucion_inicial = self.saveState(paneles.VERSION)
        self._barra_estado()

        s = self.sesion
        s.archivo_cambiado.connect(self._actualizar_titulo)
        s.modelo_cambiado.connect(self._actualizar_explorador)
        s.modelo_cambiado.connect(self._actualizar_etapas)
        s.resultados_cambiados.connect(self._actualizar_resultados)
        s.seleccion_cambiada.connect(self._actualizar_propiedades)
        s.diseno_cambiado.connect(self._actualizar_diseno)
        s.historial_cambiado.connect(self._actualizar_deshacer)
        self.asistente.pendientes_cambiadas.connect(self._actualizar_insignia)
        self.canal.estado_cambiado.connect(self.a_conectar_ia.setChecked)
        self._actualizar_insignia(len(s.propuestas))
        self._actualizar_deshacer()
        s.diseno_cambiado.connect(self._actualizar_explorador)
        s.seleccion_cambiada.connect(self._marcar_arbol)
        s.resultados_cambiados.connect(self._marcar_arbol)
        self.vista.diagrama_cambiado.connect(self._marcar_diagrama)
        self.edificio.cambiado.connect(self._actualizar_edificio)
        self.edificio.cambiado.connect(self._resaltar_en_3d)
        s.fisico_cambiado.connect(self._resaltar_en_3d)
        self.edificio.mensaje.connect(lambda t: self.statusBar().showMessage(f"✕ {t}", 6000))
        self.vista.dibujo.mensaje.connect(lambda t: self.statusBar().showMessage(f"✕ {t}", 6000))
        # Barra de título propia (nervi.gui.marco): la fila superior hace de barra de
        # título y lleva los botones de la ventana; la de sistema queda en Preferencias.
        self.marco: marco.Marco | None = None
        if self.botones_ventana is not None:
            self.marco = marco.Marco(
                self, self.findChild(QWidget, "barra"), self.botones_ventana, barra_superior
            )
        self._actualizar_todo()
        self._modo_del_proyecto()
        paneles.recuperar(self)

    def _barra_fija(self, clave: str, widget: QWidget, area) -> QToolBar:
        """Una barra que no se mueve ni se cierra (la superior, la contextual, el riel)."""
        barra = QToolBar(objectName=f"barra_{clave}")
        barra.setMovable(False)
        barra.setFloatable(False)
        barra.setContextMenuPolicy(Qt.PreventContextMenu)
        barra.toggleViewAction().setVisible(False)
        vertical = area in (Qt.LeftToolBarArea, Qt.RightToolBarArea)
        widget.setSizePolicy(
            QSizePolicy.Preferred if vertical else QSizePolicy.Expanding,
            QSizePolicy.Expanding if vertical else QSizePolicy.Preferred,
        )
        barra.addWidget(widget)
        self.addToolBar(area, barra)
        return barra

    def _barra_herramientas_dibujo(self) -> QToolBar:
        """Barra *Dibujo* con las herramientas del modo que se ve. Se puede mover a otro
        borde (se pone vertical a los costados), desacoplar o cerrar desde *Ver >
        Paneles*."""
        barra = QToolBar("Barra de dibujo", objectName="barra_dibujo")
        barra.setMovable(True)
        barra.setFloatable(True)
        self.dibujo_edificio = self._barra_dibujo()
        self.dibujo_calculo = self._barra_dibujo(
            self.vista.dibujo, HERRAMIENTAS_CALCULO, ENGANCHES_CALCULO
        )
        self._accion_dibujo = {
            "edificio": barra.addWidget(self.dibujo_edificio),
            "calculo": barra.addWidget(self.dibujo_calculo),
        }
        self._accion_dibujo["edificio"].setVisible(False)
        barra.orientationChanged.connect(self._orientar_dibujo)
        self.addToolBar(Qt.TopToolBarArea, barra)
        return barra

    def _orientar_dibujo(self, orientacion) -> None:
        direccion = QBoxLayout.TopToBottom if orientacion == Qt.Vertical else QBoxLayout.LeftToRight
        for w in (self.dibujo_edificio, self.dibujo_calculo):
            for capa in w.property("capas"):
                capa.setDirection(direccion)

    # --- Paneles y distribuciones ---------------------------------------------------
    def _menu_paneles(self) -> QMenu:
        """*Ver › Paneles*. Se llena al abrirse: el riel se arma antes que los paneles."""
        self.menu_paneles = QMenu("Paneles", self)
        self.menu_paneles.aboutToShow.connect(self._llenar_paneles)
        self.menu_distribuciones = QMenu("Distribuciones guardadas", self)
        self.menu_distribuciones.aboutToShow.connect(self._llenar_distribuciones)
        return self.menu_paneles

    def _llenar_paneles(self) -> None:
        menu = self.menu_paneles
        menu.clear()
        for clave in ("estructura", "propiedades", "inferior", "consola", "asistente"):
            menu.addAction(self.paneles[clave].toggleViewAction())
        menu.addAction(self.barra_dibujo.toggleViewAction())
        menu.addSeparator()
        menu.addAction(self.a_guardar_distribucion)
        menu.addMenu(self.menu_distribuciones)
        menu.addAction(self.a_restablecer_distribucion)

    def _llenar_distribuciones(self) -> None:
        m = self.menu_distribuciones
        m.clear()
        nombres = paneles.distribuciones()
        for nombre in nombres:
            m.addAction(nombre, lambda n=nombre: self.aplicar_distribucion(n))
        if not nombres:
            m.addAction("Ninguna todavía").setEnabled(False)
            return
        m.addSeparator()
        borrar = m.addMenu("Borrar")
        for nombre in nombres:
            borrar.addAction(nombre, lambda n=nombre: paneles.borrar_distribucion(n))

    def guardar_distribucion(self, nombre: str | None = None) -> str | None:
        """Guarda la distribución de los paneles con un nombre (lo pide si falta)."""
        if nombre is None:
            nombre, ok = QInputDialog.getText(
                self, "Guardar distribución", "Nombre de la distribución:"
            )
            if not ok:
                return None
        try:
            nombre = paneles.guardar_distribucion(self, nombre)
        except ValueError as e:
            self.statusBar().showMessage(f"✕ {e}", 6000)
            return None
        self.statusBar().showMessage(f"Distribución «{nombre}» guardada", 4000)
        return nombre

    def aplicar_distribucion(self, nombre: str) -> bool:
        ok = paneles.aplicar_distribucion(self, nombre)
        if not ok:
            self.statusBar().showMessage(f"✕ No se pudo usar la distribución «{nombre}»", 6000)
        return ok

    def restablecer_distribucion(self) -> None:
        """Vuelve los paneles a la distribución de fábrica."""
        for dock in self.paneles.values():
            dock.setFloating(False)
        self.restoreState(self._distribucion_inicial, paneles.VERSION)

    # --- Acciones y menú ------------------------------------------------------------
    def _accion(self, texto: str, funcion, atajo: str | QKeySequence | None = None) -> QAction:
        a = QAction(texto, self)
        if atajo:
            a.setShortcut(QKeySequence(atajo))
        a.triggered.connect(funcion)
        self.addAction(a)
        return a

    def _acciones(self) -> None:
        self.a_nuevo = self._accion("Nuevo edificio", self.nuevo, QKeySequence.New)
        self.a_nuevo_portico = self._accion(
            "Nuevo pórtico plano", lambda: self.nuevo(edificio=False)
        )
        self.a_ejemplo = self._accion("Abrir ejemplo: pórtico simple", self.abrir_ejemplo)
        self.a_abrir = self._accion("Abrir", self.abrir_dialogo, QKeySequence.Open)
        self.a_importar_dxf = self._accion("Importar DXF", self.importar_dxf_dialogo)
        self.a_guardar = self._accion("Guardar", self.guardar, QKeySequence.Save)
        self.a_guardar_como = self._accion("Guardar como", self.guardar_como, QKeySequence.SaveAs)
        self.a_deshacer = self._accion("Deshacer", self.deshacer, QKeySequence.Undo)
        self.a_rehacer = self._accion("Rehacer", self.rehacer, QKeySequence.Redo)
        self.a_calcular = self._accion("Calcular", self.calcular, "F5")
        self.a_disenar = self._accion("Diseñar elementos de hormigón armado", self.disenar)
        self.a_dinamica = self._accion("Análisis modal y espectral", self.analizar_dinamica)
        self.a_memoria = self._accion(
            "Exportar memoria de cálculo (PDF)", self.exportar_memoria, "Ctrl+P"
        )
        self.a_resultados = self._accion(
            "Exportar resultados a precisión completa (JSON)", self.exportar_resultados
        )
        self.a_conectar_ia = self._accion("Conectar con mi IA", self.conectar_ia)
        self.a_conectar_ia.setCheckable(True)
        self.a_buscar = self._accion("Buscar comando o elemento", self.abrir_paleta, "Ctrl+K")
        self.a_salir = self._accion("Salir", self.close, QKeySequence.Quit)
        self.a_preferencias = self._accion("Preferencias", self.abrir_preferencias, "Ctrl+,")
        self.a_configuracion = self._accion(
            "Configuración del proyecto", self.configurar_proyecto, "Ctrl+Shift+,"
        )
        self.a_consola = self._accion("Consola Python", self.mostrar_consola)
        self.a_revision = self._accion("Revisión del modelo", self.mostrar_revision)
        self.a_acerca = self._accion("Acerca de Nervi", self.acerca_de)
        self.a_informar = self._accion(
            "Informar un error",
            lambda: QDesktopServices.openUrl(QUrl(URL_REPOSITORIO + "/issues")),
        )
        self.a_codigo = self._accion(
            "Código fuente y documentación",
            lambda: QDesktopServices.openUrl(QUrl(URL_REPOSITORIO)),
        )
        self.a_diagramas = {}
        for clave, nombre in DIAGRAMAS.items():
            atajo = {"M": "M", "V": "V", "N": "N", "D": "D"}[clave]
            self.a_diagramas[clave] = self._accion(
                f"Mostrar {nombre.lower()}",
                lambda _=False, c=clave: self.elegir_diagrama(c),
                atajo,
            )
            self.a_diagramas[clave].setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.a_orto = self._accion(
            "Orto: dibujar en horizontal y vertical",
            self.alternar_orto,
            "F8",
        )
        self.a_guardar_distribucion = self._accion(
            "Guardar distribución…", lambda: self.guardar_distribucion()
        )
        self.a_restablecer_distribucion = self._accion(
            "Restablecer distribución", self.restablecer_distribucion
        )
        self.a_plantas = self._accion("Plantas", self.gestionar_plantas)
        self.a_subir = self._accion("Subir una planta", lambda: self.subir_planta(1), "PgUp")
        self.a_bajar = self._accion("Bajar una planta", lambda: self.subir_planta(-1), "PgDown")
        # Re Pág y Av Pág solo en el modo Edificio (fuera del menú: en Cálculo están
        # inactivas para que las tablas usen esas teclas).
        self.a_subir.setEnabled(False)
        self.a_bajar.setEnabled(False)
        self.a_planta = self._accion("Vista en planta", lambda: self.mostrar_vista("planta"))
        self.a_vista2d = self._accion("Vista de frente", lambda: self.mostrar_vista("frente"))
        self.a_vista3d = self._accion("Vista 3D", lambda: self.mostrar_vista("3d"))
        self.a_temas = {}
        grupo_temas = QActionGroup(self)
        for clave, tema in estilo.TEMAS.items():
            a = self._accion(
                f"Tema {tema.nombre.lower()}", lambda _=False, c=clave: self.elegir_tema(c)
            )
            a.setCheckable(True)
            a.setChecked(clave == tema_guardado())
            grupo_temas.addAction(a)
            self.a_temas[clave] = a

    def _barra_superior(self) -> QWidget:
        barra = QWidget(objectName="barra")
        capa = QHBoxLayout(barra)
        capa.setContentsMargins(8, 6, 10, 6)
        capa.setSpacing(10)
        menu = QMenu(self)
        for a in (
            self.a_nuevo,
            self.a_nuevo_portico,
            self.a_abrir,
            self.a_ejemplo,
            self.a_importar_dxf,
            None,
            self.a_guardar,
            self.a_guardar_como,
            self.a_memoria,
            self.a_resultados,
            self.a_configuracion,
            None,
            self.a_deshacer,
            self.a_rehacer,
            None,
            *self.a_temas.values(),
            self.a_preferencias,
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
            if nombre == "Memoria":
                b.setEnabled(False)
                b.setToolTip(
                    "Llega con la Fase 4. Mientras tanto, exportá la memoria en PDF con Ctrl+P"
                )
            elif nombre == "Diseño":
                b.setToolTip(
                    "Armadura de vigas y columnas de hormigón según ACI 318-19 (experimental)"
                )
            self.etapas.addButton(b, n)
            self.botones_etapa.append(b)
            capa.addWidget(b)
        self.etapas.idClicked.connect(self.ir_a_etapa)
        capa.addStretch()

        buscar = QPushButton("Buscar…      Ctrl K", objectName="buscar")
        buscar.setToolTip("Buscar comando o elemento (Ctrl+K)")
        buscar.setAccessibleName("Buscar comando o elemento")
        buscar.clicked.connect(self.abrir_paleta)
        calcular = QPushButton("Calcular   F5", objectName="primario")
        calcular.clicked.connect(self.calcular)
        capa.addWidget(buscar)
        capa.addWidget(calcular)
        #: Minimizar, maximizar y cerrar, si la fila superior es la barra de título.
        self.botones_ventana: marco.BotonesVentana | None = None
        if marco.usar_propia():
            capa.setContentsMargins(8, 0, 0, 0)
            barra.setFixedHeight(marco.ALTO_BARRA)
            capa.addSpacing(8)
            capa.addWidget(marco.separador())
            capa.addSpacing(2)
            self.botones_ventana = marco.BotonesVentana(self)
            capa.addWidget(self.botones_ventana)
        return barra

    # --- Barra lateral de menús -------------------------------------------------------
    def _riel(self) -> QWidget:
        """Barra de íconos a la izquierda: cada ícono abre su menú hacia la derecha.

        Los menús solo tienen acciones que ya existen; el resto se agrega cuando llega
        (``docs/diseno-interfaz.md`` §Menús y ajustes)."""
        riel = QWidget(objectName="riel")
        riel.setAttribute(Qt.WA_StyledBackground)
        riel.setFixedWidth(52)
        capa = QVBoxLayout(riel)
        capa.setContentsMargins(6, 8, 6, 8)
        capa.setSpacing(4)
        self.menus_riel = self._menus_riel()
        self.botones_riel: dict[str, QToolButton] = {}
        for grupo in (MENUS_RIEL, MENUS_RIEL_ABAJO):
            if grupo is MENUS_RIEL_ABAJO:
                capa.addStretch()
            for clave, nombre in grupo:
                b = QToolButton(objectName="menu_riel")
                b.setFixedSize(40, 40)
                b.setIconSize(QSize(20, 20))
                b.setCheckable(True)
                b.setToolTip(nombre)
                b.setAccessibleName(nombre)
                b.clicked.connect(lambda _=False, c=clave: self.abrir_menu_riel(c))
                if clave in self.menus_riel:
                    self.menus_riel[clave].aboutToHide.connect(lambda b=b: b.setChecked(False))
                self.botones_riel[clave] = b
                capa.addWidget(b, 0, Qt.AlignHCenter)
        self._iconos_riel()
        # Cuántas propuestas de la IA esperan, sobre el ícono del asistente.
        self.insignia_ia = QLabel(self.botones_riel["ia"], objectName="insignia")
        self.insignia_ia.setAlignment(Qt.AlignCenter)
        self.insignia_ia.setFixedSize(14, 14)
        self.insignia_ia.move(24, 2)
        self.insignia_ia.hide()
        return riel

    def _menus_riel(self) -> dict[str, QMenu]:
        def menu(*items) -> QMenu:
            m = QMenu(self)
            for a in items:
                if a is None:
                    m.addSeparator()
                elif isinstance(a, QMenu):
                    m.addMenu(a)
                else:
                    m.addAction(a)
            return m

        self.menu_recientes = QMenu("Abrir reciente", self)
        self.menu_recientes.aboutToShow.connect(self._llenar_recientes)
        modelo = QMenu(self)
        modelo.addAction(self.a_plantas)
        modelo.addSeparator()
        for lista, (titulo, _cols) in LISTAS.items():
            modelo.addAction(titulo, lambda l=lista: self.mostrar_tabla(l))
        modelo.addSeparator()
        modelo.addAction(self.a_revision)
        modelo.addAction(self.a_configuracion)
        return {
            "archivo": menu(
                self.a_nuevo,
                self.a_nuevo_portico,
                self.a_abrir,
                self.menu_recientes,
                self.a_ejemplo,
                None,
                self.a_importar_dxf,
                None,
                self.a_guardar,
                self.a_guardar_como,
                None,
                self.a_memoria,
                None,
                self.a_configuracion,
                None,
                self.a_salir,
            ),
            "editar": menu(self.a_deshacer, self.a_rehacer),
            "modelo": modelo,
            "calcular": menu(self.a_calcular, self.a_dinamica, self.a_disenar),
            "ver": menu(
                self.a_planta,
                self.a_vista2d,
                self.a_vista3d,
                None,
                *self.a_diagramas.values(),
                None,
                self._menu_paneles(),
            ),
            "herramientas": menu(self.a_buscar, self.a_consola),
            "ayuda": menu(self.a_codigo, self.a_informar, None, self.a_acerca),
        }

    def _iconos_riel(self) -> None:
        self._iconos_dibujo()
        for dock in getattr(self, "paneles", {}).values():
            dock.titleBarWidget().actualizar_iconos()
        # Ícono del gestor de plantas: tres losas apiladas, con el color del tema.
        self.b_plantas.setIcon(
            QIcon(icono_trazo(ICONO_PLANTAS, estilo.TEXTO_2, 20, self.devicePixelRatioF()))
        )
        cargas = QIcon(icono_trazo(ICONO_CARGAS, estilo.TEXTO_2, 18, self.devicePixelRatioF()))
        cargas.addPixmap(
            icono_trazo(ICONO_CARGAS, estilo.ACENTO, 18, self.devicePixelRatioF()),
            QIcon.Normal,
            QIcon.On,
        )
        self.b_cargas.setIcon(cargas)
        for boton, cuerpo in ((self.b_subir, ICONO_SUBIR), (self.b_bajar, ICONO_BAJAR)):
            icono = QIcon(icono_trazo(cuerpo, estilo.TEXTO_2, 18, self.devicePixelRatioF()))
            icono.addPixmap(
                icono_trazo(cuerpo, estilo.TEXTO_3, 18, self.devicePixelRatioF()), QIcon.Disabled
            )
            boton.setIcon(icono)
        rutas = estilo.iconos_menu(estilo.actual)
        for clave, b in self.botones_riel.items():
            icono_b = QIcon()
            icono_b.addFile(rutas[clave], QSize(), QIcon.Normal, QIcon.Off)
            icono_b.addFile(rutas[clave + "_activo"], QSize(), QIcon.Normal, QIcon.On)
            b.setIcon(icono_b)

    def abrir_menu_riel(self, clave: str) -> None:
        """Abre el menú de ese ícono a su derecha; *Preferencias* abre su ventana."""
        b = self.botones_riel[clave]
        if clave == "ia":
            self.mostrar_asistente(not self.asistente.isVisible())
            return
        if clave == "preferencias":
            b.setChecked(False)
            self.abrir_preferencias()
            return
        menu = self.menus_riel[clave]
        b.setChecked(True)
        menu.popup(b.mapToGlobal(QPoint(b.width() + 8, 0)))

    def _llenar_recientes(self) -> None:
        self.menu_recientes.clear()
        rutas = ajustes.recientes()
        for ruta in rutas:
            a = self.menu_recientes.addAction(Path(ruta).name)
            a.triggered.connect(lambda _=False, r=ruta: self.abrir_reciente(r))
            a.setToolTip(ruta)
        if not rutas:
            self.menu_recientes.addAction("Todavía no hay proyectos recientes").setEnabled(False)

    def _selector_vista(self) -> QWidget:
        """Vista: Planta | 3D en un edificio, Frente | 3D en un pórtico plano (y
        Paralela | Perspectiva en 3D). Es el primer control del visor."""
        self.selector_vista = QWidget()
        capa = QHBoxLayout(self.selector_vista)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(10)
        # Visor único: la vista de frente (plana, con dibujo y enganche) y la 3D son
        # dos formas de mirar el mismo modelo (docs/diseno-interfaz.md, Visor).
        capa.addWidget(QLabel("Vista", objectName="tenue"))
        vistas = QWidget(objectName="grupo")
        v = QHBoxLayout(vistas)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)
        self.grupo_vistas = QButtonGroup(self)
        self.botones_vista: dict[str, QToolButton] = {}
        for nombre, texto, icono, ayuda in (
            ("planta", "Planta", "vista_planta", "Planta del edificio: se dibuja piso por piso"),
            ("frente", "Frente", "vista_alzado", "Vista de frente: se dibuja y se engancha"),
            ("3d", "3D", "vista_3d", "Vista 3D: arrastrar con el botón derecho gira"),
        ):
            b = QToolButton(objectName="segmento", checkable=True)
            b.setText(texto)
            b.setProperty("icono", icono)
            b.setIconSize(QSize(16, 16))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setToolTip(ayuda)
            b.clicked.connect(lambda _=False, n=nombre: self.mostrar_vista(n))
            self.grupo_vistas.addButton(b)
            self.botones_vista[nombre] = b
            v.addWidget(b)
        self.botones_vista["frente"].setChecked(True)
        capa.addWidget(vistas)
        # Paralela o perspectiva: solo en la vista 3D.
        self.grupo_proyeccion = QWidget(objectName="grupo")
        g = QHBoxLayout(self.grupo_proyeccion)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        proyeccion = QButtonGroup(self)
        self.botones_proyeccion: dict[str, QPushButton] = {}
        for clave, texto in (("paralela", "Paralela"), ("perspectiva", "Perspectiva")):
            b = QPushButton(texto, objectName="segmento", checkable=True)
            b.clicked.connect(lambda _=False, c=clave: self.elegir_proyeccion(c))
            proyeccion.addButton(b)
            self.botones_proyeccion[clave] = b
            g.addWidget(b)
        self.botones_proyeccion["paralela"].setChecked(True)
        self.grupo_proyeccion.hide()
        capa.addWidget(self.grupo_proyeccion)
        return self.selector_vista

    def _barra_contextual(self) -> QWidget:
        barra = QWidget(objectName="contexto")
        capa = QHBoxLayout(barra)
        capa.setContentsMargins(12, 5, 12, 5)
        capa.setSpacing(10)
        # Sin selector Edificio | Cálculo: el proyecto dice qué es (edificio o pórtico
        # plano) y el modelo de cálculo del edificio se genera solo (#74).
        capa.addWidget(self._selector_vista())
        # Controles del modo Edificio: planta que se ve, ▲▼ y el gestor de plantas.
        self.ctx_edificio = QWidget()
        e = QHBoxLayout(self.ctx_edificio)
        e.setContentsMargins(0, 0, 0, 0)
        e.setSpacing(6)
        e.addWidget(QLabel("Planta", objectName="tenue"))
        self.combo_planta = QComboBox()
        self.combo_planta.setMinimumWidth(190)
        self.combo_planta.activated.connect(
            lambda i: self.edificio.ir_a_piso(self.combo_planta.itemData(i))
        )
        e.addWidget(self.combo_planta)
        self.b_plantas = QToolButton()
        self.b_plantas.setToolTip("Plantas: agregar, editar, quitar y copiar")
        self.b_plantas.setAccessibleName("Plantas")
        self.b_plantas.setIconSize(QSize(20, 20))
        self.b_plantas.clicked.connect(self.gestionar_plantas)
        e.addWidget(self.b_plantas)
        # Chevrones en un grupo, como los demás segmentos de la barra (26/11/2026).
        flechas = QWidget(objectName="grupo")
        f = QHBoxLayout(flechas)
        f.setContentsMargins(2, 2, 2, 2)
        f.setSpacing(2)
        self.b_subir = QToolButton(objectName="segmento")
        self.b_subir.setToolTip("Subir una planta (Re Pág)")
        self.b_subir.setAccessibleName("Subir una planta")
        self.b_subir.clicked.connect(lambda: self.subir_planta(1))
        self.b_bajar = QToolButton(objectName="segmento")
        self.b_bajar.setToolTip("Bajar una planta (Av Pág)")
        self.b_bajar.setAccessibleName("Bajar una planta")
        self.b_bajar.clicked.connect(lambda: self.subir_planta(-1))
        for b in (self.b_subir, self.b_bajar):
            b.setIconSize(QSize(18, 18))
            f.addWidget(b)
        e.addWidget(flechas)
        e.addSpacing(8)
        # Cargas por planta (#78): las cargas de las losas y su reparto a las vigas.
        cargas = QWidget(objectName="grupo")
        c = QHBoxLayout(cargas)
        c.setContentsMargins(2, 2, 2, 2)
        c.setSpacing(2)
        self.b_cargas = QToolButton(objectName="segmento", checkable=True)
        self.b_cargas.setToolTip("Cargas: ver las cargas de las losas y su reparto a vigas y muros")
        self.b_cargas.setAccessibleName("Cargas")
        self.b_cargas.setIconSize(QSize(18, 18))
        self.b_cargas.toggled.connect(lambda v: self.edificio.mostrar_cargas(v))
        c.addWidget(self.b_cargas)
        e.addWidget(cargas)
        self.combo_caso = QComboBox()
        for clave, nombre in CASOS_VISTA.items():
            self.combo_caso.addItem(nombre, clave)
        self.combo_caso.activated.connect(
            lambda i: self.edificio.mostrar_cargas(True, self.combo_caso.itemData(i))
        )
        self.combo_caso.setVisible(False)
        self.b_cargas.toggled.connect(self.combo_caso.setVisible)
        e.addWidget(self.combo_caso)
        self.ctx_edificio.hide()
        capa.addWidget(self.ctx_edificio)

        self.ctx_calculo = QWidget()
        capa_calculo = capa
        capa = QHBoxLayout(self.ctx_calculo)
        capa.setContentsMargins(0, 0, 0, 0)
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
            b.clicked.connect(lambda _=False, c=clave: self.elegir_diagrama(c))
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
        capa_calculo.addWidget(self.ctx_calculo)
        capa_calculo.addStretch()
        return barra

    def _barra_dibujo(self, dibujo=None, herramientas=HERRAMIENTAS, enganches=ENGANCHES):
        """Herramientas de dibujo y enganches de un lienzo (``nervi.gui.dibujo``). Sin
        ``dibujo``, los de la planta del edificio."""
        calculo = dibujo is not None
        dibujo = dibujo or self.planta.dibujo
        barra = QWidget()
        # QBoxLayout: si la barra de dibujo se lleva a un costado, se pone vertical.
        capa = QBoxLayout(QBoxLayout.LeftToRight, barra)
        capa.setContentsMargins(8, 4, 8, 4)
        capa.setSpacing(6)
        capa.addWidget(QLabel("Dibujar", objectName="tenue"))
        grupo = QWidget(objectName="grupo")
        g = QBoxLayout(QBoxLayout.LeftToRight, grupo)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        botones_h: dict[str, QToolButton] = {}
        grupo_h = QButtonGroup(self)
        for clave, (icono_clave, nombre) in herramientas.items():
            b = QToolButton(objectName="segmento", checkable=True)
            b.setText("" if clave == "seleccionar" else nombre)
            b.setToolTip(nombre)
            b.setAccessibleName(nombre)
            b.setIconSize(QSize(18, 18))
            b.setToolButtonStyle(
                Qt.ToolButtonIconOnly if clave == "seleccionar" else Qt.ToolButtonTextBesideIcon
            )
            b.setProperty("icono", icono_clave)
            b.clicked.connect(
                lambda _=False, c=clave, d=dibujo: self.elegir_herramienta(
                    c, d is not self.planta.dibujo
                )
            )
            grupo_h.addButton(b)
            botones_h[clave] = b
            g.addWidget(b)
        capa.addWidget(grupo)
        capa.addSpacing(6)
        capa.addWidget(QLabel("Enganche", objectName="tenue"))
        grupo_e = QWidget(objectName="grupo")
        ge = QBoxLayout(QBoxLayout.LeftToRight, grupo_e)
        ge.setContentsMargins(2, 2, 2, 2)
        ge.setSpacing(2)
        botones_e: dict[str, QPushButton] = {}
        for clave, nombre in enganches.items():
            texto = f"{nombre} {PASO_GRILLA_M:.2f}" if clave == "grilla" else nombre
            b = QPushButton(texto, objectName="segmento", checkable=True)
            b.setChecked(dibujo.opciones.enganches[clave])
            b.toggled.connect(lambda v, c=clave, d=dibujo: d.poner_enganche(c, v))
            botones_e[clave] = b
            ge.addWidget(b)
        capa.addWidget(grupo_e)
        barra.setProperty("capas", [capa, g, ge])
        if calculo:
            self.botones_herramienta_calculo, self.botones_enganche_calculo = botones_h, botones_e
        else:
            self.botones_herramienta, self.botones_enganche = botones_h, botones_e
        dibujo.cambiado.connect(self._actualizar_dibujo)
        return barra

    def _dibujos(self):
        """(dibujo, botones de herramientas, botones de enganche) de cada lienzo."""
        salida = [(self.planta.dibujo, self.botones_herramienta, self.botones_enganche)]
        if hasattr(self, "botones_herramienta_calculo"):
            salida.append(
                (self.vista.dibujo, self.botones_herramienta_calculo, self.botones_enganche_calculo)
            )
        return salida

    def elegir_herramienta(self, clave: str, calculo: bool = False) -> None:
        """Elige una herramienta de dibujo de la planta del edificio o, con ``calculo``,
        de la vista 2D (pasa al modo y a la vista que corresponde)."""
        modo = "calculo" if calculo else "edificio"
        if self.modo != modo:
            self.elegir_modo(modo)
        if calculo:
            self.mostrar_vista("2D")
            self.vista.dibujo.elegir(clave)
            self.vista.setFocus()
        else:
            self.planta.dibujo.elegir(clave)
            self.planta.setFocus()

    def alternar_orto(self) -> None:
        """F8: Orto del lienzo del modo que se ve."""
        botones = self.botones_enganche_calculo if self.modo == "calculo" else self.botones_enganche
        botones["orto"].toggle()

    def _actualizar_dibujo(self) -> None:
        for dibujo, botones_h, botones_e in self._dibujos():
            botones_h[dibujo.herramienta].setChecked(True)
            for clave, b in botones_e.items():
                b.blockSignals(True)
                b.setChecked(dibujo.opciones.enganches[clave])
                b.blockSignals(False)
        if not hasattr(self, "pila_prop"):
            return
        if self.modo == "edificio":
            self.pila_prop.setCurrentWidget(
                self.panel_herramienta if self.planta.dibujo.activo else self.prop_edificio
            )
        else:
            self.pila_prop.setCurrentWidget(
                self.panel_calculo if self.vista.dibujo.activo else self.pila_prop.widget(0)
            )

    def _iconos_dibujo(self) -> None:
        for b in self.botones_vista.values():
            b.setIcon(
                iconos.qicon(b.property("icono"), estilo.actual, 16, self.devicePixelRatioF())
            )
        for _dibujo, botones_h, _ in self._dibujos():
            for b in botones_h.values():
                b.setIcon(
                    iconos.qicon(b.property("icono"), estilo.actual, 18, self.devicePixelRatioF())
                )

    def _explorador(self) -> QWidget:
        panel = QWidget(objectName="panel")
        capa = QVBoxLayout(panel)
        capa.setContentsMargins(0, 10, 0, 8)
        capa.setSpacing(6)
        self.arbol = ArbolModelo()
        self.arbol.elegido.connect(self._item_explorador)
        self.arbol_edificio = ArbolModelo()
        self.arbol_edificio.elegido.connect(self._item_explorador)
        self.pila_arbol = QStackedWidget()
        self.pila_arbol.addWidget(self.arbol)
        self.pila_arbol.addWidget(self.arbol_edificio)
        capa.addWidget(self.pila_arbol)
        panel.setMinimumWidth(240)
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
        self.lbl_dis = QLabel("DISEÑO · ACI 318-19 (experimental)", objectName="seccion")
        self.form_dis = QFormLayout()
        self.form_dis.setVerticalSpacing(6)
        for w in (self.lbl_tipo_sel, self.lbl_sel):
            self.capa_prop.addWidget(w)
        self.capa_prop.addLayout(self.form)
        self.capa_prop.addSpacing(6)
        self.capa_prop.addWidget(self.lbl_res)
        self.capa_prop.addLayout(self.form_res)
        self.capa_prop.addSpacing(6)
        self.capa_prop.addWidget(self.lbl_dis)
        self.capa_prop.addLayout(self.form_dis)
        self.capa_prop.addStretch()
        panel.setMinimumWidth(240)
        self.prop_edificio = PropiedadesEdificio(self.edificio)
        self.pila_prop = QStackedWidget()
        self.pila_prop.addWidget(panel)
        self.pila_prop.addWidget(self.prop_edificio)
        self.panel_herramienta = PanelHerramienta(self.planta.dibujo)
        self.pila_prop.addWidget(self.panel_herramienta)
        self.panel_calculo = PanelCalculo(self.vista.dibujo)
        self.pila_prop.addWidget(self.panel_calculo)
        self._actualizar_dibujo()
        return self.pila_prop

    def _panel_inferior(self) -> QTabWidget:
        """Panel inferior sin pestañas de primer nivel: la etapa elegida arriba
        (Geometría › Cargas › Análisis › Resultados › Diseño) dice qué se ve, y solo
        quedan las pestañas de esa etapa (``docs/diseno-interfaz.md`` §Etapas)."""
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().hide()
        # Geometría y Cargas del pórtico plano: las tablas de modelo.json.
        self.tabs_modelo = QTabWidget()
        self.tabs_modelo.setDocumentMode(True)
        for lista, (titulo, _cols) in LISTAS.items():
            self.tabs_modelo.addTab(EditorLista(self.sesion, lista), titulo)
        tabs.addTab(self.tabs_modelo, "Modelo")
        # Geometría y Cargas del edificio: las tablas del modelo físico.
        self.tablas_edificio = TablasEdificio(self.edificio)
        self.tablas_edificio.setDocumentMode(True)
        tabs.addTab(self.tablas_edificio, "Edificio")

        # Análisis: Revisión · Modelo de cálculo (edificio) · Dinámica (pórtico).
        self.tabs_analisis = QTabWidget()
        self.tabs_analisis.setDocumentMode(True)
        self.revision = QListWidget()
        self.tabs_analisis.addTab(self.revision, "Revisión")
        self.panel_modelo_calculo = PanelModeloCalculo(self.sesion)
        self.tabs_analisis.addTab(self.panel_modelo_calculo, "Modelo de cálculo")
        self.panel_dinamica = PanelDinamica(self.sesion)
        self.panel_dinamica.resultado_elegido.connect(self.ver_resultado_dinamica)
        self.panel_dinamica.animar.connect(self.animar_modo)
        self.tabs_analisis.addTab(self.panel_dinamica, "Dinámica")
        tabs.addTab(self.tabs_analisis, "Análisis")
        self._reloj = QTimer(self)
        self._reloj.setInterval(40)
        self._reloj.timeout.connect(self._cuadro_animacion)
        self._tiempo = QElapsedTimer()

        # Resultados del pórtico plano y del edificio.
        self.tabs_res = QTabWidget()
        self.tabs_res.setDocumentMode(True)
        for tipo, titulo in (
            ("reacciones", "Reacciones"),
            ("fuerzas_extremo", "Fuerzas de extremo"),
            ("desplazamientos", "Desplazamientos"),
        ):
            self.tabs_res.addTab(vista_tabla(TablaResultados(self.sesion, tipo)), titulo)
        tabs.addTab(self.tabs_res, "Resultados")
        self.res_edificio = PanelResultadosEdificio(self.sesion)
        self.res_edificio.elemento_elegido.connect(lambda l, i: self.edificio.elegir(l, i))
        tabs.addTab(self.res_edificio, "Resultados del edificio")

        self.panel_diseno = PanelDiseno(self.sesion)
        self.panel_diseno.disenado.connect(lambda: self.ir_a_etapa(4))
        tabs.addTab(self.panel_diseno, "Diseño")
        self.diseno_edificio = QLabel(
            "El diseño de las vigas y columnas del edificio llega en una próxima versión. "
            "Mientras tanto, el diseño según ACI 318-19 trabaja sobre los pórticos planos.",
            objectName="tenue",
        )
        self.diseno_edificio.setWordWrap(True)
        self.diseno_edificio.setAlignment(Qt.AlignCenter)
        tabs.addTab(self.diseno_edificio, "Diseño del edificio")

        # La consola no es de ninguna etapa: es un panel propio, desde Herramientas.
        self.consola = Consola(self.sesion)
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
            "El diseño de vigas y columnas según ACI 318-19 es experimental y no fue revisado "
            "por un ingeniero estructural."
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
        if self.modo == "edificio":
            self._actualizar_etapas_edificio()
            return
        m = self.sesion.modelo
        listos = (
            bool(m["nudos"] and m["barras"] and m.get("apoyos")),
            bool(m["casos"]),
            self.sesion.al_dia,
            self.sesion.al_dia,
            self.sesion.diseno_al_dia,
        )
        for b, listo, nombre in zip(self.botones_etapa, listos, ETAPAS, strict=False):
            b.setText(f"✓ {nombre}" if listo else nombre)
        u = m["unidades"]
        self.lbl_unidades.setText(f"{u['fuerza']} · {u['longitud']}")
        n, b = len(m["nudos"]), len(m["barras"])
        self.lbl_tamano.setText(f"{n} nudos · {b} barras · {3 * n} GDL")

    def _actualizar_etapas_edificio(self) -> None:
        """✓ en las etapas del edificio: Geometría con elementos, Cargas con losas
        cargadas, Análisis y Resultados con el cálculo al día."""
        s = self.sesion
        mf = self.edificio.modelo()
        # Las losas siempre cargan su peso propio.
        cargas = bool(mf.lista("losas"))
        listos = (len(mf) > 0, cargas, s.edificio_al_dia, s.edificio_al_dia, False)
        for b, listo, nombre in zip(self.botones_etapa, listos, ETAPAS, strict=False):
            b.setText(f"✓ {nombre}" if listo else nombre)

    def _actualizar_explorador(self) -> None:
        m = self.sesion.modelo
        try:
            elementos = proyecto.elementos(m, self.sesion.diseno)
        except (KeyError, ValueError, ZeroDivisionError):
            elementos = None  # sección sin A o I válidos: el árbol muestra solo los nudos
        self.arbol.mostrar(m, elementos)
        self._marcar_arbol()
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
        if self.modo == "edificio":
            al_dia, hay = s.edificio_al_dia, s.resultados_edificio is not None
            vacio = not s.es_edificio or len(self.edificio.modelo()) == 0
        else:
            al_dia, hay = s.al_dia, s.resultados is not None
            vacio = not s.modelo["barras"]
        if vacio:
            estado = "Modelo vacío"
        elif al_dia:
            estado = "● Resultados al día"
        elif hay:
            estado = "● Resultados desactualizados: calculá de nuevo (F5)"
        else:
            estado = "Sin calcular"
        self.lbl_estado.setText(estado)
        color = estilo.OK if al_dia else estilo.NEGATIVO if hay else estilo.TEXTO_2
        self.lbl_estado.setStyleSheet(f"color: {color};")
        self._actualizar_etapas()
        self._actualizar_revision()
        self._actualizar_propiedades()

    def _actualizar_diseno(self) -> None:
        s = self.sesion
        en_diseno = self.etapas.checkedId() == 4
        self.vista.colores_barra = (
            {r.elemento.barra: color_estado(r.estado) for r in s.resultados_diseno or []}
            if en_diseno and s.diseno_al_dia
            else {}
        )
        self.vista.update()
        self._actualizar_etapas()
        self._actualizar_propiedades()

    def _propiedades_diseno(self, barra: int) -> None:
        r = self.sesion.resultado_diseno(barra)
        if r is None:
            return
        self.lbl_dis.setVisible(True)
        el = r.elemento
        self.form_dis.addRow("Elemento", _valor(f"{el.tipo.capitalize()} {el.b:g} × {el.h:g} mm"))
        for nombre, texto in r.armadura.items():
            self.form_dis.addRow(nombre, _valor(texto))
        rel = r.relacion
        if rel is not None:
            color = estilo.OK if r.estado == "cumple" else estilo.NEGATIVO
            lbl = _valor(f"{rel:.2f} · {r.estado}")
            lbl.setStyleSheet(f"color: {color};")
            self.form_dis.addRow("Relación máx.", lbl)
        for m in r.mensajes:
            self.form_dis.addRow(_tenue(m))

    def _actualizar_propiedades(self) -> None:
        for form in (self.form, self.form_res, self.form_dis):
            while form.rowCount():
                form.removeRow(0)
        sel = self.sesion.seleccion
        m = self.sesion.modelo
        u = m["unidades"]
        f, l = u["fuerza"], u["longitud"]
        self.lbl_res.setVisible(False)
        self.lbl_dis.setVisible(False)
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
        self._propiedades_diseno(barra["id"])

    def _marcar_diagrama(self, clave: str) -> None:
        self.botones_diagrama[clave].setChecked(True)

    def _valores(self, activo: bool) -> None:
        self.vista.mostrar_valores = activo
        self.vista.update()
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.mostrar_valores = activo
            self.vista3d.actualizar()

    def elegir_diagrama(self, clave: str) -> None:
        """Mismo diagrama en la vista 2D y en la 3D."""
        self.vista.elegir_diagrama(clave)
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.elegir_diagrama(clave)

    def _vista3d(self) -> QWidget:
        """El visor 3D, creado la primera vez (VTK tarda en arrancar)."""
        if self.vista3d is None:
            self.vista3d = vista3d.crear(self.sesion)
            if isinstance(self.vista3d, Vista3D):
                self.vista3d.mostrar_valores = self.vista.mostrar_valores
                self.vista3d.elegir_diagrama(self.vista.diagrama)
                self.vista3d.perspectiva = self.botones_proyeccion["perspectiva"].isChecked()
                self.vista3d.vista_pedida.connect(self._vista_desde_brujula)
                self.vista3d.barra_pulsada.connect(self._barra_del_edificio)
                self.vista3d.botones_navegacion.actualizar_iconos()
                self.vista3d.mostrar_edificio(self.modo == "edificio")
                self._resaltar_en_3d()
            self.vistas.addWidget(self.vista3d)
        return self.vista3d

    def _camara_de_frente(self):
        """La cámara 3D que muestra exactamente lo que muestra la vista de frente."""
        v = self.vista.vista_actual()
        if v is None:
            return None
        return camara3d.Camara3D.de_frente(v.escala, v.cx, v.cy)

    def vista_visible(self) -> str:
        """``"planta"``, ``"frente"`` o ``"3d"``: la vista que se ve."""
        for nombre in ("3d", "planta"):
            if self.botones_vista[nombre].isChecked():
                return nombre
        return "frente"

    def mostrar_vista(self, nombre: str, animar: bool = True) -> None:
        """Muestra la vista ``"planta"`` (edificio), ``"frente"`` (pórtico plano) o
        ``"3d"`` en el centro de la ventana.

        Es un solo visor: en el pórtico, al pasar de frente a 3D y volver, la cámara se
        mueve con una transición corta desde donde se lo miraba de frente."""
        nombre = ALIAS_VISTAS.get(nombre, nombre)
        edificio = self.modo == "edificio"
        # Un edificio se mira en planta o en 3D; un pórtico plano, de frente o en 3D.
        if nombre in ("planta", "frente"):
            nombre = "planta" if edificio else "frente"
        actual = self.vistas.currentWidget()
        # El diagrama y la combinación son de los resultados: no van en la planta.
        self.ctx_calculo.setVisible(not edificio or nombre == "3d")
        if nombre == "planta":
            self.vistas.setCurrentWidget(self.planta)
        elif edificio:
            if self.planta.dibujo.activo:
                self.planta.dibujo.elegir("seleccionar")
            w = self._vista3d()
            self.vistas.setCurrentWidget(w)
        elif nombre == "3d":
            # Se dibuja en la vista de frente: al pasar a 3D se vuelve a Seleccionar.
            if self.vista.dibujo.activo:
                self.vista.dibujo.elegir("seleccionar")
            w = self._vista3d()
            if isinstance(w, Vista3D) and actual is not w:
                frente = self._camara_de_frente()
                if frente is not None:
                    w.poner(replace(frente, perspectiva=w.perspectiva))
                self.vistas.setCurrentWidget(w)
                if animar and w.escena is not None and w.escena.barras:
                    w.ir_a("isometrica")
            else:
                self.vistas.setCurrentWidget(w)
        else:
            w = self.vista3d
            frente = self._camara_de_frente()
            if isinstance(w, Vista3D) and actual is w and animar and frente is not None:
                w.animar_a(
                    replace(frente, perspectiva=False),
                    lambda: self.vistas.setCurrentWidget(self.vista),
                )
            else:
                self.vistas.setCurrentWidget(self.vista)
        self.botones_vista[nombre].setChecked(True)
        self.grupo_proyeccion.setVisible(nombre == "3d")

    def elegir_proyeccion(self, clave: str) -> None:
        """``"paralela"`` o ``"perspectiva"`` en la vista 3D."""
        self.botones_proyeccion[clave].setChecked(True)
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.elegir_perspectiva(clave == "perspectiva")

    def _barra_del_edificio(self, barra) -> None:
        """Clic en una barra del edificio en 3D: elige el elemento del que sale."""
        if barra is None or not self.sesion.es_edificio:
            self.edificio.elegir(None)
            return
        o = self.sesion.modelo_calculo().origenes[barra]
        self.edificio.elegir(o.lista, o.id)

    def _resaltar_en_3d(self) -> None:
        """Resalta en 3D las barras del elemento elegido del edificio."""
        if not isinstance(self.vista3d, Vista3D):
            return
        barras: list[int] = []
        eleccion = self.edificio.eleccion
        if eleccion is not None and eleccion[0] in ("columnas", "vigas", "muros"):
            try:
                barras = self.sesion.modelo_calculo().barras_de(*eleccion)
            except (ValueError, KeyError):
                barras = []
        self.vista3d.resaltar(barras)

    def _vista_desde_brujula(self, extremo: str) -> None:
        """Clic en la brújula: de frente (``-Y``) es la vista plana del pórtico; las
        demás, y todas en un edificio, la 3D."""
        if extremo == "-Y" and self.modo != "edificio":
            self.mostrar_vista("frente")
            return
        self.mostrar_vista("3d", animar=False)
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.ir_a(extremo)

    def _girar_desde_frente(self, pos: QPointF, x: float, y: float) -> None:
        """Arrastre con el botón derecho en la vista de frente: pasa a 3D sin saltos y
        gira alrededor del punto donde empezó el arrastre."""
        self.mostrar_vista("3d", animar=False)
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.empezar_giro(pos, (x, 0.0, y))

    def _seguir_giro(self, dx: float, dy: float) -> None:
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.girar(dx, dy)

    def _terminar_giro(self) -> None:
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.terminar_arrastre()

    def _item_explorador(self, tipo: str, valor) -> None:
        if tipo == "edificio":
            self.edificio.elegir(*valor)
        elif tipo == "tabla_edificio":
            self.mostrar_tabla_edificio(valor)
        elif tipo in ("barra", "nudo"):
            self.sesion.seleccionar(Seleccion(tipo, valor))
        elif tipo == "tabla":
            self.mostrar_tabla(valor)
        elif tipo == "resultado":
            self.combo.setCurrentText(valor)

    def _marcar_arbol(self) -> None:
        """Resalta en el árbol la barra o el nudo elegido y el caso o la combinación que se ve."""
        sel = self.sesion.seleccion
        if sel is not None and sel.tipo in ("barra", "nudo"):
            clave = "barras" if sel.tipo == "barra" else "nudos"
            self.arbol.marcar(clave, f"{sel.tipo[0].upper()}{sel.id}")
        else:
            self.arbol.marcar(None, None)
        nombre = self.sesion.combinacion
        casos = {c["nombre"] for c in self.sesion.modelo["casos"]}
        self.arbol.marcar_activo("cargas" if nombre in casos else "combinaciones", nombre)

    def mostrar_tabla(self, lista: str) -> None:
        """Tabla ``lista`` del pórtico plano, en la etapa que le toca (Geometría o
        Cargas)."""
        self.botones_etapa[1 if lista in LISTAS_CARGAS else 0].setChecked(True)
        self._mostrar_etapa(self.etapas.checkedId())
        self.tabs_modelo.setCurrentIndex(list(LISTAS).index(lista))

    # --- Modelo físico del edificio (#73) ------------------------------------------
    def _modo_del_proyecto(self) -> None:
        """Edificio si el proyecto tiene modelo físico; si no, pórtico plano. No hay
        selector: el edificio manda y su modelo de cálculo se genera solo (#74)."""
        self.elegir_modo("edificio" if self.sesion.es_edificio else "calculo")

    def elegir_modo(self, modo: str) -> None:
        """Pone la ventana para un edificio (``"edificio"``) o para un pórtico plano
        armado a mano (``"calculo"``). Lo decide el proyecto
        (:meth:`_modo_del_proyecto`), no un control de la ventana."""
        self.modo = modo
        edificio = modo == "edificio"
        self.ctx_edificio.setVisible(edificio)
        self.botones_vista["planta"].setVisible(edificio)
        self.botones_vista["frente"].setVisible(not edificio)
        self.a_planta.setVisible(edificio)
        self.a_vista2d.setVisible(not edificio)
        self._accion_dibujo["edificio"].setVisible(edificio)
        self._accion_dibujo["calculo"].setVisible(not edificio)
        self.paneles["estructura"].setWindowTitle("Edificio" if edificio else "Estructura")
        self.pila_arbol.setCurrentWidget(self.arbol_edificio if edificio else self.arbol)
        self._actualizar_dibujo()
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.mostrar_edificio(edificio)
        if self.vista_visible() == "3d":
            self.mostrar_vista("3d", animar=False)
        else:
            self.mostrar_vista("planta" if edificio else "frente", animar=False)
        # Re Pág y Av Pág cambian de planta solo en un edificio; en un pórtico son de
        # las tablas.
        self.a_subir.setEnabled(edificio)
        self.a_bajar.setEnabled(edificio)
        self._actualizar_edificio()
        self._actualizar_resultados()
        self._mostrar_etapa(max(self.etapas.checkedId(), 0))

    def subir_planta(self, pasos: int) -> None:
        """▲ (``pasos`` = 1) o ▼ (``pasos`` = -1): la planta de arriba o la de abajo."""
        if self.modo == "edificio":
            self.edificio.subir(pasos)

    def gestionar_plantas(self) -> GestorPlantas:
        """Abre el gestor de plantas (no modal: lo aplica *Aceptar*)."""
        if self.modo != "edificio":
            self.elegir_modo("edificio")
        dialogo = GestorPlantas(self.edificio, self)
        dialogo.setAttribute(Qt.WA_DeleteOnClose)
        dialogo.show()
        self._gestor_plantas = dialogo
        return dialogo

    def mostrar_tabla_edificio(self, lista: str) -> None:
        if self.etapas.checkedId() not in (0, 1):
            self.botones_etapa[0].setChecked(True)
            self._mostrar_etapa(0)
        self.tablas_edificio.mostrar(lista)

    def _actualizar_edificio(self) -> None:
        """Árbol, selector de planta, ▲▼ y barra de estado del modo Edificio."""
        est = self.edificio
        mf = est.modelo()
        if est.eleccion is not None:
            # La sección del elemento elegido se abre para que se vea marcado.
            lista = est.eleccion[0]
            self.arbol_edificio.abiertas.add(lista if lista != "secciones" else "materiales")
        self.arbol_edificio.mostrar_filas(filas_arbol(mf, est.piso))
        if est.eleccion is not None:
            lista, id = est.eleccion
            clave = lista if lista != "secciones" else "materiales"
            self.arbol_edificio.marcar(clave, nombre_elemento(lista, mf.elemento(lista, id)))
        elif est.piso is not None:
            self.arbol_edificio.marcar("pisos", mf.elemento("pisos", est.piso)["nombre"])
        else:
            self.arbol_edificio.marcar(None, None)
        self.combo_planta.blockSignals(True)
        self.combo_planta.clear()
        for p in reversed(mf.pisos_ordenados()):
            self.combo_planta.addItem(f"{p['nombre']} · {p['nivel']:+.2f} {mf.longitud}", p["id"])
        if est.piso is not None:
            self.combo_planta.setCurrentIndex(self.combo_planta.findData(est.piso))
        self.combo_planta.blockSignals(False)
        self.b_subir.setEnabled(est.puede(1))
        self.b_bajar.setEnabled(est.puede(-1))
        if self.modo == "edificio":
            n = {k: len(mf.lista(k)) for k in ("pisos", "columnas", "vigas", "losas", "muros")}
            self.lbl_unidades.setText(f"{mf.longitud} · mm · MPa")
            texto = (
                f"{n['pisos']} pisos · {n['columnas']} columnas · {n['vigas']} vigas · "
                f"{n['losas']} losas · {n['muros']} muros"
            )
            if self.sesion.es_edificio and len(mf):
                try:
                    mc = self.sesion.modelo_calculo()
                    texto += f"  →  {len(mc.nudos)} nudos · {mc.n_barras} barras"
                except (ValueError, KeyError):
                    pass
            self.lbl_tamano.setText(texto)

    def ir_a_etapa(self, n: int) -> None:
        """Etapa ``n`` (0 Geometría … 4 Diseño): qué se ve en el panel inferior y,
        en Geometría y Cargas, qué tabla."""
        self.botones_etapa[n].setChecked(True)
        edificio = self.modo == "edificio"
        if n == 0:
            if edificio:
                self.tablas_edificio.mostrar("pisos")
            else:
                self.tabs_modelo.setCurrentIndex(list(LISTAS).index("nudos"))
        elif n == 1:
            if edificio:
                self.tablas_edificio.mostrar("losas")
            else:
                self.tabs_modelo.setCurrentIndex(list(LISTAS).index("cargas_barra"))
        elif n == 2:
            self.tabs_analisis.setCurrentWidget(self.revision)
        self._mostrar_etapa(n)
        if n == 4 and not edificio:
            # La tabla de diseño necesita más alto que las tablas del modelo.
            self._agrandar_panel_inferior()
        self._actualizar_diseno()

    def _mostrar_etapa(self, n: int) -> None:
        """Muestra en el panel inferior la página de la etapa ``n`` y solo sus pestañas."""
        edificio = self.modo == "edificio"
        tabs = self.panel_inferior
        if n in (0, 1):
            pagina = self.tablas_edificio if edificio else self.tabs_modelo
        elif n == 2:
            pagina = self.tabs_analisis
        elif n == 3:
            pagina = self.res_edificio if edificio else self.tabs_res
        else:
            pagina = self.diseno_edificio if edificio else self.panel_diseno
        tabs.setCurrentWidget(pagina)
        # Pórtico: Geometría y Cargas reparten las tablas de modelo.json.
        if pagina is self.tabs_modelo:
            cargas = n == 1
            for k, lista in enumerate(LISTAS):
                self.tabs_modelo.setTabVisible(k, (lista in LISTAS_CARGAS) == cargas)
        # Análisis: el modelo de cálculo es del edificio; la dinámica, del pórtico.
        a = self.tabs_analisis
        a.setTabVisible(a.indexOf(self.panel_modelo_calculo), edificio)
        a.setTabVisible(a.indexOf(self.panel_dinamica), not edificio)

    def mostrar_dinamica(self) -> None:
        """Análisis › Dinámica (del pórtico plano; la del edificio llega después)."""
        if self.modo == "edificio":
            self.statusBar().showMessage(
                "El análisis modal y espectral del edificio llega en una próxima versión",
                8000,
            )
            return
        self.ir_a_etapa(2)
        self.tabs_analisis.setCurrentWidget(self.panel_dinamica)
        self._agrandar_panel_inferior()

    def _agrandar_panel_inferior(self) -> None:
        """Lleva el panel de tablas y resultados al 45 % del alto, si está acoplado abajo
        y es más bajo (Diseño y Dinámica necesitan más alto que las tablas)."""
        dock = self.paneles["inferior"]
        if dock.isFloating() or self.dockWidgetArea(dock) != Qt.BottomDockWidgetArea:
            return
        alto = self.vistas.height() + dock.height()
        if dock.height() < 0.42 * alto:
            self.resizeDocks([dock], [alto - int(0.55 * alto)], Qt.Vertical)

    def analizar_dinamica(self) -> bool:
        """Va a la pestaña Dinámica y hace el análisis modal y espectral."""
        self.mostrar_dinamica()
        return self.panel_dinamica.analizar()

    def ver_resultado_dinamica(self, nombre: str) -> None:
        """Muestra un modo (su forma, como deformada) o un espectro (su momento)."""
        self.combo.setCurrentText(nombre)
        din = self.sesion.resultados_dinamica
        if din is not None and nombre in din.modos:
            self.elegir_diagrama("D")
        elif self.vista.diagrama == "D":
            self.elegir_diagrama("M")

    def animar_modo(self, activo: bool) -> None:
        if activo:
            self.elegir_diagrama("D")
            self._tiempo.start()
            self._reloj.start()
        else:
            self._reloj.stop()
            self.vista.fase = 1.0
            self.vista.update()

    def _cuadro_animacion(self) -> None:
        self.vista.fase = fase(self._tiempo.elapsed() / 1000.0)
        self.vista.update()

    def disenar(self) -> bool:
        """Va a la etapa Diseño y diseña todas las barras."""
        self.ir_a_etapa(4)
        return self.panel_diseno.disenar()

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

    def nuevo(self, edificio: bool = True) -> None:
        """*Nuevo edificio* (Ctrl+N): un proyecto con el modelo físico vacío, que se
        dibuja en planta. ``edificio=False``: *Nuevo pórtico plano*, armado a mano."""
        if self._seguir_si_hay_cambios():
            doc = formato.Documento.nuevo()
            if edificio:
                doc.fisico = formato.fisico.nuevo()
            self.sesion.nuevo(doc)
            self._modo_del_proyecto()
            self._encuadrar_vistas()
            self.ir_a_etapa(0)

    def _encuadrar_vistas(self) -> None:
        """Un proyecto nuevo o abierto se ve entero, sin el zoom del anterior."""
        self.vista.encuadrar()
        self.planta.encuadrar()

    def abrir_ejemplo(self) -> None:
        if self._seguir_si_hay_cambios():
            self.sesion.nuevo(documento_ejemplo())
            self._modo_del_proyecto()
            self._encuadrar_vistas()
            self.ir_a_etapa(0)

    def abrir_dialogo(self) -> None:
        if not self._seguir_si_hay_cambios():
            return
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", "Proyectos de Nervi (*.nrv)"
        )
        if ruta:
            self.abrir(ruta)

    def importar_dxf_dialogo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Importar DXF", "", "Dibujos DXF (*.dxf *.DXF)")
        if ruta:
            self.importar_dxf(ruta)

    def importar_dxf(self, ruta: str | Path):
        """Abre el diálogo de importación de un DXF. Devuelve el diálogo (o ``None``
        si el archivo no se pudo leer)."""
        from ..importar.dxf import DXFError
        from .importar import DialogoImportarDXF

        try:
            dialogo = DialogoImportarDXF(self.sesion, ruta, self)
        except (DXFError, OSError) as e:
            QMessageBox.warning(self, "No se pudo importar el DXF", str(e))
            return None
        dialogo.setAttribute(Qt.WA_DeleteOnClose)
        dialogo.open()
        return dialogo

    def abrir_reciente(self, ruta: str) -> bool:
        return self._seguir_si_hay_cambios() and self.abrir(ruta)

    def abrir(self, ruta: str | Path) -> bool:
        try:
            self.sesion.abrir(ruta)
        except (formato.FormatoError, OSError) as e:
            QMessageBox.warning(self, "No se pudo abrir el proyecto", str(e))
            return False
        ajustes.agregar_reciente(self.sesion.ruta)
        self._modo_del_proyecto()
        self._encuadrar_vistas()
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
        ajustes.agregar_reciente(self.sesion.ruta)
        return True

    # --- Deshacer y rehacer -------------------------------------------------------------
    def _actualizar_deshacer(self) -> None:
        s = self.sesion
        self.a_deshacer.setEnabled(s.puede_deshacer)
        self.a_rehacer.setEnabled(s.puede_rehacer)
        self.a_deshacer.setText(f"Deshacer: {s.que_deshacer}" if s.que_deshacer else "Deshacer")
        self.a_rehacer.setText(f"Rehacer: {s.que_rehacer}" if s.que_rehacer else "Rehacer")

    def deshacer(self) -> bool:
        cambio = self.sesion.deshacer()
        if cambio is not None:
            self.statusBar().showMessage(f"Deshecho: {cambio.descripcion}", 4000)
        return cambio is not None

    def rehacer(self) -> bool:
        cambio = self.sesion.rehacer()
        if cambio is not None:
            self.statusBar().showMessage(f"Rehecho: {cambio.descripcion}", 4000)
        return cambio is not None

    def exportar_resultados(self, ruta: str | Path | None = None) -> bool:
        """Calcula si hace falta y guarda todos los resultados sin redondear (JSON)."""
        if not self.sesion.al_dia and not self.calcular():
            return False
        if ruta is None:
            base = (
                self.sesion.ruta.with_suffix(".resultados.json").name
                if self.sesion.ruta
                else "resultados.json"
            )
            ruta, _ = QFileDialog.getSaveFileName(
                self, "Exportar resultados", base, "Resultados de Nervi (*.json)"
            )
            if not ruta:
                return False
        try:
            self.sesion.exportar_resultados(ruta)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "No se pudieron exportar los resultados", str(e))
            return False
        self.statusBar().showMessage(f"Resultados guardados en {ruta}", 6000)
        return True

    def exportar_memoria(self, ruta: str | Path | None = None) -> bool:
        """Calcula si hace falta y guarda la memoria de cálculo en PDF."""
        if not self.sesion.al_dia and not self.calcular():
            return False
        if ruta is None:
            base = self.sesion.ruta.with_suffix(".pdf").name if self.sesion.ruta else "memoria.pdf"
            ruta, _ = QFileDialog.getSaveFileName(
                self, "Exportar memoria de cálculo", base, "Documentos PDF (*.pdf)"
            )
            if not ruta:
                return False
        try:
            self.sesion.memoria().guardar_pdf(ruta)
        except ImportError as e:
            QMessageBox.warning(self, "Falta un componente", str(e))
            return False
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "No se pudo exportar la memoria", str(e))
            return False
        self.statusBar().showMessage(f"Memoria de cálculo guardada en {ruta}", 6000)
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
        self.mostrar_revision()
        self.statusBar().showMessage(texto, 8000)

    def entradas_paleta(self) -> list[Entrada]:
        entradas = [
            Entrada(a.text().replace("&", ""), "Comando", a.shortcut().toString(), a.trigger)
            for a in self.actions()
        ]
        for n, nombre in enumerate(ETAPAS[:5]):
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

    # --- Ajustes ------------------------------------------------------------------------
    def abrir_preferencias(self) -> Preferencias:
        dialogo = Preferencias(self)
        dialogo.aplicado.connect(lambda: self.elegir_tema(ajustes.leer(CLAVE_TEMA)))
        dialogo.open()
        return dialogo

    def configurar_proyecto(self, apartado: str | None = None) -> ConfiguracionProyecto:
        dialogo = ConfiguracionProyecto(self.sesion, self)
        if apartado:
            dialogo.elegir_apartado(apartado)
        dialogo.open()
        return dialogo

    def mostrar_consola(self) -> None:
        """Abre el panel de la consola Python (Herramientas › Consola Python)."""
        dock = self.paneles["consola"]
        dock.show()
        dock.raise_()
        self.consola.setFocus()

    def mostrar_revision(self) -> None:
        self.ir_a_etapa(2)
        self.tabs_analisis.setCurrentWidget(self.revision)

    def acerca_de(self) -> None:
        version = formato.contenedor._version_programa()
        QMessageBox.about(
            self,
            "Acerca de Nervi",
            f"<b>Nervi</b> {version}<br>Software libre de análisis y dimensionamiento "
            "estructural.<br><br>Licencia GPL-3.0-or-later. "
            f'<a href="{URL_REPOSITORIO}">{URL_REPOSITORIO}</a>',
        )

    def elegir_tema(self, clave: str) -> None:
        """Cambia entre el tema claro y el oscuro y lo recuerda para la próxima vez.
        Toma el tamaño de letra de las preferencias."""
        ajustes.guardar(CLAVE_TEMA, clave)
        estilo.aplicar(tema=ajustes.tema(clave))
        self.a_temas[clave].setChecked(True)
        self._iconos_riel()
        for lienzo in (self.vista, self.planta):
            lienzo.botones_navegacion.actualizar_iconos()
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.botones_navegacion.actualizar_iconos()
        self._actualizar_explorador()
        self._actualizar_resultados()
        self._actualizar_propiedades()
        self.vista.update()
        if self.botones_ventana is not None:
            self.botones_ventana.actualizar_iconos()
        if isinstance(self.vista3d, Vista3D):
            self.vista3d.actualizar()

    def mostrar_asistente(self, mostrar: bool = True) -> None:
        """Abre o cierra el panel del asistente de IA junto a la barra lateral."""
        dock = self.paneles["asistente"]
        if mostrar and not dock.isVisible():
            dock.show()
            if not dock.isFloating():
                self.resizeDocks([dock], [370], Qt.Horizontal)
            dock.raise_()
        elif not mostrar:
            dock.hide()
        self.botones_riel["ia"].setChecked(mostrar)

    def _actualizar_insignia(self, pendientes: int) -> None:
        self.insignia_ia.setText(str(pendientes) if pendientes < 10 else "9+")
        self.insignia_ia.setVisible(pendientes > 0)
        self.botones_riel["ia"].setToolTip(
            f"Asistente de IA · {pendientes} propuesta{'s' if pendientes != 1 else ''} pendiente"
            f"{'s' if pendientes != 1 else ''}"
            if pendientes
            else "Asistente de IA"
        )

    def conectar_ia(self, conectar: bool | None = None) -> bool:
        """Abre o cierra el canal local para que la app de IA de la persona use
        ``nervi-mcp`` con este proyecto (``docs/agentes-ia.md``)."""
        if conectar is None or not isinstance(conectar, bool):
            conectar = not self.canal.activo
        try:
            self.canal.abrir() if conectar else self.canal.cerrar()
        except OSError as e:
            QMessageBox.warning(self, "Conectar con mi IA", str(e))
        self.statusBar().showMessage(
            "IA conectada: tu app de IA ya puede usar nervi-mcp con este proyecto"
            if self.canal.activo
            else "IA desconectada",
            6000,
        )
        return self.canal.activo

    def nativeEvent(self, tipo, mensaje):
        """En Windows, la barra de título propia atiende los mensajes del marco."""
        if self.marco is not None:
            respuesta = self.marco.evento_nativo(tipo, mensaje)
            if respuesta is not None:
                return respuesta
        return super().nativeEvent(tipo, mensaje)

    def paintEvent(self, evento) -> None:
        super().paintEvent(evento)
        if self.marco is not None:
            self.marco.pintar_borde(self)

    def closeEvent(self, evento) -> None:
        if self._seguir_si_hay_cambios():
            paneles.guardar_al_cerrar(self)
            self.canal.cerrar()
            if isinstance(self.vista3d, Vista3D):
                self.vista3d.plotter.close()
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
