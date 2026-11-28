# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo de cálculo generado desde el modelo físico del edificio (issue #74).

:func:`generar` idealiza un :class:`nervi.fisico.ModeloFisico` en un pórtico espacial
(:class:`nervi.Modelo3D`): columnas y vigas en sus ejes, brazos rígidos de las vigas
hasta la cara de la columna o del muro, un diafragma rígido por cada piso con losas,
empotramientos en la base y las cargas de las losas repartidas a las vigas (#78) más
el peso propio. La geometría, la partición de las barras y el paso de las cargas
están en Rust (``nervi_core::idealizacion``); este módulo arma los datos, pone las
secciones y los materiales y guarda de qué elemento físico sale cada barra, para
devolverle los resultados.

Casos de carga: ``D`` (peso propio de losas y barras más la permanente de las losas)
y ``L`` (sobrecarga).

Provisorio hasta las láminas (Fase 6): un muro es una columna ancha equivalente
sobre su centro, y una viga apoyada en todo su largo sobre un muro no es una barra:
su carga pasa al muro.

>>> import sys; sys.path.insert(0, "examples")
>>> from edificio_fisico import armar
>>> mc = generar(armar())
>>> len(mc.modelo.diafragmas)
3
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import _core
from .modelo3d import Modelo3D, ResultadoCaso3D
from .reparto import A_METROS, PESO_HORMIGON, TOL_RELATIVA
from .secciones import circular, rectangular

#: Casos del modelo generado y de qué casos del reparto de las losas salen.
CASOS = {"D": ("peso_propio", "permanente"), "L": ("sobrecarga",)}
#: Peso específico del acero estructural, kN/m³ (EN 1991-1-1, Anexo A, Tabla A.4).
PESO_ACERO = 78.5
#: Coeficientes de Poisson ``nu`` para ``G = E / (2 (1 + nu))``: hormigón 0.2 (ACI
#: 318-19 R19.2.3) y acero 0.3 (AISC 360-22, Sección B4).
POISSON = {"hormigon": 0.2, "acero": 0.3}
TIPOS = ("columnas", "muros", "vigas")
#: Combinaciones de resistencia con que se calcula el edificio mientras el modelo
#: físico no guarde las suyas: ACI 318-19 §5.3.1, Tabla 5.3.1, ecuaciones (5.3.1a)
#: ``1.4D`` y (5.3.1b) ``1.2D + 1.6L`` (sin cargas de techo, viento ni sismo).
COMBINACIONES = {"1.4D": {"D": 1.4}, "1.2D+1.6L": {"D": 1.2, "L": 1.6}}
#: Esfuerzos que resume :meth:`ModeloCalculo.resumen` por elemento físico.
ESFUERZOS = ("N", "Vy", "Vz", "T", "My", "Mz")

_MOTIVOS = {
    "viga_sobre_muro": "apoya en todo su largo sobre el muro {otro}: su carga pasa al muro",
    "brazos_sin_luz": "tiene un tramo sin luz flexible entre los brazos rígidos: va sin brazos",
}


def modulo_elasticidad(material: dict) -> float:
    """``E`` del material en MPa: el dado o, si falta, el de la norma.

    Hormigón: ``Ec = 4700 √f'c`` (ACI 318-19 §19.2.2.1(b)). Acero: 200 000 MPa
    (AISC 360-22, Glosario y Sección B4)."""
    if material.get("E") is not None:
        return float(material["E"])
    if material["tipo"] == "hormigon":
        return 4700.0 * math.sqrt(material["fc"])
    return 200_000.0


def peso_especifico(material: dict) -> float:
    """Peso específico en kN/m³: el dado o el habitual del tipo de material."""
    if material.get("peso") is not None:
        return float(material["peso"])
    return PESO_HORMIGON if material["tipo"] == "hormigon" else PESO_ACERO


@dataclass(frozen=True)
class OrigenBarra:
    """De qué elemento físico sale una barra: ``lista`` (``"columnas"``, ``"muros"`` o
    ``"vigas"``), ``id`` y tramo ``s0``-``s1`` de su eje (desde ``p1`` en vigas y muros,
    desde la base en columnas, en la unidad de longitud del modelo)."""

    lista: str
    id: int
    s0: float
    s1: float
    brazo_i: float
    brazo_j: float


@dataclass(frozen=True)
class AvisoModelo:
    viga: int
    otro: int | None
    motivo: str

    def texto(self, mf) -> str:
        nombre = mf.elemento("vigas", self.viga).get("nombre") or f"V{self.viga}"
        otro = ""
        if self.otro is not None:
            otro = mf.elemento("muros", self.otro).get("nombre") or f"M{self.otro}"
        return f"{nombre} " + _MOTIVOS[self.motivo].format(otro=otro)


class ModeloCalculo:
    """Modelo de cálculo generado: el :class:`Modelo3D` y de dónde sale cada barra."""

    def __init__(self, modelo, origenes, nudos, apoyos, maestros, niveles, avisos, longitud):
        #: El pórtico espacial, listo para :meth:`Modelo3D.resolver` o ``modal``.
        self.modelo: Modelo3D = modelo
        #: ``origenes[barra]``: el elemento físico y el tramo de su eje.
        self.origenes: list[OrigenBarra] = origenes
        #: Coordenadas de los nudos (sin los maestros de los diafragmas).
        self.nudos: np.ndarray = nudos
        self.apoyos: list[int] = apoyos
        #: Piso (``id``) -> nudo maestro de su diafragma.
        self.maestros: dict[int, int] = maestros
        self.niveles: dict[int, float] = niveles
        self.avisos: list[AvisoModelo] = avisos
        self.longitud: str = longitud
        self._de: dict[tuple[str, int], list[int]] = {}
        for k, o in enumerate(origenes):
            self._de.setdefault((o.lista, o.id), []).append(k)

    @property
    def n_barras(self) -> int:
        return len(self.origenes)

    def barras_de(self, lista: str, id: int) -> list[int]:
        """Barras en que se idealizó un elemento, en el orden de su eje (vacía si no
        es una barra, como una viga apoyada sobre un muro)."""
        return list(self._de.get((lista, id), []))

    def diagrama(self, resultado: ResultadoCaso3D, lista: str, id: int) -> dict[str, np.ndarray]:
        """Diagramas de un elemento físico armados con los de sus barras, con ``s``
        (abscisa sobre su eje, desde ``p1`` o la base) en lugar de ``x``. Las barras
        dan sus diagramas en la parte flexible: entre brazos no hay estaciones."""
        partes = []
        for k in self.barras_de(lista, id):
            d = resultado.diagrama(k)
            o = self.origenes[k]
            partes.append({**d, "s": d["x"] + o.s0 + o.brazo_i, "barra": np.full(len(d["x"]), k)})
        if not partes:
            return {}
        claves = [c for c in partes[0] if c != "x"]
        return {c: np.concatenate([p[c] for p in partes]) for c in claves}

    def resumen(self, resultado: ResultadoCaso3D, lista: str) -> dict[str, np.ndarray]:
        """Esfuerzos de cada elemento físico de ``lista`` leídos sobre todas sus barras.

        Devuelve arreglos alineados por elemento, ordenados por ``id``: ``id``,
        ``barras`` (cuántas), y por cada esfuerzo ``E`` de :data:`ESFUERZOS` su valor
        al principio (``E_i``, en ``p1`` o en la base), al final (``E_j``), el máximo
        (``E_max``) y el mínimo (``E_min``) sobre el eje. ``V_max`` es el cortante
        resultante ``hypot(Vy, Vz)`` más grande. En vigas, ``Mz`` es el momento de
        flexión vertical (negativo sobre los apoyos). Sin bucles por barra: agrupa
        las estaciones de todas las barras con ``numpy``."""
        d = resultado.diagramas
        barra = np.asarray(d["barra"], dtype=np.int64)
        de_lista = np.array([o.lista == lista for o in self.origenes], dtype=bool)
        ids_barra = np.array([o.id for o in self.origenes], dtype=np.int64)
        inicio = np.array([o.s0 + o.brazo_i for o in self.origenes], dtype=float)
        vacio = {"id": np.zeros(0, dtype=np.int64), "barras": np.zeros(0, dtype=np.int64)}
        for e in ESFUERZOS:
            for sufijo in ("_i", "_j", "_max", "_min"):
                vacio[e + sufijo] = np.zeros(0)
        vacio["V_max"] = np.zeros(0)
        if not de_lista.any() or barra.size == 0:
            return vacio
        sel = de_lista[barra]
        if not sel.any():
            return vacio
        b = barra[sel]
        elemento = ids_barra[b]
        s = np.asarray(d["x"], dtype=float)[sel] + inicio[b]
        orden = np.lexsort((s, elemento))
        elemento = elemento[orden]
        ids, primero, cuantas = np.unique(elemento, return_index=True, return_counts=True)
        ultimo = primero + cuantas - 1
        salida = {"id": ids}
        salida["barras"] = np.bincount(
            np.searchsorted(ids, ids_barra[de_lista]), minlength=len(ids)
        ).astype(np.int64)
        for e in ESFUERZOS:
            v = np.asarray(d[e], dtype=float)[sel][orden]
            salida[e + "_i"] = v[primero]
            salida[e + "_j"] = v[ultimo]
            salida[e + "_max"] = np.maximum.reduceat(v, primero)
            salida[e + "_min"] = np.minimum.reduceat(v, primero)
        v = np.hypot(np.asarray(d["Vy"])[sel], np.asarray(d["Vz"])[sel])[orden]
        salida["V_max"] = np.maximum.reduceat(v, primero)
        return salida


def _tolerancia(mf) -> float:
    datos = mf._datos
    uno = 1.0 / A_METROS[mf.longitud]
    coords = [abs(x) for c in datos["columnas"] for x in c["punto"]]
    coords += [abs(x) for v in datos["vigas"] for x in (*v["p1"], *v["p2"])]
    coords += [abs(x) for m in datos["muros"] for x in (*m["p1"], *m["p2"])]
    coords += [abs(p["nivel"]) for p in datos["pisos"]]
    return TOL_RELATIVA * max(max(coords, default=0.0), uno)


def generar(mf, *, peso_propio: bool = True, tol: float | None = None) -> ModeloCalculo:
    """Genera el modelo de cálculo de ``mf`` (:class:`nervi.fisico.ModeloFisico`).

    Unidades del modelo generado: kN y la unidad de longitud del modelo físico.
    ``peso_propio=False`` deja afuera el peso de las barras (no el de las losas, que
    viene del reparto)."""
    datos = mf._datos
    a_m = A_METROS[mf.longitud]
    mm = 1e-3 / a_m  # un mm en la unidad del modelo
    nivel = {p["id"]: p["nivel"] for p in datos["pisos"]}
    pisos = sorted(nivel, key=nivel.get)
    indice_nivel = {p: k for k, p in enumerate(pisos)}
    secciones = {s["id"]: s for s in datos["secciones"]}
    materiales = {m["id"]: m for m in datos["materiales"]}
    columnas, muros, vigas = datos["columnas"], datos["muros"], datos["vigas"]

    def dims(s):
        if s["forma"] == "circular":
            return s["d"] * mm, s["d"] * mm, 1.0
        return s["b"] * mm, s["h"] * mm, 0.0

    f_col = np.array(
        [
            [
                *c["punto"],
                nivel[c["desde"]],
                nivel[c["hasta"]],
                *dims(secciones[c["seccion"]])[:2],
                math.radians(c.get("angulo") or 0.0),
                dims(secciones[c["seccion"]])[2],
            ]
            for c in columnas
        ],
        dtype=float,
    ).reshape(-1, 8)
    f_muro = np.array(
        [
            [*m["p1"], *m["p2"], nivel[m["desde"]], nivel[m["hasta"]], m["espesor"] * mm]
            for m in muros
        ],
        dtype=float,
    ).reshape(-1, 7)
    f_viga = np.array([[*v["p1"], *v["p2"], nivel[v["piso"]]] for v in vigas], dtype=float).reshape(
        -1, 5
    )
    niveles = np.array([nivel[p] for p in pisos], dtype=float)
    con_losa = sorted({indice_nivel[losa["piso"]] for losa in datos["losas"]})

    # Cargas lineales (kN/m del reparto -> kN por unidad de longitud del modelo).
    reparto = mf.repartir_cargas()
    casos = list(CASOS)
    piezas, lineales = reparto._piezas, reparto._lineales
    fila_viga = {v["id"]: k for k, v in enumerate(vigas)}
    fila_muro = {m["id"]: k for k, m in enumerate(muros)}
    # Por apoyo del reparto: tipo (0 viga, 1 muro), fila y nivel.
    destino = np.array(
        [
            [0, fila_viga[id], 0]
            if lista == "vigas"
            else [1, fila_muro[id], indice_nivel[reparto._pisos_apoyo[k]]]
            for k, (lista, id) in enumerate(reparto._apoyos)
        ],
        dtype=float,
    ).reshape(-1, 3)
    apoyo = piezas[:, 1].astype(np.int64) if len(piezas) else np.zeros(0, dtype=np.int64)
    f_tramos = (
        np.column_stack([destino[apoyo], piezas[:, 2:4]]) if len(piezas) else np.zeros((0, 5))
    )
    orden_casos = list(reparto.casos)
    f_cargas = (
        np.stack(
            [lineales[:, [orden_casos.index(x) for x in CASOS[c]], :].sum(axis=1) for c in casos],
            axis=1,
        )
        * a_m
        if len(piezas)
        else np.zeros((0, len(casos), 2))
    )
    props: dict[int, dict] = {}
    areas: dict[tuple[str, int], float] = {}
    pesos: dict[tuple[str, int], float] = {}
    for lista, filas in (("columnas", columnas), ("vigas", vigas), ("muros", muros)):
        for el in filas:
            if lista == "muros":
                area = el["espesor"] * mm * math.dist(el["p1"], el["p2"])
            else:
                sid = el["seccion"]
                if sid not in props:
                    b, h, circ = dims(secciones[sid])
                    props[sid] = circular(b) if circ else rectangular(b, h)
                area = props[sid]["A"]
            areas[lista, el["id"]] = area
            # kN/m³ · (unidad)² -> kN por unidad de longitud: · a_m³
            pesos[lista, el["id"]] = peso_especifico(materiales[el["material"]]) * area * a_m**3
    if peso_propio and vigas:
        w = np.array([pesos["vigas", v["id"]] for v in vigas])
        largos = np.hypot(f_viga[:, 2] - f_viga[:, 0], f_viga[:, 3] - f_viga[:, 1])
        n = len(vigas)
        pp = np.column_stack([np.zeros(n), np.arange(n), np.zeros(n), np.zeros(n), largos])
        q = np.zeros((n, len(casos), 2))
        q[:, casos.index("D"), :] = w[:, None]
        f_tramos = np.vstack([f_tramos, pp])
        f_cargas = np.concatenate([f_cargas, q])
    if tol is None:
        tol = _tolerancia(mf)
    s = _core.idealizar_edificio(
        _core.VERSION_CONTRATO_IDEALIZACION,
        f_col,
        f_muro,
        f_viga,
        niveles,
        float(niveles[0]) if len(niveles) else 0.0,
        np.array(con_losa, dtype=np.int64),
        f_tramos,
        f_cargas,
        float(tol),
    )

    m = Modelo3D()
    nudos = s["nudos"]
    for p in nudos:
        m.agregar_nudo(*p)
    for c in casos:
        m.caso(c)
    origenes: list[OrigenBarra] = []
    filas_de = {"columnas": columnas, "muros": muros, "vigas": vigas}
    for fila in s["barras"]:
        lista = TIPOS[int(fila[0])]
        el = filas_de[lista][int(fila[1])]
        i, j = int(fila[2]), int(fila[3])
        mat = materiales[el["material"]]
        E = modulo_elasticidad(mat) * 1e3 * a_m**2  # MPa -> kN/(unidad)²
        G = E / (2 * (1 + POISSON[mat["tipo"]]))
        bi, bj = float(fila[6]), float(fila[7])
        if lista == "muros":
            largo = math.dist(el["p1"], el["p2"])
            dx, dy = (el["p2"][0] - el["p1"][0]) / largo, (el["p2"][1] - el["p1"][1]) / largo
            # Columna ancha: el largo del muro sobre y local (en su plano).
            k = m.agregar_barra(
                i, j, E, G, seccion=rectangular(el["espesor"] * mm, largo), referencia=(dx, dy, 0)
            )
        else:
            circ = secciones[el["seccion"]]["forma"] == "circular"
            sec = props[el["seccion"]]
            ref = None
            if lista == "columnas" and not circ:
                # h sobre y local: la dirección girada 90° de la del ancho b.
                a = math.radians(el.get("angulo") or 0.0)
                ref = (-math.sin(a), math.cos(a), 0.0)
            k = m.agregar_barra(
                i, j, E, G, seccion=sec, referencia=ref, brazo_i=bi or None, brazo_j=bj or None
            )
        if peso_propio and lista != "vigas":
            m.carga_uniforme("D", k, qz=-pesos[lista, el["id"]], ejes="global")
        origenes.append(OrigenBarra(lista, el["id"], float(fila[4]), float(fila[5]), bi, bj))
    for n in s["apoyos"]:
        m.apoyar(int(n))
    maestros = {}
    for k_nivel, del_piso in s["diafragmas"]:
        maestros[pisos[k_nivel]] = m.diafragma(list(del_piso))
    # Cargas de barra en bloque, con el mismo formato que Modelo3D.carga_trapezoidal.
    cb = s["cargas_barra"]
    if len(cb):
        filas = np.zeros((len(cb), 12))
        indices = np.array([m._indice_caso(c) for c in casos], dtype=float)
        filas[:, 0] = indices[cb[:, 1].astype(np.int64)]
        filas[:, 1] = cb[:, 0]
        filas[:, 2] = 2  # trapezoidal
        filas[:, 3] = 1  # ejes globales
        filas[:, 4:6] = cb[:, 2:4]
        filas[:, 8] = -cb[:, 4]
        filas[:, 11] = -cb[:, 5]
        m._cargas_barra.extend(map(tuple, filas.tolist()))
    # Cargas en nudos: se suman por nudo y caso antes de pasarlas.
    cn = s["cargas_nudo"]
    if len(cn):
        n_nudos = len(nudos)
        clave = cn[:, 1].astype(np.int64) * n_nudos + cn[:, 0].astype(np.int64)
        unicas, inv = np.unique(clave, return_inverse=True)
        suma = np.zeros((len(unicas), 3))
        np.add.at(suma, inv, cn[:, 2:5])
        for k, (fz, mx, my) in zip(unicas.tolist(), suma.tolist(), strict=True):
            m.carga_nodal(casos[k // n_nudos], k % n_nudos, fz=fz, mx=mx, my=my)
    avisos = [
        AvisoModelo(vigas[v]["id"], None if o is None else muros[o]["id"], mot)
        for v, o, mot in s["avisos"]
    ]
    return ModeloCalculo(
        m,
        origenes,
        nudos,
        [int(n) for n in s["apoyos"]],
        maestros,
        {p: nivel[p] for p in pisos},
        avisos,
        mf.longitud,
    )
