// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación de las cargas térmicas en barras (issue #4).
//!
//! Unidades: kN, m y °C. Deformaciones térmicas libres: `ε₀ = α·ΔT` y
//! `κ₀ = α·ΔT_g/h`, con `ΔT_g = T(cara -y) - T(cara +y)`. Fuentes: Ghali, Neville
//! y Brown, Structural Analysis: A Unified Classical and Matrix Approach, 6.ª ed.,
//! §4.6 y §6.4 (deformaciones por temperatura, método de las fuerzas); Weaver y
//! Gere, Matrix Analysis of Framed Structures, 3.ª ed., §3.5; y estática.

use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Modelo, TipoCargaBarra,
};

const E: f64 = 2.0e8; // kN/m²
const A: f64 = 0.01; // m²
const I: f64 = 1.0e-4; // m⁴
const ALFA: f64 = 1.2e-5; // 1/°C (acero)
const H: f64 = 0.4; // m, canto de la sección
const TOL: f64 = 1e-9;

fn cerca(calc: f64, esperado: f64, que: &str) {
    let escala = esperado.abs().max(1e-12);
    assert!(
        (calc - esperado).abs() <= TOL * escala,
        "{que}: calculado {calc:e}, esperado {esperado:e}"
    );
}

fn nulo(calc: f64, escala: f64, que: &str) {
    assert!(
        calc.abs() <= TOL * escala,
        "{que}: calculado {calc:e}, esperado 0"
    );
}

fn termica(barra: usize, dt: f64, gradiente: f64) -> CargaBarra {
    CargaBarra {
        barra,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Termica {
            alfa: ALFA,
            dt,
            gradiente,
            h: H,
        },
    }
}

/// Viga horizontal de una barra entre (0,0) y (L,0) con una carga térmica.
fn viga(l: f64, dt: f64, gradiente: f64) -> Modelo {
    let mut m = Modelo::new();
    let a = m.agregar_nudo(0.0, 0.0);
    let b = m.agregar_nudo(l, 0.0);
    m.agregar_barra(Barra::new(a, b, E, A, I));
    let mut c = CasoCarga::new("T");
    c.en_barras.push(termica(0, dt, gradiente));
    m.agregar_caso(c);
    m
}

#[test]
fn barra_biempotrada_con_variacion_uniforme() {
    // Dilatación impedida: N = -EAαΔT en toda la barra, desplazamientos nulos.
    let (l, dt) = (5.0, 30.0);
    let mut m = viga(l, dt, 0.0);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let r = analizar(&m).unwrap();
    let n = -E * A * ALFA * dt;
    for x in [0.0, 1.3, l / 2.0, l] {
        let s = r.seccion(0, 0, x, false);
        cerca(s.n, n, "N");
        nulo(s.m, n.abs(), "M");
        nulo(s.u_local, 1e-6, "u");
        nulo(s.v_local, 1e-6, "v");
    }
    // El apoyo izquierdo empuja hacia +x, el derecho hacia -x.
    cerca(r.casos[0].reacciones[0][0], -n, "Rx A");
    cerca(r.casos[0].reacciones[1][0], n, "Rx B");
}

#[test]
fn barra_libre_de_dilatarse_no_tiene_esfuerzos() {
    // Viga isostática con ΔT uniforme y gradiente: ningún esfuerzo, el carrito se
    // desplaza αΔT·L, la flecha a media luz es -κ₀L²/8 y los giros de extremo ∓κ₀L/2.
    let (l, dt, dg) = (6.0, 25.0, 15.0);
    let mut m = viga(l, dt, dg);
    m.apoyar(0, true, true, false);
    m.apoyar(1, false, true, false);
    let r = analizar(&m).unwrap();
    let k0 = ALFA * dg / H;
    for x in [0.0, 1.0, l / 2.0, 4.5, l] {
        let s = r.seccion(0, 0, x, false);
        nulo(s.n, E * A * ALFA * dt, "N");
        nulo(s.v, E * I * k0, "V");
        nulo(s.m, E * I * k0, "M");
    }
    for reaccion in r.casos[0].reacciones.iter().take(2) {
        for &valor in reaccion.iter() {
            nulo(valor, E * A * ALFA * dt, "reacción");
        }
    }
    let d = &r.casos[0].desplazamientos;
    cerca(d[1][0], ALFA * dt * l, "alargamiento");
    cerca(d[0][2], -k0 * l / 2.0, "giro en A");
    cerca(d[1][2], k0 * l / 2.0, "giro en B");
    cerca(
        r.seccion(0, 0, l / 2.0, false).v_local,
        -k0 * l * l / 8.0,
        "flecha a media luz (αΔT·L²/8h)",
    );
}

#[test]
fn viga_biempotrada_con_gradiente() {
    // Curvatura impedida: momento constante M = -EIαΔT_g/h, sin cortante ni flecha.
    let (l, dg) = (4.0, 20.0);
    let mut m = viga(l, 0.0, dg);
    m.apoyar(0, true, true, true);
    m.apoyar(1, true, true, true);
    let r = analizar(&m).unwrap();
    let mom = -E * I * ALFA * dg / H;
    for x in [0.0, 0.7, l / 2.0, l] {
        let s = r.seccion(0, 0, x, false);
        cerca(s.m, mom, "M");
        nulo(s.v, mom.abs(), "V");
        nulo(s.v_local, 1e-6, "v");
    }
    nulo(r.casos[0].reacciones[0][1], mom.abs(), "Ry A");
}

