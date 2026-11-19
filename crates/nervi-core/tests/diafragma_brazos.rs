// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación de los brazos rígidos (issue #13) y del diafragma rígido de
//! piso (issue #14) del pórtico espacial.
//!
//! Unidades: kN, m, s y t (kN·s²/m). Soluciones de referencia:
//! - Voladizo con brazo rígido en el empotramiento: la parte flexible de largo
//!   `Lf` se deforma como un voladizo, `δ = P Lf³ / (3 EI)`; el momento en la
//!   cara es `P Lf` y en el nudo `P L` (estática).
//! - Una barra con brazos rígidos es lo mismo que tres barras en serie con las
//!   de los extremos muy rígidas (criterio de verificación del issue #13).
//! - Un piso con diafragma rígido es lo mismo que la losa modelada con barras
//!   muy rígidas en su plano (criterio del issue #14).
//! - Torsión en planta: con columnas de rigideces `kx = 3 EIz/h³`,
//!   `ky = 3 EIy/h³` (voladizo) y `GJ/h`, el centro de rigidez es
//!   `x_r = Σ ky x / Σ ky`, `y_r = Σ kx y / Σ kx` y el piso se traslada
//!   `F / Σ kx` y gira `T / Kθ`, con `Kθ = Σ kx (y - y_r)² + Σ ky (x - x_r)² +
//!   Σ GJ/h` y `T` el momento de la fuerza respecto del centro de rigidez
//!   (A. K. Chopra, *Dynamics of Structures*, 4.ª ed., cap. 9, sistemas con
//!   planta asimétrica; R. Park y T. Paulay, *Reinforced Concrete Structures*,
//!   Wiley 1975, cap. 11, reparto de fuerzas sísmicas entre pórticos).
//! - Modos del piso: `ω² = Σ k / M` en traslación y `ω² = Kθ / J` en torsión,
//!   con `J = Σ m r²` respecto del centro de masa (Chopra, op. cit., cap. 9).

#![allow(clippy::needless_range_loop)]

use nervi_core::espacial::dinamica::ensamblar_masa;
use nervi_core::espacial::{
    analizar_3d, analizar_espectro_3d, analizar_modal_3d, Barra3d, CargaBarra3d, CasoCarga3d,
    CombinacionModal, Espectro, Masas3d, MetodoModal, Modelo3d, Resultados3d, TipoCargaBarra3d,
    TipoMasa,
};
use nervi_core::{Ejes, ErrorNervi};

const E: f64 = 2.5e7;
const G: f64 = 1.0e7;

fn cerca(calc: f64, esperado: f64, tol: f64, que: &str) {
    let err = (calc - esperado).abs() / esperado.abs().max(1e-300);
    assert!(
        err <= tol,
        "{que}: calculado {calc:e}, esperado {esperado:e} (error {err:e})"
    );
}

/// Compara dos números con una tolerancia relativa a una escala.
fn igual(a: f64, b: f64, escala: f64, tol: f64, que: &str) {
    assert!(
        (a - b).abs() <= tol * escala,
        "{que}: {a:e} contra {b:e} (escala {escala:e})"
    );
}

fn columna(i: usize, j: usize, iy: f64, iz: f64, jt: f64) -> Barra3d {
    Barra3d::new(i, j, E, G, 0.16, iy, iz, jt)
}

// --- Brazos rígidos ------------------------------------------------------------

