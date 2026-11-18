// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación de masas, análisis modal y espectro de respuesta del pórtico
//! espacial (issues #16, #17 y #18) contra soluciones cerradas.
//!
//! Unidades: kN, m, s y t (kN·s²/m). Fuentes de las soluciones cerradas:
//! - Viga de Euler-Bernoulli simplemente apoyada `ωₙ = (nπ/L)² √(EI/m)` y en
//!   voladizo `ωₙ = (βₙL)² √(EI/(m L⁴))` con `β₁L = 1.875104`, `β₂L = 4.694091`,
//!   `β₃L = 7.854757`: Chopra, *Dynamics of Structures*, 4.ª ed., §16.3
//!   (tabla de frecuencias de vigas uniformes); Clough y Penzien, *Dynamics of
//!   Structures*, 2.ª ed., cap. 18.
//! - Edificio de cortante de dos pisos `ω² = (k/m)(3 ∓ √5)/2`: Chopra, op. cit.,
//!   cap. 10 (ejemplo de dos pisos con masas y rigideces iguales).
//! - Factor de participación, masa efectiva, SRSS y CQC: Chopra, op. cit.,
//!   §13.2 y §13.7 (ec. 13.7.10).
//! - Rigidez lateral de una columna biempotrada sin giro en los extremos
//!   `12 EI/h³` y en voladizo `3 EI/h³`.

#![allow(clippy::needless_range_loop)]

use std::f64::consts::PI;

use nervi_core::espacial::dinamica::ensamblar_masa;
use nervi_core::espacial::{
    analizar_espectro_3d, analizar_modal_3d, coeficiente_cqc, Barra3d, CargaBarra3d, CasoCarga3d,
    CombinacionModal, Espectro, Masas3d, MetodoModal, Modelo3d, ResultadosModal3d,
    TipoCargaBarra3d, TipoMasa,
};
use nervi_core::{Ejes, ErrorNervi};

fn relativo(calc: f64, esperado: f64) -> f64 {
    (calc - esperado).abs() / esperado.abs()
}

fn cerca(calc: f64, esperado: f64, tol: f64, que: &str) {
    assert!(
        relativo(calc, esperado) <= tol,
        "{que}: calculado {calc:e}, esperado {esperado:e} (error {:e})",
        relativo(calc, esperado)
    );
}

/// Viga sobre X de `n` elementos con masa `m` por unidad de longitud.
fn viga(l: f64, n: usize, props: [f64; 6]) -> Modelo3d {
    let mut md = Modelo3d::new();
    for k in 0..=n {
        md.agregar_nudo(l * k as f64 / n as f64, 0.0, 0.0);
    }
    let [e, g, a, iy, iz, j] = props;
    for k in 0..n {
        md.agregar_barra(Barra3d::new(k, k + 1, e, g, a, iy, iz, j));
    }
    md
}

/// Componente traslacional dominante de un modo (0 = X, 1 = Y, 2 = Z).
fn direccion_dominante(modal: &ResultadosModal3d, k: usize) -> usize {
    let mut suma = [0.0; 3];
    for nudo in &modal.modos[k] {
        for d in 0..3 {
            suma[d] += nudo[d] * nudo[d];
        }
    }
    (0..3).max_by(|&a, &b| suma[a].total_cmp(&suma[b])).unwrap()
}

