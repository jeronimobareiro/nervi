// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación del pórtico espacial (issue #11) contra soluciones cerradas, el
//! motor plano y la estática.
//!
//! Unidades: kN y m. Fuentes: Timoshenko y Gere, *Mechanics of Materials*
//! (voladizo y torsión uniforme); Hibbeler, *Structural Analysis* (trabajos
//! virtuales en cerchas y emparrillados); estática para el equilibrio global.

#![allow(clippy::needless_range_loop)]

use nervi_core::espacial::{
    analizar_3d, ejes_locales, Barra3d, CargaBarra3d, CasoCarga3d, Modelo3d, TipoCargaBarra3d,
};
use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Gdl, Modelo, TipoCargaBarra,
};

const E: f64 = 2.0e8;
const G: f64 = 7.7e7;
const A: f64 = 0.012;
const IY: f64 = 4.0e-5;
const IZ: f64 = 1.5e-4;
const J: f64 = 6.0e-6;
const TOL: f64 = 1e-9;

fn cerca(calc: f64, esperado: f64, escala: f64, que: &str) {
    assert!(
        (calc - esperado).abs() <= TOL * escala.abs().max(1e-300),
        "{que}: calculado {calc:e}, esperado {esperado:e}"
    );
}

fn barra(i: usize, j: usize) -> Barra3d {
    Barra3d::new(i, j, E, G, A, IY, IZ, J)
}

/// Rota un vector local a globales: `g = λᵀ l`.
fn a_global(r: &[[f64; 3]; 3], l: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|i| (0..3).map(|k| r[k][i] * l[k]).sum())
}

/// `l = λ g`.
fn a_local(r: &[[f64; 3]; 3], g: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|i| (0..3).map(|k| r[i][k] * g[k]).sum())
}

#[test]
fn voladizo_oblicuo_con_flexion_biaxial_axil_y_torsion() {
    // Barra en una dirección cualquiera del espacio, con vector de referencia,
    // empotrada en i y con cargas en el extremo dadas en ejes locales:
    //   u = PL/EA, v = Py L³/3EIz, w = Pz L³/3EIy, φ = TL/GJ,
    //   θz = Py L²/2EIz, θy = -Pz L²/2EIy (θy = -dw/dx).
    // Esfuerzos: Mz(x) = Py (L - x), My(x) = -Pz (L - x), Vy = -Py, Vz = Pz,
    // T = Tx, N = Px.
    let (pi, pj): ([f64; 3], [f64; 3]) = ([1.0, -2.0, 0.5], [3.5, 1.0, 4.0]);
    let refv = [0.2, 1.0, -0.4];
    let l = (pj[0] - pi[0]).hypot(pj[1] - pi[1]).hypot(pj[2] - pi[2]);
    let r = ejes_locales(pi, pj, Some(refv)).unwrap();
    let (px, py, pz, tx) = (30.0, -12.0, 7.0, 4.5);

    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(pi[0], pi[1], pi[2]);
    let b = m.agregar_nudo(pj[0], pj[1], pj[2]);
    m.agregar_barra(barra(a, b).con_referencia(refv));
    m.empotrar(a);
    let f = a_global(&r, [px, py, pz]);
    let mo = a_global(&r, [tx, 0.0, 0.0]);
    let mut c = CasoCarga3d::new("P");
    c.nodales.push((b, [f[0], f[1], f[2], mo[0], mo[1], mo[2]]));
    m.agregar_caso(c);
    let res = analizar_3d(&m).unwrap();
    let d = res.casos[0].desplazamientos[b];
    let tras = a_local(&r, [d[0], d[1], d[2]]);
    let giro = a_local(&r, [d[3], d[4], d[5]]);

    let esperado_t = [
        px * l / (E * A),
        py * l.powi(3) / (3.0 * E * IZ),
        pz * l.powi(3) / (3.0 * E * IY),
    ];
    let esperado_g = [
        tx * l / (G * J),
        -pz * l * l / (2.0 * E * IY),
        py * l * l / (2.0 * E * IZ),
    ];
    let escala_t = esperado_t.iter().fold(0.0_f64, |m, v| m.max(v.abs()));
    let escala_g = esperado_g.iter().fold(0.0_f64, |m, v| m.max(v.abs()));
    for k in 0..3 {
        cerca(
            tras[k],
            esperado_t[k],
            escala_t,
            &format!("traslación local {k}"),
        );
        cerca(giro[k], esperado_g[k], escala_g, &format!("giro local {k}"));
    }

    // Reacción: equilibra la carga y su momento respecto del empotramiento.
    let reac = res.casos[0].reacciones[a];
    let brazo = [pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2]];
    let mf = [
        brazo[1] * f[2] - brazo[2] * f[1],
        brazo[2] * f[0] - brazo[0] * f[2],
        brazo[0] * f[1] - brazo[1] * f[0],
    ];
    for k in 0..3 {
        cerca(reac[k], -f[k], 50.0, "reacción");
        cerca(reac[3 + k], -(mo[k] + mf[k]), 500.0, "momento de reacción");
    }

    for s in res.diagrama(0, 0, 7) {
        let resto = l - s.x;
        cerca(s.n, px, 50.0, "N");
        cerca(s.vy, -py, 50.0, "Vy");
        cerca(s.vz, pz, 50.0, "Vz");
        cerca(s.t, tx, 50.0, "T");
        cerca(s.mz, py * resto, 500.0, "Mz");
        cerca(s.my, -pz * resto, 500.0, "My");
        // Flecha del voladizo: v(x) = Py x²(3L - x)/(6EIz).
        cerca(
            s.v,
            py * s.x * s.x * (3.0 * l - s.x) / (6.0 * E * IZ),
            escala_t,
            "v(x)",
        );
        cerca(
            s.w,
            pz * s.x * s.x * (3.0 * l - s.x) / (6.0 * E * IY),
            escala_t,
            "w(x)",
        );
        cerca(s.rx, tx * s.x / (G * J), escala_g, "giro de torsión");
    }
}