#[test]
fn voladizo_con_brazo_rigido_en_el_empotramiento() {
    let (l, a, p) = (4.0, 0.5, 10.0);
    let (iy, iz) = (2.0e-3, 3.0e-3);
    let mut m = Modelo3d::new();
    let n0 = m.agregar_nudo(0.0, 0.0, 0.0);
    let n1 = m.agregar_nudo(l, 0.0, 0.0);
    m.agregar_barra(
        Barra3d::new(n0, n1, E, G, 0.12, iy, iz, 1.0e-3).con_brazos([a, 0.0, 0.0], [0.0; 3]),
    );
    m.empotrar(n0);
    let mut caso = CasoCarga3d::new("P");
    caso.nodales.push((n1, [0.0, 0.0, -p, 0.0, 0.0, 0.0]));
    m.agregar_caso(caso);
    let r = analizar_3d(&m).unwrap();
    let lf = l - a;
    cerca(r.barras[0].l, lf, 1e-14, "longitud flexible");
    // Viga horizontal sin referencia: y local = +Z, la flexión vertical usa Iz.
    let c = &r.casos[0];
    cerca(
        c.desplazamientos[n1][2],
        -p * lf.powi(3) / (3.0 * E * iz),
        1e-12,
        "flecha",
    );
    cerca(
        c.desplazamientos[n1][4],
        p * lf * lf / (2.0 * E * iz),
        1e-12,
        "giro",
    );
    // Momento en la cara (sobre la barra, extremo i) y reacción en el nudo.
    cerca(
        c.fuerzas_extremo[0][5].abs(),
        p * lf,
        1e-12,
        "momento en la cara",
    );
    cerca(c.reacciones[n0][2], p, 1e-12, "reacción vertical");
    cerca(c.reacciones[n0][4], -p * l, 1e-12, "momento en el nudo");
    // El diagrama empieza en la cara.
    let d = r.diagrama(0, 0, 3);
    cerca(d[0].mz.abs(), p * lf, 1e-12, "diagrama en x = 0");
    assert!(d.last().unwrap().mz.abs() < 1e-9);
}

/// Pórtico con una barra oblicua con brazos rígidos que no están sobre su eje
/// (excéntricos), una articulación y cargas en el tramo y en los nudos.
fn portico_con_brazos(brazos: bool) -> (Modelo3d, usize, Vec<usize>) {
    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(0.0, 0.0, 0.0);
    let b = m.agregar_nudo(3.0, 2.0, 1.5);
    let c = m.agregar_nudo(5.0, -1.0, 0.0);
    let (bi, bj) = ([0.3, 0.1, 0.2], [-0.2, 0.25, -0.1]);
    let base = Barra3d::new(0, 0, E, G, 0.09, 6.75e-4, 1.2e-3, 1.1e-3)
        .con_referencia([0.2, -0.4, 1.0])
        .articulada(false, true);
    let flexible;
    if brazos {
        let mut barra = base.clone().con_brazos(bi, bj);
        barra.nudo_i = a;
        barra.nudo_j = b;
        flexible = m.agregar_barra(barra);
    } else {
        // Tres barras: brazo, parte flexible y brazo, con los brazos 10⁶ veces
        // más rígidos.
        let ai = m.agregar_nudo(bi[0], bi[1], bi[2]);
        let bj_ = m.agregar_nudo(3.0 + bj[0], 2.0 + bj[1], 1.5 + bj[2]);
        let rigida = |i, j| Barra3d::new(i, j, E * 1e6, G * 1e6, 0.09, 6.75e-4, 1.2e-3, 1.1e-3);
        m.agregar_barra(rigida(a, ai));
        let mut barra = base.clone();
        barra.nudo_i = ai;
        barra.nudo_j = bj_;
        flexible = m.agregar_barra(barra);
        m.agregar_barra(rigida(bj_, b));
    }
    m.agregar_barra(Barra3d::new(b, c, E, G, 0.08, 4.0e-4, 9.0e-4, 6.0e-4));
    m.empotrar(a);
    m.empotrar(c);
    let mut caso = CasoCarga3d::new("cargas");
    caso.nodales.push((b, [12.0, -7.0, -20.0, 3.0, -2.0, 5.0]));
    caso.en_barras.push(CargaBarra3d {
        barra: flexible,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra3d::Uniforme {
            q: [1.0, -4.0, 2.5],
        },
    });
    caso.en_barras.push(CargaBarra3d {
        barra: flexible,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra3d::Puntual {
            a: 1.1,
            p: [0.0, 3.0, -9.0],
        },
    });
    m.agregar_caso(caso);
    (m, flexible, vec![a, b, c])
}