#[test]
fn viga_simplemente_apoyada_masa_consistente() {
    // Flexión vertical con Iz (en una viga horizontal el eje y local es +Z).
    // Flexión lateral, axil y torsión mucho más rígidos para que los tres
    // primeros modos sean verticales.
    let (l, n, m) = (6.0, 12, 0.1);
    let props = [2.0e8, 8.0e7, 0.2, 0.05, 2.0e-4, 1.0];
    let mut md = viga(l, n, props);
    md.apoyar(0, [true, true, true, true, false, false]);
    md.apoyar(n, [false, true, true, false, false, false]);
    let mut masas = Masas3d::new();
    masas.tipo = TipoMasa::Consistente;
    masas.lineales = (0..n).map(|b| (b, m)).collect();
    let r = analizar_modal_3d(&md, &masas, 3, MetodoModal::Denso).unwrap();
    assert_eq!(r.omegas.len(), 3);
    let ei = props[0] * props[4];
    for k in 0..3 {
        let esperada = ((k + 1) as f64 * PI / l).powi(2) * (ei / m).sqrt();
        cerca(r.omegas[k], esperada, 5e-4, &format!("ω{}", k + 1));
        cerca(r.periodos[k], 2.0 * PI / esperada, 5e-4, "T");
        assert_eq!(direccion_dominante(&r, k), 2, "modo {} vertical", k + 1);
    }
    // Normalización a masa y ortogonalidad: φᵢᵀ M φⱼ = δᵢⱼ.
    for i in 0..3 {
        for j in 0..3 {
            let p: f64 = (0..=n)
                .map(|nd| {
                    (0..6)
                        .map(|d| r.modos[i][nd][d] * r.inercias[j][nd][d])
                        .sum::<f64>()
                })
                .sum();
            let esperado = if i == j { 1.0 } else { 0.0 };
            assert!((p - esperado).abs() < 1e-9, "φ{i}ᵀMφ{j} = {p}");
        }
    }
    // Masa total que puede moverse en Z: la de toda la viga menos la de los
    // apoyos (ninguna en masa consistente, que acopla los GDL).
    assert!(r.masa_total[2] < m * l);
}

#[test]
fn voladizo_converge_con_masa_concentrada_y_consistente() {
    let (l, m): (f64, f64) = (3.0, 0.25);
    let props = [3.0e7, 1.2e7, 3.0, 5.0, 2.0e-3, 1000.0];
    let ei = props[0] * props[4];
    let beta_l: [f64; 3] = [1.875_104_07, 4.694_091_13, 7.854_757_44];
    let exacta = |k: usize| beta_l[k].powi(2) * (ei / (m * l.powi(4))).sqrt();

    let resolver = |n: usize, tipo: TipoMasa| {
        let mut md = viga(l, n, props);
        md.empotrar(0);
        let mut masas = Masas3d::new();
        masas.tipo = tipo;
        masas.lineales = (0..n).map(|b| (b, m)).collect();
        analizar_modal_3d(&md, &masas, 3, MetodoModal::Automatico).unwrap()
    };
    // Consistente: 10 elementos alcanzan para los tres primeros modos.
    let c = resolver(10, TipoMasa::Consistente);
    for k in 0..3 {
        assert_eq!(direccion_dominante(&c, k), 2);
        cerca(
            c.omegas[k],
            exacta(k),
            1e-3,
            &format!("consistente ω{}", k + 1),
        );
        // La masa consistente sobrestima la frecuencia (cota superior).
        assert!(c.omegas[k] >= exacta(k) * (1.0 - 1e-9));
    }
    // Concentrada: converge al refinar la malla.
    let gruesa = resolver(10, TipoMasa::Concentrada);
    let fina = resolver(40, TipoMasa::Concentrada);
    let (eg, ef) = (
        relativo(gruesa.omegas[0], exacta(0)),
        relativo(fina.omegas[0], exacta(0)),
    );
    assert!(ef < eg, "no converge: {eg:e} -> {ef:e}");
    cerca(
        fina.omegas[0],
        exacta(0),
        5e-3,
        "concentrada ω1 con 40 elementos",
    );
    cerca(
        fina.omegas[1],
        exacta(1),
        5e-3,
        "concentrada ω2 con 40 elementos",
    );
    // Con masa concentrada solo las traslaciones tienen masa.
    assert_eq!(fina.n_gdl_masa, 3 * 40);
}

/// Edificio de cortante de `pisos` pisos, cuatro columnas en las esquinas de
/// un rectángulo de `2a × 2b`, vigas prácticamente rígidas y masa `m` por piso
/// repartida en las esquinas (traslacional en X, Y y Z).
struct Edificio {
    modelo: Modelo3d,
    masas: Masas3d,
    kx: f64,
    ky: f64,
    kt_columna: f64,
}

