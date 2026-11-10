// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación del motor contra soluciones analíticas cerradas.
//!
//! Cada prueba cita la fórmula de referencia. Unidades: kN y m.
//! Fuentes: tablas clásicas de vigas (p. ej. Roark's Formulas for Stress and
//! Strain, cap. 8; Hibbeler, Structural Analysis, apéndices) y estática.

#![allow(clippy::needless_range_loop)]

use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Gdl, Modelo, TipoCargaBarra,
};

const E: f64 = 2.0e8; // kN/m² (acero)
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

fn uniforme(barra: usize, qy: f64) -> CargaBarra {
    CargaBarra {
        barra,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Uniforme { qx: 0.0, qy },
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
fn voladizo_carga_puntual_en_extremo() {
    // δ = PL³/3EI, θ = PL²/2EI, R = P, M_empotramiento = PL.
    let (l, p) = (4.0, 25.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    let mut c = CasoCarga::new("P");
    c.nodales.push((1, [0.0, -p, 0.0]));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];
    cerca(
        rc.desplazamientos[1][1],
        -p * l.powi(3) / (3.0 * E * I),
        "flecha",
    );
    cerca(rc.desplazamientos[1][2], -p * l * l / (2.0 * E * I), "giro");
    cerca(rc.reacciones[0][1], p, "reacción vertical");
    cerca(rc.reacciones[0][2], p * l, "momento de empotramiento");
    // M(0) = -PL (tracciona arriba), M(L) = 0.
    cerca(r.seccion(0, 0, 0.0, false).m, -p * l, "M(0)");
    assert!(r.seccion(0, 0, l, false).m.abs() < 1e-9);
}

#[test]
fn voladizo_carga_uniforme() {
    // δ = qL⁴/8EI, M_empotramiento = qL²/2.
    let (l, q) = (3.0, 12.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    let mut c = CasoCarga::new("q");
    c.en_barras.push(uniforme(0, -q));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];
    cerca(
        rc.desplazamientos[1][1],
        -q * l.powi(4) / (8.0 * E * I),
        "flecha",
    );
    cerca(rc.reacciones[0][1], q * l, "reacción");
    cerca(rc.reacciones[0][2], q * l * l / 2.0, "momento");
    // Flecha a media luz (interpolación + solución particular):
    // v(x) = -q x² (6L² - 4Lx + x²) / 24EI.
    let x = l / 2.0;
    let esperado = -q * x * x * (6.0 * l * l - 4.0 * l * x + x * x) / (24.0 * E * I);
    cerca(
        r.seccion(0, 0, x, false).v_local,
        esperado,
        "flecha a media luz",
    );
}

#[test]
fn viga_biapoyada_carga_uniforme() {
    // M_max = qL²/8, δ_max = 5qL⁴/384EI, R = qL/2. Una sola barra.
    let (l, q) = (6.0, 10.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, false);
    m.apoyar(1, false, true, false);
    let mut c = CasoCarga::new("q");
    c.en_barras.push(uniforme(0, -q));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(r.casos[0].reacciones[0][1], q * l / 2.0, "R izquierda");
    cerca(r.casos[0].reacciones[1][1], q * l / 2.0, "R derecha");
    let s = r.seccion(0, 0, l / 2.0, false);
    cerca(s.m, q * l * l / 8.0, "M a media luz");
    cerca(
        s.v_local,
        -5.0 * q * l.powi(4) / (384.0 * E * I),
        "flecha a media luz",
    );
    assert!(s.v.abs() < 1e-9, "V a media luz debe ser 0");
    // El diagrama debe incluir el punto de V = 0 con el momento máximo.
    let d = r.diagrama(0, 0, 4); // estaciones 0, 2, 4, 6: no incluyen L/2 por sí mismas
    let m_max = d.iter().map(|s| s.m).fold(f64::MIN, f64::max);
    cerca(m_max, q * l * l / 8.0, "M máximo del diagrama");
}

#[test]
fn viga_biempotrada_carga_uniforme() {
    // M_extremos = -qL²/12, M_centro = qL²/24, δ = qL⁴/384EI.
    let (l, q) = (5.0, 8.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("q");
    c.en_barras.push(uniforme(0, -q));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(r.seccion(0, 0, 0.0, false).m, -q * l * l / 12.0, "M(0)");
    cerca(r.seccion(0, 0, l, false).m, -q * l * l / 12.0, "M(L)");
    let s = r.seccion(0, 0, l / 2.0, false);
    cerca(s.m, q * l * l / 24.0, "M centro");
    cerca(s.v_local, -q * l.powi(4) / (384.0 * E * I), "flecha centro");
}

#[test]
fn viga_biempotrada_carga_puntual_excentrica() {
    // M_A = -Pab²/L², M_B = -Pa²b/L², R_A = Pb²(3a+b)/L³, δ_P = Pa³b³/(3EI L³).
    let (l, p, a) = (6.0, 30.0, 2.0);
    let b = l - a;
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("P");
    c.en_barras.push(CargaBarra {
        barra: 0,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Puntual { a, px: 0.0, py: -p },
    });
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(
        r.seccion(0, 0, 0.0, false).m,
        -p * a * b * b / (l * l),
        "M_A",
    );
    cerca(r.seccion(0, 0, l, false).m, -p * a * a * b / (l * l), "M_B");
    cerca(
        r.casos[0].reacciones[0][1],
        p * b * b * (3.0 * a + b) / l.powi(3),
        "R_A",
    );
    let s = r.seccion(0, 0, a, false);
    cerca(
        s.v_local,
        -p * a.powi(3) * b.powi(3) / (3.0 * E * I * l.powi(3)),
        "flecha bajo P",
    );
    // Salto de cortante igual a P bajo la carga.
    let izq = r.seccion(0, 0, a, false).v;
    let der = r.seccion(0, 0, a, true).v;
    cerca(izq - der, p, "salto de cortante");
}

#[test]
fn viga_continua_dos_tramos_iguales() {
    // R_extremos = 3qL/8, R_centro = 5qL/4, M_apoyo central = -qL²/8.
    let (l, q) = (5.0, 10.0);
    let mut m = Modelo::new();
    let n: Vec<usize> = (0..3).map(|k| m.agregar_nudo(k as f64 * l, 0.0)).collect();
    m.agregar_barra(Barra::new(n[0], n[1], E, A, I));
    m.agregar_barra(Barra::new(n[1], n[2], E, A, I));
    m.apoyar(n[0], true, true, false);
    m.apoyar(n[1], false, true, false);
    m.apoyar(n[2], false, true, false);
    let mut c = CasoCarga::new("q");
    c.en_barras.push(uniforme(0, -q));
    c.en_barras.push(uniforme(1, -q));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];
    cerca(
        rc.reacciones[0][1],
        3.0 * q * l / 8.0,
        "R extremo izquierdo",
    );
    cerca(rc.reacciones[1][1], 5.0 * q * l / 4.0, "R central");
    cerca(rc.reacciones[2][1], 3.0 * q * l / 8.0, "R extremo derecho");
    cerca(
        r.seccion(0, 0, l, false).m,
        -q * l * l / 8.0,
        "M sobre apoyo central",
    );
}

#[test]
fn portico_empotrado_carga_lateral() {
    // Pórtico de una crujía, bases empotradas, carga H en la cabeza.
    // Con barras axialmente rígidas y k = (I_v/L)/(I_c/h):
    // M_base = (Hh/2)(3k+1)/(6k+1), M_cabeza = (Hh/2)(3k)/(6k+1).
    let (h, l, fh) = (3.0, 6.0, 20.0);
    let (ic, iv) = (2.0e-4, 4.0e-4);
    let a_rigida = 1.0e6; // anula la deformación axial
    let k = (iv / l) / (ic / h);
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(0.0, h);
    let n2 = m.agregar_nudo(l, h);
    let n3 = m.agregar_nudo(l, 0.0);
    m.agregar_barra(Barra::new(n0, n1, E, a_rigida, ic));
    m.agregar_barra(Barra::new(n1, n2, E, a_rigida, iv));
    m.agregar_barra(Barra::new(n3, n2, E, a_rigida, ic));
    m.apoyar(n0, true, true, true);
    m.apoyar(n3, true, true, true);
    let mut c = CasoCarga::new("H");
    c.nodales.push((n1, [fh, 0.0, 0.0]));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];
    let m_base = fh * h / 2.0 * (3.0 * k + 1.0) / (6.0 * k + 1.0);
    let m_cabeza = fh * h / 2.0 * (3.0 * k) / (6.0 * k + 1.0);
    let tol = 1e-6; // la rigidez axial es grande pero finita
    let rel = |x: f64, y: f64| (x - y).abs() / y.abs();
    assert!(rel(rc.reacciones[n0][2].abs(), m_base) < tol, "M base izq");
    assert!(rel(rc.reacciones[n3][2].abs(), m_base) < tol, "M base der");
    assert!(
        rel(r.seccion(0, 0, h, false).m.abs(), m_cabeza) < tol,
        "M cabeza"
    );
    // Cortante en cada columna = H/2.
    assert!(rel(rc.reacciones[n0][0].abs(), fh / 2.0) < tol);
}

#[test]
fn cercha_triangular_con_barras_biarticuladas() {
    // Triángulo de base 2a y altura a, carga P vertical en el vértice.
    // Diagonales: N = -P/√2 (compresión). Cordón inferior: N = P/2 (tracción).
    let (a, p) = (2.0, 100.0);
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(2.0 * a, 0.0);
    let n2 = m.agregar_nudo(a, a);
    m.agregar_barra(Barra::biarticulada(n0, n2, E, A, I));
    m.agregar_barra(Barra::biarticulada(n2, n1, E, A, I));
    m.agregar_barra(Barra::biarticulada(n0, n1, E, A, I));
    m.apoyar(n0, true, true, false);
    m.apoyar(n1, false, true, false);
    let mut c = CasoCarga::new("P");
    c.nodales.push((n2, [0.0, -p, 0.0]));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    // Los giros de los tres nudos no tienen rigidez y se fijan automáticamente.
    assert_eq!(r.gdl_sin_rigidez.len(), 3);
    assert!(r.gdl_sin_rigidez.iter().all(|(_, g)| *g == Gdl::Rz));
    cerca(
        r.seccion(0, 0, 0.5, false).n,
        -p / 2f64.sqrt(),
        "diagonal izquierda",
    );
    cerca(
        r.seccion(0, 1, 0.5, false).n,
        -p / 2f64.sqrt(),
        "diagonal derecha",
    );
    cerca(r.seccion(0, 2, 0.5, false).n, p / 2.0, "cordón inferior");
    assert!(
        r.seccion(0, 0, 1.0, false).m.abs() < 1e-9,
        "biela sin momento"
    );
}

#[test]
fn voladizo_inclinado_con_carga_vertical_global() {
    // Barra a 30° empotrada en el origen, carga P vertical (global) en el extremo.
    // δ_perp = P cos30 L³/3EI, δ_axial = P sin30 L/EA.
    let (l, p) = (4.0, 10.0);
    let ang = 30f64.to_radians();
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(l * ang.cos(), l * ang.sin());
    m.agregar_barra(Barra::new(n0, n1, E, A, I));
    m.apoyar(n0, true, true, true);
    let mut c = CasoCarga::new("P");
    c.nodales.push((n1, [0.0, -p, 0.0]));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let d_perp = p * ang.cos() * l.powi(3) / (3.0 * E * I);
    let d_ax = p * ang.sin() * l / (E * A);
    // Componentes: perpendicular (-sin, cos)·(-d_perp) y axial (cos, sin)·(-d_ax).
    let ux = d_perp * ang.sin() - d_ax * ang.cos();
    let uy = -d_perp * ang.cos() - d_ax * ang.sin();
    cerca(r.casos[0].desplazamientos[n1][0], ux, "ux");
    cerca(r.casos[0].desplazamientos[n1][1], uy, "uy");
    cerca(
        r.seccion(0, 0, 0.0, false).n,
        -p * ang.sin(),
        "axil (compresión)",
    );
}

#[test]
fn carga_uniforme_global_en_barra_inclinada() {
    // Carga uniforme vertical (global, por unidad de longitud de barra) sobre una
    // barra inclinada con dos apoyos articulados fijos: ΣR_y = qL y el momento a
    // media luz depende solo de la componente perpendicular q·cos(α).
    let (l, q) = (5.0, 4.0);
    let ang = 40f64.to_radians();
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(l * ang.cos(), l * ang.sin());
    m.agregar_barra(Barra::new(n0, n1, E, A, I));
    m.apoyar(n0, true, true, false);
    m.apoyar(n1, true, true, false);
    let mut c = CasoCarga::new("q");
    c.en_barras.push(CargaBarra {
        barra: 0,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra::Uniforme { qx: 0.0, qy: -q },
    });
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let ry = r.casos[0].reacciones[n0][1] + r.casos[0].reacciones[n1][1];
    cerca(ry, q * l, "suma de reacciones verticales");
    // Momento máximo con la componente perpendicular: q cos(α) L² / 8.
    cerca(
        r.seccion(0, 0, l / 2.0, false).m,
        q * ang.cos() * l * l / 8.0,
        "M a media luz",
    );
}

#[test]
fn asentamiento_de_apoyo_en_viga_biempotrada() {
    // Descenso Δ del extremo derecho: M = 6EIΔ/L², V = 12EIΔ/L³.
    let (l, delta) = (5.0, 0.01);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let mut c = CasoCarga::new("asentamiento");
    c.desplazamientos_impuestos.push((1, [0.0, -delta, 0.0]));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    cerca(
        r.casos[0].desplazamientos[1][1],
        -delta,
        "desplazamiento impuesto",
    );
    cerca(
        r.casos[0].reacciones[0][2].abs(),
        6.0 * E * I * delta / (l * l),
        "momento",
    );
    // El apoyo que desciende tiene que tirar de la viga hacia abajo.
    cerca(
        r.casos[0].reacciones[1][1],
        -12.0 * E * I * delta / l.powi(3),
        "reacción",
    );
}

#[test]
fn apoyo_elastico_axial() {
    // Barra empotrada con resorte axial en el extremo: u = P/(EA/L + k).
    let (l, p, k) = (3.0, 50.0, 1.0e5);
    let mut m = viga(l);
    m.apoyar(0, true, true, true);
    m.apoyar(1, false, true, true);
    m.resorte(1, k, 0.0, 0.0);
    let mut c = CasoCarga::new("P");
    c.nodales.push((1, [p, 0.0, 0.0]));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let u = p / (E * A / l + k);
    cerca(r.casos[0].desplazamientos[1][0], u, "desplazamiento");
    cerca(r.casos[0].reacciones[1][0], -k * u, "fuerza del resorte");
    cerca(
        r.casos[0].reacciones[0][0],
        -E * A / l * u,
        "reacción del empotramiento",
    );
}

#[test]
fn viga_gerber_con_articulacion_interna() {
    // Voladizo AB (empotrado en A) + tramo BC articulado en B y apoyado en C,
    // carga uniforme solo en BC: R_C = qL₂/2, R_A = qL₂/2, M_A = (qL₂/2)·L₁.
    let (l1, l2, q) = (2.0, 4.0, 6.0);
    let mut m = Modelo::new();
    let a = m.agregar_nudo(0.0, 0.0);
    let b = m.agregar_nudo(l1, 0.0);
    let c_ = m.agregar_nudo(l1 + l2, 0.0);
    m.agregar_barra(Barra::new(a, b, E, A, I));
    let mut bc = Barra::new(b, c_, E, A, I);
    bc.liberaciones[2] = true; // articulación en B
    m.agregar_barra(bc);
    m.apoyar(a, true, true, true);
    m.apoyar(c_, false, true, false);
    let mut caso = CasoCarga::new("q");
    caso.en_barras.push(uniforme(1, -q));
    m.agregar_caso(caso);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];
    cerca(rc.reacciones[c_][1], q * l2 / 2.0, "R_C");
    cerca(rc.reacciones[a][1], q * l2 / 2.0, "R_A");
    cerca(rc.reacciones[a][2], q * l2 / 2.0 * l1, "M_A");
    assert!(
        r.seccion(0, 1, 0.0, false).m.abs() < 1e-9,
        "momento nulo en la articulación"
    );
    cerca(
        r.seccion(0, 1, l2 / 2.0, false).m,
        q * l2 * l2 / 8.0,
        "M centro de BC",
    );
    // La flecha de B: voladizo con carga P = qL₂/2 en el extremo.
    let p = q * l2 / 2.0;
    cerca(
        rc.desplazamientos[b][1],
        -p * l1.powi(3) / (3.0 * E * I),
        "flecha en B",
    );
}