#[test]
fn barra_con_brazos_igual_a_tres_barras_con_extremos_rigidos() {
    let (m1, f1, n1) = portico_con_brazos(true);
    let (m2, f2, n2) = portico_con_brazos(false);
    let r1 = analizar_3d(&m1).unwrap();
    let r2 = analizar_3d(&m2).unwrap();
    let (c1, c2) = (&r1.casos[0], &r2.casos[0]);
    let escala_u = n1
        .iter()
        .flat_map(|&k| c1.desplazamientos[k])
        .fold(0.0_f64, |a, v| a.max(v.abs()));
    let escala_f = c1
        .fuerzas_extremo
        .iter()
        .flatten()
        .fold(0.0_f64, |a, v| a.max(v.abs()));
    for (&k1, &k2) in n1.iter().zip(&n2) {
        for d in 0..6 {
            igual(
                c1.desplazamientos[k1][d],
                c2.desplazamientos[k2][d],
                escala_u,
                1e-5,
                &format!("desplazamiento nudo {k1} GDL {d}"),
            );
            igual(
                c1.reacciones[k1][d],
                c2.reacciones[k2][d],
                escala_f,
                1e-5,
                &format!("reacción nudo {k1} GDL {d}"),
            );
        }
    }
    for d in 0..12 {
        igual(
            c1.fuerzas_extremo[f1][d],
            c2.fuerzas_extremo[f2][d],
            escala_f,
            1e-5,
            &format!("fuerza de extremo {d}"),
        );
    }
    cerca(r1.barras[f1].l, r2.barras[f2].l, 1e-14, "longitud flexible");
    for x in [0.0, 0.7, 1.1, 2.0] {
        let (s1, s2) = (r1.seccion(0, f1, x, false), r2.seccion(0, f2, x, false));
        for (a, b) in [(s1.mz, s2.mz), (s1.my, s2.my), (s1.n, s2.n), (s1.t, s2.t)] {
            igual(a, b, escala_f, 1e-5, &format!("esfuerzo en x = {x}"));
        }
    }
}

/// Fuerza y momento resultante (respecto del origen) de cargas y reacciones.
fn resultante(m: &Modelo3d, r: &Resultados3d) -> [f64; 6] {
    let mut s = [0.0; 6];
    let mut sumar = |p: [f64; 3], f: [f64; 6]| {
        for d in 0..3 {
            s[d] += f[d];
            s[3 + d] += f[3 + d];
        }
        s[3] += p[1] * f[2] - p[2] * f[1];
        s[4] += p[2] * f[0] - p[0] * f[2];
        s[5] += p[0] * f[1] - p[1] * f[0];
    };
    for (k, reac) in r.casos[0].reacciones.iter().enumerate() {
        sumar(m.nudos[k], *reac);
    }
    for (k, f) in &m.casos[0].nodales {
        sumar(m.nudos[*k], *f);
    }
    // Cargas en el tramo: resultante en ejes globales en su punto de aplicación.
    for cb in &m.casos[0].en_barras {
        let b = &m.barras[cb.barra];
        let (pi, _) = m.extremos(b);
        let ejes = m.ejes_barra(b).unwrap();
        let l = m.longitud(b);
        let glob = |q: [f64; 3]| -> [f64; 3] {
            match cb.ejes {
                Ejes::Global => q,
                Ejes::Local => std::array::from_fn(|d| (0..3).map(|i| ejes[i][d] * q[i]).sum()),
            }
        };
        let (f, x) = match cb.tipo {
            TipoCargaBarra3d::Uniforme { q } => (glob(q).map(|v| v * l), l / 2.0),
            TipoCargaBarra3d::Puntual { a, p } => (glob(p), a),
            _ => unreachable!(),
        };
        let p: [f64; 3] = std::array::from_fn(|d| pi[d] + x * ejes[0][d]);
        sumar(p, [f[0], f[1], f[2], 0.0, 0.0, 0.0]);
    }
    s
}

#[test]
fn equilibrio_global_y_de_la_union_con_brazos() {
    let (m, flexible, nudos) = portico_con_brazos(true);
    let r = analizar_3d(&m).unwrap();
    for (d, v) in resultante(&m, &r).iter().enumerate() {
        assert!(v.abs() < 1e-9, "resultante {d} = {v:e}");
    }
    // Equilibrio del nudo b: la carga nodal es igual a la suma de las fuerzas
    // que le transmiten sus barras, llevadas de las caras al nudo.
    let b = nudos[1];
    let mut suma = [0.0; 6];
    for (k, ba) in r.barras.iter().enumerate() {
        let barra = &m.barras[k];
        let g = ba.local_a_nudos(&r.casos[0].fuerzas_extremo[k]);
        for (o, n) in [(0, barra.nudo_i), (6, barra.nudo_j)] {
            if n == b {
                for d in 0..6 {
                    suma[d] += g[o + d];
                }
            }
        }
    }
    let carga = m.casos[0].nodales[0].1;
    for d in 0..6 {
        igual(suma[d], carga[d], 20.0, 1e-10, &format!("nudo b, GDL {d}"));
    }
    assert!(m.barras[flexible].tiene_brazos());
}

