// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación de la generación del modelo de cálculo desde el modelo físico
//! (issue #74): partición de barras, brazos rígidos, apoyos, diafragmas y paso de
//! las cargas por estática exacta. El criterio de salida (mismo resultado que el
//! modelo armado a mano) está en `tests/test_idealizacion.py`.

use nervi_core::idealizacion::{
    idealizar, Cargado, ColumnaIdeal, Entrada, ModeloIdeal, MotivoIdeal, MuroIdeal, TipoBarra,
    TramoIdeal, VigaIdeal,
};

const TOL: f64 = 1e-6;

fn columna(x: f64, y: f64, z1: f64, z2: f64, b: f64, h: f64, angulo: f64) -> ColumnaIdeal {
    ColumnaIdeal {
        punto: [x, y],
        z1,
        z2,
        b,
        h,
        angulo,
        circular: false,
    }
}

fn viga(p1: [f64; 2], p2: [f64; 2], z: f64) -> VigaIdeal {
    VigaIdeal { p1, p2, z }
}

fn base() -> Entrada {
    Entrada {
        niveles: vec![0.0, 3.0, 6.0],
        base: 0.0,
        n_casos: 1,
        tol: TOL,
        ..Default::default()
    }
}

fn de(m: &ModeloIdeal, tipo: TipoBarra, origen: usize) -> Vec<usize> {
    (0..m.barras.len())
        .filter(|&k| m.barras[k].tipo == tipo && m.barras[k].origen == origen)
        .collect()
}

/// Fuerza vertical total y momentos alrededor del origen de todas las cargas del
/// modelo generado (las de barra, con su posición real sobre la barra).
fn resultantes(m: &ModeloIdeal) -> [f64; 3] {
    let mut r = [0.0; 3];
    for c in &m.cargas_nudo {
        let p = m.nudos[c.nudo];
        r[0] += c.fz;
        r[1] += c.mx + p[1] * c.fz;
        r[2] += c.my - p[0] * c.fz;
    }
    for c in &m.cargas_barra {
        let b = &m.barras[c.barra];
        let (pi, pj) = (m.nudos[b.i], m.nudos[b.j]);
        let l = ((pj[0] - pi[0]).powi(2) + (pj[1] - pi[1]).powi(2)).sqrt();
        let d = [(pj[0] - pi[0]) / l, (pj[1] - pi[1]) / l];
        let f = 0.5 * (c.q_a + c.q_b) * (c.b - c.a);
        let centro = if f != 0.0 {
            c.a + (c.b - c.a) * (c.q_a + 2.0 * c.q_b) / (3.0 * (c.q_a + c.q_b))
        } else {
            c.a
        };
        let s = b.brazo_i + centro;
        let (x, y) = (pi[0] + d[0] * s, pi[1] + d[1] * s);
        r[0] -= f;
        r[1] -= y * f;
        r[2] += x * f;
    }
    r
}

fn cerca(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-12 * a.abs().max(b.abs()).max(1.0)
}

#[test]
fn portico_de_un_vano_con_brazos() {
    let mut e = base();
    e.columnas = vec![
        columna(0.0, 0.0, 0.0, 3.0, 0.4, 0.4, 0.0),
        columna(6.0, 0.0, 0.0, 3.0, 0.4, 0.4, 0.0),
    ];
    e.vigas = vec![viga([0.0, 0.0], [6.0, 0.0], 3.0)];
    e.diafragmas = vec![1];
    let m = idealizar(&e).unwrap();
    assert_eq!(m.nudos.len(), 4);
    assert_eq!(m.barras.len(), 3);
    assert_eq!(m.apoyos.len(), 2);
    let v = m.barras[de(&m, TipoBarra::Viga, 0)[0]];
    assert!(cerca(v.brazo_i, 0.2) && cerca(v.brazo_j, 0.2));
    assert_eq!(m.diafragmas.len(), 1);
    assert_eq!(m.diafragmas[0].1.len(), 2);
}

