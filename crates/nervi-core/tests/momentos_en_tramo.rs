// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación de los momentos concentrados en el tramo de una barra (issue #3).
//!
//! Unidades: kN y m. Momento antihorario positivo. Fuentes de las soluciones
//! cerradas:
//! - Viga biempotrada con momento concentrado `M0` en `a` (`b = L - a`):
//!   `R_A = 6·M0·a·b/L³`, `M_A = -M0·b·(b - 2a)/L²`, `M_B = -M0·a·(a - 2b)/L²`
//!   (Ghali, Neville y Brown, Structural Analysis: A Unified Classical and Matrix
//!   Approach, 6.ª ed., apéndice D; Roark's Formulas for Stress and Strain,
//!   8.ª ed., tabla 8.1, caso 3e). Con `a = L/2`: `M0/4` en cada extremo.
//! - Voladizo con momento en `a`: flecha en el extremo libre
//!   `M0·a·(2L - a)/(2EI)` (integración directa de `EI v'' = M`, con `M = M0`
//!   en `[0, a]` y cero después).
//!
//! Además se compara con el mismo modelo con un nudo en `a` y el momento como
//! carga nodal, que usa caminos de código independientes.

use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Modelo, TipoCargaBarra,
};

const E: f64 = 2.0e8; // kN/m²
const A: f64 = 0.01; // m²
const I: f64 = 1.0e-4; // m⁴
const TOL: f64 = 1e-9;

fn cerca_escala(calc: f64, esperado: f64, escala: f64, que: &str) {
    assert!(
        (calc - esperado).abs() <= TOL * escala,
        "{que}: calculado {calc:e}, esperado {esperado:e}"
    );
}