#[test]
fn viga_empotrada_y_apoyada_con_gradiente() {
    // Hiperestática de grado 1 (método de las fuerzas): el voladizo libre subiría
    // κ₀L²/2 en la punta; el carrito lo impide con R = 3EIκ₀/(2L) hacia abajo.
    // M(0) = -RL = -3EIκ₀/2, M(L) = 0, V = R constante.
    let (l, dg) = (5.0, 18.0);
    let mut m = viga(l, 0.0, dg);
    m.apoyar(0, true, true, true);
    m.apoyar(1, false, true, false);
    let r = analizar(&m).unwrap();
    let k0 = ALFA * dg / H;
    let rr = 3.0 * E * I * k0 / (2.0 * l);
    cerca(r.casos[0].reacciones[1][1], -rr, "R en el carrito");
    cerca(r.casos[0].reacciones[0][1], rr, "R en el empotramiento");
    cerca(
        r.seccion(0, 0, 0.0, false).m,
        -rr * l,
        "M en el empotramiento",
    );
    nulo(r.seccion(0, 0, l, false).m, rr * l, "M en el carrito");
    cerca(r.seccion(0, 0, l / 2.0, false).v, rr, "V");
}

#[test]
fn liberaciones_anulan_los_esfuerzos_que_no_pueden_transmitirse() {
    // Barra articulada en ambos extremos entre apoyos fijos: el gradiente no genera
    // momento (los extremos giran libremente) y el ΔT uniforme sí genera axil.
    let (l, dt, dg) = (3.0, 40.0, 10.0);
    let mut m = Modelo::new();
    let a = m.agregar_nudo(0.0, 0.0);
    let b = m.agregar_nudo(l, 0.0);
    m.agregar_barra(Barra::biarticulada(a, b, E, A, I));
    m.apoyar(a, true, true, false);
    m.apoyar(b, true, true, false);
    let mut c = CasoCarga::new("T");
    c.en_barras.push(termica(0, dt, dg));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let n = -E * A * ALFA * dt;
    for x in [0.0, l / 2.0, l] {
        let s = r.seccion(0, 0, x, false);
        cerca(s.n, n, "N");
        nulo(s.m, n.abs(), "M");
    }
    // La flecha a media luz es la de la barra libre de curvarse: -κ₀L²/8.
    let k0 = ALFA * dg / H;
    cerca(
        r.seccion(0, 0, l / 2.0, false).v_local,
        -k0 * l * l / 8.0,
        "flecha",
    );
}

#[test]
fn portico_simetrico_con_dintel_calentado() {
    // Pórtico biempotrado de una crujía, dintel con ΔT uniforme: el dintel se
    // alarga y empuja las columnas. Por simetría los nudos superiores se
    // desplazan ±αΔT·L/2 y las reacciones horizontales son iguales y opuestas.
    // Equilibrio global: ΣRx = 0, ΣRy = 0.
    let (l, h, dt) = (6.0, 3.0, 35.0);
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(0.0, h);
    let n2 = m.agregar_nudo(l, h);
    let n3 = m.agregar_nudo(l, 0.0);
    m.agregar_barra(Barra::new(n0, n1, E, A, I));
    m.agregar_barra(Barra::new(n1, n2, E, A, I));
    m.agregar_barra(Barra::new(n3, n2, E, A, I));
    m.apoyar(n0, true, true, true);
    m.apoyar(n3, true, true, true);
    let mut c = CasoCarga::new("T");
    c.en_barras.push(termica(1, dt, 0.0));
    m.agregar_caso(c);
    let r = analizar(&m).unwrap();
    let rc = &r.casos[0];
    let escala = E * A * ALFA * dt;
    nulo(rc.reacciones[n0][0] + rc.reacciones[n3][0], escala, "ΣRx");
    nulo(rc.reacciones[n0][1] + rc.reacciones[n3][1], escala, "ΣRy");
    cerca(
        rc.desplazamientos[n1][0],
        -rc.desplazamientos[n2][0],
        "simetría",
    );
    // Alargamiento del dintel = térmico + mecánico (N/EA): u2 - u1 = αΔT·L + N·L/EA.
    let n_dintel = r.seccion(0, 1, l / 2.0, false).n;
    cerca(
        rc.desplazamientos[n2][0] - rc.desplazamientos[n1][0],
        ALFA * dt * l + n_dintel * l / (E * A),
        "compatibilidad del dintel",
    );
    // El dintel queda comprimido por las columnas.
    assert!(n_dintel < 0.0, "N dintel = {n_dintel}");
}

#[test]
fn gradiente_sin_canto_se_rechaza() {
    let mut m = Modelo::new();
    m.agregar_nudo(0.0, 0.0);
    m.agregar_nudo(3.0, 0.0);
    m.agregar_barra(Barra::new(0, 1, E, A, I));
    m.apoyar(0, true, true, true);
    let mut c = CasoCarga::new("T");
    c.en_barras.push(CargaBarra {
        barra: 0,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Termica {
            alfa: ALFA,
            dt: 0.0,
            gradiente: 10.0,
            h: 0.0,
        },
    });
    m.agregar_caso(c);
    assert!(matches!(analizar(&m), Err(ErrorNervi::ModeloInvalido(_))));
}