#[test]
fn emparrillado_en_l_con_torsion() {
    // Emparrillado horizontal en L: AB sobre X (largo a), BC sobre Y (largo b),
    // empotrado en A, carga vertical P hacia abajo en C. AB trabaja a flexión y a
    // torsión (T = P·b). Por trabajos virtuales:
    //   δC = P a³/3EIz + P b³/3EIz + P b² a/GJ.
    // En vigas horizontales el eje y local es +Z, así que la flexión vertical usa Iz.
    let (a_l, b_l, p) = (3.0, 2.0, 10.0);
    let mut m = Modelo3d::new();
    let na = m.agregar_nudo(0.0, 0.0, 0.0);
    let nb = m.agregar_nudo(a_l, 0.0, 0.0);
    let nc = m.agregar_nudo(a_l, b_l, 0.0);
    m.agregar_barra(barra(na, nb));
    m.agregar_barra(barra(nb, nc));
    m.empotrar(na);
    let mut c = CasoCarga3d::new("P");
    c.nodales.push((nc, [0.0, 0.0, -p, 0.0, 0.0, 0.0]));
    m.agregar_caso(c);
    let res = analizar_3d(&m).unwrap();
    let rc = &res.casos[0];
    let esperado = -(p * a_l.powi(3) / (3.0 * E * IZ)
        + p * b_l.powi(3) / (3.0 * E * IZ)
        + p * b_l * b_l * a_l / (G * J));
    cerca(rc.desplazamientos[nc][2], esperado, esperado, "flecha en C");
    // Torsor en AB: el momento de P respecto del eje X en B es -P·b (alrededor de +X).
    let s = res.seccion(0, 0, 0.5 * a_l, false);
    cerca(s.t.abs(), p * b_l, p * b_l, "torsor en AB");
    // Reacciones en A: Rz = P, Mx = P·b, My = -P·a.
    let r = rc.reacciones[na];
    cerca(r[2], p, p, "Rz");
    cerca(r[3], p * b_l, p * b_l, "Mx");
    cerca(r[4], -p * a_l, p * a_l, "My");
}