#[test]
fn varios_casos_con_una_factorizacion_y_equilibrio() {
    let (l, q, p) = (6.0, 5.0, 20.0);
    let mut m = viga(l);
    m.apoyar(0, true, true, false);
    m.apoyar(1, false, true, false);
    let mut c1 = CasoCarga::new("q");
    c1.en_barras.push(uniforme(0, -q));
    let mut c2 = CasoCarga::new("P");
    c2.nodales.push((1, [p, 0.0, 0.0]));
    m.agregar_caso(c1);
    m.agregar_caso(c2);
    let r = analizar(&m).unwrap();
    assert_eq!(r.casos.len(), 2);
    cerca(r.casos[0].reacciones[0][1], q * l / 2.0, "caso 1");
    cerca(r.casos[1].reacciones[0][0], -p, "caso 2");
    cerca(r.seccion(1, 0, 3.0, false).n, p, "axil caso 2");
}

#[test]
fn equilibrio_global_en_portico_de_varios_pisos() {
    // Pórtico de 3 pisos y 2 vanos con cargas variadas: ΣR + ΣF = 0 y ΣM = 0.
    let mut m = Modelo::new();
    let (vano, alto) = (5.0, 3.0);
    let mut id = vec![vec![0; 3]; 4];
    for (p, fila) in id.iter_mut().enumerate() {
        for (c, nudo) in fila.iter_mut().enumerate() {
            *nudo = m.agregar_nudo(c as f64 * vano, p as f64 * alto);
        }
    }
    for p in 0..3 {
        for c in 0..3 {
            m.agregar_barra(Barra::new(id[p][c], id[p + 1][c], E, 0.09, 6.75e-4));
        }
        for c in 0..2 {
            m.agregar_barra(Barra::new(id[p + 1][c], id[p + 1][c + 1], E, 0.12, 1.6e-3));
        }
    }
    for c in 0..3 {
        m.apoyar(id[0][c], true, true, true);
    }
    let mut caso = CasoCarga::new("mixto");
    for b in 0..m.barras.len() {
        let (_, _, s) = m.geometria_barra(&m.barras[b]);
        if s.abs() < 1e-12 {
            caso.en_barras.push(CargaBarra {
                barra: b,
                ejes: Ejes::Global,
                tipo: TipoCargaBarra::Uniforme { qx: 0.0, qy: -15.0 },
            });
            caso.en_barras.push(CargaBarra {
                barra: b,
                ejes: Ejes::Global,
                tipo: TipoCargaBarra::Puntual {
                    a: 1.5,
                    px: 0.0,
                    py: -30.0,
                },
            });
        }
    }
    for p in 1..4 {
        caso.nodales.push((id[p][0], [10.0 * p as f64, 0.0, 0.0]));
    }
    m.agregar_caso(caso);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];

    let (mut fx, mut fy, mut mz) = (0.0, 0.0, 0.0);
    let mut suma = |x: f64, y: f64, f: [f64; 3]| {
        fx += f[0];
        fy += f[1];
        mz += f[2] + x * f[1] - y * f[0];
    };
    for (n, reac) in rc.reacciones.iter().enumerate() {
        suma(m.nudos[n][0], m.nudos[n][1], *reac);
    }
    for (n, f) in &m.casos[0].nodales {
        suma(m.nudos[*n][0], m.nudos[*n][1], *f);
    }
    for cb in &m.casos[0].en_barras {
        let b = &m.barras[cb.barra];
        let (l, c, s) = m.geometria_barra(b);
        let [xi, yi] = m.nudos[b.nudo_i];
        match cb.tipo {
            TipoCargaBarra::Uniforme { qx, qy } => {
                suma(xi + c * l / 2.0, yi + s * l / 2.0, [qx * l, qy * l, 0.0])
            }
            TipoCargaBarra::Puntual { a, px, py } => suma(xi + c * a, yi + s * a, [px, py, 0.0]),
            TipoCargaBarra::Trapezoidal {
                a,
                b,
                qx1,
                qy1,
                qx2,
                qy2,
            } => {
                // Cada componente es un trapecio: resultante en su centroide.
                for (q1, q2, dir) in [(qx1, qx2, 0), (qy1, qy2, 1)] {
                    let r = 0.5 * (q1 + q2) * (b - a);
                    if r != 0.0 {
                        let d = a + (b - a) * (q1 + 2.0 * q2) / (3.0 * (q1 + q2));
                        let mut f = [0.0; 3];
                        f[dir] = r;
                        suma(xi + c * d, yi + s * d, f);
                    }
                }
            }
        }
    }
    let total = 15.0 * 30.0 + 30.0 * 6.0;
    assert!(fx.abs() < 1e-9 * total, "ΣFx = {fx}");
    assert!(fy.abs() < 1e-9 * total, "ΣFy = {fy}");
    assert!(mz.abs() < 1e-9 * total * 10.0, "ΣM = {mz}");
}

