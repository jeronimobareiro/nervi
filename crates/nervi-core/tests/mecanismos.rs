// SPDX-License-Identifier: GPL-3.0-or-later
//! Diagnóstico de mecanismos (issue #9): casos con mecanismo conocido que deben
//! informar el nudo y el GDL correctos.
//!
//! Los modos esperados salen de la cinemática de cuerpos rígidos: en un
//! mecanismo de un grado de libertad, los nudos de cada parte rígida se mueven
//! según una rotación (o traslación) rígida de esa parte.

use nervi_core::{analizar, Barra, CasoCarga, DiagnosticoMecanismo, ErrorNervi, Gdl, Modelo};

const E: f64 = 2.0e8;
const A: f64 = 0.01;
const I: f64 = 1.0e-4;

fn diagnostico(m: &Modelo) -> DiagnosticoMecanismo {
    match analizar(m) {
        Err(ErrorNervi::Mecanismo(d)) => d,
        otro => panic!("se esperaba un mecanismo, se obtuvo {otro:?}"),
    }
}

/// Componente del primer modo para (nudo, gdl); 0 si no figura.
fn componente(d: &DiagnosticoMecanismo, nudo: usize, gdl: Gdl) -> f64 {
    d.modos[0]
        .iter()
        .find(|c| c.nudo == nudo && c.gdl == gdl)
        .map_or(0.0, |c| c.valor)
}

fn caso(nudo: usize, f: [f64; 3]) -> CasoCarga {
    let mut c = CasoCarga::new("P");
    c.nodales.push((nudo, f));
    c
}

#[test]
fn viga_sobre_dos_carritos_se_desplaza_en_x() {
    // Sin ninguna restricción horizontal: traslación rígida en X.
    let mut m = Modelo::new();
    let a = m.agregar_nudo(0.0, 0.0);
    let b = m.agregar_nudo(4.0, 0.0);
    m.agregar_barra(Barra::new(a, b, E, A, I));
    m.apoyar(a, false, true, false);
    m.apoyar(b, false, true, false);
    m.agregar_caso(caso(b, [1.0, 0.0, 0.0]));

    let d = diagnostico(&m);
    assert_eq!(d.modos.len(), 1, "{d:?}");
    assert_eq!(d.ubicacion.map(|u| u.1), Some(Gdl::Ux));
    for n in [a, b] {
        assert!((componente(&d, n, Gdl::Ux) - 1.0).abs() < 1e-6, "{d:?}");
        assert!(componente(&d, n, Gdl::Uy).abs() < 1e-6);
        assert!(componente(&d, n, Gdl::Rz).abs() < 1e-6);
    }
    let texto = ErrorNervi::Mecanismo(d).to_string();
    assert!(
        texto.contains("mecanismo") && texto.contains("en ux"),
        "{texto}"
    );
}

#[test]
fn viga_con_articulacion_de_mas() {
    // Viga simplemente apoyada de 2 tramos de 3 m con una rótula en el centro:
    // A(articulado) ─ C(rótula) ─ B(carrito). El centro baja libremente; los
    // tramos giran como cuerpos rígidos: θ_A = -1/3 y θ_B = +1/3 por unidad de
    // descenso... con uy_C = 1 (sube), θ_A = +1/3 y θ_B = -1/3.
    let mut m = Modelo::new();
    let a = m.agregar_nudo(0.0, 0.0);
    let c = m.agregar_nudo(3.0, 0.0);
    let b = m.agregar_nudo(6.0, 0.0);
    let mut b1 = Barra::new(a, c, E, A, I);
    b1.liberaciones[5] = true;
    let mut b2 = Barra::new(c, b, E, A, I);
    b2.liberaciones[2] = true;
    m.agregar_barra(b1);
    m.agregar_barra(b2);
    m.apoyar(a, true, true, false);
    m.apoyar(b, false, true, false);
    m.agregar_caso(caso(c, [0.0, -10.0, 0.0]));

    let d = diagnostico(&m);
    assert_eq!(d.ubicacion, Some((c, Gdl::Uy)), "{d:?}");
    assert_eq!(d.modos.len(), 1);
    assert!((componente(&d, c, Gdl::Uy) - 1.0).abs() < 1e-9);
    assert!(
        (componente(&d, a, Gdl::Rz) - 1.0 / 3.0).abs() < 1e-9,
        "{d:?}"
    );
    assert!(
        (componente(&d, b, Gdl::Rz) + 1.0 / 3.0).abs() < 1e-9,
        "{d:?}"
    );
    assert!(componente(&d, b, Gdl::Ux).abs() < 1e-9);
    let texto = ErrorNervi::Mecanismo(d).to_string();
    assert!(
        texto.contains(&format!("el nudo {c} se puede mover en uy")),
        "{texto}"
    );
}

