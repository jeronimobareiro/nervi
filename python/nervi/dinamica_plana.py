# SPDX-License-Identifier: GPL-3.0-or-later
"""Análisis modal y espectro de respuesta del pórtico plano.

El pórtico plano no tiene motor dinámico propio: :func:`modelo_espacial` lo
lleva al plano XZ de un :class:`nervi.Modelo3D` (Y del plano → Z, los GDL
fuera del plano restringidos) y el análisis lo hace ``nervi.dinamica``
(issues #16, #17 y #18). Los resultados vuelven al plano con las convenciones
del pórtico plano: ``ux, uy, rz``, ``N, V, M`` y reacciones ``Rx, Ry, Mz``.

La equivalencia de ejes está en ``docs/convenciones.md`` («Pórtico espacial»,
ejes locales) y la verifica ``portico_plano_en_xz_coincide_con_el_motor_plano``
en ``crates/nervi-core/tests/portico_3d.rs``: con el vector de referencia igual
al eje ``y`` local plano, ``N``, ``Vy`` y ``Mz`` del motor espacial son ``N``,
``V`` y ``M`` del plano, y el giro plano ``rz`` es ``-ry``.

Las masas salen de las cargas verticales de los casos (``m = -Fy · factor / g``)
y de masas nodales, siempre concentradas en los nudos.

>>> import nervi
>>> from nervi import dinamica_plana
>>> m = nervi.Modelo()
>>> a, b = m.agregar_nudo(0, 0), m.agregar_nudo(0, 3)
>>> _ = m.agregar_barra(a, b, E=2.5e7, A=0.09, I=6.75e-4)
>>> m.apoyar(a)
>>> m.carga_nodal("D", b, fy=-98.0665)
>>> modal = dinamica_plana.modal(m, {"D": 1.0}, n_modos=1)
>>> float(round(modal.periodos[0], 4))  # T = 2π √(m h³ / 3EI), m = 10 t
0.4589
>>> r = modal.espectro([(0.0, 5.0), (1.0, 5.0)], direccion="X")
>>> float(round(r.cortante_basal[0], 6))
50.0
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from .dinamica import ResultadoEspectro3D, ResultadosModal3D
from .modelo import Modelo, ResultadoCaso
from .modelo3d import Modelo3D

#: Gravedad según la unidad de longitud del modelo (aceleraciones en longitud/s²).
GRAVEDAD = {"m": 9.80665, "cm": 980.665, "mm": 9806.65}

#: Componentes del plano dentro de los 6 GDL espaciales: ux, uz, ry (con signo -1).
_GDL = (0, 2, 4)
_SIGNO = np.array([1.0, 1.0, -1.0])
#: Fuerzas de extremo locales del plano (N, V, M en i y en j) dentro de las 12 espaciales.
_EXTREMO = (0, 1, 5, 6, 7, 11)
#: Columnas de las direcciones X e Y del plano en las magnitudes espaciales (X, Y, Z).
_DIR = (0, 2)
_DIRECCIONES = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 0.0, 1.0)}


def modelo_espacial(
    modelo: Modelo,
    masas: Mapping[str, float] | None = None,
    gravedad: float = 9.80665,
    masas_nodales: Mapping[int, float] | None = None,
) -> Modelo3D:
    """El pórtico plano en el plano XZ de un :class:`Modelo3D`.

    Nudos ``(x, y) → (x, 0, y)``; cada barra con ``Iz = I`` y el vector de
    referencia igual a su eje ``y`` local plano; en todos los nudos quedan
    restringidos ``uy``, ``rx`` y ``rz`` (fuera del plano). Las cargas nodales y
    las uniformes, puntuales y trapezoidales se trasladan; las térmicas y los
    momentos en el tramo no, porque no generan masa (``masas``) y el modelo
    espacial solo se usa para la dinámica. ``masas`` son los factores de
    :meth:`Modelo3D.masa_desde_casos` y ``masas_nodales`` masas concentradas
    ``{nudo: m}`` que se suman en las dos direcciones del plano.
    """
    arr = modelo.arreglos()
    m3 = Modelo3D()
    for x, y in arr["coords"]:
        m3.agregar_nudo(x, 0.0, y)
    coords = arr["coords"]
    for k, (i, j) in enumerate(arr["conectividad"]):
        E, A, inercia = (float(v) for v in arr["props"][k])
        dx, dy = coords[j] - coords[i]
        largo = float(np.hypot(dx, dy))
        if largo <= 0.0:
            raise ValueError(f"la barra {k} tiene longitud nula")
        cx, cy = dx / largo, dy / largo
        lib_plano = arr["liberaciones"][k].astype(bool)
        lib = [False] * 12
        for p, e in zip(range(6), _EXTREMO, strict=True):
            lib[e] = bool(lib_plano[p])
        # Fuera del plano (Iy, J y G) no interviene: esos GDL están restringidos.
        m3.agregar_barra(
            int(i),
            int(j),
            E=E,
            G=E / 2.4,
            A=A,
            Iy=inercia,
            Iz=inercia,
            J=inercia,
            referencia=(-cy, 0.0, cx),
            liberaciones=lib,
        )
    for k, (ux, uy, rz) in enumerate(arr["restricciones"].astype(bool)):
        m3.apoyar(k, ux=bool(ux), uy=True, uz=bool(uy), rx=True, ry=bool(rz), rz=True)
    for k, (kx, ky, kr) in enumerate(arr["resortes"]):
        if kx or ky or kr:
            m3.resorte(k, kx=float(kx), kz=float(ky), kry=float(kr))
    nombres = modelo._casos
    for c, caso in enumerate(nombres):
        m3.caso(caso.nombre)
        for k, (fx, fy, mz) in enumerate(arr["cargas_nodales"][c]):
            if fx or fy or mz:
                m3.carga_nodal(c, k, fx=float(fx), fz=float(fy), my=-float(mz))
    for fila in arr["cargas_barra"]:
        caso, barra, tipo, ejes = (int(v) for v in fila[:4])
        ejes_txt = "global" if ejes == 1 else "local"

        def vector(qx: float, qy: float, ejes_txt=ejes_txt) -> tuple[float, float, float]:
            return (qx, 0.0, qy) if ejes_txt == "global" else (qx, qy, 0.0)

        a, q1x, q1y, b, q2x, q2y = (float(v) for v in fila[4:10])
        if tipo == 0:
            m3.carga_uniforme(caso, barra, *vector(q1x, q1y), ejes=ejes_txt)
        elif tipo == 1:
            m3.carga_puntual(caso, barra, a, *vector(q1x, q1y), ejes=ejes_txt)
        elif tipo == 2:
            m3.carga_trapezoidal(
                caso, barra, vector(q1x, q1y), vector(q2x, q2y), a=a, b=b, ejes=ejes_txt
            )
        # 3 (térmica) y 4 (momento en el tramo): sin resultante vertical, no dan masa.
    if masas:
        m3.masa_desde_casos(dict(masas), gravedad)
    for k, valor in (masas_nodales or {}).items():
        m3.masa_nodal(int(k), mx=float(valor), my=0.0, mz=float(valor))
    return m3


def modal(
    modelo: Modelo,
    masas: Mapping[str, float] | None = None,
    gravedad: float = 9.80665,
    masas_nodales: Mapping[int, float] | None = None,
    n_modos: int = 12,
    metodo: str = "automatico",
) -> ResultadosModalPlano:
    """Análisis modal del pórtico plano: los ``n_modos`` modos de menor frecuencia.

    ``masas`` son factores por caso, p. ej. ``{"D": 1.0, "L": 0.25}``: la masa
    de cada nudo es ``-Fy · factor / g`` con las cargas de barra repartidas a
    sus nudos por estática. ``gravedad`` en las unidades de longitud del modelo
    (:data:`GRAVEDAD`). La masa actúa en X y en Y, así que también aparecen los
    modos verticales de las vigas. Lanza ``ValueError`` si no hay masa y
    ``MecanismoError`` si la estructura es inestable.
    """
    m3 = modelo_espacial(modelo, masas, gravedad, masas_nodales)
    n = min(int(n_modos), 2 * len(modelo._nudos))
    return ResultadosModalPlano(m3, m3.modal(n_modos=max(n, 1), metodo=metodo))


def _caso_plano(nombre: str, r3) -> ResultadoCaso:
    """Lleva un resultado del modelo espacial (en el plano XZ) al pórtico plano."""
    d = r3._diagramas
    diagramas = {
        "barra": d["barra"],
        "x": d["x"],
        "N": d["N"],
        "V": d["Vy"],
        "M": d["Mz"],
        "u": d["u"],
        "v": d["v"],
    }
    return ResultadoCaso(
        nombre,
        r3.desplazamientos[:, _GDL] * _SIGNO,
        r3.reacciones[:, _GDL] * _SIGNO,
        r3.fuerzas_extremo[:, _EXTREMO],
        diagramas,
    )


class ResultadosModalPlano:
    """Resultados del análisis modal del pórtico plano (:func:`modal`)."""

    def __init__(self, modelo3d: Modelo3D, modal3d: ResultadosModal3D) -> None:
        self._m3 = modelo3d
        #: Resultados del motor espacial (``nervi.dinamica.ResultadosModal3D``).
        self.modal3d = modal3d
        self.omegas: np.ndarray = modal3d.omegas
        self.periodos: np.ndarray = modal3d.periodos
        self.frecuencias: np.ndarray = modal3d.frecuencias
        #: (n_modos, 2) masas modales efectivas en X e Y.
        self.masas_efectivas: np.ndarray = modal3d.masas_efectivas[:, _DIR]
        #: (2,) masa que puede participar en X e Y.
        self.masa_total: np.ndarray = modal3d.masa_total[list(_DIR)]
        #: (n_modos, 2) factores de participación Γ en X e Y.
        self.factores_participacion: np.ndarray = modal3d.factores_participacion[:, _DIR]
        self._modos: list[ResultadoCaso] | None = None

    @property
    def n_modos(self) -> int:
        return int(self.omegas.size)

    @property
    def masa_participante(self) -> np.ndarray:
        """(n_modos, 2) fracción de la masa total en X e Y que moviliza cada modo."""
        total = np.where(self.masa_total > 0, self.masa_total, np.inf)
        return self.masas_efectivas / total

    @property
    def masa_participante_acumulada(self) -> np.ndarray:
        """(n_modos, 2) suma acumulada de :attr:`masa_participante`."""
        return np.cumsum(self.masa_participante, axis=0)

    def formas(self) -> np.ndarray:
        """(n_modos, n_nudos, 3) formas modales ``[ux, uy, rz]`` normalizadas a masa."""
        return self.modal3d.modos[:, :, _GDL] * _SIGNO

    def modos(self) -> list[ResultadoCaso]:
        """Cada modo como un resultado del pórtico plano (para dibujarlo).

        La forma está escalada para que la mayor traslación valga 1 (en unidades
        de longitud) y los esfuerzos son los que produce esa deformada: solo
        muestran la forma, no son solicitaciones. Se obtienen resolviendo el
        modelo con las fuerzas de inercia ``ω² M φ``, que con masa concentrada
        dan exactamente ``φ`` (``K φ = ω² M φ``) y sus diagramas.
        """
        if self._modos is None:
            m3 = _copia_sin_casos(self._m3)
            inercias = self.modal3d.inercias
            escalas = []
            for k in range(self.n_modos):
                tras = np.abs(self.modal3d.modos[k][:, [0, 2]]).max()
                escala = 1.0 / tras if tras > 0 else 1.0
                escalas.append(escala)
                m3.caso(f"modo {k + 1}")
                fuerzas = self.omegas[k] ** 2 * escala * inercias[k]
                for nudo, f in enumerate(fuerzas):
                    if np.any(f):
                        m3.carga_nodal(k, nudo, *(float(v) for v in f))
            res = m3.resolver()
            self._modos = [
                _caso_plano(f"Modo {k + 1}", res[f"modo {k + 1}"]) for k in range(self.n_modos)
            ]
        return self._modos

    def modo(self, k: int) -> ResultadoCaso:
        """El modo ``k`` (desde 0) como resultado del pórtico plano; ver :meth:`modos`."""
        return self.modos()[k]

    def espectro(
        self,
        espectro: Sequence[tuple[float, float]] | np.ndarray,
        direccion: str = "X",
        amortiguamiento: float = 0.05,
        combinacion: str = "CQC",
        n_estaciones: int = 11,
        nombre: str | None = None,
    ) -> ResultadoEspectroPlano:
        """Respuesta por espectro en la dirección ``"X"`` o ``"Y"`` del plano.

        ``espectro`` son pares ``(T, Sa)`` con ``Sa`` en longitud/s² (las unidades
        del modelo); el resto como :meth:`nervi.dinamica.ResultadosModal3D.espectro`.
        Las magnitudes son valores absolutos combinados.
        """
        clave = direccion.upper()
        if clave not in _DIRECCIONES:
            raise ValueError(f"dirección {direccion!r} desconocida ('X' o 'Y')")
        r3 = self.modal3d.espectro(
            espectro,
            _DIRECCIONES[clave],
            amortiguamiento=amortiguamiento,
            combinacion=combinacion,
            n_estaciones=n_estaciones,
        )
        return ResultadoEspectroPlano(nombre or f"Espectro {clave}", clave, r3)

    def tabla(self) -> str:
        """Tabla de texto con periodo, frecuencia y masa participante en X e Y."""
        filas = ["modo   T [s]    f [Hz]   %Mx    %My    ΣMx    ΣMy"]
        p = 100 * self.masa_participante
        a = 100 * self.masa_participante_acumulada
        for k in range(self.n_modos):
            filas.append(
                f"{k + 1:4d} {self.periodos[k]:8.4f} {self.frecuencias[k]:8.3f} "
                + " ".join(f"{v:6.1f}" for v in (*p[k], *a[k]))
            )
        return "\n".join(filas)

    def __repr__(self) -> str:
        return f"ResultadosModalPlano({self.n_modos} modos, T1 = {self.periodos[0]:.4g})"


class ResultadoEspectroPlano(ResultadoCaso):
    """Respuesta espectral del pórtico plano: valores absolutos combinados.

    Tiene la forma de un caso de carga del plano, pero no se puede sumar con
    signo a otros casos ni entrar en combinaciones.
    """

    def __init__(self, nombre: str, direccion: str, r3: ResultadoEspectro3D) -> None:
        base = _caso_plano(nombre, r3)
        super().__init__(
            nombre,
            np.abs(base.desplazamientos),
            np.abs(base.reacciones),
            np.abs(base.fuerzas_extremo),
            base._diagramas,
        )
        self.direccion = direccion
        self.combinacion: str = r3.combinacion
        #: (2,) cortante basal combinado ``[Vx, Vy]``.
        self.cortante_basal: np.ndarray = r3.cortante_basal[list(_DIR)]
        #: (n_modos, 2) cortante basal de cada modo, con signo.
        self.cortante_basal_modal: np.ndarray = r3.cortante_basal_modal[:, _DIR]
        #: Aceleración espectral Sa(T) de cada modo.
        self.aceleraciones: np.ndarray = r3.aceleraciones
        #: Factor de participación de cada modo en la dirección de excitación.
        self.factores: np.ndarray = r3.factores

    def __repr__(self) -> str:
        return f"ResultadoEspectroPlano({self.nombre!r}, {self.combinacion})"


def _copia_sin_casos(m3: Modelo3D) -> Modelo3D:
    """Misma geometría, apoyos y resortes, sin casos ni masas."""
    copia = Modelo3D()
    copia._nudos = list(m3._nudos)
    copia._barras = list(m3._barras)
    copia._restricciones = {k: list(v) for k, v in m3._restricciones.items()}
    copia._resortes = dict(m3._resortes)
    return copia