fn edificio(pisos: usize, m: f64, a: f64, b: f64) -> Edificio {
    let (h, e, g) = (3.0, 2.5e7, 1.0e7);
    let (ac, iy, iz, j) = (1.0e4, 6.0e-3, 4.0e-3, 1.0e-3);
    let rigida = 1.0e5;
    let esquinas = [(-a, -b), (a, -b), (a, b), (-a, b)];
    let mut md = Modelo3d::new();
    let mut masas = Masas3d::new();
    for p in 0..=pisos {
        for (x, y) in esquinas {
            md.agregar_nudo(x, y, h * p as f64);
        }
    }
    for k in 0..4 {
        md.empotrar(k);
    }
    for p in 1..=pisos {
        for k in 0..4 {
            let (abajo, arriba) = (4 * (p - 1) + k, 4 * p + k);
            md.agregar_barra(Barra3d::new(abajo, arriba, e, g, ac, iy, iz, j));
            let siguiente = 4 * p + (k + 1) % 4;
            md.agregar_barra(Barra3d::new(
                arriba,
                siguiente,
                e * rigida,
                g * rigida,
                1.0,
                1.0,
                1.0,
                1.0,
            ));
            masas
                .nodales
                .push((arriba, [m / 4.0, m / 4.0, m / 4.0, 0.0, 0.0, 0.0]));
        }
    }
    // En una columna vertical el eje y local es -X: el desplazamiento en X
    // flexiona con Iz y el desplazamiento en Y con Iy.
    Edificio {
        modelo: md,
        masas,
        kx: 4.0 * 12.0 * e * iz / h.powi(3),
        ky: 4.0 * 12.0 * e * iy / h.powi(3),
        kt_columna: g * j / h,
    }
}

#[test]
fn edificio_de_cortante_de_dos_pisos() {
    let m = 20.0;
    let ed = edificio(2, m, 3.0, 2.0);
    let todos_x = analizar_modal_3d(&ed.modelo, &ed.masas, 6, MetodoModal::Denso).unwrap();
    // Los dos modos con participación en X (entre ellos hay modos en Y y de
    // torsión, que no participan en X).
    let x: Vec<usize> = (0..6)
        .filter(|&k| todos_x.masas_efectivas[k][0] > 1e-6 * m)
        .collect();
    assert_eq!(x.len(), 2);
    let r = ResultadosModal3d {
        omegas: x.iter().map(|&k| todos_x.omegas[k]).collect(),
        modos: x.iter().map(|&k| todos_x.modos[k].clone()).collect(),
        factores_participacion: x
            .iter()
            .map(|&k| todos_x.factores_participacion[k])
            .collect(),
        masas_efectivas: x.iter().map(|&k| todos_x.masas_efectivas[k]).collect(),
        ..todos_x.clone()
    };
    let k = ed.kx;
    let w1 = ((3.0 - 5f64.sqrt()) / 2.0 * k / m).sqrt();
    let w2 = ((3.0 + 5f64.sqrt()) / 2.0 * k / m).sqrt();
    cerca(r.omegas[0], w1, 1e-5, "ω1");
    cerca(r.omegas[1], w2, 1e-5, "ω2");
    // Formas modales (piso 1, piso 2): φ1 ∝ (1, φ), φ2 ∝ (1, 1 - φ), con φ el
    // número de oro. Normalizadas a masa con M = diag(m, m).
    let oro = (1.0 + 5f64.sqrt()) / 2.0;
    for (modo, (r1, r2)) in [(0, (1.0, oro)), (1, (1.0, 1.0 - oro))] {
        let norma = (m * (r1 * r1 + r2 * r2)).sqrt();
        let (p1, p2) = (r1 / norma, r2 / norma);
        let signo = if p2.abs() > p1.abs() {
            p2.signum()
        } else {
            p1.signum()
        };
        for e in 0..4 {
            cerca(r.modos[modo][4 + e][0], signo * p1, 1e-5, "φ piso 1");
            cerca(r.modos[modo][8 + e][0], signo * p2, 1e-5, "φ piso 2");
        }
        // Γ = φᵀ M 1 y masa efectiva Γ².
        let gamma = m * (p1 + p2) * signo;
        cerca(r.factores_participacion[modo][0], gamma, 1e-5, "Γx");
        cerca(
            r.masas_efectivas[modo][0],
            gamma * gamma,
            1e-5,
            "masa efectiva",
        );
        assert!(r.factores_participacion[modo][1].abs() < 1e-6 * gamma.abs());
    }
    cerca(r.masa_total[0], 2.0 * m, 1e-12, "masa total X");
    // Con todos los modos, las masas efectivas suman la masa total.
    let todos = analizar_modal_3d(&ed.modelo, &ed.masas, 1000, MetodoModal::Denso).unwrap();
    assert_eq!(todos.omegas.len(), todos.n_gdl_masa);
    for d in 0..3 {
        let suma: f64 = todos.masas_efectivas.iter().map(|x| x[d]).sum();
        cerca(suma, todos.masa_total[d], 1e-9, "suma de masas efectivas");
    }
}

