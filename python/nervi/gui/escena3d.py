# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometría del visor 3D, sin dependencias gráficas (issue #30).

Arma, con ``numpy`` y a partir de ``modelo.json`` y de un ``ResultadoCaso``, todo
lo que dibuja el visor: barras, nudos, apoyos, cargas, diagramas N/V/M y
deformada, en coordenadas globales 3D. ``vista3d`` solo traduce esto a PyVista.
Separarlo permite probar la geometría sin VTK ni pantalla.

Ejes del visor: Z hacia arriba. El pórtico plano (``portico_2d``) vive en el
plano XZ: el nudo ``(x, y)`` del modelo va a ``(x, 0, y)``. Así, el día que el
modelo tenga nudos con ``z`` (Fase 2a, issue #11), la geometría ya se dibuja en
su lugar sin cambiar el visor; solo falta sumar los diagramas en los dos planos
locales de la barra (ver ``ejes_locales``).

Convenciones de dibujo, las mismas que la vista 2D (``docs/convenciones.md``):
el momento positivo tracciona la fibra ``-y`` local y se dibuja de ese lado; N y
V positivos se dibujan del lado ``+y`` local.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DIAGRAMAS = {"M": "Momento", "V": "Cortante", "N": "Axil", "D": "Deformada"}
#: lado del eje ``y`` local hacia el que se dibuja el valor positivo
LADO = {"M": -1.0, "V": 1.0, "N": 1.0}
#: altura del diagrama más grande, como fracción del tamaño del modelo
ALTURA_DIAGRAMA = 0.16
#: desplazamiento más grande de la deformada, como fracción del tamaño del modelo
ALTURA_DEFORMADA = 0.10
#: largo de la flecha de la carga más grande, como fracción del tamaño del modelo
LARGO_CARGA = 0.12


@dataclass
class Barra:
    id: int
    #: índice de la barra en el motor (``Indices.barras``), ``None`` sin calcular
    indice: int | None
    i: int
    j: int
    p_i: np.ndarray
    p_j: np.ndarray
    #: ejes locales en coordenadas globales (filas x, y, z)
    ejes: np.ndarray

    @property
    def largo(self) -> float:
        return float(np.linalg.norm(self.p_j - self.p_i))


@dataclass
class Apoyo:
    nudo: int
    punto: np.ndarray
    tipo: str  # "empotrado", "articulado" o "deslizante"


@dataclass
class Flecha:
    """Carga dibujada como flecha: ``punta`` es el punto de aplicación."""

    punta: np.ndarray
    #: dirección unitaria de la fuerza
    direccion: np.ndarray
    valor: float
    #: carga distribuida (fuerza por unidad de longitud) o concentrada
    distribuida: bool = False


@dataclass
class Relleno:
    """Parte de un diagrama de un solo signo: franja entre el eje de la barra y el
    borde del diagrama (puntos correspondientes, ``(n, 3)`` cada uno)."""

    barra: int
    signo: int
    eje: np.ndarray
    borde: np.ndarray


@dataclass
class Etiqueta:
    punto: np.ndarray
    valor: float


@dataclass
class Escena:
    nudos: dict[int, np.ndarray]
    barras: list[Barra]
    apoyos: list[Apoyo]
    #: tamaño característico del modelo (mayor lado de la caja que lo contiene)
    tamano: float
    cargas: list[Flecha] = field(default_factory=list)
    rellenos: list[Relleno] = field(default_factory=list)
    etiquetas: list[Etiqueta] = field(default_factory=list)
    deformada: list[np.ndarray] = field(default_factory=list)
    #: valor del diagrama por unidad de longitud dibujada
    escala_diagrama: float = 0.0
    #: factor de amplificación de la deformada
    amplificacion: float = 0.0
    # --- Solo en el edificio (modelo de cálculo generado, #74) ---
    #: piezas del edificio con volumen: ``(n, 8, 3)``, cuatro esquinas de cada
    #: punta (ver :func:`cajas`); columnas, vigas y muros
    cajas: np.ndarray = field(default_factory=lambda: np.zeros((0, 8, 3)))
    #: contorno de cada losa, ``(k, 3)``, a la altura de su piso
    losas: list[np.ndarray] = field(default_factory=list)
    #: brazos rígidos: segmento del nudo a la cara, ``(2, 3)`` cada uno
    brazos: list[np.ndarray] = field(default_factory=list)
    #: maestro de cada diafragma y las líneas que lo unen a sus nudos
    maestros: list[tuple[str, np.ndarray]] = field(default_factory=list)
    diafragmas: list[np.ndarray] = field(default_factory=list)
    #: barras resaltadas (las del elemento elegido del edificio)
    resaltadas: set[int] = field(default_factory=set)
    #: rótulos ``N1``, ``N2``… junto a los nudos (no en el edificio: son miles)
    rotulos_nudos: bool = True
    #: dibujar los nudos (en el edificio con *Mostrar: Edificio* no se dibujan, pero
    #: siguen en :attr:`nudos` para el encuadre y la grilla)
    ver_nudos: bool = True

    @property
    def centro(self) -> np.ndarray:
        if not self.nudos:
            return np.zeros(3)
        p = np.array(list(self.nudos.values()))
        return (p.min(axis=0) + p.max(axis=0)) / 2

    @property
    def es_plano(self) -> bool:
        """Todos los nudos en el plano XZ (pórtico plano)."""
        return all(abs(p[1]) < 1e-12 for p in self.nudos.values())


def punto_3d(nudo: dict) -> np.ndarray:
    """Coordenadas globales del visor. Sin ``z``, el pórtico plano va al plano XZ."""
    if "z" in nudo:
        return np.array([nudo["x"], nudo["y"], nudo["z"]], dtype=float)
    return np.array([nudo["x"], 0.0, nudo["y"]], dtype=float)


def ejes_locales(p_i: np.ndarray, p_j: np.ndarray, plano: bool = True) -> np.ndarray:
    """Ejes locales ``x, y, z`` de la barra, como filas, en coordenadas globales.

    En el pórtico plano, ``y`` local es ``x`` local girado 90° antihorario en el
    plano del pórtico, igual que en el motor (``docs/convenciones.md``), y ``z``
    local sale del plano. Para barras espaciales se usa por ahora la regla
    habitual (``y`` local horizontal; en barras verticales, sobre el eje Y
    global). El eje de referencia definitivo lo fija la barra 3D (issue #11).
    """
    ex = p_j - p_i
    ex = ex / max(float(np.linalg.norm(ex)), 1e-15)
    if plano:
        # (x, y) del modelo -> (X, Z) del visor; giro antihorario en ese plano
        ey = np.array([-ex[2], 0.0, ex[0]])
    else:
        ref = np.array([0.0, 0.0, 1.0])
        if abs(float(ex @ ref)) > 1 - 1e-9:
            ref = np.array([0.0, 1.0, 0.0])
        ey = np.cross(ref, ex)
        ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    return np.vstack([ex, ey, ez])


def _vector_global(modelo: dict, x: float, y: float) -> np.ndarray:
    """Vector global ``(x, y)`` del modelo plano en ejes del visor."""
    return np.array([x, 0.0, y])


def geometria(modelo: dict, indices=None) -> Escena:
    """Barras, nudos y apoyos de ``modelo.json``. ``indices`` es el
    ``formato.modelo.Indices`` del último cálculo (para ubicar resultados)."""
    nudos = {n["id"]: punto_3d(n) for n in modelo.get("nudos", [])}
    plano = all("z" not in n for n in modelo.get("nudos", []))
    barras = []
    for b in modelo.get("barras", []):
        if b["i"] not in nudos or b["j"] not in nudos or b["i"] == b["j"]:
            continue
        p_i, p_j = nudos[b["i"]], nudos[b["j"]]
        indice = indices.barras.get(b["id"]) if indices is not None else None
        barras.append(
            Barra(b["id"], indice, b["i"], b["j"], p_i, p_j, ejes_locales(p_i, p_j, plano))
        )
    apoyos = []
    for a in modelo.get("apoyos", []):
        if a["nudo"] not in nudos:
            continue
        if a.get("ux") and a.get("uy") and a.get("rz"):
            tipo = "empotrado"
        elif a.get("ux") and a.get("uy"):
            tipo = "articulado"
        else:
            tipo = "deslizante"
        apoyos.append(Apoyo(a["nudo"], nudos[a["nudo"]], tipo))
    if nudos:
        p = np.array(list(nudos.values()))
        tamano = float(max((p.max(axis=0) - p.min(axis=0)).max(), 1e-9))
    else:
        tamano = 1.0
    return Escena(nudos, barras, apoyos, tamano)


def factores_de(modelo: dict, nombre: str) -> dict[str, float]:
    """Factor de cada caso en el caso o la combinación ``nombre``."""
    for c in modelo.get("combinaciones", []):
        if c["nombre"] == nombre:
            return dict(c["factores"])
    return {nombre: 1.0} if any(c["nombre"] == nombre for c in modelo.get("casos", [])) else {}


def cargas(escena: Escena, modelo: dict, nombre: str) -> list[Flecha]:
    """Flechas de las cargas nodales y en barra del caso o la combinación
    ``nombre``, ya multiplicadas por sus factores y sumadas cuando caen en el
    mismo punto. Las cargas distribuidas se dibujan como una fila de flechas;
    térmicas y momentos no llevan flecha."""
    factores = factores_de(modelo, nombre)
    por_id = {
        c["id"]: factores[c["nombre"]] for c in modelo.get("casos", []) if c["nombre"] in factores
    }
    barras = {b.id: b for b in escena.barras}
    crudas: list[tuple[np.ndarray, np.ndarray, bool]] = []  # (punto, vector, distribuida)
    for c in modelo.get("cargas_nodales", []):
        f = por_id.get(c["caso"])
        if f is None or c["nudo"] not in escena.nudos:
            continue
        v = _vector_global(modelo, c.get("fx", 0.0), c.get("fy", 0.0)) * f
        crudas.append((escena.nudos[c["nudo"]], v, False))
    for c in modelo.get("cargas_barra", []):
        f = por_id.get(c["caso"])
        b = barras.get(c["barra"])
        if f is None or b is None or c["tipo"] in ("termica", "momento"):
            continue

        def vector(qx: float, qy: float, b=b, c=c, f=f) -> np.ndarray:
            if c["ejes"] == "local":
                return (qx * b.ejes[0] + qy * b.ejes[1]) * f
            return _vector_global(modelo, qx, qy) * f

        L = b.largo
        if c["tipo"] == "puntual":
            a = c.get("a", 0.0)
            crudas.append(
                (b.p_i + b.ejes[0] * a, vector(c.get("px", 0.0), c.get("py", 0.0)), False)
            )
            continue
        if c["tipo"] == "uniforme":
            a, fin = 0.0, L
            q1 = q2 = (c.get("qx", 0.0), c.get("qy", 0.0))
        else:  # trapezoidal
            a, fin = c.get("a", 0.0), c.get("b", L)
            q1 = (c.get("qx1", 0.0), c.get("qy1", 0.0))
            q2 = (c.get("qx2", 0.0), c.get("qy2", 0.0))
        n = max(2, round(9 * (fin - a) / max(L, 1e-12)) + 1)
        for s in np.linspace(0.0, 1.0, n):
            qx = q1[0] + (q2[0] - q1[0]) * s
            qy = q1[1] + (q2[1] - q1[1]) * s
            crudas.append((b.p_i + b.ejes[0] * (a + (fin - a) * s), vector(qx, qy), True))
    # Cargas en el mismo punto (por ejemplo D y L en la misma viga) se suman en una flecha.
    suma: dict[tuple, list] = {}
    for punto, v, distribuida in crudas:
        clave = (*np.round(punto / escena.tamano, 9), distribuida)
        if clave in suma:
            suma[clave][1] = suma[clave][1] + v
        else:
            suma[clave] = [punto, v, distribuida]
    flechas = []
    for punto, v, distribuida in suma.values():
        valor = float(np.linalg.norm(v))
        if valor > 1e-12:
            flechas.append(Flecha(punto, v / valor, valor, distribuida))
    return flechas


def diagrama(escena: Escena, resultado, clave: str, valores: bool = True) -> None:
    """Agrega a ``escena`` el diagrama ``clave`` (``N``, ``V`` o ``M``) del
    resultado, con la misma escala para todas las barras."""
    barras = [b for b in escena.barras if b.indice is not None]
    maximo = max(
        (float(np.abs(resultado.diagrama(b.indice)[clave]).max()) for b in barras), default=0.0
    )
    escena.rellenos, escena.etiquetas = [], []
    if maximo <= 1e-12:
        escena.escala_diagrama = 0.0
        return
    largo = ALTURA_DIAGRAMA * escena.tamano / maximo
    escena.escala_diagrama = largo
    lado = LADO[clave]
    for b in barras:
        d = resultado.diagrama(b.indice)
        xs = d["x"] / max(float(d["x"][-1]), 1e-12) * b.largo
        vals = np.asarray(d[clave], dtype=float)
        eje = b.p_i + np.outer(xs, b.ejes[0])
        for signo in (1, -1):
            parte = np.where(signo * vals > 0, vals, 0.0)
            if not np.any(parte):
                continue
            borde = eje + np.outer(lado * parte * largo, b.ejes[1])
            escena.rellenos.append(Relleno(b.id, signo, eje, borde))
        if valores:
            for idx in sorted({int(np.argmax(vals)), int(np.argmin(vals)), 0, len(vals) - 1}):
                v = float(vals[idx])
                if abs(v) < 0.005 * maximo:
                    continue
                punto = eje[idx] + b.ejes[1] * (lado * v * largo)
                escena.etiquetas.append(Etiqueta(punto, v))


def deformada(escena: Escena, resultado) -> None:
    """Agrega a ``escena`` la deformada amplificada de cada barra."""
    barras = [b for b in escena.barras if b.indice is not None]
    maximo = max(
        (
            float(
                np.hypot(resultado.diagrama(b.indice)["u"], resultado.diagrama(b.indice)["v"]).max()
            )
            for b in barras
        ),
        default=0.0,
    )
    escena.deformada = []
    if maximo <= 1e-15:
        escena.amplificacion = 0.0
        return
    amplif = ALTURA_DEFORMADA * escena.tamano / maximo
    escena.amplificacion = amplif
    for b in barras:
        d = resultado.diagrama(b.indice)
        xs = d["x"] / max(float(d["x"][-1]), 1e-12) * b.largo
        puntos = (
            b.p_i + np.outer(xs + d["u"] * amplif, b.ejes[0]) + np.outer(d["v"] * amplif, b.ejes[1])
        )
        escena.deformada.append(puntos)


def armar(
    modelo: dict,
    resultado=None,
    indices=None,
    clave: str = "M",
    nombre: str = "",
    valores: bool = True,
) -> Escena:
    """Escena completa: geometría, cargas de ``nombre`` y, si hay resultado,
    el diagrama ``clave`` o la deformada (``"D"``)."""
    escena = geometria(modelo, indices if resultado is not None else None)
    if nombre:
        escena.cargas = cargas(escena, modelo, nombre)
    if resultado is not None:
        if clave == "D":
            deformada(escena, resultado)
        elif clave in LADO:
            diagrama(escena, resultado, clave, valores)
    return escena


# --- Edificio: el modelo de cálculo generado y sus piezas (#74) ------------------------
#: Qué se ve del edificio en 3D: sus piezas, el modelo de cálculo o los dos.
MOSTRAR = {"edificio": "Edificio", "calculo": "Cálculo", "ambos": "Ambos"}
#: Esfuerzo del pórtico espacial que dibuja cada diagrama: el del plano ``x-y`` local,
#: que en las vigas es el de flexión vertical (``y`` local hacia arriba).
ESFUERZO_3D = {"M": "Mz", "V": "Vy", "N": "N"}
#: Con más barras que esto, los diagramas del edificio van sin rótulos.
MAX_ROTULOS = 300
#: Elementos del edificio cuyos diagramas llevan rótulos (los demás quedan sin
#: números para que se lean): momento y cortante en vigas, axil en columnas y muros.
ROTULOS_EN = {"M": ("vigas",), "V": ("vigas",), "N": ("columnas", "muros")}


def cajas(a: np.ndarray, b: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Prismas de eje ``a`` -> ``b`` (``(n, 3)``) con medio ancho ``u`` y medio alto
    ``v`` (vectores ``(n, 3)``): ``(n, 8, 3)``, las cuatro esquinas en ``a`` y luego
    las cuatro en ``b``, en el mismo orden."""
    esquinas = (-u - v, u - v, u + v, -u + v)
    return np.stack([a + e for e in esquinas] + [b + e for e in esquinas], axis=1)


def piezas_edificio(mf) -> tuple[np.ndarray, list[np.ndarray]]:
    """Cajas de columnas, vigas y muros y contornos de las losas de ``mf``
    (:class:`nervi.fisico.ModeloFisico`), en su unidad de longitud. Las columnas
    circulares se dibujan como un prisma de lado ``d``; la viga cuelga de su nivel."""
    from ..reparto import A_METROS

    mm = 1e-3 / A_METROS[mf.longitud]
    nivel = {p["id"]: p["nivel"] for p in mf.lista("pisos")}
    secs = {s["id"]: s for s in mf.lista("secciones")}

    def bh(sid):
        s = secs[sid]
        return (s["d"], s["d"]) if s["forma"] == "circular" else (s["b"], s["h"])

    partes = []
    cols = mf.lista("columnas")
    if cols:
        p = np.array([c["punto"] for c in cols], dtype=float)
        z1 = np.array([nivel[c["desde"]] for c in cols])
        z2 = np.array([nivel[c["hasta"]] for c in cols])
        d = np.array([bh(c["seccion"]) for c in cols], dtype=float) * mm / 2
        a = np.radians([c.get("angulo") or 0.0 for c in cols])
        u = np.column_stack([np.cos(a), np.sin(a), np.zeros(len(a))]) * d[:, :1]
        v = np.column_stack([-np.sin(a), np.cos(a), np.zeros(len(a))]) * d[:, 1:]
        partes.append(cajas(np.column_stack([p, z1]), np.column_stack([p, z2]), u, v))
    for lista, alto in (("vigas", True), ("muros", False)):
        els = mf.lista(lista)
        if not els:
            continue
        p1 = np.array([e["p1"] for e in els], dtype=float)
        p2 = np.array([e["p2"] for e in els], dtype=float)
        t = p2 - p1
        t /= np.maximum(np.linalg.norm(t, axis=1), 1e-12)[:, None]
        n = np.column_stack([-t[:, 1], t[:, 0], np.zeros(len(t))])
        if alto:
            z = np.array([nivel[e["piso"]] for e in els], dtype=float)
            d = np.array([bh(e["seccion"]) for e in els], dtype=float) * mm
            u = n * (d[:, :1] / 2)
            # Del nivel hacia abajo: medio alto alrededor de z - h/2.
            v = np.column_stack([np.zeros((len(z), 2)), d[:, 1] / 2])
            zc = z - d[:, 1] / 2
            a, b = np.column_stack([p1, zc]), np.column_stack([p2, zc])
        else:
            z1 = np.array([nivel[e["desde"]] for e in els], dtype=float)
            z2 = np.array([nivel[e["hasta"]] for e in els], dtype=float)
            esp = np.array([e["espesor"] for e in els], dtype=float) * mm
            u = n * (esp[:, None] / 2)
            v = np.column_stack([np.zeros((len(z1), 2)), (z2 - z1) / 2])
            zc = (z1 + z2) / 2
            a, b = np.column_stack([p1, zc]), np.column_stack([p2, zc])
        partes.append(cajas(a, b, u, v))
    losas = [
        np.column_stack(
            [
                np.asarray(lo["contorno"], dtype=float),
                np.full(len(lo["contorno"]), nivel[lo["piso"]]),
            ]
        )
        for lo in mf.lista("losas")
    ]
    todas = np.concatenate(partes) if partes else np.zeros((0, 8, 3))
    return todas, losas


def edificio(mc, mf=None, resultados=None, mostrar: str = "ambos") -> Escena:
    """Escena del edificio: el modelo de cálculo generado ``mc``
    (:class:`nervi.idealizacion.ModeloCalculo`) con sus brazos rígidos, diafragmas y
    empotramientos, y las piezas de ``mf`` según ``mostrar`` (:data:`MOSTRAR`). Con
    ``resultados`` (``Resultados3D``), los ejes locales de cada barra son los del
    motor; si no, los de la regla habitual."""
    coords = mc.modelo.arreglos()["coords"] if mc.n_barras else np.zeros((0, 3))
    conect = np.array([b["nudos"] for b in mc.modelo._barras], dtype=np.int64).reshape(-1, 2)
    n_fisicos = len(mc.nudos)
    calculo = mostrar in ("calculo", "ambos")
    nudos = {k: coords[k] for k in range(n_fisicos)}
    barras = []
    for k, (i, j) in enumerate(conect.tolist()):
        p_i, p_j = coords[i], coords[j]
        ejes = resultados.ejes[k] if resultados is not None else ejes_locales(p_i, p_j, plano=False)
        barras.append(Barra(k, k, i, j, p_i, p_j, ejes))
    apoyos = [Apoyo(n, coords[n], "empotrado") for n in mc.apoyos] if calculo else []
    todos = coords[:n_fisicos] if n_fisicos else np.zeros((1, 3))
    tamano = float(max((todos.max(axis=0) - todos.min(axis=0)).max(), 1e-9))
    escena = Escena(nudos, barras, apoyos, tamano, rotulos_nudos=False, ver_nudos=calculo)
    if calculo:
        for k, o in enumerate(mc.origenes):
            b = barras[k]
            for brazo, p, signo in ((o.brazo_i, b.p_i, 1.0), (o.brazo_j, b.p_j, -1.0)):
                if brazo > 0:
                    escena.brazos.append(np.vstack([p, p + signo * brazo * b.ejes[0]]))
        nombres = {nudo: piso for piso, nudo in mc.maestros.items()}
        for maestro, del_piso in mc.modelo.diafragmas:
            centro = coords[maestro]
            escena.maestros.append((str(nombres.get(maestro, "")), centro))
            for n in del_piso:
                escena.diafragmas.append(np.vstack([centro, coords[n]]))
    if mf is not None and mostrar in ("edificio", "ambos"):
        escena.cajas, escena.losas = piezas_edificio(mf)
    return escena


def _por_barra(barra: np.ndarray) -> list[int]:
    """Dónde empieza cada barra en un arreglo de estaciones ordenado por barra."""
    return (np.flatnonzero(np.diff(barra)) + 1).tolist()


def _estaciones(escena: Escena, mc, resultado) -> tuple[dict, np.ndarray, np.ndarray]:
    """Diagramas de todas las barras, el punto de cada estación sobre el eje y los
    ejes locales de su barra (``(n, 3, 3)``). Las estaciones están en la parte
    flexible: se corren el brazo rígido del extremo ``i``."""
    d = resultado.diagramas
    barra = np.asarray(d["barra"], dtype=np.int64)
    p_i = np.array([b.p_i for b in escena.barras]).reshape(-1, 3)
    ejes = np.array([b.ejes for b in escena.barras]).reshape(-1, 3, 3)
    brazo_i = np.array([o.brazo_i for o in mc.origenes], dtype=float)
    x = np.asarray(d["x"], dtype=float) + brazo_i[barra]
    eje = p_i[barra] + x[:, None] * ejes[barra, 0]
    return d, eje, ejes[barra]


def diagrama_edificio(escena: Escena, mc, resultado, clave: str, valores: bool = True) -> None:
    """Agrega a ``escena`` el diagrama ``clave`` (``N``, ``V`` o ``M``, ver
    :data:`ESFUERZO_3D`) de todas las barras del edificio, con una sola escala. Arma
    todas las estaciones juntas con ``numpy`` (sin un bucle por barra)."""
    escena.rellenos, escena.etiquetas = [], []
    d, eje, ejes = _estaciones(escena, mc, resultado)
    vals = np.asarray(d[ESFUERZO_3D[clave]], dtype=float)
    maximo = float(np.abs(vals).max()) if vals.size else 0.0
    if maximo <= 1e-12:
        escena.escala_diagrama = 0.0
        return
    largo = ALTURA_DIAGRAMA * escena.tamano / maximo
    escena.escala_diagrama = largo
    lado = LADO[clave]
    barra = np.asarray(d["barra"], dtype=np.int64)
    cortes = _por_barra(barra)
    for signo in (1, -1):
        parte = np.where(signo * vals > 0, vals, 0.0)
        borde = eje + (lado * parte * largo)[:, None] * ejes[:, 1]
        ids = barra[np.r_[0, cortes]] if barra.size else []
        for b, e, bo, tiene in zip(
            ids,
            np.split(eje, cortes),
            np.split(borde, cortes),
            np.split(parte != 0, cortes),
            strict=True,
        ):
            if tiene.any():
                escena.rellenos.append(Relleno(int(b), signo, e, bo))
    if not valores or len(escena.barras) > MAX_ROTULOS:
        return
    rotuladas = ROTULOS_EN[clave]
    primeras = barra[np.r_[0, cortes]]
    for b, idx in zip(primeras, np.split(np.arange(len(vals)), cortes), strict=True):
        if mc.origenes[int(b)].lista not in rotuladas:
            continue
        v = vals[idx]
        for k in {int(np.argmax(v)), int(np.argmin(v)), 0, len(v) - 1}:
            if abs(v[k]) < 0.05 * maximo:
                continue
            g = idx[k]
            escena.etiquetas.append(
                Etiqueta(eje[g] + ejes[g, 1] * (lado * v[k] * largo), float(v[k]))
            )


def deformada_edificio(escena: Escena, mc, resultado) -> None:
    """Agrega a ``escena`` la deformada amplificada de todas las barras del edificio
    (desplazamientos locales ``u, v, w`` de cada estación)."""
    escena.deformada = []
    d, eje, ejes = _estaciones(escena, mc, resultado)
    u = np.column_stack([d["u"], d["v"], d["w"]])
    maximo = float(np.linalg.norm(u, axis=1).max()) if len(u) else 0.0
    if maximo <= 1e-15:
        escena.amplificacion = 0.0
        return
    amplif = ALTURA_DEFORMADA * escena.tamano / maximo
    escena.amplificacion = amplif
    puntos = eje + amplif * np.einsum("nk,nkj->nj", u, ejes)
    escena.deformada = np.split(puntos, _por_barra(np.asarray(d["barra"])))


def armar_edificio(
    mc,
    mf=None,
    resultados=None,
    resultado=None,
    clave: str = "M",
    mostrar: str = "ambos",
    valores: bool = True,
) -> Escena:
    """Escena completa del edificio (:func:`edificio`) con el diagrama ``clave`` o la
    deformada (``"D"``) de ``resultado`` (``ResultadoCaso3D``), si hay."""
    escena = edificio(mc, mf, resultados, mostrar)
    if resultado is not None and escena.barras:
        if clave == "D":
            deformada_edificio(escena, mc, resultado)
        elif clave in ESFUERZO_3D:
            diagrama_edificio(escena, mc, resultado, clave, valores)
    return escena