fn momento(barra: usize, a: f64, mz: f64, ejes: Ejes) -> CargaBarra {
    CargaBarra {
        barra,
        ejes,
        tipo: TipoCargaBarra::Momento { a, mz },
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
fn viga_biempotrada_momento_en_el_centro_y_en_un_tercio() {
    let (l, m0) = (6.0, 30.0);
    for a in [l / 2.0, l / 3.0, 0.8] {
        let b = l - a;
        let mut m = viga(l);
        m.apoyar(0, true, true, true);
        m.apoyar(1, true, true, true);
        let mut c = CasoCarga::new("m");
        c.en_barras.push(momento(0, a, m0, Ejes::Local));
        m.agregar_caso(c);
        let r = analizar(&m).unwrap();
        let reac = &r.casos[0].reacciones;
        let ra = 6.0 * m0 * a * b / l.powi(3);
        cerca_escala(reac[0][1], ra, m0, "R_A");
        cerca_escala(reac[1][1], -ra, m0, "R_B");
        cerca_escala(reac[0][2], -m0 * b * (b - 2.0 * a) / (l * l), m0, "M_A");
        cerca_escala(reac[1][2], -m0 * a * (a - 2.0 * b) / (l * l), m0, "M_B");
        cerca_escala(reac[0][0], 0.0, m0, "H_A");
        // Equilibrio de momentos respecto de A.
        let suma = reac[0][2] + reac[1][2] + m0 + reac[1][1] * l;
        cerca_escala(suma, 0.0, m0, "ΣM_A");
    }
    // Centro: M0/4 en cada empotramiento, con el mismo signo.
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("m");
    c.en_barras.push(momento(0, l / 2.0, m0, Ejes::Local));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca_escala(r.casos[0].reacciones[0][2], m0 / 4.0, m0, "M_A centro");
    cerca_escala(r.casos[0].reacciones[1][2], m0 / 4.0, m0, "M_B centro");
}

#[test]
fn salto_del_diagrama_igual_al_momento_aplicado() {
    let (l, a, m0) = (5.0, 2.0, -18.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, false);
    m.apoyar(1, false, true, false);
    let mut c = CasoCarga::new("m");
    c.en_barras.push(momento(0, a, m0, Ejes::Local));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let izq = r.seccion(0, 0, a, false);
    let der = r.seccion(0, 0, a, true);
    // Un par antihorario aplicado a la izquierda del corte resta al momento.
    cerca_escala(der.m - izq.m, -m0, m0.abs(), "salto de M");
    cerca_escala(der.v - izq.v, 0.0, m0.abs(), "V sin salto");
    // Biapoyada: R_A = M0/L, V = M0/L constante, M(a-) = M0·a/L, M(a+) = -M0·b/L.
    cerca_escala(r.casos[0].reacciones[0][1], m0 / l, m0.abs(), "R_A");
    cerca_escala(izq.v, m0 / l, m0.abs(), "V");
    cerca_escala(izq.m, m0 * a / l, m0.abs(), "M(a-)");
    cerca_escala(der.m, -m0 * (l - a) / l, m0.abs(), "M(a+)");
    // El diagrama tiene las dos estaciones del salto.
    let d = r.diagrama(0, 0, 11);
    let en_a: Vec<f64> = d.iter().filter(|s| s.x == a).map(|s| s.m).collect();
    assert_eq!(en_a.len(), 2, "estaciones en x = a: {en_a:?}");
    cerca_escala(en_a[1] - en_a[0], -m0, m0.abs(), "salto en el diagrama");
}

#[test]
fn voladizo_flecha_en_el_extremo() {
    let (l, a, m0) = (4.0, 1.5, 12.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    let mut c = CasoCarga::new("m");
    c.en_barras.push(momento(0, a, m0, Ejes::Global));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let d = &r.casos[0].desplazamientos[1];
    let v = m0 * a * (2.0 * l - a) / (2.0 * E * I);
    cerca_escala(d[1], v, v, "flecha en el extremo");
    cerca_escala(
        d[2],
        m0 * a / (E * I),
        m0 * a / (E * I),
        "giro en el extremo",
    );
    // Flecha en el tramo cargado: v(x) = M0·x²/(2EI) para x <= a.
    let x = 0.9;
    let s = r.seccion(0, 0, x, false);
    cerca_escala(s.v_local, m0 * x * x / (2.0 * E * I), v, "flecha en x");
    cerca_escala(s.m, m0, m0, "M en [0, a]");
    cerca_escala(r.seccion(0, 0, 3.0, false).m, 0.0, m0, "M después de a");
}

#[test]
fn igual_al_modelo_con_nudo_en_a() {
    // Barra inclinada, empotrada y apoyada; el momento en el tramo tiene que dar
    // lo mismo que un momento nodal en un nudo intermedio ubicado en a.
    let (l, a, m0, ang) = (7.0, 2.6, -25.0, 30f64.to_radians());
    let (c, s) = (ang.cos(), ang.sin());

    let mut m1 = Modelo::new();
    m1.agregar_nudo(0.0, 0.0);
    m1.agregar_nudo(l * c, l * s);
    m1.agregar_barra(Barra::new(0, 1, E, A, I));
    m1.apoyar(0, true, true, true);
    m1.apoyar(1, true, true, false);
    let mut caso = CasoCarga::new("m");
    caso.en_barras.push(momento(0, a, m0, Ejes::Global));
    m1.agregar_caso(caso);
    let r1 = analizar(&m1).unwrap();

    let mut m2 = Modelo::new();
    m2.agregar_nudo(0.0, 0.0);
    m2.agregar_nudo(a * c, a * s);
    m2.agregar_nudo(l * c, l * s);
    m2.agregar_barra(Barra::new(0, 1, E, A, I));
    m2.agregar_barra(Barra::new(1, 2, E, A, I));
    m2.apoyar(0, true, true, true);
    m2.apoyar(2, true, true, false);
    let mut caso = CasoCarga::new("m");
    caso.nodales.push((1, [0.0, 0.0, m0]));
    m2.agregar_caso(caso);
    let r2 = analizar(&m2).unwrap();

    for d in 0..3 {
        let esc = m0.abs();
        cerca_escala(
            r1.casos[0].reacciones[0][d],
            r2.casos[0].reacciones[0][d],
            esc,
            "reacción A",
        );
        cerca_escala(
            r1.casos[0].reacciones[1][d],
            r2.casos[0].reacciones[2][d],
            esc,
            "reacción B",
        );
    }
    let esc_v = m0.abs() * l * l / (E * I);
    for k in 0..=28 {
        let x = l * k as f64 / 28.0;
        let s1 = r1.seccion(0, 0, x, false);
        let (barra, x0) = if x <= a { (0, 0.0) } else { (1, a) };
        let s2 = r2.seccion(0, barra, x - x0, false);
        cerca_escala(s1.n, s2.n, m0.abs(), "N");
        cerca_escala(s1.v, s2.v, m0.abs(), "V");
        cerca_escala(s1.m, s2.m, m0.abs(), "M");
        cerca_escala(s1.u_local, s2.u_local, esc_v, "u");
        cerca_escala(s1.v_local, s2.v_local, esc_v, "v");
    }
}

#[test]
fn momento_en_los_extremos_de_la_barra() {
    // a = 0 y a = L equivalen a un momento nodal en el nudo correspondiente.
    let (l, m0) = (3.0, 9.0);
    for (a, nudo) in [(0.0, 0), (l, 1)] {
        let construir = |en_tramo: bool| {
            let mut m = viga(l);
            m.apoyar(0, true, true, false);
            m.apoyar(1, false, true, false);
            let mut c = CasoCarga::new("m");
            if en_tramo {
                c.en_barras.push(momento(0, a, m0, Ejes::Local));
            } else {
                c.nodales.push((nudo, [0.0, 0.0, m0]));
            }
            m.agregar_caso(c);
            analizar(&m).unwrap()
        };
        let (r1, r2) = (construir(true), construir(false));
        for n in 0..2 {
            for d in 0..3 {
                cerca_escala(
                    r1.casos[0].reacciones[n][d],
                    r2.casos[0].reacciones[n][d],
                    m0,
                    "reacción",
                );
                cerca_escala(
                    r1.casos[0].desplazamientos[n][d],
                    r2.casos[0].desplazamientos[n][d],
                    m0 * l / (E * I),
                    "desplazamiento",
                );
            }
        }
    }
}

#[test]
fn posicion_invalida_se_rechaza() {
    for a in [-0.1, 3.5, f64::NAN] {
        let mut m = viga(3.0);
        m.apoyar(0, true, true, true);
        let mut c = CasoCarga::new("x");
        c.en_barras.push(momento(0, a, 1.0, Ejes::Local));
        m.agregar_caso(c);
        assert!(
            matches!(analizar(&m), Err(ErrorNervi::ModeloInvalido(_))),
            "a = {a} debería rechazarse"
        );
    }
}