#[test]
fn brazo_de_columna_girada_y_circular() {
    // Columna de 0.6 x 0.2 girada 30°: semiancho sobre X = 0.3·cos30 + 0.1·sin30.
    let mut e = base();
    let a = 30f64.to_radians();
    e.columnas = vec![columna(0.0, 0.0, 0.0, 3.0, 0.6, 0.2, a)];
    e.columnas.push(ColumnaIdeal {
        circular: true,
        ..columna(5.0, 0.0, 0.0, 3.0, 0.5, 0.5, 0.0)
    });
    e.vigas = vec![viga([0.0, 0.0], [5.0, 0.0], 3.0)];
    let m = idealizar(&e).unwrap();
    let v = m.barras[de(&m, TipoBarra::Viga, 0)[0]];
    assert!(cerca(v.brazo_i, 0.3 * a.cos() + 0.1 * a.sin()));
    assert!(cerca(v.brazo_j, 0.25));
}

#[test]
fn particion_en_cruces_apoyos_y_pisos() {
    let mut e = base();
    // Columna de dos pisos: se parte donde llega la viga en el nivel 3.
    e.columnas = vec![
        columna(0.0, 0.0, 0.0, 6.0, 0.3, 0.3, 0.0),
        columna(8.0, 0.0, 0.0, 3.0, 0.3, 0.3, 0.0),
        columna(0.0, 8.0, 0.0, 3.0, 0.3, 0.3, 0.0),
        columna(8.0, 8.0, 0.0, 3.0, 0.3, 0.3, 0.0),
    ];
    e.vigas = vec![
        viga([0.0, 0.0], [8.0, 0.0], 3.0),
        viga([0.0, 0.0], [8.0, 8.0], 3.0), // diagonal
        viga([0.0, 8.0], [8.0, 0.0], 3.0), // diagonal: se cruzan en (4, 4)
        viga([4.0, 0.0], [4.0, 4.0], 3.0), // apoya en el medio de la 0 y en el cruce
    ];
    let m = idealizar(&e).unwrap();
    assert_eq!(de(&m, TipoBarra::Columna, 0).len(), 2);
    assert_eq!(de(&m, TipoBarra::Viga, 0).len(), 2);
    assert_eq!(de(&m, TipoBarra::Viga, 1).len(), 2);
    assert_eq!(de(&m, TipoBarra::Viga, 2).len(), 2);
    assert_eq!(de(&m, TipoBarra::Viga, 3).len(), 1);
    // Solo las bases van empotradas.
    assert_eq!(m.apoyos.len(), 4);
    assert!(m.apoyos.iter().all(|&n| m.nudos[n][2] == 0.0));
    // Sin columnas en el cruce ni en el apoyo de la viga sobre viga: sin brazos ahí.
    for k in de(&m, TipoBarra::Viga, 3) {
        assert_eq!((m.barras[k].brazo_i, m.barras[k].brazo_j), (0.0, 0.0));
    }
}

#[test]
fn nudos_a_menos_de_la_tolerancia_se_unen() {
    let mut e = base();
    e.columnas = vec![columna(0.0, 0.0, 0.0, 3.0, 0.3, 0.3, 0.0)];
    e.vigas = vec![viga([0.3e-6, -0.2e-6], [4.0, 0.0], 3.0)];
    let m = idealizar(&e).unwrap();
    assert_eq!(m.nudos.len(), 3);
}

#[test]
fn cargas_por_estatica_exacta() {
    // Viga de 6 m entre columnas de 0.4 con un trapecio y un triángulo en dos casos:
    // la fuerza y los momentos totales no cambian al pasar a barras y nudos.
    let mut e = base();
    e.n_casos = 2;
    e.columnas = vec![
        columna(0.0, 0.0, 0.0, 3.0, 0.4, 0.4, 0.0),
        columna(6.0, 1.0, 0.0, 3.0, 0.4, 0.4, 0.0),
        columna(3.0, 0.5, 0.0, 3.0, 0.3, 0.3, 0.0),
    ];
    e.vigas = vec![viga([0.0, 0.0], [6.0, 1.0], 3.0)];
    let l = 37f64.sqrt();
    e.tramos = vec![
        TramoIdeal {
            elemento: Cargado::Viga(0),
            a: 0.0,
            b: 2.5,
            q: vec![[0.0, 10.0], [0.0, 4.0]],
        },
        TramoIdeal {
            elemento: Cargado::Viga(0),
            a: 2.5,
            b: l,
            q: vec![[10.0, 1.0], [4.0, 0.0]],
        },
    ];
    let m = idealizar(&e).unwrap();
    assert_eq!(de(&m, TipoBarra::Viga, 0).len(), 2);
    // Resultantes esperadas, integradas a mano sobre el eje de la viga.
    let d = [6.0 / l, 1.0 / l];
    let mut esperado = [0.0; 3];
    for t in &e.tramos {
        for q in &t.q {
            let f = 0.5 * (q[0] + q[1]) * (t.b - t.a);
            let s = t.a + (t.b - t.a) * (q[0] + 2.0 * q[1]) / (3.0 * (q[0] + q[1]));
            esperado[0] -= f;
            esperado[1] -= d[1] * s * f;
            esperado[2] += d[0] * s * f;
        }
    }
    let r = resultantes(&m);
    for k in 0..3 {
        assert!(cerca(r[k], esperado[k]), "{k}: {} != {}", r[k], esperado[k]);
    }
    assert!(
        !m.cargas_nudo.is_empty(),
        "lo de los brazos pasa a los nudos"
    );
}

