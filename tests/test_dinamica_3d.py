# SPDX-License-Identifier: GPL-3.0-or-later
"""Análisis modal y espectro de respuesta desde Python (issues #16, #17 y #18).

Soluciones cerradas: frecuencias de la viga de Euler-Bernoulli simplemente
apoyada ``ωₙ = (nπ/L)² √(EI/m)`` y del edificio de cortante de dos pisos
``ω² = (k/m)(3 ∓ √5)/2`` (Chopra, *Dynamics of Structures*, 4.ª ed., §16.3 y
cap. 10); respuesta espectral de un grado de libertad ``V = M Sa``,
``u = Sa/ω²`` y combinación SRSS (Chopra, §13.2 y §13.7).
"""

import math

import numpy as np
import pytest

import nervi
from nervi import _core

E, G = 2.5e7, 1.0e7


def voladizo_con_masa(M=12.0, h=3.0, Iz=2.0e-3, Iy=3.0e-3):
    m = nervi.Modelo3D()
    a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(0, 0, h)
    m.agregar_barra(a, b, E, G, A=0.16, Iy=Iy, Iz=Iz, J=3e-3)
    m.apoyar(a)
    m.masa_nodal(b, mx=M, my=M, mz=0.0)
    return m, a, b


def test_un_grado_de_libertad_por_direccion():
    M, h, Iz, Iy = 12.0, 3.0, 2.0e-3, 3.0e-3
    m, a, b = voladizo_con_masa(M, h, Iz, Iy)
    modal = m.modal(n_modos=5)
    # En una columna vertical, X flexiona con Iz e Y con Iy.
    wx = math.sqrt(3 * E * Iz / (M * h**3))
    wy = math.sqrt(3 * E * Iy / (M * h**3))
    assert modal.n_modos == 2
    np.testing.assert_allclose(modal.omegas, [wx, wy], rtol=1e-10)
    np.testing.assert_allclose(modal.periodos, 2 * math.pi / modal.omegas, rtol=1e-14)
    np.testing.assert_allclose(modal.masa_total, [M, M, 0.0])
    np.testing.assert_allclose(modal.masa_participante[:, :2], np.eye(2), atol=1e-10)
    assert modal.modos.shape == (2, 2, 6)
    assert "modo" in modal.tabla()

    sa = 4.0
    r = modal.espectro([(0.0, sa), (5.0, sa)], direccion="Y", combinacion="SRSS")
    assert isinstance(r, nervi.ResultadoEspectro3D)
    np.testing.assert_allclose(r.cortante_basal, [0.0, M * sa, 0.0], atol=1e-9)
    np.testing.assert_allclose(r.desplazamientos[b, 1], sa / wy**2, rtol=1e-10)
    np.testing.assert_allclose(r.reacciones[a, 3], M * sa * h, rtol=1e-10)
    d = r.diagrama(0)
    # En la columna, Y global es -z local: el momento de la base es My.
    np.testing.assert_allclose(d["My"], M * sa * (h - d["x"]), rtol=1e-9, atol=1e-9)
    assert np.all(d["Mz"] < 1e-9)


def test_espectro_interpolado_y_direccion_oblicua():
    M = 12.0
    m, _, _ = voladizo_con_masa(M)
    modal = m.modal()
    T = modal.periodos
    espectro = [(0.0, 2.0), (0.1, 8.0), (1.0, 8.0), (3.0, 2.0)]
    r = modal.espectro(espectro, direccion=[1.0, 1.0, 0.0], combinacion="SRSS")
    sa = np.interp(T, [0.0, 0.1, 1.0, 3.0], [2.0, 8.0, 8.0, 2.0])
    np.testing.assert_allclose(r.aceleraciones, sa, rtol=1e-12)
    # Cada modo tiene Γ = √M en su dirección; con r = (1, 1, 0) los dos
    # participan y sus cortantes basales son perpendiculares.
    np.testing.assert_allclose(np.abs(r.factores), math.sqrt(M), rtol=1e-10)
    np.testing.assert_allclose(r.cortante_basal[:2], M * sa, rtol=1e-10)
    np.testing.assert_allclose(r.correlacion, np.eye(2))


def edificio_de_cortante(m=20.0):
    """Dos pisos, una columna por esquina de un rectángulo de 6 x 4 m, vigas
    prácticamente rígidas, masa m por piso solo en X."""
    h, Iz, Iy, J = 3.0, 4.0e-3, 6.0e-3, 1.0e-3
    mod = nervi.Modelo3D()
    esquinas = [(-3, -2), (3, -2), (3, 2), (-3, 2)]
    for p in range(3):
        for x, y in esquinas:
            mod.agregar_nudo(x, y, h * p)
    for k in range(4):
        mod.apoyar(k)
    for p in (1, 2):
        for k in range(4):
            mod.agregar_barra(4 * (p - 1) + k, 4 * p + k, E, G, A=1e4, Iy=Iy, Iz=Iz, J=J)
            mod.agregar_barra(
                4 * p + k, 4 * p + (k + 1) % 4, E * 1e5, G * 1e5, A=1, Iy=1, Iz=1, J=1
            )
            mod.masa_nodal(4 * p + k, mx=m / 4, my=0.0, mz=0.0)
    return mod, 4 * 12 * E * Iz / h**3