#[test]
fn mecanismo_viga_sobre_dos_carritos() {
    // Sin restricción horizontal: la estructura puede desplazarse en X.
    let mut m = viga(4.0);
    m.apoyar(0, false, true, false);
    m.apoyar(1, false, true, false);
    let mut c = CasoCarga::new("H");
    c.nodales.push((1, [1.0, 0.0, 0.0]));
    m.agregar_caso(c);
    match analizar(&m) {
        Err(ErrorNervi::Mecanismo(_)) => {}
        otro => panic!("se esperaba un mecanismo, se obtuvo {otro:?}"),
    }
}

#[test]
fn carga_sobre_giro_sin_rigidez_es_error() {
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(1.0, 0.0);
    m.agregar_barra(Barra::biarticulada(n0, n1, E, A, I));
    m.apoyar(n0, true, true, false);
    m.apoyar(n1, false, true, false);
    let mut c = CasoCarga::new("M");
    c.nodales.push((n1, [0.0, 0.0, 5.0]));
    m.agregar_caso(c);
    assert_eq!(
        analizar(&m).unwrap_err(),
        ErrorNervi::CargaSinRigidez {
            nudo: n1,
            gdl: Gdl::Rz
        }
    );
}

#[test]
fn datos_invalidos_se_rechazan_con_mensaje() {
    let mut m = viga(3.0);
    m.barras[0].e = 0.0;
    assert!(matches!(analizar(&m), Err(ErrorNervi::ModeloInvalido(_))));

    let mut m = Modelo::new();
    m.agregar_nudo(0.0, 0.0);
    m.agregar_nudo(0.0, 0.0);
    m.agregar_barra(Barra::new(0, 1, E, A, I));
    assert!(matches!(analizar(&m), Err(ErrorNervi::ModeloInvalido(_))));

    let mut m = viga(3.0);
    m.barras[0].nudo_j = 7;
    assert!(matches!(analizar(&m), Err(ErrorNervi::ModeloInvalido(_))));
}

