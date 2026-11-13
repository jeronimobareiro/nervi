# SPDX-License-Identifier: GPL-3.0-or-later
"""Solución a mano, independiente del motor, de los casos de ``verification/libros/``.

Cada caso se resuelve con el método clásico que enseña el libro citado en su
archivo ``.toml``: pendiente-deflexión (vigas continuas y pórticos, con
desplazamiento lateral cuando corresponde) o método de los nudos más trabajo
virtual (cerchas). No se usa la matriz de rigidez de Nervi: las ecuaciones se
escriben barra por barra y se resuelven con aritmética exacta (``sympy``).

Uso (``sympy`` no es dependencia de Nervi, solo de esta derivación)::

    pip install sympy
    python verification/libros/derivaciones.py

Imprime los valores que figuran como ``valor`` en cada ``[[esperado]]``.

Convención de la pendiente-deflexión usada acá, la misma de
``docs/convenciones.md`` para giros y momentos de extremo: giros y momentos de
extremo positivos en sentido antihorario,

    M_ij = 2EI/L · (2θ_i + θ_j - 3ψ) + MEP_ij,     ψ = (v_j - v_i)/L,

con ``v`` el desplazamiento transversal en ejes locales de la barra. Fuente:
Hibbeler, *Structural Analysis*, 10.ª ed., §11.1 (allí con signo horario
positivo; acá se usa el antihorario para comparar directamente con Nervi).
"""

from __future__ import annotations

import sympy as sp

R = sp.Rational


# --- Pendiente-deflexión ---------------------------------------------------------
def momentos(EI, L, ti, tj, psi, mep_i=0, mep_j=0):
    """Momentos de extremo antihorarios (M_ij, M_ji) de una barra."""
    k = 2 * sp.sympify(EI) / L
    return k * (2 * ti + tj - 3 * psi) + mep_i, k * (2 * tj + ti - 3 * psi) + mep_j


def mep_uniforme(q, L):
    """Viga biempotrada, carga uniforme q hacia abajo: (M_i, M_j) antihorarios."""
    q, L = sp.sympify(q), sp.sympify(L)
    return q * L**2 / 12, -q * L**2 / 12


def mep_puntual(P, a, L):
    """Viga biempotrada, carga P hacia abajo a la distancia a del nudo i."""
    P, a, L = sp.sympify(P), sp.sympify(a), sp.sympify(L)
    b = L - a
    return P * a * b**2 / L**2, -P * a**2 * b / L**2


def cortantes(Mi, Mj, L, R0i=0, R0j=0):
    """Fuerzas transversales (eje y local) de los nudos sobre la barra.

    ``R0i``, ``R0j``: reacciones hacia +y de la barra simplemente apoyada con
    sus cargas. Equilibrio de momentos de la barra respecto de cada extremo.
    """
    return (Mi + Mj) / L + R0i, -(Mi + Mj) / L + R0j


def mostrar(titulo, valores):
    print(f"\n== {titulo}")
    for nombre, v in valores.items():
        print(f"  {nombre:>28} = {sp.simplify(v)!s:>34} = {float(v): .10g}")


# --- 1. Viga continua de tres tramos ---------------------------------------------
def viga_tres_tramos():
    # A empotrado, B, C y D apoyos simples. Tramos 6, 8 y 5 m; EI constante.
    # AB: 20 kN/m; BC: 60 kN a 3 m de B; CD: 15 kN/m.
    EI = sp.Integer(2 * 10**8) * R(3, 10**4)  # E = 2e8 kN/m², I = 3e-4 m⁴
    tB, tC, tD = sp.symbols("tB tC tD")
    L1, L2, L3 = 6, 8, 5
    MAB, MBA = momentos(EI, L1, 0, tB, 0, *mep_uniforme(20, L1))
    MBC, MCB = momentos(EI, L2, tB, tC, 0, *mep_puntual(60, 3, L2))
    MCD, MDC = momentos(EI, L3, tC, tD, 0, *mep_uniforme(15, L3))
    sol = sp.solve([MBA + MBC, MCB + MCD, MDC], [tB, tC, tD], dict=True)[0]
    s = {k: sp.simplify(v.subs(sol)) for k, v in dict(MAB=MAB, MBA=MBA, MCB=MCB).items()}
    VA, VBa = cortantes(s["MAB"], s["MBA"], L1, 60, 60)
    VBb, VCa = cortantes(-s["MBA"], s["MCB"], L2, R(60 * 5, 8), R(60 * 3, 8))
    VCb, VD = cortantes(-s["MCB"], 0, L3, R(75, 2), R(75, 2))
    mostrar(
        "Viga continua de tres tramos",
        {
            "M_A (reacción, Mz)": s["MAB"],
            "M sección B (barra 0, x=L)": s["MBA"],
            "M sección C (barra 1, x=L)": s["MCB"],
            "Ry A": VA,
            "Ry B": VBa + VBb,
            "Ry C": VCa + VCb,
            "Ry D": VD,
            "θ_B": sol[tB],
            "θ_D": sol[tD],
        },
    )