def test_edificio_de_cortante_de_dos_pisos():
    m = 20.0
    mod, k = edificio_de_cortante(m)
    modal = mod.modal(n_modos=8, metodo="denso")
    en_x = modal.masas_efectivas[:, 0] > 1e-6 * m
    assert en_x.sum() == 2
    w = modal.omegas[en_x]
    raiz5 = math.sqrt(5)
    np.testing.assert_allclose(
        w, [math.sqrt((3 - raiz5) / 2 * k / m), math.sqrt((3 + raiz5) / 2 * k / m)], rtol=1e-5
    )
    np.testing.assert_allclose(modal.masas_efectivas[en_x, 0].sum(), 2 * m, rtol=1e-9)
    # Primer modo: φ2/φ1 = número de oro.
    phi = modal.modos[np.argmax(en_x)]
    np.testing.assert_allclose(phi[8, 0] / phi[4, 0], (1 + raiz5) / 2, rtol=1e-5)
    # Lanczos da lo mismo.
    lz = mod.modal(n_modos=8, metodo="lanczos")
    assert lz.metodo == "lanczos"
    np.testing.assert_allclose(lz.omegas, modal.omegas, rtol=1e-6)


def test_cqc_con_modos_cercanos_supera_a_srss():
    m = 20.0
    mod, _ = edificio_de_cortante(m)
    modal = mod.modal(n_modos=8)
    esp = [(0.0, 3.0), (10.0, 3.0)]
    srss = modal.espectro(esp, "X", combinacion="SRSS")
    cqc = modal.espectro(esp, "X", combinacion="CQC", amortiguamiento=0.05)
    # Los dos modos en X están bien separados (ω2/ω1 = 2.6): CQC ≈ SRSS.
    np.testing.assert_allclose(cqc.cortante_basal[0], srss.cortante_basal[0], rtol=0.02)
    assert np.allclose(np.diag(cqc.correlacion), 1.0)
    assert np.allclose(cqc.correlacion, cqc.correlacion.T)


def test_masa_consistente_de_viga_simplemente_apoyada():
    L, n, mu, Iz = 6.0, 12, 0.1, 2.0e-4
    m = nervi.Modelo3D()
    for k in range(n + 1):
        m.agregar_nudo(L * k / n, 0, 0)
    for k in range(n):
        b = m.agregar_barra(k, k + 1, 2e8, 8e7, A=0.2, Iy=0.05, Iz=Iz, J=1.0)
        m.masa_lineal(b, mu)
    m.apoyar(0, rx=True, ry=False, rz=False)
    m.apoyar(n, ux=False, rx=False, ry=False, rz=False)
    modal = m.modal(n_modos=2, masa="consistente")
    esperadas = [(j * math.pi / L) ** 2 * math.sqrt(2e8 * Iz / mu) for j in (1, 2)]
    np.testing.assert_allclose(modal.omegas, esperadas, rtol=2e-4)


def test_masa_desde_casos_de_carga():
    # Columna con 98.0665 kN de carga permanente y 40 kN de sobrecarga en la
    # punta: con D + 0.25 L la masa es (98.0665 + 10) / 9.80665.
    m, _, b = voladizo_con_masa(M=0.0)
    m.carga_nodal("D", b, fz=-98.0665)
    m.carga_nodal("L", b, fz=-40.0)
    m.masa_desde_casos({"D": 1.0, "L": 0.25})
    modal = m.modal()
    masa = (98.0665 + 10.0) / 9.80665
    np.testing.assert_allclose(modal.masa_total, [masa, masa, masa], rtol=1e-12)
    with pytest.raises(ValueError, match="inexistente"):
        m.masa_desde_casos({"W": 1.0})
        m.modal()


def test_errores():
    m, _, _ = voladizo_con_masa()
    with pytest.raises(ValueError):
        m.modal(masa="rara")
    with pytest.raises(ValueError):
        m.modal(n_modos=0)
    modal = m.modal()
    with pytest.raises(ValueError):
        modal.espectro([(0.0, 1.0)], direccion="W")
    with pytest.raises(ValueError):
        modal.espectro([(1.0, 1.0), (0.5, 1.0)])
    with pytest.raises(ValueError):
        modal.espectro([(0.0, 1.0)], combinacion="ABS")
    with pytest.raises(ValueError):
        modal.espectro([(0.0, 1.0)], amortiguamiento=1.5)
    sin_masa = nervi.Modelo3D()
    p, q = sin_masa.agregar_nudo(0, 0, 0), sin_masa.agregar_nudo(1, 0, 0)
    sin_masa.agregar_barra(p, q, E, G, A=0.1, Iy=1e-3, Iz=1e-3, J=1e-3)
    sin_masa.apoyar(p)
    with pytest.raises(ValueError, match="masa"):
        sin_masa.modal()
    # Mecanismo: el mismo modelo sin apoyos.
    suelto = nervi.Modelo3D()
    p, q = suelto.agregar_nudo(0, 0, 0), suelto.agregar_nudo(1, 0, 0)
    suelto.agregar_barra(p, q, E, G, A=0.1, Iy=1e-3, Iz=1e-3, J=1e-3)
    suelto.masa_nodal(q, 1.0)
    with pytest.raises(nervi.MecanismoError):
        suelto.modal()
    with pytest.raises(ValueError, match="versión"):
        _core.resolver_modal_3d(
            99, m.arreglos(), np.zeros((2, 6)), np.zeros(1), np.zeros(0), 9.8, 0, 1
        )
