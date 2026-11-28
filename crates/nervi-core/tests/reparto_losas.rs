// SPDX-License-Identifier: GPL-3.0-or-later
//! Verificación del reparto de las losas a sus apoyos por áreas tributarias
//! (issue #78). Cada caso se compara con el cálculo a mano de las zonas a 45° y
//! con el equilibrio global: la suma de las áreas tributarias es el área de la losa.

use nervi_core::losas::{repartir, ApoyoReparto, LosaReparto, Motivo, Pieza, Reparto};

const TOL: f64 = 1e-9;

fn losa(contorno: &[[f64; 2]]) -> LosaReparto {
    LosaReparto {
        grupo: 0,
        contorno: contorno.to_vec(),
    }
}

fn apoyo(p1: [f64; 2], p2: [f64; 2]) -> ApoyoReparto {
    ApoyoReparto { grupo: 0, p1, p2 }
}

/// Vigas en los cuatro lados de un rectángulo `lx × ly` con esquina en el origen:
/// 0 abajo, 1 a la derecha, 2 arriba, 3 a la izquierda (p1 → p2 antihorario).
fn cuatro_vigas(lx: f64, ly: f64) -> Vec<ApoyoReparto> {
    vec![
        apoyo([0.0, 0.0], [lx, 0.0]),
        apoyo([lx, 0.0], [lx, ly]),
        apoyo([lx, ly], [0.0, ly]),
        apoyo([0.0, ly], [0.0, 0.0]),
    ]
}

fn rect(lx: f64, ly: f64) -> LosaReparto {
    losa(&[[0.0, 0.0], [lx, 0.0], [lx, ly], [0.0, ly]])
}

fn area_apoyo(r: &Reparto, k: usize) -> f64 {
    r.piezas
        .iter()
        .filter(|p| p.apoyo == k)
        .map(Pieza::area)
        .sum()
}

fn area_total(r: &Reparto) -> f64 {
    r.piezas.iter().map(Pieza::area).sum()
}

fn cerca(a: f64, b: f64) {
    assert!(
        (a - b).abs() <= 1e-12 * b.abs().max(1.0),
        "{a} no es {b} (diferencia {})",
        a - b
    );
}

/// Ancho tributario en la abscisa `x` del apoyo `k` (suma de los tramos que la cubren).
fn ancho(r: &Reparto, k: usize, x: f64) -> f64 {
    r.piezas
        .iter()
        .filter(|p| p.apoyo == k && p.a <= x && x <= p.b)
        .map(|p| p.ancho_a + (p.ancho_b - p.ancho_a) * (x - p.a) / (p.b - p.a))
        .fold(0.0, f64::max)
}

#[test]
fn losa_cuadrada_cuatro_triangulos() {
    // Cuadrado de 5 m apoyado en los cuatro lados: cada viga recibe un triángulo
    // de altura a/2 = 2,5 m y área a²/4 = 6,25 m².
    let r = repartir(&[rect(5.0, 5.0)], &cuatro_vigas(5.0, 5.0), TOL).unwrap();
    assert!(r.repartida[0] && r.avisos.is_empty());
    for k in 0..4 {
        cerca(area_apoyo(&r, k), 6.25);
        cerca(ancho(&r, k, 2.5), 2.5);
        cerca(ancho(&r, k, 0.0), 0.0);
        cerca(ancho(&r, k, 1.0), 1.0);
    }
    assert_eq!(r.regiones.len(), 4);
}

#[test]
fn losa_rectangular_trapecios_y_triangulos() {
    // 6 × 4 m en los cuatro lados: las vigas largas reciben un trapecio de altura
    // 2 m entre x = 2 y x = 4 (área (6 + 2)/2 · 2 = 8 m²); las cortas, un
    // triángulo de altura 2 m (área 4 m²). Total 2·8 + 2·4 = 24 m² = 6 · 4.
    let r = repartir(&[rect(6.0, 4.0)], &cuatro_vigas(6.0, 4.0), TOL).unwrap();
    cerca(area_apoyo(&r, 0), 8.0);
    cerca(area_apoyo(&r, 2), 8.0);
    cerca(area_apoyo(&r, 1), 4.0);
    cerca(area_apoyo(&r, 3), 4.0);
    cerca(area_total(&r), 24.0);
    // Viga inferior: 0 en los extremos, 1 m a 1 m, 2 m entre 2 y 4.
    for (x, w) in [
        (0.0, 0.0),
        (1.0, 1.0),
        (2.0, 2.0),
        (3.0, 2.0),
        (4.0, 2.0),
        (5.5, 0.5),
    ] {
        cerca(ancho(&r, 0, x), w);
    }
    // Viga superior, que va de (6, 4) a (0, 4): sus abscisas empiezan en x = 6.
    cerca(ancho(&r, 2, 0.5), 0.5);
    // Viga izquierda: triángulo con su pico de 2 m en el medio.
    cerca(ancho(&r, 3, 2.0), 2.0);
    // Las piezas tienen a < b y anchos no negativos.
    for p in &r.piezas {
        assert!(p.a < p.b && p.ancho_a >= 0.0 && p.ancho_b >= 0.0);
    }
}