# --- 2. Viga con asentamiento y voladizo -----------------------------------------
def viga_asentamiento_voladizo():
    # A articulado, B apoyo simple que asienta 12 mm, C apoyo simple, voladizo C-D.
    # Tramos 7 y 7 m, voladizo 2 m. 18 kN/m en AB y BC, 25 kN en la punta D.
    EI = sp.Integer(2 * 10**8) * R(25, 10**5)  # I = 2.5e-4 m⁴
    tA, tB, tC = sp.symbols("tA tB tC")
    L, d, c, P, q = 7, R(-12, 1000), 2, 25, 18
    MAB, MBA = momentos(EI, L, tA, tB, (d - 0) / L, *mep_uniforme(q, L))
    MBC, MCB = momentos(EI, L, tB, tC, (0 - d) / L, *mep_uniforme(q, L))
    MCD = P * c  # voladizo isostático: momento antihorario del nudo C sobre la barra CD
    sol = sp.solve([MAB, MBA + MBC, MCB + MCD], [tA, tB, tC], dict=True)[0]
    s = {k: sp.simplify(v.subs(sol)) for k, v in dict(MBA=MBA, MCB=MCB).items()}
    VA, VBa = cortantes(0, s["MBA"], L, R(q * L, 2), R(q * L, 2))
    VBb, VCa = cortantes(-s["MBA"], s["MCB"], L, R(q * L, 2), R(q * L, 2))
    mostrar(
        "Viga con asentamiento y voladizo",
        {
            "M sección B": s["MBA"],
            "M sección C": s["MCB"],
            "Ry A": VA,
            "Ry B": VBa + VBb,
            "Ry C": VCa + P,  # el voladizo descarga P sobre C
            "θ_A": sol[tA],
        },
    )


# --- 3. Pórtico de columnas desiguales -------------------------------------------
def portico_columnas_desiguales():
    # Nudos: A (0,0) empotrado, B (0,4), C (8,4), D (8,-2) articulado.
    # Columna AB h=4 (Ic), viga BC L=8 (2Ic) con 24 kN/m, columna DC h=6 (Ic).
    # 30 kN horizontal en B. Barras axialmente rígidas: B y C se desplazan Δ.
    E = sp.Integer(2 * 10**8)
    Ic = R(2, 10**4)
    tB, tC, tD, D = sp.symbols("tB tC tD D")
    # Columnas de abajo hacia arriba: v local = -ux ⇒ ψ = -Δ/h.
    MAB, MBA = momentos(E * Ic, 4, 0, tB, -D / 4)
    MBC, MCB = momentos(E * 2 * Ic, 8, tB, tC, 0, *mep_uniforme(24, 8))
    MDC, MCD = momentos(E * Ic, 6, tD, tC, -D / 6)
    # Equilibrio horizontal: reacciones Rx = -(M_i + M_j)/h en cada base, más los 30 kN.
    RxA = -(MAB + MBA) / 4
    RxD = -(MDC + MCD) / 6
    sol = sp.solve([MBA + MBC, MCB + MCD, MDC, RxA + RxD + 30], [tB, tC, tD, D], dict=True)[0]
    v = {
        "M_A (reacción, Mz)": MAB,
        "M sección B, columna (x=h)": MBA,
        "M sección C, columna (x=h)": MCD,
        "Rx A": RxA,
        "Rx D": RxD,
        "Δ (ux de B)": D,
        "θ_D": tD,
    }
    mostrar("Pórtico de columnas desiguales", {k: x.subs(sol) for k, x in v.items()})


