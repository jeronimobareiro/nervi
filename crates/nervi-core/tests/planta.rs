// SPDX-License-Identifier: GPL-3.0-or-later
//! Pruebas de la geometría en planta de las herramientas de dibujo (`nervi_core::planta`).

use nervi_core::planta::{cruces, pano_en, partir};

const TOL: f64 = 1e-6;

/// Vigas del ejemplo: ejes A, B, C (x = 0, 6, 12) y 1, 2 (y = 0, 5).
fn vigas() -> Vec<[[f64; 2]; 2]> {
    let mut s = Vec::new();
    for y in [0.0, 5.0] {
        s.push([[0.0, y], [6.0, y]]);
        s.push([[6.0, y], [12.0, y]]);
    }
    for x in [0.0, 6.0, 12.0] {
        s.push([[x, 0.0], [x, 5.0]]);
    }
    s
}

fn area(p: &[[f64; 2]]) -> f64 {
    (0..p.len())
        .map(|k| {
            let (a, b) = (p[k], p[(k + 1) % p.len()]);
            a[0] * b[1] - a[1] * b[0]
        })
        .sum::<f64>()
        / 2.0
}

fn mismo_poligono(p: &[[f64; 2]], esperado: &[[f64; 2]]) {
    assert_eq!(p.len(), esperado.len(), "{p:?}");
    let k = p
        .iter()
        .position(|q| (q[0] - esperado[0][0]).abs() < 1e-9 && (q[1] - esperado[0][1]).abs() < 1e-9)
        .expect("falta el primer vértice");
    for (i, e) in esperado.iter().enumerate() {
        let q = p[(k + i) % p.len()];
        assert!(
            (q[0] - e[0]).abs() < 1e-9 && (q[1] - e[1]).abs() < 1e-9,
            "{p:?}"
        );
    }
}

#[test]
fn pano_rectangular() {
    let p = pano_en(&vigas(), [8.0, 2.0], TOL).unwrap();
    mismo_poligono(&p, &[[6.0, 0.0], [12.0, 0.0], [12.0, 5.0], [6.0, 5.0]]);
    assert!((area(&p) - 30.0).abs() < 1e-9);
    let p = pano_en(&vigas(), [1.0, 4.0], TOL).unwrap();
    mismo_poligono(&p, &[[0.0, 0.0], [6.0, 0.0], [6.0, 5.0], [0.0, 5.0]]);
    // Afuera no hay paño.
    assert!(pano_en(&vigas(), [13.0, 2.0], TOL).is_none());
    assert!(pano_en(&vigas(), [6.0, 7.0], TOL).is_none());
}

#[test]
fn vigas_de_punta_a_punta_y_voladizos() {
    // Las vigas largas se cruzan sin cortarse en el medio; un voladizo y una viga
    // suelta adentro no cambian el paño.
    let mut s = vec![
        [[0.0, 0.0], [12.0, 0.0]],
        [[0.0, 5.0], [12.0, 5.0]],
        [[0.0, 0.0], [0.0, 5.0]],
        [[6.0, -1.0], [6.0, 6.0]],
        [[12.0, 0.0], [12.0, 5.0]],
    ];
    s.push([[12.0, 0.0], [14.5, 0.0]]); // voladizo
    s.push([[8.0, 2.0], [9.0, 2.0]]); // isla suelta
    let p = pano_en(&s, [10.0, 1.0], TOL).unwrap();
    mismo_poligono(&p, &[[6.0, 0.0], [12.0, 0.0], [12.0, 5.0], [6.0, 5.0]]);
}

#[test]
fn pano_en_l_y_triangulo() {
    let s = vec![
        [[0.0, 0.0], [10.0, 0.0]],
        [[10.0, 0.0], [10.0, 4.0]],
        [[10.0, 4.0], [4.0, 4.0]],
        [[4.0, 4.0], [4.0, 8.0]],
        [[4.0, 8.0], [0.0, 8.0]],
        [[0.0, 8.0], [0.0, 0.0]],
        [[0.0, 0.0], [4.0, 4.0]], // diagonal: deja un triángulo abajo a la izquierda
    ];
    let p = pano_en(&s, [3.0, 1.0], TOL).unwrap();
    mismo_poligono(&p, &[[0.0, 0.0], [10.0, 0.0], [10.0, 4.0], [4.0, 4.0]]);
    let p = pano_en(&s, [1.0, 5.0], TOL).unwrap();
    mismo_poligono(&p, &[[0.0, 0.0], [4.0, 4.0], [4.0, 8.0], [0.0, 8.0]]);
}

#[test]
fn abierto_no_es_pano() {
    let s = vec![
        [[0.0, 0.0], [6.0, 0.0]],
        [[6.0, 0.0], [6.0, 5.0]],
        [[6.0, 5.0], [0.0, 5.0]],
    ];
    assert!(pano_en(&s, [3.0, 2.0], TOL).is_none());
    assert!(pano_en(&[], [0.0, 0.0], TOL).is_none());
}

#[test]
fn cruces_de_ejes() {
    let ejes = vec![
        [[0.0, -1.0], [0.0, 6.0]],
        [[6.0, -1.0], [6.0, 6.0]],
        [[-1.0, 0.0], [13.0, 0.0]],
        [[-1.0, 5.0], [13.0, 5.0]],
    ];
    let mut c = cruces(&ejes, TOL);
    c.sort_by(|a, b| a[0].total_cmp(&b[0]).then(a[1].total_cmp(&b[1])));
    assert_eq!(c, vec![[0.0, 0.0], [0.0, 5.0], [6.0, 0.0], [6.0, 5.0]]);
}

#[test]
fn partir_en_columnas() {
    let cols = [
        [0.0, 0.0],
        [6.0, 0.0],
        [12.0, 0.0],
        [6.0, 5.0],
        [9.0, 0.0000001],
    ];
    let t = partir([[0.0, 0.0], [12.0, 0.0]], &cols, 1e-6);
    assert_eq!(t.len(), 2);
    assert!((t[0] - 0.5).abs() < 1e-12 && (t[1] - 0.75).abs() < 1e-12);
    assert!(partir([[0.0, 0.0], [12.0, 0.0]], &cols, 1e-9).len() == 1);
}