// --- Diafragma rígido ------------------------------------------------------------

/// Piso de 2 × 1 vanos (6 columnas de 3 m) con vigas en los bordes. Con
/// `diafragma` las vigas son comunes y el piso tiene diafragma rígido; sin él,
/// la losa se modela con bielas diagonales y vigas 10⁶ veces más rígidas en el
/// plano (axil y flexión horizontal). Carga lateral excéntrica en X e Y.
fn piso_con_vigas(diafragma: bool) -> (Modelo3d, Vec<usize>) {
    let mut m = Modelo3d::new();
    let (xs, ys, h) = ([0.0, 5.0, 11.0], [0.0, 6.0], 3.0);
    let mut arriba = Vec::new();
    let mut col = 0;
    for &y in &ys {
        for &x in &xs {
            let base = m.agregar_nudo(x, y, 0.0);
            let tope = m.agregar_nudo(x, y, h);
            m.empotrar(base);
            // Columnas distintas para que el centro de rigidez no sea el
            // geométrico.
            let f = 1.0 + 0.5 * col as f64;
            m.agregar_barra(columna(base, tope, 2.1e-3 * f, 1.3e-3 * f, 2.0e-3));
            arriba.push(tope);
            col += 1;
        }
    }
    let rig = if diafragma { 1.0 } else { 1e6 };
    let viga =
        |i: usize, j: usize| Barra3d::new(i, j, E, G, 0.12 * rig, 1.6e-3 * rig, 3.6e-3, 1.8e-3);
    for fila in 0..2 {
        for k in 0..2 {
            m.agregar_barra(viga(arriba[3 * fila + k], arriba[3 * fila + k + 1]));
        }
    }
    for k in 0..3 {
        m.agregar_barra(viga(arriba[k], arriba[3 + k]));
    }
    if diafragma {
        m.agregar_diafragma(&arriba, None);
    } else {
        for k in 0..2 {
            for (i, j) in [(k, 4 + k), (k + 1, 3 + k)] {
                m.agregar_barra(
                    Barra3d::new(arriba[i], arriba[j], E * 1e6, G, 0.12, 1.0, 1.0, 1.0).biela(),
                );
            }
        }
    }
    let mut caso = CasoCarga3d::new("sismo");
    caso.nodales
        .push((arriba[0], [40.0, 15.0, 0.0, 0.0, 0.0, 0.0]));
    caso.nodales
        .push((arriba[5], [10.0, -25.0, -30.0, 0.0, 0.0, 0.0]));
    m.agregar_caso(caso);
    (m, arriba)
}

#[test]
fn diafragma_igual_a_losa_con_barras_muy_rigidas() {
    let (m1, t1) = piso_con_vigas(true);
    let (m2, t2) = piso_con_vigas(false);
    let r1 = analizar_3d(&m1).unwrap();
    let r2 = analizar_3d(&m2).unwrap();
    let (c1, c2) = (&r1.casos[0], &r2.casos[0]);
    let escala_u = t1
        .iter()
        .flat_map(|&k| c1.desplazamientos[k])
        .fold(0.0_f64, |a, v| a.max(v.abs()));
    for (&a, &b) in t1.iter().zip(&t2) {
        for d in 0..6 {
            igual(
                c1.desplazamientos[a][d],
                c2.desplazamientos[b][d],
                escala_u,
                1e-5,
                &format!("nudo {a} GDL {d}"),
            );
        }
    }
    // Reacciones en las bases y fuerzas de extremo de las columnas.
    for k in 0..6 {
        for d in 0..6 {
            igual(
                c1.reacciones[2 * k][d],
                c2.reacciones[2 * k][d],
                50.0,
                1e-5,
                &format!("reacción columna {k} GDL {d}"),
            );
        }
        for d in 0..12 {
            igual(
                c1.fuerzas_extremo[k][d],
                c2.fuerzas_extremo[k][d],
                50.0,
                1e-5,
                &format!("columna {k} fuerza {d}"),
            );
        }
    }
    // El maestro (centroide) se mueve con el piso y el nudo sin barras tiene
    // uz, rx y ry restringidos, sin reacciones.
    let maestro = m1.diafragmas[0].maestro;
    assert_eq!(maestro, m1.nudos.len() - 1);
    cerca(m1.nudos[maestro][0], 5.0 + 1.0 / 3.0, 1e-14, "centroide x");
    let um = c1.desplazamientos[maestro];
    for &k in &t1 {
        let (dx, dy) = (
            m1.nudos[k][0] - m1.nudos[maestro][0],
            m1.nudos[k][1] - m1.nudos[maestro][1],
        );
        let u = c1.desplazamientos[k];
        igual(u[0], um[0] - dy * um[5], escala_u, 1e-12, "ux esclavo");
        igual(u[1], um[1] + dx * um[5], escala_u, 1e-12, "uy esclavo");
        igual(u[5], um[5], escala_u, 1e-12, "rz esclavo");
    }
    assert!(c1.reacciones[maestro].iter().all(|v| v.abs() < 1e-9));
    assert!(r1.gdl_sin_rigidez.is_empty());
}