#[test]
fn piso_con_modos_de_traslacion_y_torsion() {
    let (m, a, b) = (40.0, 3.0, 2.0);
    let mut ed = edificio(1, m, a, b);
    // Sin masa vertical, para que solo queden los tres modos del piso.
    for (_, mm) in ed.masas.nodales.iter_mut() {
        mm[2] = 0.0;
    }
    let r = analizar_modal_3d(&ed.modelo, &ed.masas, 3, MetodoModal::Denso).unwrap();
    let wx = (ed.kx / m).sqrt();
    let wy = (ed.ky / m).sqrt();
    // Torsión: cada columna aporta kx·y² + ky·x² + GJ/h; inercia polar m(a² + b²).
    let kt = ed.kx * b * b + ed.ky * a * a + 4.0 * ed.kt_columna;
    let wt = (kt / (m * (a * a + b * b))).sqrt();
    let mut esperadas = [wx, wy, wt];
    esperadas.sort_by(f64::total_cmp);
    for k in 0..3 {
        cerca(r.omegas[k], esperadas[k], 1e-5, &format!("ω{}", k + 1));
    }
    // El modo de torsión no tiene participación en X ni en Y.
    let kt_modo = (0..3).find(|&k| relativo(r.omegas[k], wt) < 1e-5).unwrap();
    for d in 0..2 {
        assert!(r.masas_efectivas[kt_modo][d] < 1e-9 * m);
    }
}

#[test]
fn lanczos_da_lo_mismo_que_el_metodo_denso() {
    // Pórtico de 2 × 2 vanos y 4 pisos con masa consistente en vigas y columnas.
    let (e, g) = (2.5e7, 1.0e7);
    let mut md = Modelo3d::new();
    let mut idx = vec![vec![vec![0; 3]; 3]; 5];
    for p in 0..5 {
        for i in 0..3 {
            for j in 0..3 {
                idx[p][i][j] = md.agregar_nudo(5.0 * i as f64, 4.0 * j as f64, 3.0 * p as f64);
            }
        }
    }
    let mut masas = Masas3d::new();
    masas.tipo = TipoMasa::Consistente;
    for i in 0..3 {
        for j in 0..3 {
            md.empotrar(idx[0][i][j]);
        }
    }
    let mut agregar = |md: &mut Modelo3d, a: usize, b: usize, ancho: f64| {
        let bar = md.agregar_barra(Barra3d::new(
            a,
            b,
            e,
            g,
            0.3 * ancho,
            0.3 * ancho.powi(3) / 12.0,
            ancho * 0.027 / 12.0,
            2e-3,
        ));
        masas.lineales.push((bar, 2.4 * 0.3 * ancho));
    };
    for p in 1..5 {
        for i in 0..3 {
            for j in 0..3 {
                agregar(&mut md, idx[p - 1][i][j], idx[p][i][j], 0.4);
                if i < 2 {
                    agregar(&mut md, idx[p][i][j], idx[p][i + 1][j], 0.5);
                }
                if j < 2 {
                    agregar(&mut md, idx[p][i][j], idx[p][i][j + 1], 0.5);
                }
            }
        }
    }
    let denso = analizar_modal_3d(&md, &masas, 8, MetodoModal::Denso).unwrap();
    let lanczos = analizar_modal_3d(&md, &masas, 8, MetodoModal::Lanczos).unwrap();
    assert_eq!(lanczos.metodo, MetodoModal::Lanczos);
    assert_eq!(denso.omegas.len(), 8);
    assert_eq!(lanczos.omegas.len(), 8);
    for k in 0..8 {
        cerca(
            lanczos.omegas[k],
            denso.omegas[k],
            1e-8,
            &format!("ω{}", k + 1),
        );
        let suma = |r: &ResultadosModal3d| r.masas_efectivas[k].iter().sum::<f64>();
        let total = denso.masa_total.iter().sum::<f64>();
        assert!(
            (suma(&lanczos) - suma(&denso)).abs() < 1e-6 * total,
            "masa efectiva del modo {}",
            k + 1
        );
    }
}

