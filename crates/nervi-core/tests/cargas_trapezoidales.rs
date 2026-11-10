// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación de las cargas trapezoidales y parciales en barras (issue #2).
//!
//! Unidades: kN y m. Fuentes de las soluciones cerradas:
//! - Roark's Formulas for Stress and Strain, 8.ª ed., tabla 8.1 (vigas con cargas
//!   linealmente variables y uniformes parciales).
//! - Las expresiones se comprobaron además integrando `EI v'''' = q` con las
//!   condiciones de borde de cada caso (cálculo simbólico).
//!
//! Los casos de carga parcial en una barra se comparan también con el mismo
//! modelo subdividido en nudos en `a` y `b`, que usa caminos de código
//! independientes (cargas en toda la luz de la sub-barra).

#![allow(clippy::needless_range_loop)]

use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Modelo, TipoCargaBarra,
};

const E: f64 = 2.0e8; // kN/m²
const A: f64 = 0.01; // m²
const I: f64 = 1.0e-4; // m⁴
const TOL: f64 = 1e-9;

fn cerca(calc: f64, esperado: f64, que: &str) {
    let escala = esperado.abs().max(1e-12);
    assert!(
        (calc - esperado).abs() <= TOL * escala,
        "{que}: calculado {calc:e}, esperado {esperado:e}"
    );
}

/// Igualdad relativa a una escala de referencia (para valores que pueden ser cero).
fn cerca_escala(calc: f64, esperado: f64, escala: f64, que: &str) {
    assert!(
        (calc - esperado).abs() <= TOL * escala,
        "{que}: calculado {calc:e}, esperado {esperado:e}"
    );
}

fn trapezoidal(barra: usize, a: f64, b: f64, qy1: f64, qy2: f64) -> CargaBarra {
    CargaBarra {
        barra,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Trapezoidal {
            a,
            b,
            qx1: 0.0,
            qy1,
            qx2: 0.0,
            qy2,
        },
    }
}

/// Viga horizontal de una barra entre (0,0) y (L,0).
fn viga(l: f64) -> Modelo {
    let mut m = Modelo::new();
    let a = m.agregar_nudo(0.0, 0.0);
    let b = m.agregar_nudo(l, 0.0);
    m.agregar_barra(Barra::new(a, b, E, A, I));
    m
}

#[test]
fn trapezoidal_con_intensidad_constante_es_la_uniforme() {
    // q1 = q2 en toda la luz tiene que dar lo mismo que el tipo uniforme, en una
    // barra inclinada con cargas en ejes globales (axil y flexión a la vez).
    let (l, ang) = (5.0, 35f64.to_radians());
    let construir = |tipo: TipoCargaBarra| {
        let mut m = Modelo::new();
        let n0 = m.agregar_nudo(0.0, 0.0);
        let n1 = m.agregar_nudo(l * ang.cos(), l * ang.sin());
        m.agregar_barra(Barra::new(n0, n1, E, A, I));
        m.apoyar(n0, true, true, true);
        m.apoyar(n1, false, true, false);
        let mut c = CasoCarga::new("q");
        c.en_barras.push(CargaBarra {
            barra: 0,
            ejes: Ejes::Global,
            tipo,
        });
        m.agregar_caso(c);
        analizar(&m).unwrap()
    };
    let (qx, qy) = (1.5, -6.0);
    let ru = construir(TipoCargaBarra::Uniforme { qx, qy });
    let rt = construir(TipoCargaBarra::Trapezoidal {
        a: 0.0,
        b: l,
        qx1: qx,
        qy1: qy,
        qx2: qx,
        qy2: qy,
    });
    for n in 0..2 {
        for d in 0..3 {
            let e = ru.casos[0].reacciones[n][d];
            cerca_escala(rt.casos[0].reacciones[n][d], e, 10.0, "reacción");
            let e = ru.casos[0].desplazamientos[n][d];
            cerca_escala(rt.casos[0].desplazamientos[n][d], e, 1e-2, "desplazamiento");
        }
    }
    for k in 0..=10 {
        let x = l * k as f64 / 10.0;
        let (su, st) = (ru.seccion(0, 0, x, false), rt.seccion(0, 0, x, false));
        cerca_escala(st.n, su.n, 10.0, "N");
        cerca_escala(st.v, su.v, 10.0, "V");
        cerca_escala(st.m, su.m, 10.0, "M");
        cerca_escala(st.u_local, su.u_local, 1e-2, "u");
        cerca_escala(st.v_local, su.v_local, 1e-2, "v");
    }
}