#[test]
fn tripode_de_bielas() {
    // Cercha espacial: tres bielas iguales del vértice D(0, 0, h) a la base,
    // en un círculo de radio R a 0°, 120° y 240°, con apoyos fijos. Carga P hacia
    // abajo en D. Por simetría y equilibrio vertical N = -P L/(3h) en cada barra;
    // por trabajos virtuales δD = Σ N n L/EA = P L³/(3 h² EA).
    let (rad, h, p): (f64, f64, f64) = (2.0, 3.0, 60.0);
    let l = rad.hypot(h);
    let mut m = Modelo3d::new();
    let d = m.agregar_nudo(0.0, 0.0, h);
    for k in 0..3 {
        let ang = 2.0 * std::f64::consts::PI * k as f64 / 3.0;
        let n = m.agregar_nudo(rad * ang.cos(), rad * ang.sin(), 0.0);
        m.apoyar(n, [true, true, true, false, false, false]);
        m.agregar_barra(barra(n, d).biela());
    }
    let mut c = CasoCarga3d::new("P");
    c.nodales.push((d, [0.0, 0.0, -p, 0.0, 0.0, 0.0]));
    m.agregar_caso(c);
    let res = analizar_3d(&m).unwrap();
    let rc = &res.casos[0];
    cerca(
        rc.desplazamientos[d][2],
        -p * l.powi(3) / (3.0 * h * h * E * A),
        1.0,
        "descenso del vértice",
    );
    cerca(rc.desplazamientos[d][0], 0.0, 1e-6, "ux del vértice");
    cerca(rc.desplazamientos[d][1], 0.0, 1e-6, "uy del vértice");
    for k in 0..3 {
        let s = res.seccion(0, k, 0.5 * l, false);
        cerca(s.n, -p * l / (3.0 * h), p, "axil");
        for (v, que) in [
            (s.vy, "Vy"),
            (s.vz, "Vz"),
            (s.t, "T"),
            (s.my, "My"),
            (s.mz, "Mz"),
        ] {
            cerca(v, 0.0, p, que);
        }
    }
    // Los giros de los cuatro nudos no tienen rigidez y se fijan solos.
    assert_eq!(res.gdl_sin_rigidez.len(), 12, "{:?}", res.gdl_sin_rigidez);
}

/// Pórtico plano en el plano XZ resuelto con los dos motores. Datos 2D:
/// columnas y viga con articulación, barra inclinada, resorte, asentamiento y
/// cargas nodales, uniformes, puntuales y trapezoidales en ejes locales y globales.
fn portico_plano() -> Modelo {
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(0.0, 4.0);
    let n2 = m.agregar_nudo(6.0, 5.0);
    let n3 = m.agregar_nudo(6.0, 0.0);
    let n4 = m.agregar_nudo(10.0, 3.0);
    m.agregar_barra(Barra::new(n0, n1, E, A, IZ));
    let mut viga = Barra::new(n1, n2, E, A, 2.0 * IZ);
    viga.liberaciones[5] = true; // articulada en n2
    m.agregar_barra(viga);
    m.agregar_barra(Barra::new(n3, n2, E, A, IZ));
    m.agregar_barra(Barra::new(n4, n2, E, 0.5 * A, IZ)); // de derecha a izquierda
    m.apoyar(n0, true, true, true);
    m.apoyar(n3, true, true, false);
    m.apoyar(n4, false, true, false);
    m.resorte(n4, 3.0e3, 0.0, 0.0);
    let mut c = CasoCarga::new("todo");
    c.nodales.push((n1, [15.0, -20.0, 8.0]));
    c.desplazamientos_impuestos.push((n3, [0.0, -0.004, 0.0]));
    c.en_barras.push(CargaBarra {
        barra: 1,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra::Uniforme { qx: 0.0, qy: -12.0 },
    });
    c.en_barras.push(CargaBarra {
        barra: 0,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Puntual {
            a: 1.5,
            px: 2.0,
            py: -9.0,
        },
    });
    c.en_barras.push(CargaBarra {
        barra: 3,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Trapezoidal {
            a: 0.5,
            b: 4.0,
            qx1: 1.0,
            qy1: -3.0,
            qx2: -2.0,
            qy2: 6.0,
        },
    });
    c.en_barras.push(CargaBarra {
        barra: 2,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra::Trapezoidal {
            a: 1.0,
            b: 3.0,
            qx1: 4.0,
            qy1: 0.0,
            qx2: 1.0,
            qy2: 0.0,
        },
    });
    m.agregar_caso(c);
    m
}