#[test]
fn espectro_de_un_grado_de_libertad() {
    // Columna en voladizo de 3 m con una masa M en la punta, solo en X.
    let (h, e, iz, mm) = (3.0, 2.5e7, 2.0e-3, 12.0);
    let mut md = Modelo3d::new();
    let base = md.agregar_nudo(0.0, 0.0, 0.0);
    let punta = md.agregar_nudo(0.0, 0.0, h);
    md.agregar_barra(Barra3d::new(
        base, punta, e, 1.0e7, 0.16, 3.0e-3, iz, 1.0e-3,
    ));
    md.empotrar(base);
    let mut masas = Masas3d::new();
    masas.nodales.push((punta, [mm, 0.0, 0.0, 0.0, 0.0, 0.0]));
    let modal = analizar_modal_3d(&md, &masas, 5, MetodoModal::Automatico).unwrap();
    assert_eq!(modal.omegas.len(), 1);
    let w = (3.0 * e * iz / (h.powi(3) * mm)).sqrt();
    cerca(modal.omegas[0], w, 1e-10, "ω");
    // Espectro con un tramo inclinado que contiene a T.
    let t = 2.0 * PI / w;
    let esp = Espectro::new(vec![0.0, t / 2.0, 2.0 * t], vec![2.0, 6.0, 3.0]).unwrap();
    let sa = 6.0 - 3.0 * (t - t / 2.0) / (1.5 * t);
    cerca(esp.sa(t), sa, 1e-12, "Sa");
    let r = analizar_espectro_3d(
        &md,
        &modal,
        &esp,
        [1.0, 0.0, 0.0],
        0.05,
        CombinacionModal::Cqc,
    )
    .unwrap();
    cerca(
        r.desplazamientos[punta][0],
        sa / (w * w),
        1e-10,
        "desplazamiento",
    );
    cerca(r.cortante_basal[0], mm * sa, 1e-10, "cortante basal");
    cerca(r.reacciones[base][0], mm * sa, 1e-10, "reacción");
    cerca(
        r.reacciones[base][4],
        mm * sa * h,
        1e-10,
        "momento en la base",
    );
    let s0 = r.seccion(0, 0.0);
    cerca(s0.mz, mm * sa * h, 1e-10, "Mz en la base");
    cerca(s0.vy, mm * sa, 1e-10, "Vy");
    cerca(
        r.seccion(0, h / 2.0).mz,
        mm * sa * h / 2.0,
        1e-10,
        "Mz a media altura",
    );
    assert_eq!(r.diagrama(0, 5).len(), 5);
    // En Y no hay masa: respuesta nula.
    let ry = analizar_espectro_3d(
        &md,
        &modal,
        &esp,
        [0.0, 1.0, 0.0],
        0.05,
        CombinacionModal::Srss,
    )
    .unwrap();
    assert!(ry.cortante_basal[0].abs() < 1e-12);
}