/// Planta de 6 × 4 con cuatro columnas en voladizo (sin vigas: solo el
/// diafragma une sus topes), de inercias distintas.
struct Planta {
    m: Modelo3d,
    topes: Vec<usize>,
    maestro: usize,
    kx: Vec<f64>,
    ky: Vec<f64>,
    gj_h: f64,
    pos: Vec<[f64; 2]>,
}

fn planta(fz: [f64; 4], fy: [f64; 4]) -> Planta {
    let h = 3.5;
    let (i0, jt) = (1.0e-3, 1.5e-3);
    let pos = vec![[0.0, 0.0], [6.0, 0.0], [0.0, 4.0], [6.0, 4.0]];
    let mut m = Modelo3d::new();
    let mut topes = Vec::new();
    let (mut kx, mut ky) = (Vec::new(), Vec::new());
    for (k, p) in pos.iter().enumerate() {
        let a = m.agregar_nudo(p[0], p[1], 0.0);
        let b = m.agregar_nudo(p[0], p[1], h);
        m.empotrar(a);
        // Columna vertical: y local = -X (flexión en X con Iz), z local = -Y
        // (flexión en Y con Iy).
        m.agregar_barra(columna(a, b, fy[k] * i0, fz[k] * i0, jt));
        kx.push(3.0 * E * fz[k] * i0 / h.powi(3));
        ky.push(3.0 * E * fy[k] * i0 / h.powi(3));
        topes.push(b);
    }
    let maestro = m.agregar_diafragma(&topes, None);
    Planta {
        m,
        topes,
        maestro,
        kx,
        ky,
        gj_h: 4.0 * G * jt / h,
        pos,
    }
}

#[test]
fn torsion_en_planta_con_excentricidad_conocida() {
    let mut p = planta([1.0, 1.0, 2.0, 2.0], [1.0, 3.0, 1.0, 3.0]);
    let (fx, fy) = (100.0, -40.0);
    let mut caso = CasoCarga3d::new("F");
    caso.nodales.push((p.maestro, [fx, fy, 0.0, 0.0, 0.0, 0.0]));
    p.m.agregar_caso(caso);
    let r = analizar_3d(&p.m).unwrap();
    let c = &r.casos[0];

    let (skx, sky): (f64, f64) = (p.kx.iter().sum(), p.ky.iter().sum());
    let xr = (0..4).map(|k| p.ky[k] * p.pos[k][0]).sum::<f64>() / sky;
    let yr = (0..4).map(|k| p.kx[k] * p.pos[k][1]).sum::<f64>() / skx;
    cerca(xr, 4.5, 1e-14, "x del centro de rigidez");
    cerca(yr, 8.0 / 3.0, 1e-14, "y del centro de rigidez");
    let ktheta = (0..4)
        .map(|k| p.kx[k] * (p.pos[k][1] - yr).powi(2) + p.ky[k] * (p.pos[k][0] - xr).powi(2))
        .sum::<f64>()
        + p.gj_h;
    // La fuerza actúa en el centroide (3, 2).
    let (xp, yp) = (3.0, 2.0);
    let torsor = (xp - xr) * fy - (yp - yr) * fx;
    let theta = torsor / ktheta;
    let (ur, vr) = (fx / skx, fy / sky);
    let um = c.desplazamientos[p.maestro];
    cerca(um[5], theta, 1e-9, "giro del piso");
    cerca(um[0], ur - (yp - yr) * theta, 1e-9, "ux del maestro");
    cerca(um[1], vr + (xp - xr) * theta, 1e-9, "uy del maestro");
    // Cortante de cada columna = su rigidez por el desplazamiento de su tope.
    let mut suma = [0.0; 2];
    for k in 0..4 {
        let ux = ur - (p.pos[k][1] - yr) * theta;
        let uy = vr + (p.pos[k][0] - xr) * theta;
        let base = 2 * k;
        cerca(
            c.reacciones[base][0],
            -p.kx[k] * ux,
            1e-9,
            "cortante X columna",
        );
        cerca(
            c.reacciones[base][1],
            -p.ky[k] * uy,
            1e-9,
            "cortante Y columna",
        );
        cerca(c.desplazamientos[p.topes[k]][0], ux, 1e-9, "ux del tope");
        suma[0] += c.reacciones[base][0];
        suma[1] += c.reacciones[base][1];
    }
    cerca(-suma[0], fx, 1e-12, "suma de cortantes X");
    cerca(-suma[1], fy, 1e-12, "suma de cortantes Y");
}

