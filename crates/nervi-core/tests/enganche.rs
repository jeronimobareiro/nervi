// SPDX-License-Identifier: GPL-3.0-or-later
//! Pruebas del enganche de puntos en planta (`nervi_core::enganche`).

use nervi_core::enganche::{Enganche, IndiceEnganche, Opciones, Tipo};

fn cerca(a: [f64; 2], b: [f64; 2]) -> bool {
    (a[0] - b[0]).abs() < 1e-12 && (a[1] - b[1]).abs() < 1e-12
}

/// Planta del ejemplo: ejes A, B, C (x = 0, 6, 12) y 1, 2 (y = 0, 5), vigas en los
/// ejes y columnas en los cruces.
fn planta() -> IndiceEnganche {
    let mut segs = Vec::new();
    for y in [0.0, 5.0] {
        segs.push([[0.0, y], [6.0, y]]);
        segs.push([[6.0, y], [12.0, y]]);
    }
    for x in [0.0, 6.0, 12.0] {
        segs.push([[x, 0.0], [x, 5.0]]);
    }
    let mut pts = Vec::new();
    for x in [0.0, 6.0, 12.0] {
        for y in [0.0, 5.0] {
            pts.push([x, y]);
        }
    }
    IndiceEnganche::nuevo(pts, segs)
}

fn op(radio: f64) -> Opciones {
    Opciones {
        radio,
        ..Opciones::default()
    }
}

#[test]
fn punto_y_extremo_ganan_al_mas_cercano() {
    let idx = planta();
    let e = idx.enganchar([6.1, 0.05], &op(0.3));
    assert_eq!(e.tipo, Tipo::Punto);
    assert!(cerca(e.punto, [6.0, 0.0]));
    // Sin puntos sueltos, el extremo de la viga.
    let sin_puntos = Opciones {
        puntos: false,
        ..op(0.3)
    };
    let e = idx.enganchar([6.1, 0.05], &sin_puntos);
    assert_eq!(e.tipo, Tipo::Extremo);
    assert!(cerca(e.punto, [6.0, 0.0]));
}

#[test]
fn medio_y_cerca() {
    let idx = planta();
    let e = idx.enganchar([3.1, 0.1], &op(0.3));
    assert_eq!(e.tipo, Tipo::Medio);
    assert!(cerca(e.punto, [3.0, 0.0]));
    let e = idx.enganchar([4.2, 0.1], &op(0.3));
    assert_eq!(e.tipo, Tipo::Cerca);
    assert!(cerca(e.punto, [4.2, 0.0]));
    // Fuera del radio no hay enganche.
    let e = idx.enganchar([4.2, 1.0], &op(0.3));
    assert_eq!(e.tipo, Tipo::Libre);
    assert!(cerca(e.punto, [4.2, 1.0]));
}

#[test]
fn cruce_de_dos_segmentos() {
    let idx = IndiceEnganche::nuevo(
        vec![],
        vec![[[0.0, 0.0], [4.0, 4.0]], [[0.0, 4.0], [4.0, 0.0]]],
    );
    let e = idx.enganchar([2.05, 1.9], &op(0.3));
    assert_eq!(e.tipo, Tipo::Cruce);
    assert!(cerca(e.punto, [2.0, 2.0]));
    assert_eq!((e.elemento, e.otro), (Some(0), Some(1)));
}

#[test]
fn perpendicular_desde_el_punto_anterior() {
    let idx = IndiceEnganche::nuevo(vec![], vec![[[0.0, 0.0], [10.0, 0.0]]]);
    let o = Opciones {
        anterior: Some([3.7, 4.0]),
        paso_polar: 0.0,
        ..op(0.3)
    };
    let e = idx.enganchar([3.8, 0.1], &o);
    assert_eq!(e.tipo, Tipo::Perpendicular);
    assert!(cerca(e.punto, [3.7, 0.0]));
    assert_eq!(e.guia, Some([[3.7, 4.0], [3.7, 0.0]]));
}

#[test]
fn polar_cruza_un_segmento() {
    // Desde (12, 2.5) hacia la izquierda, la horizontal corta la viga del eje B.
    let idx = planta();
    let o = Opciones {
        anterior: Some([12.0, 2.5]),
        puntos: false,
        ..op(0.3)
    };
    let e = idx.enganchar([6.1, 2.4], &o);
    assert_eq!(e.tipo, Tipo::Cruce);
    assert!(cerca(e.punto, [6.0, 2.5]));
}