#[test]
fn espectro_de_dos_pisos_srss_y_cqc() {
    let m = 20.0;
    let ed = edificio(2, m, 3.0, 2.0);
    let mut masas = ed.masas.clone();
    for (_, mm) in masas.nodales.iter_mut() {
        mm[1] = 0.0;
        mm[2] = 0.0;
    }
    // Ocho GDL con masa (ux de cada nudo): además de los dos modos del edificio
    // de cortante hay modos de torsión y modos que deforman las vigas, que no
    // participan en X.
    let modal = analizar_modal_3d(&ed.modelo, &masas, 10, MetodoModal::Denso).unwrap();
    assert_eq!(modal.omegas.len(), 8);
    let x: Vec<usize> = (0..8)
        .filter(|&k| modal.masas_efectivas[k][0] > 1e-6 * m)
        .collect();
    assert_eq!(x.len(), 2);
    let dos: f64 = x.iter().map(|&k| modal.masas_efectivas[k][0]).sum();
    cerca(dos, 2.0 * m, 1e-9, "masa efectiva de los dos modos en X");
    let k = ed.kx;
    let w = [
        ((3.0 - 5f64.sqrt()) / 2.0 * k / m).sqrt(),
        ((3.0 + 5f64.sqrt()) / 2.0 * k / m).sqrt(),
    ];
    let oro = (1.0 + 5f64.sqrt()) / 2.0;
    let formas = [(1.0, oro), (1.0, 1.0 - oro)];
    let sa = 3.5;
    let esp = Espectro::new(vec![0.0, 10.0], vec![sa, sa]).unwrap();
    // Respuesta de cada modo: u = Γ φ Sa/ω², V = Γ² Sa (el signo de φ se
    // cancela en Γ φ y en Γ²).
    let mut u2 = [0.0; 2];
    let mut v = [0.0; 2];
    for n in 0..2 {
        let (r1, r2) = formas[n];
        let norma = (m * (r1 * r1 + r2 * r2)).sqrt();
        let (p1, p2) = (r1 / norma, r2 / norma);
        let gamma = m * (p1 + p2);
        u2[n] = gamma * p2 * sa / (w[n] * w[n]);
        v[n] = gamma * gamma * sa;
    }
    let srss = analizar_espectro_3d(
        &ed.modelo,
        &modal,
        &esp,
        [1.0, 0.0, 0.0],
        0.05,
        CombinacionModal::Srss,
    )
    .unwrap();
    cerca(
        srss.desplazamientos[8][0],
        u2[0].hypot(u2[1]),
        1e-5,
        "u techo SRSS",
    );
    cerca(
        srss.cortante_basal[0],
        v[0].hypot(v[1]),
        1e-5,
        "V basal SRSS",
    );
    for n in 0..2 {
        cerca(
            srss.cortante_basal_modal[x[n]][0].abs(),
            v[n],
            1e-5,
            "V basal modal",
        );
    }

    let zeta = 0.05;
    let cqc = analizar_espectro_3d(
        &ed.modelo,
        &modal,
        &esp,
        [1.0, 0.0, 0.0],
        zeta,
        CombinacionModal::Cqc,
    )
    .unwrap();
    let rho = coeficiente_cqc(w[0], w[1], zeta);
    let u_cqc = (u2[0] * u2[0] + u2[1] * u2[1] + 2.0 * rho * u2[0] * u2[1]).sqrt();
    let v_cqc = (v[0] * v[0] + v[1] * v[1] + 2.0 * rho * v[0] * v[1]).sqrt();
    cerca(cqc.desplazamientos[8][0], u_cqc, 1e-5, "u techo CQC");
    cerca(cqc.cortante_basal[0], v_cqc, 1e-5, "V basal CQC");
}

#[test]
fn coeficiente_cqc_de_der_kiureghian() {
    // Calculado a mano para β = 0.5 y ζ = 5 %:
    // 8·0.0025·1.5·0.5^1.5 / ((1 - 0.25)² + 4·0.0025·0.5·1.5²)
    //   = 0.0106066017 / 0.57375 = 0.0184864517…
    cerca(
        coeficiente_cqc(1.0, 2.0, 0.05),
        0.010_606_601_7 / 0.573_75,
        1e-8,
        "ρ",
    );
    assert_eq!(coeficiente_cqc(3.0, 3.0, 0.05), 1.0);
    cerca(
        coeficiente_cqc(2.0, 1.0, 0.05),
        coeficiente_cqc(1.0, 2.0, 0.05),
        1e-12,
        "simetría",
    );
    // Sin amortiguamiento, modos distintos no se correlacionan (SRSS).
    assert_eq!(coeficiente_cqc(1.0, 2.0, 0.0), 0.0);
    // Modos muy cercanos: ρ → 1.
    assert!(coeficiente_cqc(1.0, 1.001, 0.05) > 0.99);
}

