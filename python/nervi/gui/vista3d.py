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
from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import escena3d, estilo
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
    """``PolyData`` con una polilínea por arreglo ``(n, 3)``."""
    import pyvista as pv

    puntos = np.vstack(polilineas)
    celdas, base = [], 0
    for p in polilineas:
        celdas += [len(p), *range(base, base + len(p))]
        base += len(p)
    return pv.PolyData(puntos, lines=np.array(celdas))


def _franjas(rellenos: list[escena3d.Relleno]):
    """Superficie de cuadriláteros entre el eje y el borde de cada relleno."""
    import pyvista as pv

    puntos, caras, base = [], [], 0
    for r in rellenos:
        n = len(r.eje)
        puntos += [r.eje, r.borde]
        for k in range(n - 1):
            a, b = base + k, base + k + 1
            caras += [4, a, b, base + n + k + 1, base + n + k]
        base += 2 * n
    return pv.PolyData(np.vstack(puntos), faces=np.array(caras))


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
) -> dict:
    """Dibuja ``escena`` en un ``pyvista.Plotter`` (o ``QtInteractor``) vacío.
    Devuelve los actores con nombre, para elegir barras con el mouse."""
    import pyvista as pv

    plotter.clear()
    plotter.set_background(estilo.PANEL)
    actores: dict = {}
    if not escena.barras:
        plotter.add_text(
            "Agregá nudos y barras en la tabla de Geometría",
            position="upper_left",
            font_size=10,
            color=estilo.TEXTO_3,
        )
        return actores

    t = escena.tamano
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
            shape_color="white",
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

    barras = _lineas([np.vstack([b.p_i, b.p_j]) for b in escena.barras])
    barras.cell_data["barra"] = np.array([b.id for b in escena.barras])
    actores["barras"] = plotter.add_mesh(
        barras,
        color=estilo.ESTRUCTURA,
        line_width=5,
        render_lines_as_tubes=True,
        pickable=True,
    )
    if seleccion is not None and seleccion.tipo == "barra":
        elegida = [np.vstack([b.p_i, b.p_j]) for b in escena.barras if b.id == seleccion.id]
        if elegida:
            plotter.add_mesh(
                _lineas(elegida), color=estilo.ACENTO, line_width=8, render_lines_as_tubes=True
            )
    ids = list(escena.nudos)
    puntos = np.array([escena.nudos[i] for i in ids])
    colores = [
        estilo.ACENTO if seleccion == Seleccion("nudo", i) else estilo.ESTRUCTURA for i in ids
    ]
    plotter.add_points(
        pv.PolyData(puntos),
        scalars=np.array([[int(c[k : k + 2], 16) for k in (1, 3, 5)] for c in colores], np.uint8),
        rgb=True,
        point_size=11,
        render_points_as_spheres=True,
    )
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
    plotter.add_axes(color=estilo.TEXTO_2, line_width=2, labels_off=False)
    return actores


def encuadrar(plotter, escena: escena3d.Escena, vista: str = "frente") -> None:
    """Cámara de frente al pórtico (mirando hacia +Y, con X a la derecha, como
    la vista 2D) o isométrica desde el mismo lado, con Z hacia arriba."""
    direccion = np.array([0.0, -1.0, 0.0]) if vista == "frente" else np.array([0.9, -1.5, 0.8])
    centro = escena.centro
    plotter.camera_position = [
        tuple(centro + direccion * 3 * escena.tamano),
        tuple(centro),
        (0.0, 0.0, 1.0),
    ]
    plotter.reset_camera()
    plotter.camera.zoom(0.95)


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
    """Visor 3D dentro de la ventana. Girar: arrastrar; desplazar: Mayús + arrastrar;
    zoom: rueda. Clic en una barra la selecciona, igual que en la vista 2D."""

    diagrama_cambiado = Signal(str)

    def __init__(self, sesion: Sesion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from pyvistaqt import QtInteractor

        self.sesion = sesion
        self.diagrama = "M"
        self.mostrar_valores = True
        self.mostrar_cargas = True
        self.escena: escena3d.Escena | None = None
        self._actores: dict = {}
        self._encuadrada = False
        self._presion: tuple[int, int] | None = None

        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        self.plotter = QtInteractor(self, auto_update=False)
        capa.addWidget(self.plotter.interactor, 1)
        botones = QWidget(objectName="contexto")
        fila = QHBoxLayout(botones)
        fila.setContentsMargins(8, 4, 8, 4)
        for texto, vista in (("De frente", "frente"), ("Isométrica", "isometrica")):
            b = QPushButton(texto)
            b.clicked.connect(lambda _=False, v=vista: self.encuadrar(v))
            fila.addWidget(b)
        self.b_cargas = QPushButton("Cargas", checkable=True, checked=True)
        self.b_cargas.toggled.connect(self._cargas)
        fila.addWidget(self.b_cargas)
        fila.addWidget(
            QLabel("Arrastrar: girar · Mayús: desplazar · Rueda: zoom", objectName="tenue")
        )
        fila.addStretch()
        capa.addWidget(botones)

        iren = self.plotter.iren
        iren.add_observer("LeftButtonPressEvent", self._al_presionar)
        iren.add_observer("LeftButtonReleaseEvent", self._al_soltar)
        for senal in (
            sesion.modelo_cambiado,
            sesion.resultados_cambiados,
            sesion.seleccion_cambiada,
        ):
            senal.connect(self.actualizar)
        sesion.archivo_cambiado.connect(self._nuevo_archivo)
        self.actualizar()

    def elegir_diagrama(self, clave: str) -> None:
        if clave in escena3d.DIAGRAMAS and clave != self.diagrama:
            self.diagrama = clave
            self.diagrama_cambiado.emit(clave)
            self.actualizar()

    def _cargas(self, activo: bool) -> None:
        self.mostrar_cargas = activo
        self.actualizar()

    def _nuevo_archivo(self) -> None:
        self._encuadrada = False

    def actualizar(self) -> None:
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
        camara = self.plotter.camera_position if self._encuadrada else None
        self._actores = dibujar(self.plotter, self.escena, s.seleccion, texto)
        if camara is None:
            if self.escena.barras:
                encuadrar(self.plotter, self.escena, "isometrica")
                self._encuadrada = True
        else:
            self.plotter.camera_position = camara
        self.plotter.render()

    def encuadrar(self, vista: str) -> None:
        if self.escena is not None:
            encuadrar(self.plotter, self.escena, vista)
            self.plotter.render()

    # --- Selección con el mouse ---------------------------------------------------------
    def barra_en(self, x: int, y: int) -> int | None:
        """``id`` de la barra bajo el punto ``(x, y)`` de VTK (origen abajo a la izquierda)."""
        return barra_en(self.plotter, self._actores, x, y)

    def _al_presionar(self, iren, _evento) -> None:
        self._presion = iren.GetEventPosition()

    def _al_soltar(self, iren, _evento) -> None:
        if self._presion is None:
            return
        x, y = iren.GetEventPosition()
        x0, y0 = self._presion
        self._presion = None
        if abs(x - x0) + abs(y - y0) > 3:  # fue un giro, no un clic
            return
        barra = self.barra_en(x, y)
        self.sesion.seleccionar(Seleccion("barra", barra) if barra is not None else None)

    def closeEvent(self, evento) -> None:
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