# --- 4. Pórtico de dos pisos -----------------------------------------------------
def portico_dos_pisos():
    # Bases A (0,0) y F (6,0) empotradas; piso 1 a 4 m (B, E); piso 2 a 7.5 m (C, D).
    # Columnas Ic, vigas 2Ic. 40 kN en B y 20 kN en C (horizontales);
    # 30 kN/m en la viga BE y 20 kN/m en la viga CD.
    E = sp.Integer(2 * 10**8)
    Ic = R(3, 10**4)
    tB, tC, tD, tE, D1, D2 = sp.symbols("tB tC tD tE D1 D2")
    h1, h2, L = 4, R(7, 2), 6
    MAB, MBA = momentos(E * Ic, h1, 0, tB, -D1 / h1)
    MFE, MEF = momentos(E * Ic, h1, 0, tE, -D1 / h1)
    MBC, MCB = momentos(E * Ic, h2, tB, tC, -(D2 - D1) / h2)
    MED, MDE = momentos(E * Ic, h2, tE, tD, -(D2 - D1) / h2)
    MBE, MEB = momentos(E * 2 * Ic, L, tB, tE, 0, *mep_uniforme(30, L))
    MCD, MDC = momentos(E * 2 * Ic, L, tC, tD, 0, *mep_uniforme(20, L))
    ecuaciones = [
        MBA + MBC + MBE,
        MCB + MCD,
        MDC + MDE,
        MEF + MED + MEB,
        # Corte en el piso 2: -Σ(M_i + M_j)/h2 de sus columnas + 20 = 0.
        -(MBC + MCB + MED + MDE) / h2 + 20,
        # Corte en el piso 1: -Σ(M_i + M_j)/h1 + 40 + 20 = 0.
        -(MAB + MBA + MFE + MEF) / h1 + 60,
    ]
    sol = sp.solve(ecuaciones, [tB, tC, tD, tE, D1, D2], dict=True)[0]
    v = {
        "M_A (reacción, Mz)": MAB,
        "M_F (reacción, Mz)": MFE,
        "Rx A": -(MAB + MBA) / h1,
        "M sección B, viga BE (x=0)": -MBE,
        "M sección E, viga BE (x=L)": MEB,
        "M sección C, viga CD (x=0)": -MCD,
        "Δ1 (ux de B)": D1,
        "Δ2 (ux de C)": D2,
        "θ_C": tC,
    }
    mostrar("Pórtico de dos pisos", {k: x.subs(sol) for k, x in v.items()})


# --- 5. Cercha Pratt ---------------------------------------------------------------
def cercha_pratt():
    # Cordón inferior L0..L4 (x = 0, 3, 6, 9, 12; y = 0), superior U1..U3 (y = 4).
    # L0 articulado, L4 carrito. Cargas hacia abajo: 30 kN en L1, 40 en L2, 20 en L3.
    nudos = {
        "L0": (0, 0), "L1": (3, 0), "L2": (6, 0), "L3": (9, 0), "L4": (12, 0),
        "U1": (3, 4), "U2": (6, 4), "U3": (9, 4),
    }  # fmt: skip
    barras = [
        ("L0", "L1"), ("L1", "L2"), ("L2", "L3"), ("L3", "L4"),
        ("U1", "U2"), ("U2", "U3"),
        ("L0", "U1"), ("U3", "L4"),
        ("L1", "U1"), ("L2", "U2"), ("L3", "U3"),
        ("U1", "L2"), ("L2", "U3"),
    ]  # fmt: skip
    EA = sp.Integer(2 * 10**8) * R(3, 1000)

    def esfuerzos(cargas):
        N = sp.symbols(f"N0:{len(barras)}")
        Ax, Ay, Ey = sp.symbols("Ax Ay Ey")
        ecs = []
        for n, (x, y) in nudos.items():
            fx, fy = (Ax, Ay) if n == "L0" else ((0, Ey) if n == "L4" else (0, 0))
            fy += cargas.get(n, 0)
            for k, (a, b) in enumerate(barras):
                if n in (a, b):
                    o = b if n == a else a
                    dx, dy = nudos[o][0] - x, nudos[o][1] - y
                    largo = sp.sqrt(dx**2 + dy**2)
                    fx += N[k] * dx / largo  # tracción: la barra tira del nudo hacia el otro
                    fy += N[k] * dy / largo
            ecs += [fx, fy]
        sol = sp.solve(ecs, [*N, Ax, Ay, Ey], dict=True)[0]
        return [sol[x] for x in N], sol[Ay], sol[Ey]

    N, Ay, Ey = esfuerzos({"L1": -30, "L2": -40, "L3": -20})
    n, _, _ = esfuerzos({"L2": -1})  # carga virtual unitaria hacia abajo en L2

    def largo(k):
        (x1, y1), (x2, y2) = nudos[barras[k][0]], nudos[barras[k][1]]
        return sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    flecha = sum(N[k] * n[k] * largo(k) / EA for k in range(len(barras)))
    v = {f"N {a}-{b} (barra {k})": N[k] for k, (a, b) in enumerate(barras)}
    v |= {"Ry L0": Ay, "Ry L4": Ey, "uy L2 (trabajo virtual)": -flecha}
    mostrar("Cercha Pratt", v)


if __name__ == "__main__":
    viga_tres_tramos()
    viga_asentamiento_voladizo()
    portico_columnas_desiguales()
    portico_dos_pisos()
    cercha_pratt()