#[test]
fn losa_en_una_direccion() {
    // Solo las vigas largas: cada una recibe ly/2 = 2 m constantes.
    let v = cuatro_vigas(6.0, 4.0);
    let r = repartir(&[rect(6.0, 4.0)], &[v[0].clone(), v[2].clone()], TOL).unwrap();
    assert!(r.repartida[0]);
    cerca(area_apoyo(&r, 0), 12.0);
    cerca(area_apoyo(&r, 1), 12.0);
    for x in [0.0, 1.7, 6.0] {
        cerca(ancho(&r, 0, x), 2.0);
    }
}

#[test]
fn losa_con_un_borde_libre() {
    // 6 × 4 m con el borde superior libre: bisectrices y = x, y = 6 − x y x = 3.
    // Abajo: triángulo de altura 3 (área 9). Izquierda y derecha: ancho min(y, 3)
    // entre y = 0 y y = 4 (área 3²/2 + 3·1 = 7,5). Total 24.
    let v = cuatro_vigas(6.0, 4.0);
    let r = repartir(
        &[rect(6.0, 4.0)],
        &[v[0].clone(), v[1].clone(), v[3].clone()],
        TOL,
    )
    .unwrap();
    cerca(area_apoyo(&r, 0), 9.0);
    cerca(area_apoyo(&r, 1), 7.5);
    cerca(area_apoyo(&r, 2), 7.5);
    cerca(ancho(&r, 0, 3.0), 3.0);
    // El apoyo 1 va de (6, 0) a (6, 4): en y = 3.5 el ancho es 3.
    cerca(ancho(&r, 1, 3.5), 3.0);
    cerca(ancho(&r, 1, 1.0), 1.0);
}

#[test]
fn borde_con_dos_vigas_y_losas_vecinas() {
    // Dos losas de 6 × 4 m una al lado de la otra comparten la viga x = 6; el
    // borde inferior de la primera tiene dos vigas (0–3 y 3–6).
    let losas = [
        rect(6.0, 4.0),
        losa(&[[6.0, 0.0], [12.0, 0.0], [12.0, 4.0], [6.0, 4.0]]),
    ];
    let apoyos = vec![
        apoyo([0.0, 0.0], [3.0, 0.0]),   // 0
        apoyo([3.0, 0.0], [6.0, 0.0]),   // 1
        apoyo([6.0, 0.0], [6.0, 4.0]),   // 2, compartida
        apoyo([0.0, 4.0], [12.0, 4.0]),  // 3, corrida arriba
        apoyo([0.0, 4.0], [0.0, 0.0]),   // 4
        apoyo([6.0, 0.0], [12.0, 0.0]),  // 5
        apoyo([12.0, 0.0], [12.0, 4.0]), // 6
    ];
    let r = repartir(&losas, &apoyos, TOL).unwrap();
    assert!(r.repartida.iter().all(|&x| x));
    cerca(area_apoyo(&r, 0), 4.0);
    cerca(area_apoyo(&r, 1), 4.0);
    cerca(area_apoyo(&r, 2), 8.0);
    cerca(area_apoyo(&r, 3), 16.0);
    cerca(area_total(&r), 48.0);
    // La viga corrida de arriba recibe los dos trapecios: en x = 9 (abscisa 9).
    cerca(ancho(&r, 3, 9.0), 2.0);
}