/// El mismo pórtico en el plano XZ (Y del plano → Z), con el vector de
/// referencia igual al eje y local plano para que los ejes coincidan y los GDL
/// fuera del plano restringidos. `rz` plano equivale a `-ry` espacial porque, visto
/// desde -Y, el eje que sale del dibujo es -Y.
fn portico_espacial(p: &Modelo) -> Modelo3d {
    let mut m = Modelo3d::new();
    for &[x, y] in &p.nudos {
        let n = m.agregar_nudo(x, 0.0, y);
        m.apoyar(n, [false, true, false, true, false, true]);
    }
    for b in &p.barras {
        let (_, c, s) = p.geometria_barra(b);
        let mut b3 =
            Barra3d::new(b.nudo_i, b.nudo_j, E, G, b.a, IY, b.i, J).con_referencia([-s, 0.0, c]);
        let mapa = [0, 1, 5];
        for k in 0..6 {
            b3.liberaciones[6 * (k / 3) + mapa[k % 3]] = b.liberaciones[k];
        }
        m.agregar_barra(b3);
    }
    let a3 = |v: [f64; 3]| [v[0], 0.0, v[1], 0.0, -v[2], 0.0];
    for (n, r) in p.restricciones.iter().enumerate() {
        m.apoyar(n, [r[0], false, r[1], false, r[2], false]);
    }
    for (n, k) in p.resortes.iter().enumerate() {
        m.resorte(n, [k[0], 0.0, k[1], 0.0, k[2], 0.0]);
    }
    for caso in &p.casos {
        let mut c = CasoCarga3d::new(caso.nombre.clone());
        c.nodales = caso.nodales.iter().map(|&(n, f)| (n, a3(f))).collect();
        c.desplazamientos_impuestos = caso
            .desplazamientos_impuestos
            .iter()
            .map(|&(n, d)| (n, a3(d)))
            .collect();
        for cb in &caso.en_barras {
            let tipo = match cb.tipo {
                TipoCargaBarra::Uniforme { qx, qy } => TipoCargaBarra3d::Uniforme {
                    q: if cb.ejes == Ejes::Local {
                        [qx, qy, 0.0]
                    } else {
                        [qx, 0.0, qy]
                    },
                },
                TipoCargaBarra::Puntual { a, px, py } => TipoCargaBarra3d::Puntual {
                    a,
                    p: if cb.ejes == Ejes::Local {
                        [px, py, 0.0]
                    } else {
                        [px, 0.0, py]
                    },
                },
                TipoCargaBarra::Trapezoidal {
                    a,
                    b,
                    qx1,
                    qy1,
                    qx2,
                    qy2,
                } => {
                    let (q1, q2) = if cb.ejes == Ejes::Local {
                        ([qx1, qy1, 0.0], [qx2, qy2, 0.0])
                    } else {
                        ([qx1, 0.0, qy1], [qx2, 0.0, qy2])
                    };
                    TipoCargaBarra3d::Trapezoidal { a, b, q1, q2 }
                }
                _ => unreachable!("el pórtico de prueba no usa otras cargas"),
            };
            c.en_barras.push(CargaBarra3d {
                barra: cb.barra,
                ejes: cb.ejes,
                tipo,
            });
        }
        m.agregar_caso(c);
    }
    m
}