#[test]
fn masa_desde_las_cargas_de_un_caso() {
    // Viga de 4 m sobre X: carga uniforme global, puntual global y trapezoidal
    // local (en una viga horizontal el eje y local es +Z).
    let l = 4.0;
    let mut md = viga(l, 1, [2.0e8, 8.0e7, 0.01, 1e-4, 1e-4, 1e-4]);
    let mut d = CasoCarga3d::new("D");
    d.nodales.push((0, [0.0, 0.0, -9.0, 0.0, 0.0, 0.0]));
    let carga = |tipo, ejes| CargaBarra3d {
        barra: 0,
        ejes,
        tipo,
    };
    d.en_barras.push(carga(
        TipoCargaBarra3d::Uniforme {
            q: [0.0, 0.0, -5.0],
        },
        Ejes::Global,
    ));
    d.en_barras.push(carga(
        TipoCargaBarra3d::Puntual {
            a: 1.0,
            p: [0.0, 0.0, -8.0],
        },
        Ejes::Global,
    ));
    d.en_barras.push(carga(
        TipoCargaBarra3d::Trapezoidal {
            a: 1.0,
            b: 3.0,
            q1: [0.0, -2.0, 0.0],
            q2: [0.0, -4.0, 0.0],
        },
        Ejes::Local,
    ));
    md.agregar_caso(d);
    let mut masas = Masas3d::new();
    masas.desde_casos.push((0, 0.5));
    masas.gravedad = 10.0;
    let mm = ensamblar_masa(&md, &masas).unwrap();
    // Reacciones de viga simple: uniforme 10 + 10; puntual 6 + 2; trapezoidal
    // W = 6 con su centroide en 1 + 2·(2 + 2·4)/(3·6) = 2.111… m.
    let x_trap = 1.0 + 2.0 * (2.0 + 2.0 * 4.0) / (3.0 * 6.0);
    let w_j = 10.0 + 2.0 + 6.0 * x_trap / l;
    let w_i = 9.0 + 10.0 + 6.0 + 6.0 * (1.0 - x_trap / l);
    for d in 0..3 {
        cerca(mm[&(d, d)], w_i * 0.5 / 10.0, 1e-12, "masa nudo i");
        cerca(mm[&(6 + d, 6 + d)], w_j * 0.5 / 10.0, 1e-12, "masa nudo j");
    }
    assert!(!mm.contains_key(&(3, 3)));
    // Cargas hacia arriba: masa negativa, error.
    let mut arriba = CasoCarga3d::new("viento");
    arriba.nodales.push((1, [0.0, 0.0, 50.0, 0.0, 0.0, 0.0]));
    md.agregar_caso(arriba);
    masas.desde_casos = vec![(1, 1.0)];
    assert!(matches!(
        ensamblar_masa(&md, &masas),
        Err(ErrorNervi::ModeloInvalido(_))
    ));
}

#[test]
fn masa_consistente_suma_la_masa_de_la_barra() {
    // Una barra oblicua libre: la masa rígida en cada dirección global es m L.
    let mut md = Modelo3d::new();
    md.agregar_nudo(0.0, 0.0, 0.0);
    md.agregar_nudo(2.0, -1.0, 3.0);
    md.agregar_barra(
        Barra3d::new(0, 1, 2e8, 8e7, 0.02, 3e-4, 1e-4, 2e-5).con_referencia([1.0, 1.0, 0.0]),
    );
    let mut masas = Masas3d::new();
    masas.tipo = TipoMasa::Consistente;
    masas.lineales.push((0, 0.7));
    let mm = ensamblar_masa(&md, &masas).unwrap();
    let l = 14f64.sqrt();
    for d in 0..3 {
        let rigida: f64 = mm
            .iter()
            .filter(|((p, q), _)| p % 6 == d && q % 6 == d)
            .map(|(_, v)| v)
            .sum();
        cerca(rigida, 0.7 * l, 1e-12, "masa rígida");
    }
    // Simetría.
    for (&(p, q), v) in &mm {
        cerca(mm[&(q, p)], *v, 1e-12, "simetría");
    }
}