#[test]
fn portico_sin_arriostrar() {
    // Pórtico de 6 m × 4 m con columnas articuladas en la base y viga articulada
    // en los dos extremos: las columnas giran alrededor de la base y la viga se
    // traslada (mecanismo de desplazamiento lateral). Con ux = 1 arriba,
    // θ_base = θ_cabeza = -1/4 (giro horario de cada columna).
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(0.0, 4.0);
    let n2 = m.agregar_nudo(6.0, 4.0);
    let n3 = m.agregar_nudo(6.0, 0.0);
    m.agregar_barra(Barra::new(n0, n1, E, A, I));
    let mut viga = Barra::new(n1, n2, E, A, I);
    viga.liberaciones[2] = true;
    viga.liberaciones[5] = true;
    m.agregar_barra(viga);
    m.agregar_barra(Barra::new(n3, n2, E, A, I));
    m.apoyar(n0, true, true, false);
    m.apoyar(n3, true, true, false);
    m.agregar_caso(caso(n1, [5.0, 0.0, 0.0]));

    let d = diagnostico(&m);
    let (nudo, gdl) = d.ubicacion.unwrap();
    assert_eq!(gdl, Gdl::Ux, "{d:?}");
    assert!(nudo == n1 || nudo == n2);
    for n in [n1, n2] {
        assert!((componente(&d, n, Gdl::Ux) - 1.0).abs() < 1e-9, "{d:?}");
        assert!(componente(&d, n, Gdl::Uy).abs() < 1e-9);
    }
    for n in [n0, n1, n2, n3] {
        assert!((componente(&d, n, Gdl::Rz) + 0.25).abs() < 1e-9, "{d:?}");
    }
    assert_eq!(d.nudos(), vec![n0, n1, n2, n3]);
}

#[test]
fn cercha_sin_diagonal() {
    // Cuadro de cercha de 4 m × 3 m sin diagonal, articulado en los dos nudos de
    // abajo: el cordón superior se traslada en X (mecanismo de un grado).
    let mut m = Modelo::new();
    let n0 = m.agregar_nudo(0.0, 0.0);
    let n1 = m.agregar_nudo(4.0, 0.0);
    let n2 = m.agregar_nudo(4.0, 3.0);
    let n3 = m.agregar_nudo(0.0, 3.0);
    for (i, j) in [(n0, n3), (n1, n2), (n2, n3)] {
        m.agregar_barra(Barra::biarticulada(i, j, E, A, I));
    }
    m.apoyar(n0, true, true, false);
    m.apoyar(n1, true, true, false);
    m.agregar_caso(caso(n3, [10.0, 0.0, 0.0]));

    let d = diagnostico(&m);
    let (nudo, gdl) = d.ubicacion.unwrap();
    assert_eq!(gdl, Gdl::Ux, "{d:?}");
    assert!(nudo == n2 || nudo == n3);
    assert_eq!(d.modos.len(), 1);
    assert!((componente(&d, n2, Gdl::Ux) - 1.0).abs() < 1e-9);
    assert!((componente(&d, n3, Gdl::Ux) - 1.0).abs() < 1e-9);
    assert_eq!(d.nudos(), vec![n2, n3]);
}

#[test]
fn dos_mecanismos_independientes() {
    // Dos vigas sueltas sobre carritos: dos traslaciones en X independientes.
    let mut m = Modelo::new();
    for k in 0..2 {
        let y = 5.0 * k as f64;
        let a = m.agregar_nudo(0.0, y);
        let b = m.agregar_nudo(4.0, y);
        m.agregar_barra(Barra::new(a, b, E, A, I));
        m.apoyar(a, false, true, false);
        m.apoyar(b, false, true, false);
    }
    m.agregar_caso(caso(1, [1.0, 0.0, 0.0]));
    let d = diagnostico(&m);
    assert_eq!(d.modos.len(), 2, "{d:?}");
    assert_eq!(d.nudos(), vec![0, 1, 2, 3]);
    assert!(ErrorNervi::Mecanismo(d).to_string().contains("2 modos"));
}

#[test]
fn pendulo_suelto_en_un_portico_grande() {
    // Pórtico rígido de 10 vanos × 10 pisos (estable) con una barra suelta en la
    // cubierta, articulada abajo y libre arriba: solo ese extremo es un mecanismo.
    let (vanos, pisos) = (10, 10);
    let mut m = Modelo::new();
    let id = |i: usize, j: usize| j * (vanos + 1) + i;
    for j in 0..=pisos {
        for i in 0..=vanos {
            m.agregar_nudo(6.0 * i as f64, 3.0 * j as f64);
        }
    }
    for i in 0..=vanos {
        m.apoyar(id(i, 0), true, true, true);
    }
    for j in 1..=pisos {
        for i in 0..=vanos {
            m.agregar_barra(Barra::new(id(i, j - 1), id(i, j), E, A, I));
        }
        for i in 0..vanos {
            m.agregar_barra(Barra::new(id(i, j), id(i + 1, j), E, A, I));
        }
    }
    let cubierta = id(4, pisos);
    let punta = m.agregar_nudo(24.0, 3.0 * pisos as f64 + 2.0);
    let mut pendulo = Barra::new(cubierta, punta, E, A, I);
    pendulo.liberaciones[2] = true;
    m.agregar_barra(pendulo);
    let mut c = CasoCarga::new("P");
    c.nodales.push((punta, [1.0, -1.0, 0.0]));
    c.nodales.push((id(1, pisos), [5.0, 0.0, 0.0]));
    m.agregar_caso(c);

    let d = diagnostico(&m);
    assert_eq!(d.ubicacion, Some((punta, Gdl::Ux)), "{d:?}");
    assert_eq!(d.modos.len(), 1);
    // La punta gira alrededor de la rótula: ux = 1 y su giro es -1/2 (L = 2 m).
    assert!((componente(&d, punta, Gdl::Rz) + 0.5).abs() < 1e-9, "{d:?}");
    assert_eq!(d.nudos(), vec![punta]);
}