#[test]
fn portico_plano_en_xz_coincide_con_el_motor_plano() {
    let p = portico_plano();
    let r2 = analizar(&p).unwrap();
    let r3 = analizar_3d(&portico_espacial(&p)).unwrap();
    let (c2, c3) = (&r2.casos[0], &r3.casos[0]);
    let du = c2
        .desplazamientos
        .iter()
        .flatten()
        .fold(0.0_f64, |m, v| m.max(v.abs()));
    let fu = c2
        .reacciones
        .iter()
        .flatten()
        .chain(c2.fuerzas_extremo.iter().flatten())
        .fold(0.0_f64, |m, v| m.max(v.abs()));
    for n in 0..p.nudos.len() {
        let (d2, d3) = (c2.desplazamientos[n], c3.desplazamientos[n]);
        let (q2, q3) = (c2.reacciones[n], c3.reacciones[n]);
        cerca(d3[0], d2[0], du, "ux");
        cerca(d3[2], d2[1], du, "uz");
        cerca(d3[4], -d2[2], du, "ry");
        cerca(q3[0], q2[0], fu, "Rx");
        cerca(q3[2], q2[1], fu, "Rz");
        cerca(q3[4], -q2[2], fu, "My");
        for k in [1, 3, 5] {
            cerca(d3[k], 0.0, du, "GDL fuera del plano");
        }
    }
    for b in 0..p.barras.len() {
        let (f2, f3) = (c2.fuerzas_extremo[b], c3.fuerzas_extremo[b]);
        for (k, k3) in [0, 1, 5, 6, 7, 11].into_iter().enumerate() {
            cerca(
                f3[k3],
                f2[k],
                fu,
                &format!("barra {b}: fuerza de extremo {k}"),
            );
        }
        for k3 in [2, 3, 4, 8, 9, 10] {
            cerca(f3[k3], 0.0, fu, "fuerza fuera del plano");
        }
        let d2 = r2.diagrama(0, b, 9);
        let d3 = r3.diagrama(0, b, 9);
        assert_eq!(d2.len(), d3.len(), "barra {b}: estaciones");
        for (s2, s3) in d2.iter().zip(&d3) {
            cerca(s3.x, s2.x, 10.0, "x");
            cerca(s3.n, s2.n, fu, "N");
            cerca(s3.vy, s2.v, fu, "V");
            cerca(s3.mz, s2.m, fu, "M");
            cerca(s3.u, s2.u_local, du, "u");
            cerca(s3.v, s2.v_local, du, "v");
            cerca(s3.my, 0.0, fu, "My");
            cerca(s3.w, 0.0, du, "w");
        }
    }
}

#[test]
fn viga_biapoyada_flexion_en_z_local() {
    // Viga biapoyada (con la torsión impedida en un extremo) con carga uniforme
    // -q en z local: el plano x–z reproduce qL²/8 y 5qL⁴/384EIy, con
    // My(L/2) = -qL²/8 (la fibra +z queda comprimida) y Vz(0) = -qL/2.
    let (l, q) = (5.0, 8.0);
    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(0.0, 0.0, 0.0);
    let b = m.agregar_nudo(l, 0.0, 0.0);
    m.agregar_barra(barra(a, b));
    m.apoyar(a, [true, true, true, true, false, false]);
    m.apoyar(b, [false, true, true, false, false, false]);
    let mut c = CasoCarga3d::new("q");
    c.en_barras.push(CargaBarra3d {
        barra: 0,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra3d::Uniforme { q: [0.0, 0.0, -q] },
    });
    m.agregar_caso(c);
    let res = analizar_3d(&m).unwrap();
    let diag = res.diagrama(0, 0, 4); // sin estación en L/2: la agrega el cortante nulo
    let medio = diag
        .iter()
        .find(|s| (s.x - 0.5 * l).abs() < 1e-12)
        .expect("estación de cortante nulo en L/2");
    let m0 = q * l * l / 8.0;
    cerca(medio.my, -m0, m0, "My(L/2)");
    cerca(medio.mz, 0.0, m0, "Mz(L/2)");
    cerca(diag[0].vz, -q * l / 2.0, q * l, "Vz(0)");
    let w0 = 5.0 * q * l.powi(4) / (384.0 * E * IY);
    cerca(medio.w, -w0, w0, "flecha w(L/2)");
}