#[test]
fn errores_de_datos_y_de_estabilidad() {
    let mut md = viga(3.0, 2, [2e8, 8e7, 0.01, 1e-4, 1e-4, 1e-4]);
    md.empotrar(0);
    // Sin masa.
    assert!(matches!(
        analizar_modal_3d(&md, &Masas3d::new(), 3, MetodoModal::Automatico),
        Err(ErrorNervi::ModeloInvalido(_))
    ));
    // Masa negativa o en un nudo inexistente.
    let mut masas = Masas3d::new();
    masas.nodales.push((2, [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0]));
    assert!(analizar_modal_3d(&md, &masas, 3, MetodoModal::Automatico).is_err());
    masas.nodales = vec![(7, [1.0; 6])];
    assert!(analizar_modal_3d(&md, &masas, 3, MetodoModal::Automatico).is_err());
    // Mecanismo: la viga sin apoyos.
    let suelta = viga(3.0, 2, [2e8, 8e7, 0.01, 1e-4, 1e-4, 1e-4]);
    masas.nodales = vec![(2, [1.0, 1.0, 1.0, 0.0, 0.0, 0.0])];
    assert!(matches!(
        analizar_modal_3d(&suelta, &masas, 3, MetodoModal::Denso),
        Err(ErrorNervi::Mecanismo(_))
    ));
    assert!(matches!(
        analizar_modal_3d(&suelta, &masas, 3, MetodoModal::Lanczos),
        Err(ErrorNervi::Mecanismo(_))
    ));
    // Espectro mal definido.
    assert!(Espectro::new(vec![0.0, 0.0], vec![1.0, 1.0]).is_err());
    assert!(Espectro::new(vec![0.0, 1.0], vec![1.0, -1.0]).is_err());
}

#[test]
fn lanczos_encuentra_frecuencias_repetidas() {
    // Columna de sección cuadrada con masas en sus nudos: los modos en X y en Y
    // tienen las mismas frecuencias (autovalores dobles). El Lanczos de un solo
    // vector encontraría una sola copia; con el bloqueo de modos aparecen las dos.
    let (h, n, e, i) = (6.0, 6, 2.5e7, 2.0e-3);
    let mut md = Modelo3d::new();
    for k in 0..=n {
        md.agregar_nudo(0.0, 0.0, h * k as f64 / n as f64);
    }
    for k in 0..n {
        md.agregar_barra(Barra3d::new(k, k + 1, e, 1.0e7, 0.16, i, i, 3.0e-3));
    }
    md.empotrar(0);
    let mut masas = Masas3d::new();
    masas.nodales = (1..=n)
        .map(|k| (k, [1.5, 1.5, 0.0, 0.0, 0.0, 0.0]))
        .collect();
    let denso = analizar_modal_3d(&md, &masas, 6, MetodoModal::Denso).unwrap();
    let lanczos = analizar_modal_3d(&md, &masas, 6, MetodoModal::Lanczos).unwrap();
    assert_eq!(lanczos.omegas.len(), 6);
    for k in 0..6 {
        cerca(
            lanczos.omegas[k],
            denso.omegas[k],
            1e-8,
            &format!("ω{}", k + 1),
        );
    }
    for k in (0..6).step_by(2) {
        cerca(
            denso.omegas[k + 1],
            denso.omegas[k],
            1e-9,
            "autovalor doble",
        );
    }
    let suma =
        |r: &ResultadosModal3d, d: usize| r.masas_efectivas.iter().map(|x| x[d]).sum::<f64>();
    for d in 0..2 {
        cerca(
            suma(&lanczos, d),
            suma(&denso, d),
            1e-8,
            "masa efectiva acumulada",
        );
    }
}