#[test]
fn triangulo_equilatero_y_contorno_horario() {
    let h = 3.0_f64.sqrt() / 2.0 * 4.0;
    let c = [[0.0, 0.0], [4.0, 0.0], [2.0, h]];
    let apoyos = vec![apoyo(c[0], c[1]), apoyo(c[1], c[2]), apoyo(c[2], c[0])];
    let area = 0.5 * 4.0 * h;
    let r = repartir(&[losa(&c)], &apoyos, TOL).unwrap();
    for k in 0..3 {
        cerca(area_apoyo(&r, k), area / 3.0);
    }
    // El mismo contorno en sentido horario da el mismo reparto.
    let horario = [c[0], c[2], c[1]];
    let r2 = repartir(&[losa(&horario)], &apoyos, TOL).unwrap();
    for k in 0..3 {
        cerca(area_apoyo(&r2, k), area / 3.0);
    }
}

#[test]
fn poligono_convexo_cualquiera_equilibrio_exacto() {
    // Hexágono irregular con un vértice alineado de más: la suma de las áreas
    // tributarias es el área del contorno.
    let c = [
        [0.0, 0.0],
        [2.5, -0.5],
        [5.0, -1.0],
        [7.0, 1.5],
        [6.0, 5.0],
        [2.0, 6.0],
        [-1.0, 3.0],
    ];
    let n = c.len();
    let apoyos: Vec<ApoyoReparto> = (0..n).map(|k| apoyo(c[k], c[(k + 1) % n])).collect();
    let r = repartir(&[losa(&c)], &apoyos, TOL).unwrap();
    assert!(r.repartida[0]);
    let area = 0.5
        * (0..n)
            .map(|k| c[k][0] * c[(k + 1) % n][1] - c[(k + 1) % n][0] * c[k][1])
            .sum::<f64>();
    cerca(area_total(&r), area);
    // Los dos tramos del lado con el vértice alineado reciben carga.
    assert!(area_apoyo(&r, 0) > 0.0 && area_apoyo(&r, 1) > 0.0);
}

#[test]
fn avisos_de_lo_que_no_se_reparte() {
    // Losa en L: no convexa.
    let l = losa(&[
        [0.0, 0.0],
        [4.0, 0.0],
        [4.0, 2.0],
        [2.0, 2.0],
        [2.0, 4.0],
        [0.0, 4.0],
    ]);
    let r = repartir(&[l], &cuatro_vigas(4.0, 4.0), TOL).unwrap();
    assert!(!r.repartida[0] && r.piezas.is_empty());
    assert_eq!(r.avisos[0].motivo, Motivo::NoConvexa);

    // Sin apoyos en su piso.
    let mut otra = rect(4.0, 4.0);
    otra.grupo = 7;
    let r = repartir(&[otra], &cuatro_vigas(4.0, 4.0), TOL).unwrap();
    assert_eq!(r.avisos[0].motivo, Motivo::SinApoyos);

    // Borde inferior apoyado solo en la mitad: se lo trata como libre.
    let mut v = cuatro_vigas(6.0, 4.0);
    v[0] = apoyo([0.0, 0.0], [3.0, 0.0]);
    let r = repartir(&[rect(6.0, 4.0)], &v, TOL).unwrap();
    assert!(r.repartida[0]);
    assert_eq!(r.avisos.len(), 1);
    assert_eq!(r.avisos[0].motivo, Motivo::BordeParcial);
    assert_eq!(r.avisos[0].lado, Some(0));
    cerca(area_apoyo(&r, 0), 0.0);
    cerca(area_total(&r), 24.0);

    // Trapecio apoyado solo en la base corta con el lado de arriba más largo: la
    // zona se sale del borde.
    let t = losa(&[[0.0, 0.0], [2.0, 0.0], [4.0, 2.0], [-2.0, 2.0]]);
    let r = repartir(&[t], &[apoyo([0.0, 0.0], [2.0, 0.0])], TOL).unwrap();
    assert!(!r.repartida[0]);
    assert_eq!(r.avisos[0].motivo, Motivo::FueraDelBorde);
}

#[test]
fn datos_invalidos() {
    assert!(repartir(&[rect(1.0, 1.0)], &[], 0.0).is_err());
    assert!(repartir(&[losa(&[[0.0, 0.0], [1.0, 0.0]])], &[], TOL).is_err());
    assert!(repartir(&[], &[apoyo([0.0, 0.0], [0.0, 0.0])], TOL).is_err());
}