#[test]
fn equilibrio_global_de_un_portico_espacial() {
    // Pórtico de dos niveles en planta rectangular, con barras inclinadas, cargas
    // de todos los tipos en ejes locales y globales y vectores de referencia
    // arbitrarios. Las reacciones equilibran las cargas: ΣF = 0 y ΣM_O = 0.
    let mut m = Modelo3d::new();
    let (lx, ly, h) = (6.0, 4.0, 3.2);
    let mut nivel = Vec::new();
    for z in [0.0, h, 2.0 * h] {
        let fila: Vec<usize> = [(0.0, 0.0), (lx, 0.0), (lx, ly), (0.0, ly)]
            .iter()
            .map(|&(x, y)| m.agregar_nudo(x, y, z))
            .collect();
        nivel.push(fila);
    }
    for k in 0..4 {
        m.empotrar(nivel[0][k]);
        for p in 0..2 {
            m.agregar_barra(barra(nivel[p][k], nivel[p + 1][k]));
            m.agregar_barra(
                barra(nivel[p + 1][k], nivel[p + 1][(k + 1) % 4]).con_referencia([0.1, 0.3, 1.0]),
            );
        }
    }
    let diag = m.agregar_barra(barra(nivel[0][0], nivel[1][2]).con_referencia([1.0, -1.0, 0.0]));
    let mut c = CasoCarga3d::new("todo");
    c.nodales
        .push((nivel[2][1], [5.0, -3.0, -20.0, 2.0, -1.0, 4.0]));
    c.nodales
        .push((nivel[1][3], [-8.0, 6.0, 0.0, 0.0, 3.0, 0.0]));
    c.en_barras.push(CargaBarra3d {
        barra: 3,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra3d::Uniforme {
            q: [1.0, 0.5, -15.0],
        },
    });
    c.en_barras.push(CargaBarra3d {
        barra: 7,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra3d::Puntual {
            a: 1.7,
            p: [3.0, -9.0, 4.0],
        },
    });
    c.en_barras.push(CargaBarra3d {
        barra: diag,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra3d::Trapezoidal {
            a: 0.5,
            b: 4.0,
            q1: [0.5, 2.0, -3.0],
            q2: [-1.0, -4.0, 6.0],
        },
    });
    c.en_barras.push(CargaBarra3d {
        barra: 2,
        ejes: Ejes::Global,
        tipo: TipoCargaBarra3d::Trapezoidal {
            a: 0.0,
            b: 3.2,
            q1: [2.0, 0.0, 0.0],
            q2: [5.0, -1.0, 0.0],
        },
    });
    m.agregar_caso(c);
    let res = analizar_3d(&m).unwrap();

    // Resultantes de las cargas respecto del origen. Fuerza y posición son
    // lineales en s, así que el momento es cuadrático y Simpson es exacto.
    let mut f = [0.0; 3];
    let mut mo = [0.0; 3];
    let mut pares = [0.0; 3];
    let mut sumar = |r: [f64; 3], p: [f64; 3], w: f64| {
        for k in 0..3 {
            f[k] += w * p[k];
        }
        let rxp = [
            r[1] * p[2] - r[2] * p[1],
            r[2] * p[0] - r[0] * p[2],
            r[0] * p[1] - r[1] * p[0],
        ];
        for k in 0..3 {
            mo[k] += w * rxp[k];
        }
    };
    for (n, carga) in &m.casos[0].nodales {
        sumar(m.nudos[*n], [carga[0], carga[1], carga[2]], 1.0);
        for k in 0..3 {
            pares[k] += carga[3 + k];
        }
    }
    for cb in &m.casos[0].en_barras {
        let b = &m.barras[cb.barra];
        let r = m.ejes_barra(b).unwrap();
        let pi = m.nudos[b.nudo_i];
        let l = m.longitud(b);
        let pos = |s: f64| -> [f64; 3] { std::array::from_fn(|k| pi[k] + r[0][k] * s) };
        let glob = |v: [f64; 3]| {
            if cb.ejes == Ejes::Local {
                a_global(&r, v)
            } else {
                v
            }
        };
        match cb.tipo {
            TipoCargaBarra3d::Uniforme { q } => {
                for (s, w) in [(0.0, l / 6.0), (0.5 * l, 4.0 * l / 6.0), (l, l / 6.0)] {
                    sumar(pos(s), glob(q), w);
                }
            }
            TipoCargaBarra3d::Puntual { a, p } => sumar(pos(a), glob(p), 1.0),
            TipoCargaBarra3d::Trapezoidal { a, b: fin, q1, q2 } => {
                let d = fin - a;
                let qm: [f64; 3] = std::array::from_fn(|k| 0.5 * (q1[k] + q2[k]));
                for (s, q, w) in [
                    (a, q1, d / 6.0),
                    (a + 0.5 * d, qm, 4.0 * d / 6.0),
                    (fin, q2, d / 6.0),
                ] {
                    sumar(pos(s), glob(q), w);
                }
            }
        }
    }
    let rc = &res.casos[0];
    let mut fr = [0.0; 3];
    let mut mr = [0.0; 3];
    for (n, reac) in rc.reacciones.iter().enumerate() {
        let p = m.nudos[n];
        for k in 0..3 {
            fr[k] += reac[k];
            mr[k] += reac[3 + k];
        }
        mr[0] += p[1] * reac[2] - p[2] * reac[1];
        mr[1] += p[2] * reac[0] - p[0] * reac[2];
        mr[2] += p[0] * reac[1] - p[1] * reac[0];
    }
    for k in 0..3 {
        cerca(fr[k] + f[k], 0.0, 100.0, "ΣF");
        cerca(mr[k] + mo[k] + pares[k], 0.0, 1000.0, "ΣM");
    }
}

