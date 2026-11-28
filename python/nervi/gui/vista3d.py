# SPDX-License-Identifier: GPL-3.0-or-later
"""Visor 3D del modelo y de los resultados (issue #30), con PyVista y VTK.

PyVista y pyvistaqt (MIT) y VTK (BSD-3-Clause) son dependencias opcionales,
compatibles con GPL-3.0: se instalan con ``pip install nervi[visor3d]``. Sin
ellas la interfaz sigue funcionando y la pestaña 3D explica cómo instalarlas.

La geometría sale de ``escena3d`` (sin VTK); este módulo solo la dibuja. El
mismo ``dibujar`` sirve para la ventana y para ``capturar``, que renderiza a una
imagen sin pantalla (pruebas del CI y capturas para la documentación).
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import camara3d, escena3d, estilo
from .brujula import Brujula
from .navegacion import FACTOR_RUEDA, METROS, BotonesNavegacion
from .sesion import Seleccion, Sesion

UNIDAD = {"M": "{f}·{l}", "V": "{f}", "N": "{f}"}
COLOR_CARGA = estilo.OK
INSTALAR = "pip install nervi[visor3d]"


def disponible() -> str | None:
    """``None`` si se puede usar el visor; si no, el motivo."""
    try:
        import pyvista  # noqa: F401
        import pyvistaqt  # noqa: F401
    except ImportError as e:
        return f"Falta {e.name}. Para usar el visor 3D instalá: {INSTALAR}"
    return None


def _fmt(v: float) -> str:
    return f"{v:.2f}".replace("-", "−")


# --- Dibujo con PyVista --------------------------------------------------------------
def _lineas(polilineas: list[np.ndarray]):
    """``PolyData`` con una polilínea por arreglo ``(n, 3)``. Arma las celdas en
    bloque: el edificio tiene miles de barras."""
    import pyvista as pv

    puntos = np.vstack(polilineas)
    largos = np.array([len(p) for p in polilineas], dtype=np.int64)
    inicio = np.concatenate([[0], np.cumsum(largos)[:-1]])
    # Cada celda: [n, base, base + 1, …, base + n - 1].
    celdas = np.empty(len(puntos) + len(largos), dtype=np.int64)
    pos = inicio + np.arange(len(largos))
    celdas[pos] = largos
    resto = np.ones(len(celdas), dtype=bool)
    resto[pos] = False
    celdas[resto] = np.arange(len(puntos))
    return pv.PolyData(puntos, lines=celdas)


def _franjas(rellenos: list[escena3d.Relleno]):
    """Superficie de cuadriláteros entre el eje y el borde de cada relleno."""
    import pyvista as pv

    largos = np.array([len(r.eje) for r in rellenos], dtype=np.int64)
    base = np.concatenate([[0], np.cumsum(2 * largos)[:-1]])
    puntos = np.vstack([p for r in rellenos for p in (r.eje, r.borde)])
    # Un cuadrilátero por tramo k de cada relleno: eje k, eje k+1, borde k+1, borde k.
    n = np.repeat(largos, largos - 1)
    b = np.repeat(base, largos - 1)
    k = np.arange(int((largos - 1).sum())) - np.repeat(
        np.cumsum(largos - 1) - (largos - 1), largos - 1
    )
    a = b + k
    caras = np.column_stack([np.full(len(a), 4), a, a + 1, a + n + 1, a + n]).ravel()
    return pv.PolyData(puntos, faces=caras)


#: Caras de un prisma de :func:`escena3d.cajas` (índices de sus 8 esquinas).
CARAS_CAJA = np.array(
    [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
)


def _cajas(cajas: np.ndarray):
    """``PolyData`` con los seis lados de cada prisma ``(n, 8, 3)``."""
    import pyvista as pv

    n = len(cajas)
    idx = (np.arange(n)[:, None, None] * 8 + CARAS_CAJA[None]).reshape(-1, 4)
    caras = np.column_stack([np.full(len(idx), 4), idx]).ravel()
    return pv.PolyData(cajas.reshape(-1, 3), faces=caras)


def _poligonos(poligonos: list[np.ndarray]):
    import pyvista as pv

    puntos = np.vstack(poligonos)
    caras, base = [], 0
    for p in poligonos:
        caras += [len(p), *range(base, base + len(p))]
        base += len(p)
    return pv.PolyData(puntos, faces=np.array(caras))


def _flechas(flechas: list[escena3d.Flecha], tamano: float):
    """Glifos de flecha que terminan en el punto de aplicación de cada carga."""
    import pyvista as pv

    malla = None
    maximos = {
        d: max((f.valor for f in flechas if f.distribuida == d), default=1.0) for d in (False, True)
    }
    for f in flechas:
        largo = escena3d.LARGO_CARGA * tamano * (0.45 + 0.55 * f.valor / maximos[f.distribuida])
        inicio = f.punta - f.direccion * largo
        flecha = pv.Arrow(
            start=inicio,
            direction=f.direccion,
            tip_length=0.28,
            tip_radius=0.09,
            shaft_radius=0.025,
            scale=largo,
        )
        malla = flecha if malla is None else malla.merge(flecha)
    return malla


def _apoyos(apoyos: list[escena3d.Apoyo], tamano: float):
    import pyvista as pv

    s = 0.045 * tamano
    malla = None
    for a in apoyos:
        p = a.punto
        if a.tipo == "empotrado":
            piezas = [pv.Box((p[0] - s, p[0] + s, p[1] - s, p[1] + s, p[2] - 0.35 * s, p[2]))]
        else:
            piezas = [
                pv.Cone(
                    center=p - np.array([0, 0, 0.5 * s]),
                    direction=(0, 0, 1),
                    height=s,
                    radius=0.7 * s,
                    resolution=24,
                )
            ]
            if a.tipo == "deslizante":
                z = p[2] - 1.25 * s
                piezas.append(pv.Box((p[0] - s, p[0] + s, p[1] - s, p[1] + s, z - 0.12 * s, z)))
        for pieza in piezas:
            malla = pieza if malla is None else malla.merge(pieza)
    return malla


#: Líneas de grilla del terreno como mucho, por dirección.
LINEAS_GRILLA = 60


def _grilla_terreno(escena: escena3d.Escena, paso: float) -> list:
    """Grilla en el plano del nudo más bajo, alrededor del modelo: fina cada ``paso``
    (agrandado de a 5 si salen demasiadas líneas) y marcada cada 5 pasos."""

    puntos = np.array(list(escena.nudos.values()))
    z = float(puntos[:, 2].min())
    margen = 0.25 * escena.tamano
    lo = puntos[:, :2].min(axis=0) - margen
    hi = puntos[:, :2].max(axis=0) + margen
    while ((hi - lo) / paso).max() > LINEAS_GRILLA:
        paso *= 5
    lo = np.floor(lo / paso) * paso
    hi = np.ceil(hi / paso) * paso
    finas, marcadas = [], []
    for eje in (0, 1):
        n = round((hi[eje] - lo[eje]) / paso)
        for k in range(n + 1):
            v = lo[eje] + k * paso
            a, b = [0.0, 0.0, z], [0.0, 0.0, z]
            a[eje] = b[eje] = v
            a[1 - eje], b[1 - eje] = lo[1 - eje], hi[1 - eje]
            marcada = abs(round(v / paso) % 5) == 0
            (marcadas if marcada else finas).append(np.array([a, b]))
    salida = []
    for lineas, color in ((finas, estilo.BORDE), (marcadas, estilo.actual.borde_fuerte)):
        if lineas:
            salida.append((_lineas(lineas), color))
    return salida


def leyenda(escena: escena3d.Escena, clave: str, nombre: str, unidades: dict) -> str:
    u = {"f": unidades.get("fuerza", ""), "l": unidades.get("longitud", "")}
    if not nombre:
        return ""
    if clave == "D":
        if escena.amplificacion:
            return f"Deformada × {escena.amplificacion:.4g} · {nombre}"
        return f"Cargas · {nombre}"
    if escena.escala_diagrama:
        return f"{escena3d.DIAGRAMAS[clave]} [{UNIDAD[clave].format(**u)}] · {nombre}"
    return f"Cargas · {nombre}"


def dibujar(
    plotter,
    escena: escena3d.Escena,
    seleccion: Seleccion | None = None,
    texto: str = "",
    paso_grilla: float | None = None,
    ejes: bool = True,
    vacio: str = "Agregá nudos y barras en la tabla de Geometría",
) -> dict:
    """Dibuja ``escena`` en un ``pyvista.Plotter`` (o ``QtInteractor``) vacío.
    Con ``paso_grilla`` (en unidades del modelo) dibuja la grilla del terreno debajo;
    sin ``ejes`` no dibuja el triedro (el visor tiene su brújula de vistas).
    Devuelve los actores con nombre, para elegir barras con el mouse."""
    import pyvista as pv

    plotter.clear()
    plotter.set_background(estilo.PANEL)
    actores: dict = {}
    if not escena.barras:
        plotter.add_text(
            vacio,
            position="upper_left",
            font_size=10,
            color=estilo.TEXTO_3,
        )
        return actores

    t = escena.tamano
    if paso_grilla:
        grilla = _grilla_terreno(escena, paso_grilla)
        for lineas, color in grilla:
            plotter.add_mesh(lineas, color=color, line_width=1, lighting=False, pickable=False)
    if escena.rellenos:
        for signo, color in ((1, estilo.POSITIVO), (-1, estilo.NEGATIVO)):
            partes = [r for r in escena.rellenos if r.signo == signo]
            if not partes:
                continue
            plotter.add_mesh(_franjas(partes), color=color, opacity=0.16, lighting=False)
            plotter.add_mesh(
                _lineas([r.borde for r in partes]),
                color=color,
                line_width=2,
                lighting=False,
            )
    if escena.etiquetas:
        plotter.add_point_labels(
            np.array([e.punto for e in escena.etiquetas]),
            [_fmt(e.valor) for e in escena.etiquetas],
            font_size=12,
            text_color=estilo.TEXTO,
            shape_color=estilo.PANEL,
            shape_opacity=0.85,
            show_points=False,
            always_visible=True,
            margin=2,
        )
    if escena.deformada:
        plotter.add_mesh(
            _lineas(escena.deformada),
            color=estilo.ACENTO,
            line_width=3,
            render_lines_as_tubes=True,
        )
    if escena.cargas:
        plotter.add_mesh(_flechas(escena.cargas, t), color=COLOR_CARGA, smooth_shading=True)
    # Piezas del edificio (#74): volúmenes tenues detrás del modelo de cálculo.
    if len(escena.cajas):
        plotter.add_mesh(
            _cajas(escena.cajas),
            color=estilo.TEXTO_3,
            opacity=0.22,
            pickable=False,
            show_edges=True,
            edge_color=estilo.TEXTO_3,
        )
    if escena.losas:
        plotter.add_mesh(
            _poligonos(escena.losas), color=estilo.TEXTO_3, opacity=0.10, pickable=False
        )
    if escena.brazos:
        plotter.add_mesh(_lineas(escena.brazos), color=estilo.ACENTO, line_width=7, pickable=False)
    if escena.diafragmas:
        plotter.add_mesh(
            _lineas(escena.diafragmas),
            color=estilo.ACENTO,
            line_width=1,
            opacity=0.5,
            pickable=False,
        )
        centros = np.array([c for _, c in escena.maestros])
        plotter.add_points(pv.PolyData(centros), color=estilo.ACENTO, point_size=12, pickable=False)

    barras = _lineas([np.vstack([b.p_i, b.p_j]) for b in escena.barras])
    barras.cell_data["barra"] = np.array([b.id for b in escena.barras])
    actores["barras"] = plotter.add_mesh(
        barras,
        color=estilo.ESTRUCTURA,
        line_width=5,
        render_lines_as_tubes=True,
        pickable=True,
    )
    marcadas = set(escena.resaltadas)
    if seleccion is not None and seleccion.tipo == "barra":
        marcadas.add(seleccion.id)
    if marcadas:
        elegida = [np.vstack([b.p_i, b.p_j]) for b in escena.barras if b.id in marcadas]
        if elegida:
            plotter.add_mesh(
                _lineas(elegida), color=estilo.ACENTO, line_width=8, render_lines_as_tubes=True
            )
    ids = list(escena.nudos) if escena.ver_nudos else []
    if ids:
        puntos = np.array([escena.nudos[i] for i in ids])
        colores = [
            estilo.ACENTO if seleccion == Seleccion("nudo", i) else estilo.ESTRUCTURA for i in ids
        ]
        plotter.add_points(
            pv.PolyData(puntos),
            scalars=np.array(
                [[int(c[k : k + 2], 16) for k in (1, 3, 5)] for c in colores], np.uint8
            ),
            rgb=True,
            point_size=11 if escena.rotulos_nudos else 7,
            render_points_as_spheres=True,
        )
    if ids and escena.rotulos_nudos:
        plotter.add_point_labels(
            puntos + np.array([0.02, 0.0, 0.03]) * t,
            [f"N{i}" for i in ids],
            font_size=10,
            text_color=estilo.TEXTO_3,
            shape_opacity=0.0,
            show_points=False,
            always_visible=True,
        )
    if escena.apoyos:
        plotter.add_mesh(_apoyos(escena.apoyos, t), color=estilo.TEXTO_2, smooth_shading=True)
    if texto:
        plotter.add_text(texto, position="lower_left", font_size=9, color=estilo.TEXTO)
    if ejes:
        plotter.add_axes(color=estilo.TEXTO_2, line_width=2, labels_off=False)
    return actores


def poner_camara(plotter, camara: camara3d.Camara3D, alto: float) -> None:
    """Pasa la cámara de Nervi a la de VTK (``alto``: alto del lienzo en píxeles)."""
    p = camara.a_vtk(alto)
    cam = plotter.renderer.GetActiveCamera()
    cam.SetFocalPoint(*p["focal_point"])
    cam.SetPosition(*p["position"])
    cam.SetViewUp(*p["up"])
    cam.SetParallelScale(p["parallel_scale"])
    cam.SetViewAngle(p["view_angle"])
    cam.SetParallelProjection(p["parallel_projection"])
    plotter.renderer.ResetCameraClippingRange()
    # Sin esto, PyVista vuelve a encuadrar a su manera en el primer dibujo.
    plotter.camera_set = True


def camara_de_encuadre(
    escena: escena3d.Escena, ancho: float, alto: float, vista="isometrica", perspectiva=False
) -> camara3d.Camara3D:
    """Cámara que muestra todo el modelo desde ``vista`` (ver ``camara3d.encuadre``)."""
    return camara3d.encuadre(puntos_visibles(escena), ancho, alto, vista, perspectiva=perspectiva)


def puntos_visibles(escena: escena3d.Escena) -> np.ndarray:
    """Nudos, bordes de los diagramas, deformada y colas de las flechas de carga: lo que
    tiene que entrar en el encuadre."""
    partes = [np.array(list(escena.nudos.values()))] if escena.nudos else []
    partes += [r.borde for r in escena.rellenos]
    partes += list(escena.deformada)
    largo = escena3d.LARGO_CARGA * escena.tamano
    partes += [np.array([f.punta - f.direccion * largo]) for f in escena.cargas]
    return np.vstack(partes) if partes else np.zeros((0, 3))


def encuadrar(plotter, escena: escena3d.Escena, vista: str = "frente") -> None:
    """Cámara de frente al pórtico (mirando hacia +Y, con X a la derecha, como
    la vista de frente) o isométrica, con Z hacia arriba."""
    ancho, alto = plotter.window_size
    poner_camara(plotter, camara_de_encuadre(escena, ancho, alto, vista), alto)


def capturar(
    modelo: dict,
    ruta: str | Path,
    resultado=None,
    indices=None,
    clave: str = "M",
    nombre: str = "",
    vista: str = "isometrica",
    tamano: tuple[int, int] = (1200, 800),
    seleccion: Seleccion | None = None,
    cargas: bool = True,
) -> Path:
    """Renderiza el modelo y sus resultados a una imagen PNG, sin pantalla."""
    import pyvista as pv

    escena = escena3d.armar(modelo, resultado, indices, clave, nombre if cargas else "")
    plotter = pv.Plotter(off_screen=True, window_size=list(tamano))
    try:
        dibujar(plotter, escena, seleccion, leyenda(escena, clave, nombre, modelo["unidades"]))
        encuadrar(plotter, escena, vista)
        ruta = Path(ruta)
        plotter.screenshot(str(ruta))
    finally:
        plotter.close()
    return ruta


def barra_en(plotter, actores: dict, x: int, y: int) -> int | None:
    """``id`` de la barra dibujada por ``dibujar`` bajo el punto ``(x, y)`` de la
    ventana de VTK (origen abajo a la izquierda), o ``None``."""
    from vtkmodules.vtkRenderingCore import vtkCellPicker

    actor = actores.get("barras")
    if actor is None:
        return None
    picker = vtkCellPicker()
    picker.SetTolerance(0.01)
    picker.PickFromListOn()
    picker.AddPickList(actor)
    if not picker.Pick(x, y, 0, plotter.renderer):
        return None
    celda = picker.GetCellId()
    ids = actor.mapper.dataset.cell_data["barra"]
    return int(ids[celda]) if 0 <= celda < len(ids) else None


def a_pantalla(plotter, punto) -> tuple[int, int]:
    """Punto global -> píxel de VTK (origen abajo a la izquierda)."""
    r = plotter.renderer
    r.SetWorldPoint(*punto, 1.0)
    r.WorldToDisplay()
    x, y, _ = r.GetDisplayPoint()
    return round(x), round(y)


# --- Widget ----------------------------------------------------------------------------
class Vista3D(QWidget):
    """Vista 3D del visor único. Nervi maneja el mouse y el teclado; VTK solo dibuja.

    - Arrastrar con el botón derecho (o el izquierdo): girar alrededor del punto que
      está bajo el cursor, con Z siempre arriba (:mod:`nervi.gui.camara3d`).
    - Botón del medio, o Mayús + botón izquierdo, arrastrado: desplazar.
    - Rueda: acercar o alejar hacia el cursor. ``F`` o ``Inicio``: encuadrar.
    - Clic en una barra: la elige, igual que en la vista de frente.
    - Brújula de vistas abajo a la derecha: mirar desde un eje.

    Con :attr:`edificio` muestra el edificio (#74): el modelo de cálculo generado,
    sus piezas o los dos (*Mostrar*, arriba a la izquierda) y los resultados del
    último cálculo del edificio. Un clic en una barra avisa con :attr:`barra_pulsada`
    (la ventana elige el elemento del edificio del que sale).
    """

    diagrama_cambiado = Signal(str)
    #: La brújula pidió una vista: ``"+Z"``, ``"-Y"``… (la ventana decide si pasa a frente).
    vista_pedida = Signal(str)
    #: Clic en el edificio: la barra del modelo de cálculo (``None``: en el vacío).
    barra_pulsada = Signal(object)

    #: Duración de la transición de la cámara, en milisegundos (0: sin animación).
    DURACION_MS = 220
    #: Píxeles que hay que mover el mouse para que un clic pase a ser un arrastre.
    UMBRAL_ARRASTRE = 4
    AYUDA = "Arrastrar: girar · Medio: desplazar · Rueda: zoom · F: encuadrar"

    def __init__(self, sesion: Sesion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from pyvistaqt import QtInteractor
        from vtkmodules.vtkInteractionStyle import vtkInteractorStyleUser

        self.sesion = sesion
        self.diagrama = "M"
        self.mostrar_valores = True
        self.mostrar_cargas = True
        self.perspectiva = False
        #: Muestra el edificio (modelo de cálculo generado) en vez del pórtico plano.
        self.edificio = False
        #: Qué se ve del edificio: ``"edificio"``, ``"calculo"`` o ``"ambos"``.
        self.mostrar = "ambos"
        #: Barras resaltadas en el edificio (las del elemento elegido).
        self.resaltadas: set[int] = set()
        self.escena: escena3d.Escena | None = None
        self.camara: camara3d.Camara3D | None = None
        self._actores: dict = {}
        self._animacion = None
        #: Arrastre en curso: ("girar" | "desplazar" | "clic", último punto, punto inicial)
        self._arrastre: tuple[str, QPointF, QPointF] | None = None
        self._pivote: np.ndarray | None = None

        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        self.plotter = QtInteractor(self, auto_update=False)
        self.lienzo = self.plotter.interactor
        capa.addWidget(self.lienzo, 1)
        # Sin estilo de interacción de VTK: los eventos los maneja eventFilter.
        self.plotter.iren.interactor.SetInteractorStyle(vtkInteractorStyleUser())
        self.lienzo.installEventFilter(self)

        self.botones_navegacion = BotonesNavegacion(self)
        self.b_cargas = QPushButton("Cargas", objectName="segmento", checkable=True, checked=True)
        self.b_cargas.setToolTip("Mostrar las cargas de la combinación")
        self.b_cargas.toggled.connect(self._cargas)
        self.botones_navegacion.findChild(QWidget, "grupo").layout().addWidget(self.b_cargas)
        self.brujula = Brujula(self)
        self.brujula.vista_pedida.connect(self.vista_pedida)
        # Mostrar: Edificio · Cálculo · Ambos, solo con el edificio.
        self.grupo_mostrar = QWidget(self)
        m = QHBoxLayout(self.grupo_mostrar)
        m.setContentsMargins(0, 0, 0, 0)
        m.setSpacing(8)
        m.addWidget(QLabel("Mostrar", objectName="tenue"))
        segmentos = QWidget(objectName="grupo")
        g = QHBoxLayout(segmentos)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        grupo = QButtonGroup(self)
        self.botones_mostrar: dict[str, QPushButton] = {}
        for clave, texto in escena3d.MOSTRAR.items():
            b = QPushButton(texto, objectName="segmento", checkable=True)
            b.clicked.connect(lambda _=False, c=clave: self.elegir_mostrar(c))
            grupo.addButton(b)
            self.botones_mostrar[clave] = b
            g.addWidget(b)
        self.botones_mostrar[self.mostrar].setChecked(True)
        m.addWidget(segmentos)
        self.grupo_mostrar.adjustSize()
        self.grupo_mostrar.hide()

        for senal in (
            sesion.modelo_cambiado,
            sesion.resultados_cambiados,
            sesion.seleccion_cambiada,
            sesion.fisico_cambiado,
        ):
            senal.connect(self.actualizar)
        sesion.archivo_cambiado.connect(self._nuevo_archivo)
        self.actualizar()

    # --- Lo que se muestra ------------------------------------------------------------
    def elegir_diagrama(self, clave: str) -> None:
        if clave in escena3d.DIAGRAMAS and clave != self.diagrama:
            self.diagrama = clave
            self.diagrama_cambiado.emit(clave)
            self.actualizar()

    def _cargas(self, activo: bool) -> None:
        self.mostrar_cargas = activo
        self.actualizar()

    def mostrar_edificio(self, activo: bool) -> None:
        """Pasa a mostrar el edificio (``True``) o el pórtico plano."""
        if activo != self.edificio:
            self.edificio = activo
            self.camara = None
        self.grupo_mostrar.setVisible(activo)
        # Las cargas del pórtico no van en el edificio: se ven en la planta.
        self.b_cargas.setVisible(not activo)
        self.actualizar()

    def elegir_mostrar(self, clave: str) -> None:
        """*Mostrar* del edificio: ``"edificio"``, ``"calculo"`` o ``"ambos"``."""
        self.mostrar = clave
        self.botones_mostrar[clave].setChecked(True)
        self.actualizar()

    def resaltar(self, barras) -> None:
        """Resalta las barras del elemento elegido del edificio."""
        barras = set(barras)
        if barras != self.resaltadas:
            self.resaltadas = barras
            if self.edificio:
                self.actualizar()

    def _nuevo_archivo(self) -> None:
        self.camara = None

    def _paso_grilla(self) -> float:
        """Un metro en las unidades del modelo."""
        return 1.0 / METROS.get(self.sesion.modelo["unidades"]["longitud"], 1.0)

    def _actualizar_edificio(self) -> None:
        s = self.sesion
        texto = ""
        try:
            mc = s.modelo_calculo() if s.es_edificio else None
        except (ValueError, KeyError) as e:
            mc, texto = None, f"No se pudo generar el modelo de cálculo: {e}"
        if mc is None or mc.n_barras == 0:
            self.escena = escena3d.Escena({}, [], [], 1.0)
            vacio = texto or "Dibujá columnas, vigas y muros en la planta del edificio"
            self._actores = dibujar(self.plotter, self.escena, None, "", ejes=False, vacio=vacio)
            self._poner_camara()
            return
        from ..fisico import ModeloFisico

        res = s.resultado_edificio()
        self.escena = escena3d.armar_edificio(
            mc,
            ModeloFisico.desde_json(s.fisico),
            s.resultados_edificio if s.edificio_al_dia else None,
            res,
            self.diagrama,
            self.mostrar,
            self.mostrar_valores,
        )
        self.escena.resaltadas = set(self.resaltadas)
        nombre = s.combinacion
        if res is None:
            texto = "Sin resultados: calculá con F5"
        else:
            texto = leyenda(
                self.escena, self.diagrama, nombre, {"fuerza": "kN", "longitud": mc.longitud}
            )
        self._actores = dibujar(
            self.plotter,
            self.escena,
            None,
            texto,
            paso_grilla=1.0 / METROS.get(mc.longitud, 1.0),
            ejes=False,
        )
        self.plotter.add_text(self.AYUDA, position="lower_right", font_size=8, color=estilo.TEXTO_3)
        if self.camara is None:
            self.camara = self.encuadre("isometrica")
        self._poner_camara()

    def actualizar(self) -> None:
        if self.edificio:
            self._actualizar_edificio()
            return
        s = self.sesion
        res = s.resultado()
        nombre = s.combinacion or (s.nombres_resultado() or [""])[0]
        self.escena = escena3d.armar(
            s.modelo,
            res,
            s.indices,
            self.diagrama,
            nombre if self.mostrar_cargas else "",
            self.mostrar_valores,
        )
        if res is None and s.modelo["barras"]:
            texto = "Sin resultados: calculá con F5"
            if nombre and self.mostrar_cargas:
                texto = f"Cargas · {nombre} · {texto[0].lower()}{texto[1:]}"
        else:
            texto = leyenda(self.escena, self.diagrama, nombre, s.modelo["unidades"])
        self._actores = dibujar(
            self.plotter,
            self.escena,
            s.seleccion,
            texto,
            paso_grilla=self._paso_grilla(),
            ejes=False,
        )
        if self.escena.barras:
            self.plotter.add_text(
                self.AYUDA, position="lower_right", font_size=8, color=estilo.TEXTO_3
            )
        if self.camara is None and self.escena.barras:
            self.camara = self.encuadre("isometrica")
        self._poner_camara()

    # --- Cámara -----------------------------------------------------------------------
    def _tamano(self) -> tuple[float, float]:
        return float(max(self.lienzo.width(), 1)), float(max(self.lienzo.height(), 1))

    def encuadre(self, vista="isometrica") -> camara3d.Camara3D:
        """Cámara que muestra todo el modelo desde ``vista``."""
        w, h = self._tamano()
        return camara_de_encuadre(self.escena, w, h, vista, self.perspectiva)

    def _poner_camara(self) -> None:
        if self.camara is not None:
            poner_camara(self.plotter, self.camara, self._tamano()[1])
            self.brujula.mostrar(self.camara)
        self.plotter.render()

    def poner(self, camara: camara3d.Camara3D) -> None:
        """Cambia la cámara sin transición."""
        self.detener_animacion()
        self.camara = camara
        self._poner_camara()

    def animar_a(self, destino: camara3d.Camara3D, al_terminar=None) -> None:
        """Lleva la cámara a ``destino`` con una transición corta."""
        self.detener_animacion()
        origen = self.camara
        if origen is None or self.DURACION_MS <= 0 or not self.isVisible():
            self.poner(destino)
            if al_terminar is not None:
                al_terminar()
            return
        from PySide6.QtCore import QVariantAnimation

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(self.DURACION_MS)

        def paso(t) -> None:
            self.camara = camara3d.interpolar(origen, destino, float(t))
            self._poner_camara()

        def fin() -> None:
            self._animacion = None
            self.camara = destino
            self._poner_camara()
            if al_terminar is not None:
                al_terminar()

        anim.valueChanged.connect(paso)
        anim.finished.connect(fin)
        self._animacion = anim
        anim.start()

    def detener_animacion(self) -> None:
        if self._animacion is not None:
            anim, self._animacion = self._animacion, None
            anim.finished.disconnect()
            anim.stop()

    def ir_a(self, vista) -> None:
        """Encuadra el modelo desde ``vista``: un nombre de ``camara3d.VISTAS``, un
        extremo de la brújula (``"+Z"``…) o ``(acimut, elevación)``."""
        if self.escena is None or not self.escena.nudos:
            return
        if isinstance(vista, str) and vista in camara3d.EXTREMOS:
            vista = camara3d.EXTREMOS[vista]
        self.animar_a(self.encuadre(vista))

    def encuadrar(self, vista=None) -> None:
        """Muestra todo el modelo; sin ``vista``, desde la orientación actual."""
        if self.camara is not None and vista is None:
            vista = (self.camara.acimut, self.camara.elevacion)
        self.ir_a(vista or "isometrica")

    def elegir_perspectiva(self, activa: bool) -> None:
        self.perspectiva = activa
        if self.camara is not None:
            self.poner(replace(self.camara, perspectiva=activa))

    def zoom(self, factor: float, cursor: QPointF | None = None) -> None:
        if self.camara is None:
            return
        w, h = self._tamano()
        x, y = (w / 2, h / 2) if cursor is None else (cursor.x(), cursor.y())
        self.poner(self.camara.acercar(factor, x, y, w, h))

    # --- Giro y desplazamiento --------------------------------------------------------
    def punto_en(self, x: float, y: float) -> np.ndarray | None:
        """Punto del modelo dibujado bajo el píxel ``(x, y)`` del lienzo, o ``None``."""
        from vtkmodules.vtkRenderingCore import vtkCellPicker

        r = self.lienzo.devicePixelRatioF()
        picker = vtkCellPicker()
        picker.SetTolerance(0.005)
        if not picker.Pick(x * r, (self._tamano()[1] - y) * r, 0, self.plotter.renderer):
            return None
        return np.array(picker.GetPickPosition())

    def empezar_giro(self, pos: QPointF, pivote=None) -> None:
        """Empieza a girar desde ``pos``, alrededor de ``pivote`` (o del punto del modelo
        bajo el cursor; si no hay, del centro del modelo)."""
        self.detener_animacion()
        if pivote is None:
            pivote = self.punto_en(pos.x(), pos.y())
        if pivote is None and self.escena is not None and self.escena.nudos:
            pivote = self.escena.centro
        self._pivote = None if pivote is None else np.asarray(pivote, float)
        self._arrastre = ("girar", pos, pos)
        self._marcar_pivote()

    def girar(self, dx: float, dy: float) -> None:
        if self.camara is not None:
            self.poner(self.camara.girar(dx, dy, self._pivote))

    def terminar_arrastre(self) -> None:
        self._arrastre = None
        self._pivote = None
        self._marcar_pivote()
        self.lienzo.unsetCursor()

    def _marcar_pivote(self) -> None:
        """Marca el centro de giro mientras se gira."""
        self.plotter.remove_actor("centro_giro", render=False)
        if self._pivote is not None and self._arrastre is not None:
            import pyvista as pv

            self.plotter.add_mesh(
                pv.PolyData(self._pivote.reshape(1, 3)),
                color=estilo.ACENTO,
                point_size=14,
                render_points_as_spheres=True,
                pickable=False,
                name="centro_giro",
            )
        self.plotter.render()

    # --- Eventos del lienzo de VTK ----------------------------------------------------
    def eventFilter(self, objeto, evento) -> bool:
        if objeto is not self.lienzo:
            return False
        tipo = evento.type()
        if tipo == QEvent.MouseButtonPress:
            self._presionar(evento)
        elif tipo == QEvent.MouseMove:
            self._mover(evento)
        elif tipo == QEvent.MouseButtonRelease:
            self._soltar(evento)
        elif tipo == QEvent.MouseButtonDblClick:
            if evento.button() == Qt.MiddleButton:
                self.encuadrar()
        elif tipo == QEvent.Wheel:
            pasos = evento.angleDelta().y() / 120
            if pasos:
                self.zoom(FACTOR_RUEDA**pasos, evento.position())
        elif tipo == QEvent.KeyPress:
            return self._tecla(evento)
        elif tipo in (QEvent.KeyRelease, QEvent.ContextMenu):
            pass
        else:
            return False
        return True

    def _presionar(self, evento) -> None:
        self.lienzo.setFocus()
        pos, boton = evento.position(), evento.button()
        if boton == Qt.MiddleButton or (
            boton == Qt.LeftButton and evento.modifiers() & Qt.ShiftModifier
        ):
            self.detener_animacion()
            self._arrastre = ("desplazar", pos, pos)
            self.lienzo.setCursor(Qt.ClosedHandCursor)
        elif boton == Qt.RightButton:
            self.empezar_giro(pos)
        elif boton == Qt.LeftButton:
            # Clic o giro: se sabe al mover más que el umbral.
            self._arrastre = ("clic", pos, pos)

    def _mover(self, evento) -> None:
        if self._arrastre is None:
            # El giro empezó en la vista de frente y sigue acá con el botón apretado.
            return
        modo, ultimo, inicio = self._arrastre
        pos = evento.position()
        if modo == "clic":
            d = pos - inicio
            if abs(d.x()) + abs(d.y()) <= self.UMBRAL_ARRASTRE:
                return
            self.empezar_giro(inicio)
            modo, ultimo = "girar", inicio
        d = pos - ultimo
        if modo == "girar":
            self.girar(d.x(), d.y())
        else:
            self.poner(self.camara.desplazar(d.x(), d.y()))
        self._arrastre = (modo, pos, inicio)

    def _soltar(self, evento) -> None:
        if self._arrastre is None:
            return
        modo, _ultimo, inicio = self._arrastre
        self.terminar_arrastre()
        if modo == "clic" and evento.button() == Qt.LeftButton:
            barra = self.barra_en_lienzo(inicio.x(), inicio.y())
            if self.edificio:
                self.barra_pulsada.emit(barra)
                return
            self.sesion.seleccionar(Seleccion("barra", barra) if barra is not None else None)

    def _tecla(self, evento) -> bool:
        tecla = evento.key()
        if tecla in (Qt.Key_F, Qt.Key_Home) and not evento.modifiers():
            self.encuadrar()
        elif tecla in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(FACTOR_RUEDA)
        elif tecla == Qt.Key_Minus:
            self.zoom(1 / FACTOR_RUEDA)
        # Las demás teclas no llegan a VTK (sus atajos, como "q", cierran o cambian el
        # dibujo); los atajos de la ventana se resuelven antes.
        return True

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.botones_navegacion.acomodar()
        self.brujula.acomodar()
        self.grupo_mostrar.move(12, 12)
        self.grupo_mostrar.raise_()
        self.botones_navegacion.raise_()
        self.brujula.raise_()

    # --- Selección con el mouse ---------------------------------------------------------
    def barra_en(self, x: int, y: int) -> int | None:
        """``id`` de la barra bajo el punto ``(x, y)`` de VTK (origen abajo a la izquierda)."""
        return barra_en(self.plotter, self._actores, x, y)

    def barra_en_lienzo(self, x: float, y: float) -> int | None:
        """``id`` de la barra bajo el píxel ``(x, y)`` del lienzo (origen arriba)."""
        r = self.lienzo.devicePixelRatioF()
        return self.barra_en(round(x * r), round((self._tamano()[1] - y) * r))

    def closeEvent(self, evento) -> None:
        self.detener_animacion()
        self.plotter.close()
        super().closeEvent(evento)


class SinVisor3D(QWidget):
    """Lo que se ve en la pestaña 3D cuando faltan PyVista o VTK."""

    def __init__(self, motivo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        capa = QVBoxLayout(self)
        capa.addStretch()
        lbl = QLabel(motivo)
        lbl.setWordWrap(True)
        lbl.setObjectName("tenue")
        lbl.setStyleSheet("padding: 24px;")
        capa.addWidget(lbl)
        capa.addStretch()


def crear(sesion: Sesion, parent: QWidget | None = None) -> QWidget:
    """``Vista3D`` si hay PyVista y OpenGL; si no, un aviso con lo que falta."""
    motivo = disponible()
    if motivo is None and os.environ.get("NERVI_SIN_3D"):
        motivo = "Visor 3D desactivado (NERVI_SIN_3D)."
    if motivo is not None:
        return SinVisor3D(motivo, parent)
    try:
        return Vista3D(sesion, parent)
    except Exception as e:  # sin OpenGL, por ejemplo
        return SinVisor3D(f"No se pudo iniciar el visor 3D: {e}", parent)