#[test]
fn modos_del_piso_con_la_masa_en_los_nudos() {
    let p = planta([1.0; 4], [2.0; 4]);
    let m0 = 15.0;
    let mut masas = Masas3d::new();
    for &t in &p.topes {
        masas.nodales.push((t, [m0, m0, m0, 0.0, 0.0, 0.0]));
    }
    let modal = analizar_modal_3d(&p.m, &masas, 10, MetodoModal::Denso).unwrap();
    // Solo tienen masa los tres GDL del maestro (la vertical de los topes no
    // tiene rigidez propia que la separe: queda en sus nudos, con la axial).
    let mt = 4.0 * m0;
    let (skx, sky): (f64, f64) = (p.kx.iter().sum(), p.ky.iter().sum());
    let j = m0
        * p.pos
            .iter()
            .map(|q| (q[0] - 3.0).powi(2) + (q[1] - 2.0).powi(2))
            .sum::<f64>();
    let ktheta = (0..4)
        .map(|k| p.kx[k] * (p.pos[k][1] - 2.0).powi(2) + p.ky[k] * (p.pos[k][0] - 3.0).powi(2))
        .sum::<f64>()
        + p.gj_h;
    let mut esperadas = [skx / mt, sky / mt, ktheta / j];
    esperadas.sort_by(f64::total_cmp);
    for k in 0..3 {
        cerca(modal.omegas[k].powi(2), esperadas[k], 1e-9, "ω² del piso");
    }
    // Masa del diafragma en el maestro.
    let d = &modal.diafragmas[0];
    cerca(d.masa[0], mt, 1e-14, "masa del piso");
    cerca(d.centro_masa[0], 3.0, 1e-12, "x del centro de masa");
    cerca(d.centro_masa[1], 2.0, 1e-12, "y del centro de masa");
    cerca(d.inercia, j, 1e-12, "inercia del piso");
    // Las inercias de los modos horizontales están en el maestro.
    for k in 0..3 {
        for &t in &p.topes {
            assert_eq!(modal.inercias[k][t][0], 0.0);
        }
    }
    cerca(modal.masa_total[0], mt, 1e-14, "masa total X");

    // Lanczos da lo mismo.
    let lz = analizar_modal_3d(&p.m, &masas, 3, MetodoModal::Lanczos).unwrap();
    for k in 0..3 {
        cerca(lz.omegas[k], modal.omegas[k], 1e-9, "Lanczos");
    }

    // Espectro constante en X: el modo de traslación en X moviliza toda la
    // masa y el cortante basal es M Sa.
    let sa = 3.2;
    let esp = Espectro::new(vec![0.0, 5.0], vec![sa, sa]).unwrap();
    let r = analizar_espectro_3d(
        &p.m,
        &modal,
        &esp,
        [1.0, 0.0, 0.0],
        0.05,
        CombinacionModal::Cqc,
    )
    .unwrap();
    cerca(r.cortante_basal[0], mt * sa, 1e-9, "cortante basal");
}

