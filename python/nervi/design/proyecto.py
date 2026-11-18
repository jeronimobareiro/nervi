# SPDX-License-Identifier: GPL-3.0-or-later
"""Diseño de todos los elementos de un proyecto (experimental).

Toma ``modelo.json`` y ``diseno.json`` (``nervi.formato``), decide qué barra es
viga y cuál columna, arma su sección y llama al diseñador de cada tipo. Es lo que
usan la etapa *Diseño* de la interfaz y la memoria de cálculo.

Cada tipo de elemento tiene su diseñador en :data:`DISENADORES`: vigas (ACI 318-19,
#22 y #23) y columnas (#24). Otro tipo se registra igual::

    from nervi.design import proyecto

    def disenar_muro(e: proyecto.Elemento, ctx: proyecto.Contexto) -> proyecto.ResultadoElemento:
        ...

    proyecto.DISENADORES["muro"] = disenar_muro

Mientras un tipo no tenga diseñador, sus barras quedan como *pendientes*.

>>> from nervi.design import proyecto
>>> sorted(proyecto.DISENADORES)
['columna', 'viga']
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field

from ..formato import diseno as _formato_diseno
from ..memoria.documento import Capitulo, Tabla, formatear, tabla_verificaciones
from ..modelo import Resultados
from . import aci318
from .combinaciones import ModuloExperimentalWarning

#: Tipos de elemento que se diseñan.
TIPOS_DISENO = ("viga", "columna")
AVISO_EXPERIMENTAL = (
    "Diseño experimental: implementa métodos de ACI 318-19 y todavía no fue revisado "
    "por un ingeniero estructural. No usar para dimensionar estructuras reales sin "
    "verificar los resultados."
)
_A_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}


@dataclass(frozen=True)
class Verificacion:
    """Una comprobación: ``solicitacion ≤ resistencia`` según ``articulo``."""

    nombre: str
    solicitacion: float
    resistencia: float
    unidad: str
    articulo: str

    @property
    def relacion(self) -> float:
        return abs(self.solicitacion) / self.resistencia if self.resistencia > 0 else math.inf

    @property
    def cumple(self) -> bool:
        return self.relacion <= 1.0 + 1e-9


@dataclass(frozen=True)
class Elemento:
    """Una barra del modelo como elemento de hormigón armado (sección en mm)."""

    barra: int  # id de modelo.json
    indice: int  # índice en el motor
    tipo: str  # "viga", "columna" o "ninguno"
    b: float
    h: float
    #: Longitud en unidades del modelo.
    largo: float
    #: Ancho de los apoyos en cada extremo (mm): canto de las columnas que llegan.
    apoyo_i: float = 0.0
    apoyo_j: float = 0.0
    #: Si el tipo o la sección los puso el usuario (``False``: automáticos).
    tipo_manual: bool = False
    seccion_manual: bool = False


@dataclass
class ResultadoElemento:
    """Lo que devuelve un diseñador para un elemento."""

    elemento: Elemento
    #: ``"cumple"``, ``"no cumple"``, ``"pendiente"`` o ``"error"``.
    estado: str
    #: Armadura elegida, en orden: ``{"Inferior": "3Ø20", "Estribos": "eØ10 c/150 mm"}``.
    armadura: dict[str, str] = field(default_factory=dict)
    verificaciones: list[Verificacion] = field(default_factory=list)
    mensajes: list[str] = field(default_factory=list)
    #: Resultado completo del módulo de la norma (por ejemplo ``DisenoViga``).
    detalle: object = None

    @property
    def relacion(self) -> float | None:
        """La mayor relación solicitación/resistencia (``None`` si no hay)."""
        return max((v.relacion for v in self.verificaciones), default=None)


@dataclass(frozen=True)
class Contexto:
    """Datos comunes a todos los elementos."""

    modelo: dict
    diseno: dict
    resultados: Resultados
    combinaciones: list[str]
    materiales: aci318.Materiales
    fuerza: str
    longitud: str


Disenador = Callable[[Elemento, Contexto], ResultadoElemento]
#: Diseñador de cada tipo de elemento.
DISENADORES: dict[str, Disenador] = {}

_PENDIENTE: dict[str, str] = {}


def seccion_equivalente(A: float, I: float, longitud: str) -> tuple[float, float]:
    """Sección rectangular ``(b, h)`` en mm con el mismo ``A`` e ``I`` que la barra.

    Para un rectángulo ``I = b·h³/12`` y ``A = b·h``, así que ``h = √(12·I/A)``.
    """
    h = math.sqrt(12.0 * I / A)
    f = _A_MM[longitud]
    return round(A / h * f, 1), round(h * f, 1)


def tipo_automatico(dx: float, dy: float) -> str:
    """Viga si la barra está más cerca de la horizontal; columna si no."""
    return "viga" if abs(dx) >= abs(dy) else "columna"


def elementos(modelo: dict, diseno: dict, indices=None) -> list[Elemento]:
    """Elementos del proyecto: lo que dice ``diseno.json`` y lo automático para el resto."""
    nudos = {n["id"]: n for n in modelo["nudos"]}
    longitud = modelo["unidades"]["longitud"]
    propios = {e["barra"]: e for e in diseno.get("elementos", [])}
    previos: list[Elemento] = []
    for k, b in enumerate(modelo["barras"]):
        ni, nj = nudos[b["i"]], nudos[b["j"]]
        dx, dy = nj["x"] - ni["x"], nj["y"] - ni["y"]
        e = propios.get(b["id"], {})
        tipo = e.get("tipo", "auto")
        manual = tipo != "auto"
        if not manual:
            tipo = tipo_automatico(dx, dy)
        bb, hh = seccion_equivalente(b["A"], b["I"], longitud)
        previos.append(
            Elemento(
                barra=b["id"],
                indice=indices.barras[b["id"]] if indices is not None else k,
                tipo=tipo,
                b=float(e.get("b", bb)),
                h=float(e.get("h", hh)),
                largo=math.hypot(dx, dy),
                tipo_manual=manual,
                seccion_manual="b" in e or "h" in e,
            )
        )
    # Ancho de apoyo de las vigas: el canto de las columnas que llegan a cada nudo.
    canto: dict[int, float] = {}
    for b, el in zip(modelo["barras"], previos, strict=True):
        if el.tipo == "columna":
            for n in (b["i"], b["j"]):
                canto[n] = max(canto.get(n, 0.0), el.h)
    salida = []
    for b, el in zip(modelo["barras"], previos, strict=True):
        if el.tipo == "viga":
            el = Elemento(
                **{
                    **el.__dict__,
                    "apoyo_i": canto.get(b["i"], 0.0),
                    "apoyo_j": canto.get(b["j"], 0.0),
                }
            )
        salida.append(el)
    return salida


def materiales(diseno: dict) -> aci318.Materiales:
    acero = diseno["acero"]
    return aci318.Materiales(
        fc=float(diseno["hormigon"]["fc"]), fy=float(acero["fy"]), fyt=acero.get("fyt")
    )


def disenar(
    modelo: dict,
    diseno: dict | None,
    resultados: Resultados,
    indices=None,
) -> list[ResultadoElemento]:
    """Diseña todas las barras con las envolventes de las combinaciones resueltas.

    ``resultados`` tiene que venir de ``Modelo.resolver(combinaciones=...)``; sin
    combinaciones no hay envolventes y se lanza ``ValueError``. ``indices`` es la
    tabla ``id → índice`` de ``formato.construir_modelo``.
    """
    diseno = diseno if diseno is not None else _formato_diseno.nuevo()
    if not resultados.combinaciones:
        raise ValueError(
            "el diseño usa las envolventes de las combinaciones de carga: agregá al menos una"
        )
    u = modelo["unidades"]
    ctx = Contexto(
        modelo=modelo,
        diseno=diseno,
        resultados=resultados,
        combinaciones=list(resultados.combinaciones),
        materiales=materiales(diseno),
        fuerza=u["fuerza"],
        longitud=u["longitud"],
    )
    salida = []
    for el in elementos(modelo, diseno, indices):
        if el.tipo == "ninguno":
            salida.append(ResultadoElemento(el, "pendiente", mensajes=["No se diseña."]))
            continue
        disenador = DISENADORES.get(el.tipo)
        if disenador is None:
            salida.append(
                ResultadoElemento(
                    el, "pendiente", mensajes=[_PENDIENTE.get(el.tipo, "Sin diseñador.")]
                )
            )
            continue
        try:
            salida.append(disenador(el, ctx))
        except ValueError as e:
            salida.append(ResultadoElemento(el, "error", mensajes=[str(e)]))
    return salida


# --- Vigas (ACI 318-19 §9, §22) ----------------------------------------------------------


def disenar_viga(el: Elemento, ctx: Contexto) -> ResultadoElemento:
    """Armadura longitudinal y estribos de una viga con :func:`aci318.disenar_viga`."""
    c = ctx.diseno["criterios"]
    mat = ctx.materiales
    try:
        sec = aci318.SeccionRectangular(
            b=el.b,
            h=el.h,
            recubrimiento=float(c["recubrimiento"]),
            d_estribo=float(c["d_estribo"]),
            d_agregado=float(c["d_agregado"]),
        )
    except ValueError as e:
        return ResultadoElemento(el, "error", mensajes=[f"Sección {el.b:g} × {el.h:g} mm: {e}"])
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        try:
            r = aci318.disenar_viga(
                ctx.resultados,
                el.indice,
                sec,
                mat,
                combinaciones=ctx.combinaciones,
                ancho_apoyo_i=el.apoyo_i,
                ancho_apoyo_j=el.apoyo_j,
                seccion_critica_a_d=bool(c["seccion_critica_a_d"]),
                fuerza=ctx.fuerza,
                longitud=ctx.longitud,
            )
        except ValueError as e:
            return ResultadoElemento(el, "no cumple", mensajes=[_mensaje_falla(str(e))])
    mensajes = [
        str(a.message) for a in avisos if not issubclass(a.category, ModuloExperimentalWarning)
    ]
    armadura: dict[str, str] = {}
    ver: list[Verificacion] = []
    flex = "ACI 318-19 §9.5.1.1, §22.2"
    for nombre, cara, mu, disp in (
        ("Inferior", "M+", r.Mu_pos, r.inferior),
        ("Superior", "M−", -r.Mu_neg, r.superior),
    ):
        if disp is None:
            armadura[nombre] = "no requerida por cálculo"
            continue
        armadura[nombre] = disp.descripcion
        ver.append(Verificacion(f"Flexión {cara}", mu, disp.resistencia.phiMn, "kN·m", flex))
        # §9.6.1.2 con la excepción de §9.6.1.3 (4/3 de la armadura necesaria).
        as_min = aci318.armadura_minima(sec.b, disp.d, mat)
        exigida = max(disp.As_req, min(as_min, 4.0 / 3.0 * disp.As_req))
        ver.append(
            Verificacion(
                f"Armadura mínima {nombre.lower()}",
                exigida,
                disp.As,
                "mm²",
                "ACI 318-19 §9.6.1.2, §9.6.1.3",
            )
        )
        ver.append(
            Verificacion(
                f"Ancho para barras {nombre.lower()}", disp.b_nec, sec.b, "mm", "ACI 318-19 §25.2.1"
            )
        )
    cort = r.cortante
    if r.estribos is not None:
        e = r.estribos
        armadura["Estribos"] = e.descripcion
        ver.append(Verificacion("Cortante", r.Vu, e.phiVn, "kN", "ACI 318-19 §9.5.1.1, §22.5"))
        s_max = aci318.separacion_maxima(e.Vs, sec.b, r.d_cortante, mat)
        ver.append(
            Verificacion("Separación de estribos", e.s, s_max, "mm", "ACI 318-19 §9.7.6.2.2")
        )
    elif cort is not None:
        armadura["Estribos"] = "no requeridos por cálculo"
        ver.append(
            Verificacion(
                "Cortante", r.Vu, cort.phi * cort.Vc, "kN", "ACI 318-19 §9.6.3.1, §22.5.5.1"
            )
        )
    if cort is not None:
        ver.append(
            Verificacion(
                "Límite de la sección", r.Vu, cort.Vu_max_seccion, "kN", "ACI 318-19 §22.5.1.2"
            )
        )
    estado = "cumple" if all(v.cumple for v in ver) else "no cumple"
    return ResultadoElemento(el, estado, armadura, ver, mensajes, r)


def _mensaje_falla(texto: str) -> str:
    return texto[0].upper() + texto[1:] + "." if texto and not texto.endswith(".") else texto


DISENADORES["viga"] = disenar_viga


# --- Columnas (ACI 318-19 §10, §22.4, §6.6.4) ---------------------------------------------


def disenar_columna(el: Elemento, ctx: Contexto) -> ResultadoElemento:
    """Armadura longitudinal de una columna con :func:`aci318.disenar_columna`.

    La sección es el rectángulo ``h`` (en el plano del pórtico, eje ``y`` local de la
    columna) por ``b``; se busca la armadura de menor área con barras en el
    perímetro. Se toma ``k = 1`` y ``lu`` igual al largo de la barra, pórtico no
    desplazable y ``βdns = 1`` (el modelo no dice qué casos son permanentes), que
    es el lado seguro para la rigidez de §6.6.4.4.4.
    """
    if (ctx.fuerza, ctx.longitud) != ("kN", "m"):
        return ResultadoElemento(
            el,
            "pendiente",
            mensajes=[
                "El diseño de columnas necesita el modelo en kN y m; este está en "
                f"{ctx.fuerza} y {ctx.longitud}."
            ],
        )
    c = ctx.diseno["criterios"]
    mat = ctx.materiales
    try:
        sec = aci318.SeccionColumna.rectangular(
            hy=el.h,
            hz=el.b,
            n_y=2,
            n_z=2,
            diametro=16.0,
            recubrimiento=float(c["recubrimiento"]),
            d_estribo=float(c["d_estribo"]),
            d_agregado=float(c["d_agregado"]),
        )
    except ValueError as e:
        return ResultadoElemento(el, "error", mensajes=[f"Sección {el.b:g} × {el.h:g} mm: {e}"])
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        try:
            r = aci318.disenar_columna(
                ctx.resultados,
                el.indice,
                sec,
                mat,
                ctx.combinaciones,
                buscar_armadura=True,
            )
        except ValueError as e:
            return ResultadoElemento(el, "no cumple", mensajes=[_mensaje_falla(str(e))])
    mensajes = list(r.avisos) + [
        str(a.message) for a in avisos if not issubclass(a.category, ModuloExperimentalWarning)
    ]
    sec = r.seccion
    crit = r.critica
    ver: list[Verificacion] = []
    flexo = "ACI 318-19 §10.5.1.1, §22.4"
    mu = math.hypot(crit.Mz, crit.My)
    if mu > 1e-9:
        donde = "con los momentos magnificados" if crit.x is None else f"en x = {crit.x:.3g} m"
        ver.append(Verificacion("Flexocompresión", mu, crit.phiMn, "kN·m", flexo))
        mensajes.insert(0, f"Manda {crit.combinacion} con Pu = {crit.Pu:.4g} kN {donde}.")
    pu_max = max(d.Pu for d in r.demandas)
    if pu_max > 0:
        ver.append(
            Verificacion("Compresión axial", pu_max, r.axial.phiPn_max, "kN", "ACI 318-19 §22.4.2")
        )
    rho = 100.0 * sec.cuantia
    art_rho = "ACI 318-19 §10.6.1.1"
    ver.append(Verificacion("Cuantía mínima", 1.0, rho, "%", art_rho))
    ver.append(Verificacion("Cuantía máxima", rho, 8.0, "%", art_rho))
    # Esbeltez en el plano, en la combinación que manda.
    esb = r.esbeltez.get(crit.combinacion, {}).get("z")
    if esb is not None:
        if esb.esbelta:
            mensajes.append(
                f"Esbelta en el plano: k·lu/r = {esb.esbeltez:.1f} > {esb.limite:.1f} "
                f"(§6.2.5.1); momentos magnificados con δ = {esb.delta:.3f} (§6.6.4.5)."
            )
        else:
            mensajes.append(
                f"Esbeltez en el plano k·lu/r = {esb.esbeltez:.1f} ≤ {esb.limite:.1f} "
                "(§6.2.5.1): no se magnifican los momentos."
            )
    mensajes.append(
        "Supuestos: k = 1, lu = largo de la barra, pórtico no desplazable y βdns = 1. En el "
        "pórtico plano no se revisan la flexión ni la esbeltez fuera del plano. Los estribos "
        "de columnas todavía no se diseñan."
    )
    estado = "cumple" if r.cumple and all(v.cumple for v in ver) else "no cumple"
    return ResultadoElemento(el, estado, {"Longitudinal": sec.descripcion}, ver, mensajes, r)


DISENADORES["columna"] = disenar_columna


# --- Memoria de cálculo ------------------------------------------------------------------


def capitulo_memoria(
    resultados: list[ResultadoElemento],
    diseno: dict,
    nombre_barra: Callable[[int], str] = lambda i: f"B{i}",
    decimal: str = ",",
) -> Capitulo:
    """Capítulo "Diseño de hormigón armado" para :meth:`nervi.memoria.Memoria.agregar`."""
    cap = Capitulo(f"Diseño de hormigón armado ({diseno['norma']})", pagina_nueva=True)
    cap.parrafo(f"<b>{AVISO_EXPERIMENTAL}</b>", "aviso")
    c, mat = diseno["criterios"], materiales(diseno)

    def num(v: float) -> str:
        return formatear(v, decimal=decimal)

    cap.parrafo(
        f"Hormigón f'c = {num(mat.fc)} MPa; armadura longitudinal fy = {num(mat.fy)} MPa; "
        f"estribos fyt = {num(mat.fyt_efectivo)} MPa. Recubrimiento libre "
        f"{num(c['recubrimiento'])} mm hasta el estribo, estribo Ø{num(c['d_estribo'])} y "
        f"agregado de {num(c['d_agregado'])} mm. Las vigas se diseñan a flexión y cortante con "
        "las envolventes de todas las combinaciones; el cortante se toma "
        + (
            "en la sección crítica a d de la cara del apoyo (§9.4.3.2)."
            if c["seccion_critica_a_d"]
            else "en toda la luz."
        )
        + " Las columnas se arman a flexocompresión con la armadura de menor área que "
        "cumple (1 % ≤ ρ ≤ 8 %), con k = 1, lu igual al largo de la barra, pórtico no "
        "desplazable y βdns = 1 para la esbeltez (§6.6.4)."
    )
    filas = []
    for r in resultados:
        el = r.elemento
        if el.tipo == "ninguno":
            continue
        a = r.armadura
        filas.append(
            [
                nombre_barra(el.barra),
                el.tipo.capitalize(),
                f"{num(el.b)} × {num(el.h)}",
                a.get("Inferior", a.get("Longitudinal", "—")),
                a.get("Superior", "—"),
                a.get("Estribos", "—"),
                _ESTADO_TEXTO[r.estado],
            ]
        )
    if filas:
        cap.tabla(
            Tabla(
                [
                    "Elemento",
                    "Tipo",
                    "b × h (mm)",
                    "Inferior o longitudinal",
                    "Superior",
                    "Estribos",
                    "Estado",
                ],
                filas,
                titulo="Armaduras",
                anchos=[0.8, 0.8, 1.0, 1.4, 1.4, 1.7, 0.9],
                alineacion=["izq", "izq", "izq", "izq", "izq", "izq", "centro"],
            )
        )
    verif = [
        (
            nombre_barra(r.elemento.barra),
            f"{v.nombre} ({v.unidad})",
            v.solicitacion,
            v.resistencia,
            v.articulo,
        )
        for r in resultados
        for v in r.verificaciones
    ]
    if verif:
        cap.tabla(tabla_verificaciones(verif, titulo="Verificaciones", decimal=decimal))
    notas = [
        f"{nombre_barra(r.elemento.barra)}: {m}"
        for r in resultados
        if r.elemento.tipo != "ninguno"
        for m in r.mensajes
    ]
    for n in notas:
        cap.parrafo(n, "nota")
    cap.parrafo(
        "No se verifican flechas, fisuración, torsión, anclajes, corte de barras ni "
        "estribos de columnas. "
        "Los artículos citados son de ACI 318-19; la memoria cita el artículo y no "
        "transcribe el texto de la norma.",
        "nota",
    )
    return cap


_ESTADO_TEXTO = {
    "cumple": "Cumple",
    "no cumple": "NO CUMPLE",
    "pendiente": "Pendiente",
    "error": "Error",
}
