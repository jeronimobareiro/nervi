// SPDX-License-Identifier: GPL-3.0-or-later
//! Diagramas de combinaciones de casos (superposición) y estaciones comunes.
//!
//! Viga continua de dos tramos iguales con carga w1 en el tramo 1 y w2 en el 2
//! (método de las fuerzas, p. ej. Hibbeler, Structural Analysis, 10.ª ed., cap. 10):
//! M_B = -(w1 + w2)L²/16, R_A = w1·L/2 + M_B/L, M_máx del tramo 1 = R_A²/2w1 en x = R_A/w1.

use nervi_core::{analizar, Barra, CargaBarra, CasoCarga, Ejes, Modelo, TipoCargaBarra};

const E: f64 = 2.0e8;
const A: f64 = 0.01;
const I: f64 = 1.0e-4;

fn uniforme(barra: usize, qy: f64) -> CargaBarra {
    CargaBarra {
        barra,
        ejes: Ejes::Local,
        tipo: TipoCargaBarra::Uniforme { qx: 0.0, qy },
    }
}

#[test]
fn diagrama_combinado_encuentra_el_maximo_de_la_combinacion() {
    let (l, w1, w2) = (6.0, 25.0, 12.0);
    let mut m = Modelo::new();
    for k in 0..3 {
        m.agregar_nudo(k as f64 * l, 0.0);
    }
    m.agregar_barra(Barra::new(0, 1, E, A, I));
    m.agregar_barra(Barra::new(1, 2, E, A, I));
    m.apoyar(0, true, true, false);
    m.apoyar(1, false, true, false);
    m.apoyar(2, false, true, false);
    // Caso 0: carga unitaria en los dos tramos; caso 1: carga unitaria en el tramo 1.
    let mut c0 = CasoCarga::new("ambos");
    c0.en_barras.push(uniforme(0, -1.0));
    c0.en_barras.push(uniforme(1, -1.0));
    let mut c1 = CasoCarga::new("tramo1");
    c1.en_barras.push(uniforme(0, -1.0));
    m.agregar_caso(c0);
    m.agregar_caso(c1);
    let r = analizar(&m).unwrap();

    // w1 en el tramo 1 y w2 en el 2 = w2·(ambos) + (w1 - w2)·(tramo1).
    let f = [w2, w1 - w2];
    let mb = -(w1 + w2) * l * l / 16.0;
    let ra = w1 * l / 2.0 + mb / l;
    let d = r.diagrama_combinado(&f, 0, 5);
    let max = d
        .iter()
        .max_by(|a, b| a.m.total_cmp(&b.m))
        .expect("diagrama no vacío");
    assert!((max.m - ra * ra / (2.0 * w1)).abs() < 1e-9 * max.m.abs());
    assert!((max.x - ra / w1).abs() < 1e-9 * l);
    let apoyo = r.seccion_combinada(&f, 0, l, false);
    assert!((apoyo.m - mb).abs() < 1e-9 * mb.abs());

    // Las estaciones comunes incluyen el cortante nulo de cada combinación.
    let est = r.estaciones_comunes(&[vec![1.0, 0.0], f.to_vec()], 0, 5);
    for x in [3.0 * l / 8.0, ra / w1] {
        assert!(
            est.iter().any(|(xe, _)| (xe - x).abs() < 1e-9),
            "falta x = {x}"
        );
    }
}