#[test]
fn centro_de_masa_con_masas_desiguales() {
    let p = planta([1.0; 4], [1.0; 4]);
    let masas_nudo = [10.0, 20.0, 30.0, 40.0];
    let mut masas = Masas3d::new();
    for (k, &t) in p.topes.iter().enumerate() {
        masas
            .nodales
            .push((t, [masas_nudo[k], masas_nudo[k], 0.0, 0.0, 0.0, 0.0]));
    }
    let modal = analizar_modal_3d(&p.m, &masas, 3, MetodoModal::Denso).unwrap();
    let mt: f64 = masas_nudo.iter().sum();
    let xc = (0..4).map(|k| masas_nudo[k] * p.pos[k][0]).sum::<f64>() / mt;
    let yc = (0..4).map(|k| masas_nudo[k] * p.pos[k][1]).sum::<f64>() / mt;
    let j = (0..4)
        .map(|k| masas_nudo[k] * ((p.pos[k][0] - xc).powi(2) + (p.pos[k][1] - yc).powi(2)))
        .sum::<f64>();
    let d = &modal.diafragmas[0];
    cerca(d.centro_masa[0], xc, 1e-12, "x del centro de masa");
    cerca(d.centro_masa[1], yc, 1e-12, "y del centro de masa");
    cerca(d.inercia, j, 1e-12, "inercia respecto del centro de masa");
    // Con todos los modos, la suma de las masas efectivas es la masa total.
    let suma: f64 = modal.masas_efectivas.iter().map(|m| m[0]).sum();
    cerca(suma, mt, 1e-9, "suma de masas efectivas");
}

#[test]
fn masa_de_barra_con_brazos() {
    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(0.0, 0.0, 0.0);
    let b = m.agregar_nudo(6.0, 0.0, 0.0);
    m.agregar_barra(
        Barra3d::new(a, b, E, G, 0.12, 1e-3, 2e-3, 1e-3)
            .con_brazos([0.4, 0.0, 0.0], [-0.6, 0.0, 0.0]),
    );
    for tipo in [TipoMasa::Concentrada, TipoMasa::Consistente] {
        let masas = Masas3d {
            lineales: vec![(0, 2.0)],
            tipo,
            ..Masas3d::new()
        };
        let mm = ensamblar_masa(&m, &masas).unwrap();
        for d in 0..3 {
            let total: f64 = mm
                .iter()
                .filter(|((p, q), _)| p % 6 == d && q % 6 == d)
                .map(|(_, v)| v)
                .sum();
            cerca(total, 2.0 * 5.0, 1e-12, "masa de la parte flexible");
        }
    }
}

#[test]
fn errores_de_brazos_y_diafragmas() {
    let modelo_invalido = |m: &Modelo3d, texto: &str| match analizar_3d(m) {
        Err(ErrorNervi::ModeloInvalido(msg)) => assert!(msg.contains(texto), "{msg}"),
        otro => panic!("se esperaba un error con «{texto}»: {otro:?}"),
    };
    // Brazos que se tocan.
    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(0.0, 0.0, 0.0);
    let b = m.agregar_nudo(1.0, 0.0, 0.0);
    m.agregar_barra(columna(a, b, 1e-3, 1e-3, 1e-3).con_brazos([0.5, 0.0, 0.0], [-0.5, 0.0, 0.0]));
    m.empotrar(a);
    m.agregar_caso(CasoCarga3d::new("vacío"));
    modelo_invalido(&m, "brazos rígidos se tocan");

    // Esclavo con ux restringido.
    let mut p = planta([1.0; 4], [1.0; 4]);
    p.m.agregar_caso(CasoCarga3d::new("vacío"));
    p.m.apoyar(p.topes[1], [true, false, false, false, false, false]);
    modelo_invalido(&p.m, "solo se pueden restringir en el maestro");

    // Un nudo en dos diafragmas.
    let mut p = planta([1.0; 4], [1.0; 4]);
    p.m.agregar_caso(CasoCarga3d::new("vacío"));
    p.m.agregar_diafragma(&[p.topes[0], p.topes[1]], Some(p.topes[0]));
    modelo_invalido(&p.m, "cada nudo puede estar en uno solo");
}