#[test]
fn torsion_sin_restriccion_es_un_mecanismo() {
    // Viga sobre X apoyada en traslaciones en los dos extremos, sin nada que
    // impida el giro alrededor de su eje: el modo de mecanismo es rx.
    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(0.0, 0.0, 0.0);
    let b = m.agregar_nudo(2.0, 0.0, 0.0);
    let c = m.agregar_nudo(4.0, 0.0, 0.0);
    m.agregar_barra(barra(a, b));
    m.agregar_barra(barra(b, c));
    m.apoyar(a, [true, true, true, false, false, false]);
    m.apoyar(c, [false, true, true, false, false, false]);
    let mut caso = CasoCarga3d::new("P");
    caso.nodales.push((b, [0.0, 0.0, -10.0, 0.0, 0.0, 0.0]));
    m.agregar_caso(caso);
    match analizar_3d(&m) {
        Err(ErrorNervi::Mecanismo(d)) => {
            assert_eq!(d.ubicacion.map(|u| u.1), Some(Gdl::Rx), "{d:?}");
            assert_eq!(d.nudos(), vec![a, b, c]);
        }
        otro => panic!("se esperaba un mecanismo, se obtuvo {otro:?}"),
    }
}

#[test]
fn vector_de_referencia_paralelo_es_un_error() {
    let mut m = Modelo3d::new();
    let a = m.agregar_nudo(0.0, 0.0, 0.0);
    let b = m.agregar_nudo(0.0, 0.0, 3.0);
    m.agregar_barra(barra(a, b).con_referencia([0.0, 0.0, 1.0]));
    m.empotrar(a);
    m.agregar_caso(CasoCarga3d::new("vacío"));
    assert!(matches!(
        analizar_3d(&m),
        Err(ErrorNervi::ModeloInvalido(_))
    ));
}