#[test]
fn rendimiento_portico_grande() {
    // Pórtico de 40 vanos × 100 pisos (≈ 8 000 barras). Debe resolverse rápido
    // incluso en modo debug; el objetivo de < 1 s se mide en release.
    let (vanos, pisos) = (40, 100);
    let mut m = Modelo::new();
    let mut id = vec![vec![0; vanos + 1]; pisos + 1];
    for (p, fila) in id.iter_mut().enumerate() {
        for (c, n) in fila.iter_mut().enumerate() {
            *n = m.agregar_nudo(c as f64 * 5.0, p as f64 * 3.0);
        }
    }
    for p in 0..pisos {
        for c in 0..=vanos {
            m.agregar_barra(Barra::new(id[p][c], id[p + 1][c], E, 0.25, 5e-3));
        }
        for c in 0..vanos {
            m.agregar_barra(Barra::new(id[p + 1][c], id[p + 1][c + 1], E, 0.2, 3e-3));
        }
    }
    for c in 0..=vanos {
        m.apoyar(id[0][c], true, true, true);
    }
    let mut caso = CasoCarga::new("viento");
    for p in 1..=pisos {
        caso.nodales.push((id[p][0], [5.0, 0.0, 0.0]));
    }
    m.agregar_caso(caso);
    let t = std::time::Instant::now();
    let r = analizar(&m).unwrap();
    eprintln!("{} barras resueltas en {:?}", m.barras.len(), t.elapsed());
    let base: f64 = (0..=vanos)
        .map(|c| r.casos[0].reacciones[id[0][c]][0])
        .sum();
    assert!(
        (base + 5.0 * pisos as f64).abs() < 1e-6,
        "cortante basal {base}"
    );
}