#[test]
fn polar_y_grilla_sobre_la_guia() {
    let idx = IndiceEnganche::nuevo(vec![], vec![]);
    let o = Opciones {
        anterior: Some([12.0, 0.0]),
        paso_grilla: 0.5,
        ..op(0.2)
    };
    // Cerca de la horizontal: queda sobre ella, a 2.5 m (redondeado al paso).
    let e = idx.enganchar([14.6, 0.1], &o);
    assert_eq!(e.tipo, Tipo::Polar);
    assert!(cerca(e.punto, [14.5, 0.0]));
    assert_eq!(e.guia, Some([[12.0, 0.0], [14.5, 0.0]]));
    // Lejos de las polares: la grilla.
    let e = idx.enganchar([13.3, 1.2], &o);
    assert_eq!(e.tipo, Tipo::Grilla);
    assert!(cerca(e.punto, [13.5, 1.0]));
}

#[test]
fn orto_obliga_la_direccion() {
    let idx = IndiceEnganche::nuevo(vec![], vec![]);
    let o = Opciones {
        anterior: Some([0.0, 0.0]),
        orto: true,
        paso_grilla: 0.25,
        ..op(0.1)
    };
    let e = idx.enganchar([3.07, 1.4], &o);
    assert_eq!(e.tipo, Tipo::Polar);
    assert!(cerca(e.punto, [3.0, 0.0]));
    let e = idx.enganchar([-0.4, -2.6], &o);
    assert!(cerca(e.punto, [0.0, -2.5]));
    // Un punto notable le gana a orto.
    let idx = IndiceEnganche::nuevo(vec![[3.05, 1.45]], vec![]);
    let e = idx.enganchar([3.07, 1.4], &o);
    assert_eq!(e.tipo, Tipo::Punto);
}

#[test]
fn prolongacion_y_cruce_de_guias() {
    let idx = IndiceEnganche::nuevo(vec![], vec![[[0.0, 0.0], [6.0, 0.0]]]);
    let o = Opciones {
        recientes: vec![0],
        ..op(0.2)
    };
    let e = idx.enganchar([8.0, 0.1], &o);
    assert_eq!(e.tipo, Tipo::Prolongacion);
    assert!(cerca(e.punto, [8.0, 0.0]));
    assert_eq!(e.guia, Some([[6.0, 0.0], [8.0, 0.0]]));
    // Dentro del segmento no es prolongación sino "cerca".
    let e = idx.enganchar(
        [3.0, 0.1],
        &Opciones {
            medios: false,
            ..o.clone()
        },
    );
    assert_eq!(e.tipo, Tipo::Cerca);
    // La vertical desde (9, 4) cruza la prolongación en (9, 0).
    let o2 = Opciones {
        anterior: Some([9.0, 4.0]),
        ..o
    };
    let e = idx.enganchar([9.1, 0.1], &o2);
    assert_eq!(e.tipo, Tipo::CruceGuias);
    assert!(cerca(e.punto, [9.0, 0.0]));
}

fn azar(semilla: &mut u64) -> f64 {
    // Generador lineal congruente (Knuth, MMIX): reproducible y sin dependencias.
    *semilla = semilla
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407);
    (*semilla >> 11) as f64 / (1u64 << 53) as f64
}

#[test]
fn el_indice_da_lo_mismo_que_recorrer_todo() {
    let mut s = 7u64;
    let mut segs = Vec::new();
    let mut pts = Vec::new();
    for _ in 0..600 {
        let a = [azar(&mut s) * 100.0, azar(&mut s) * 60.0];
        let ang = azar(&mut s) * std::f64::consts::TAU;
        let l = 0.5 + azar(&mut s) * 15.0;
        segs.push([a, [a[0] + l * ang.cos(), a[1] + l * ang.sin()]]);
    }
    // Algunos largos y uno degenerado.
    segs.push([[-5.0, 30.0], [105.0, 30.0]]);
    segs.push([[50.0, 50.0], [50.0, 50.0]]);
    for _ in 0..300 {
        pts.push([azar(&mut s) * 100.0, azar(&mut s) * 60.0]);
    }
    let idx = IndiceEnganche::nuevo(pts, segs);
    for k in 0..3000 {
        let c = [azar(&mut s) * 110.0 - 5.0, azar(&mut s) * 70.0 - 5.0];
        let o = Opciones {
            radio: 0.05 + azar(&mut s),
            anterior: (k % 2 == 0).then(|| [azar(&mut s) * 100.0, azar(&mut s) * 60.0]),
            orto: k % 5 == 0,
            paso_grilla: if k % 3 == 0 { 0.5 } else { 0.0 },
            paso_polar: if k % 7 == 0 { 15.0 } else { 90.0 },
            recientes: vec![k % 600, (k * 7) % 600],
            ..Opciones::default()
        };
        let a: Enganche = idx.enganchar(c, &o);
        let b = idx.enganchar_sin_indice(c, &o);
        assert_eq!(a, b, "consulta {k} en {c:?}");
    }
}