#[test]
fn viga_sobre_muro_y_carga_del_muro() {
    let mut e = base();
    e.muros = vec![MuroIdeal {
        p1: [0.0, 0.0],
        p2: [0.0, 5.0],
        z1: 0.0,
        z2: 6.0,
        espesor: 0.2,
    }];
    e.columnas = vec![columna(6.0, 2.5, 0.0, 3.0, 0.4, 0.4, 0.0)];
    e.vigas = vec![
        viga([0.0, 0.0], [0.0, 5.0], 3.0), // sobre el muro
        viga([0.0, 2.5], [6.0, 2.5], 3.0), // llega al centro del muro
    ];
    e.diafragmas = vec![1, 2];
    e.tramos = vec![
        TramoIdeal {
            elemento: Cargado::Viga(0),
            a: 0.0,
            b: 5.0,
            q: vec![[2.0, 8.0]],
        },
        TramoIdeal {
            elemento: Cargado::Muro(0, 2),
            a: 1.0,
            b: 4.0,
            q: vec![[3.0, 3.0]],
        },
    ];
    let m = idealizar(&e).unwrap();
    assert!(m
        .avisos
        .iter()
        .any(|a| a.viga == 0 && a.otro == Some(0) && a.motivo == MotivoIdeal::VigaSobreMuro));
    assert!(de(&m, TipoBarra::Viga, 0).is_empty());
    // El muro: una barra por piso en su centro.
    assert_eq!(de(&m, TipoBarra::Muro, 0).len(), 2);
    // La viga que llega al muro tiene el brazo del semiespesor (0.1) en ese extremo.
    let v = m.barras[de(&m, TipoBarra::Viga, 1)[0]];
    assert!(cerca(v.brazo_i, 0.1) && cerca(v.brazo_j, 0.2));
    // La carga de la viga sobre el muro: 25 kN con el centroide en y = 3 m, al
    // nudo del centro (y = 2.5) con el momento de su excentricidad.
    let r = resultantes(&m);
    let esperado_f = -(25.0 + 9.0);
    let esperado_mx = -(25.0 * 3.0 + 9.0 * 2.5);
    assert!(cerca(r[0], esperado_f) && cerca(r[1], esperado_mx) && cerca(r[2], 0.0));
    // Muro y columna arrancan en la base: dos apoyos.
    assert_eq!(m.apoyos.len(), 2);
}

#[test]
fn brazos_que_ocupan_toda_la_luz() {
    let mut e = base();
    e.columnas = vec![
        columna(0.0, 0.0, 0.0, 3.0, 0.6, 0.6, 0.0),
        columna(0.5, 0.0, 0.0, 3.0, 0.6, 0.6, 0.0),
    ];
    e.vigas = vec![viga([0.0, 0.0], [0.5, 0.0], 3.0)];
    let m = idealizar(&e).unwrap();
    let v = m.barras[de(&m, TipoBarra::Viga, 0)[0]];
    assert_eq!((v.brazo_i, v.brazo_j), (0.0, 0.0));
    assert_eq!(m.avisos[0].motivo, MotivoIdeal::BrazosSinLuz);
}

#[test]
fn datos_invalidos() {
    let mut e = base();
    e.vigas = vec![viga([1.0, 1.0], [1.0, 1.0], 3.0)];
    assert!(idealizar(&e).is_err());
    let mut e = base();
    e.tol = 0.0;
    assert!(idealizar(&e).is_err());
}