#[test]
fn viga_biempotrada_carga_triangular() {
    // Carga de 0 en A a w en B (Roark, tabla 8.1):
    // M_A = -wL²/30, M_B = -wL²/20, R_A = 3wL/20, R_B = 7wL/20, δ(L/2) = wL⁴/768EI.
    let (l, w) = (6.0, 12.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("tri");
    c.en_barras.push(trapezoidal(0, 0.0, l, 0.0, -w));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(r.seccion(0, 0, 0.0, false).m, -w * l * l / 30.0, "M_A");
    cerca(r.seccion(0, 0, l, false).m, -w * l * l / 20.0, "M_B");
    cerca(r.casos[0].reacciones[0][1], 3.0 * w * l / 20.0, "R_A");
    cerca(r.casos[0].reacciones[1][1], 7.0 * w * l / 20.0, "R_B");
    cerca(
        r.seccion(0, 0, l / 2.0, false).v_local,
        -w * l.powi(4) / (768.0 * E * I),
        "flecha a media luz",
    );
}

#[test]
fn viga_biapoyada_carga_triangular() {
    // Carga de 0 en A a w en B (Roark, tabla 8.1): R_A = wL/6, R_B = wL/3,
    // M_máx = wL²/(9√3) en x = L/√3, δ(L/2) = 5wL⁴/768EI.
    let (l, w) = (6.0, 12.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, false);
    m.apoyar(1, false, true, false);
    let mut c = CasoCarga::new("tri");
    c.en_barras.push(trapezoidal(0, 0.0, l, 0.0, -w));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(r.casos[0].reacciones[0][1], w * l / 6.0, "R_A");
    cerca(r.casos[0].reacciones[1][1], w * l / 3.0, "R_B");
    cerca(
        r.seccion(0, 0, l / 2.0, false).v_local,
        -5.0 * w * l.powi(4) / (768.0 * E * I),
        "flecha a media luz",
    );
    // El diagrama tiene que encontrar el momento máximo (cortante nulo), que con
    // carga triangular cae en un punto donde V es cuadrático.
    let x_max = l / 3f64.sqrt();
    let diag = r.diagrama(0, 0, 11);
    let s = diag
        .iter()
        .find(|s| (s.x - x_max).abs() < 1e-9)
        .expect("el diagrama incluye el punto de cortante nulo");
    cerca(s.m, w * l * l / (9.0 * 3f64.sqrt()), "M_máx");
    cerca_escala(s.v, 0.0, w * l, "V en M_máx");
    let m_diag = diag.iter().map(|s| s.m).fold(f64::MIN, f64::max);
    cerca(
        m_diag,
        w * l * l / (9.0 * 3f64.sqrt()),
        "máximo del diagrama",
    );
}

#[test]
fn voladizo_carga_uniforme_parcial_hacia_el_extremo() {
    // Empotrado en x = 0, carga w en [a, L] (Roark, tabla 8.1):
    // δ_punta = w(3L⁴ - 4a³L + a⁴)/24EI, θ_punta = w(L³ - a³)/6EI,
    // M_empotramiento = -w(L² - a²)/2.
    let (l, w, a) = (4.0, 8.0, 1.5);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    let mut c = CasoCarga::new("parcial");
    c.en_barras.push(trapezoidal(0, a, l, -w, -w));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let d = &r.casos[0].desplazamientos[1];
    cerca(
        d[1],
        -w * (3.0 * l.powi(4) - 4.0 * a.powi(3) * l + a.powi(4)) / (24.0 * E * I),
        "flecha en la punta",
    );
    cerca(
        d[2],
        -w * (l.powi(3) - a.powi(3)) / (6.0 * E * I),
        "giro en la punta",
    );
    cerca(
        r.seccion(0, 0, 0.0, false).m,
        -w * (l * l - a * a) / 2.0,
        "M en el empotramiento",
    );
    // En el tramo descargado el cortante es constante e igual a la carga total.
    cerca(
        r.seccion(0, 0, a / 2.0, false).v,
        w * (l - a),
        "V sin carga",
    );
}

#[test]
fn carga_trapezoidal_parcial_igual_al_modelo_subdividido() {
    // Barra biempotrada con carga trapezoidal en [a, b] y axil lineal. Se compara
    // con el mismo modelo con nudos en a y b y la carga en toda la luz de la
    // barra central: esfuerzos y flechas en cualquier sección tienen que coincidir.
    let (l, a, b) = (7.0, 1.8, 5.1);
    let (qx1, qy1, qx2, qy2) = (2.0, -4.0, -1.0, -11.0);
    let carga = |barra, a, b| CargaBarra {
        barra,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Trapezoidal {
            a,
            b,
            qx1,
            qy1,
            qx2,
            qy2,
        },
    };

    let mut m1 = viga(l);
    m1.apoyar(0, true, true, true);
    m1.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("t");
    c.en_barras.push(carga(0, a, b));
    m1.agregar_caso(c);
    let r1 = analizar(&m1).unwrap();

    let mut m3 = Modelo::new();
    let xs = [0.0, a, b, l];
    for x in xs {
        m3.agregar_nudo(x, 0.0);
    }
    for k in 0..3 {
        m3.agregar_barra(Barra::new(k, k + 1, E, A, I));
    }
    m3.apoyar(0, true, true, true);
    m3.apoyar(3, true, true, true);
    let mut c = CasoCarga::new("t");
    c.en_barras.push(carga(1, 0.0, b - a));
    m3.agregar_caso(c);
    let r3 = analizar(&m3).unwrap();

    for d in 0..3 {
        cerca_escala(
            r1.casos[0].reacciones[0][d],
            r3.casos[0].reacciones[0][d],
            50.0,
            "reacción A",
        );
        cerca_escala(
            r1.casos[0].reacciones[1][d],
            r3.casos[0].reacciones[3][d],
            50.0,
            "reacción B",
        );
    }
    for k in 0..=28 {
        let x = l * k as f64 / 28.0;
        let s1 = r1.seccion(0, 0, x, false);
        let (barra, x0) = if x <= a {
            (0, 0.0)
        } else if x <= b {
            (1, a)
        } else {
            (2, b)
        };
        let s3 = r3.seccion(0, barra, x - x0, false);
        cerca_escala(s1.n, s3.n, 50.0, "N");
        cerca_escala(s1.v, s3.v, 50.0, "V");
        cerca_escala(s1.m, s3.m, 50.0, "M");
        cerca_escala(s1.u_local, s3.u_local, 1e-3, "u");
        cerca_escala(s1.v_local, s3.v_local, 1e-3, "v");
    }
}

#[test]
fn carga_axial_lineal_en_barra_biempotrada() {
    // qx de 0 en A a w en B, extremos fijos: R_A = wL/6, R_B = wL/3,
    // N(0) = +wL/6 (tracción), N(L) = -wL/3, u(L/2) = wL²/16EA
    // (de EA u'' = -w x / L con u(0) = u(L) = 0).
    let (l, w) = (5.0, 9.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("ax");
    c.en_barras.push(CargaBarra {
        barra: 0,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Trapezoidal {
            a: 0.0,
            b: l,
            qx1: 0.0,
            qy1: 0.0,
            qx2: w,
            qy2: 0.0,
        },
    });
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(r.casos[0].reacciones[0][0], -w * l / 6.0, "R_A");
    cerca(r.casos[0].reacciones[1][0], -w * l / 3.0, "R_B");
    cerca(r.seccion(0, 0, 0.0, false).n, w * l / 6.0, "N(0)");
    cerca(r.seccion(0, 0, l, false).n, -w * l / 3.0, "N(L)");
    cerca(
        r.seccion(0, 0, l / 2.0, false).u_local,
        w * l * l / (16.0 * E * A),
        "u(L/2)",
    );
}

#[test]
fn carga_trapezoidal_global_en_barra_inclinada_equilibra() {
    // Equilibrio global: la suma de reacciones es la resultante de la carga
    // (trapecio: (q1 + q2)/2 · (b - a)) y el momento respecto del origen se anula.
    let (l, ang, a, b, q1, q2) = (6.0, 25f64.to_radians(), 0.5, 4.0, -3.0, -8.0);
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(l * ang.cos(), l * ang.sin());
    m.agregar_barra(Barra::new(n0, n1, E, A, I));
    m.apoyar(n0, true, true, false);
    m.apoyar(n1, true, true, true);
    let mut c = CasoCarga::new("g");
    c.en_barras.push(CargaBarra {
        barra: 0,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra::Trapezoidal {
            a,
            b,
            qx1: 0.0,
            qy1: q1,
            qx2: 0.0,
            qy2: q2,
        },
    });
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let total = 0.5 * (q1 + q2) * (b - a);
    // Centroide del trapecio medido desde a.
    let xc = (b - a) * (q1 + 2.0 * q2) / (3.0 * (q1 + q2));
    let s = a + xc;
    let reac = &r.casos[0].reacciones;
    cerca_escala(reac[n0][0] + reac[n1][0], 0.0, total.abs(), "ΣRx");
    cerca(reac[n0][1] + reac[n1][1], -total, "ΣRy");
    // Momentos respecto del origen: reacciones + carga (fuerza vertical en x = s cos α).
    let p1 = [l * ang.cos(), l * ang.sin()];
    let mom = reac[n1][2] + p1[0] * reac[n1][1] - p1[1] * reac[n1][0] + s * ang.cos() * total;
    cerca_escala(mom, 0.0, total.abs() * l, "ΣM");
}

#[test]
fn tramo_invalido_se_rechaza() {
    for (a, b) in [(2.0, 2.0), (3.0, 1.0), (-0.1, 1.0), (0.0, 3.5)] {
        let mut m = viga(3.0);
        m.apoyar(0, true, true, true);
        let mut c = CasoCarga::new("x");
        c.en_barras.push(trapezoidal(0, a, b, -1.0, -1.0));
        m.agregar_caso(c);
        assert!(
            matches!(analizar(&m), Err(ErrorNervi::ModeloInvalido(_))),
            "a = {a}, b = {b} debería rechazarse"
        );
    }
}
