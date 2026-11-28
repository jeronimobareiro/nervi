// SPDX-License-Identifier: GPL-3.0-or-later
//! Reparto de las cargas de superficie de las losas a sus apoyos (vigas y muros)
//! por áreas tributarias (issue #78, camino sin láminas).
//!
//! Cada punto de la losa carga al borde apoyado más cercano. En una losa convexa,
//! la distancia de un punto interior al contorno es la menor de las distancias a
//! las rectas de sus lados, así que la zona que carga a cada borde apoyado `e` es
//! el polígono convexo
//!
//! ```text
//! R_e = P ∩ { p : d_e(p) ≤ d_f(p)  para todo borde apoyado f ≠ e },
//! ```
//!
//! donde `d_e` es la distancia con signo a la recta de `e` (positiva hacia
//! adentro). Cada condición es un semiplano, de modo que `R_e` sale de recortar
//! `P` con semiplanos (Sutherland y Hodgman, *Reentrant polygon clipping*, CACM
//! 17(1), 1974). Sus límites son las bisectrices de los ángulos entre bordes
//! apoyados: en una losa rectangular apoyada en los cuatro bordes salen los
//! triángulos y trapecios a 45° del método clásico de las áreas tributarias
//! (por ejemplo, Nilson, Darwin y Dolan, *Design of Concrete Structures*, 14.ª ed.,
//! §12.3; Park y Gamble, *Reinforced Concrete Slabs*, 2.ª ed., cap. 1). Los bordes
//! sin apoyo no reciben carga: su zona se reparte entre los bordes apoyados.
//!
//! La carga lineal sobre el borde `e` en la abscisa `s` es `q · w(s)`, con `w(s)` el
//! ancho de `R_e` medido en perpendicular a `e`. Como `R_e` es convexo, `w` es
//! lineal entre las abscisas de sus vértices: cada tramo es una carga trapezoidal
//! exacta y la integral de `w` es el área de `R_e`. La suma de las áreas de todas
//! las zonas es el área de la losa, así que el equilibrio global es exacto salvo
//! el redondeo de la aritmética de doble precisión.
//!
//! Lo que todavía no se reparte (y queda en [`Reparto::avisos`]): losas no
//! convexas (se dividen en losas convexas), losas sin bordes apoyados y zonas que
//! se proyectan fuera de su borde (losas con voladizos o bordes libres oblicuos).

use std::collections::HashMap;

use rayon::prelude::*;

use crate::error::ErrorNervi;

/// Losa a repartir: contorno en planta (polígono simple, sin repetir el primer
/// punto) y el grupo (piso) al que pertenece. Solo la apoyan los apoyos del mismo
/// grupo.
#[derive(Clone, Debug)]
pub struct LosaReparto {
    pub grupo: usize,
    pub contorno: Vec<[f64; 2]>,
}

/// Apoyo lineal (eje de una viga o de un muro) de un grupo.
#[derive(Clone, Debug)]
pub struct ApoyoReparto {
    pub grupo: usize,
    pub p1: [f64; 2],
    pub p2: [f64; 2],
}

/// Tramo de carga sobre un apoyo: el ancho tributario varía linealmente de
/// `ancho_a` en la abscisa `a` a `ancho_b` en `b`, con `0 ≤ a < b` medidas desde
/// `p1` del apoyo. Multiplicado por la carga de superficie da la carga lineal.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Pieza {
    pub losa: usize,
    pub apoyo: usize,
    pub a: f64,
    pub b: f64,
    pub ancho_a: f64,
    pub ancho_b: f64,
}

impl Pieza {
    /// Área tributaria del tramo (integral exacta del ancho).
    pub fn area(&self) -> f64 {
        0.5 * (self.ancho_a + self.ancho_b) * (self.b - self.a)
    }
}

/// Zona tributaria de un borde apoyado de una losa.
#[derive(Clone, Debug)]
pub struct Region {
    pub losa: usize,
    /// Apoyos que cubren ese borde, en el orden en que lo recorren.
    pub apoyos: Vec<usize>,
    /// Polígono convexo en sentido antihorario.
    pub poligono: Vec<[f64; 2]>,
}

/// Por qué una losa o uno de sus bordes no se repartió como se esperaría.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Motivo {
    /// La losa no es convexa: todavía no se reparte. No recibe ninguna pieza.
    NoConvexa,
    /// Ningún borde de la losa está apoyado. No recibe ninguna pieza.
    SinApoyos,
    /// El borde `lado` está apoyado solo en parte: se lo trata como libre.
    BordeParcial,
    /// La zona del borde `lado` se proyecta fuera de él (borde libre oblicuo o
    /// voladizo). La losa no recibe ninguna pieza.
    FueraDelBorde,
}

/// Aviso sobre una losa. `lado` es el índice del lado del contorno, contado
/// desde el lado que va del punto 0 al punto 1 del contorno tal como se dio.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Aviso {
    pub losa: usize,
    pub lado: Option<usize>,
    pub motivo: Motivo,
}

/// Resultado del reparto.
#[derive(Clone, Debug, Default)]
pub struct Reparto {
    /// Tramos de carga, por losa y en el orden en que se recorre su contorno.
    pub piezas: Vec<Pieza>,
    pub regiones: Vec<Region>,
    pub avisos: Vec<Aviso>,
    /// `repartida[k]`: si la losa `k` se repartió entera.
    pub repartida: Vec<bool>,
}

type P2 = [f64; 2];
/// Tramo `[lo, hi]` de un lado con el índice del apoyo que lo cubre.
type Tramo = (f64, f64, usize);

fn resta(a: P2, b: P2) -> P2 {
    [a[0] - b[0], a[1] - b[1]]
}

fn punto(a: P2, b: P2) -> f64 {
    a[0] * b[0] + a[1] * b[1]
}

fn cruz(a: P2, b: P2) -> f64 {
    a[0] * b[1] - a[1] * b[0]
}

fn area_con_signo(p: &[P2]) -> f64 {
    let n = p.len();
    0.5 * (0..n).map(|k| cruz(p[k], p[(k + 1) % n])).sum::<f64>()
}

/// Recta de un lado: origen, dirección unitaria, normal unitaria hacia la
/// izquierda (el interior en un contorno antihorario) y largo.
#[derive(Clone, Copy)]
struct Lado {
    o: P2,
    u: P2,
    n: P2,
    largo: f64,
}

impl Lado {
    fn new(a: P2, b: P2) -> Lado {
        let d = resta(b, a);
        let largo = d[0].hypot(d[1]);
        let u = [d[0] / largo, d[1] / largo];
        Lado {
            o: a,
            u,
            n: [-u[1], u[0]],
            largo,
        }
    }
    fn s(&self, p: P2) -> f64 {
        punto(resta(p, self.o), self.u)
    }
    fn t(&self, p: P2) -> f64 {
        punto(resta(p, self.o), self.n)
    }
    fn en(&self, s: f64) -> P2 {
        [self.o[0] + s * self.u[0], self.o[1] + s * self.u[1]]
    }
}

/// Recorta un polígono convexo con el semiplano `g(p) ≤ 0`, `g` afín.
fn recortar(poligono: &[P2], g: impl Fn(P2) -> f64) -> Vec<P2> {
    let n = poligono.len();
    let mut salida = Vec::with_capacity(n + 1);
    for k in 0..n {
        let a = poligono[k];
        let b = poligono[(k + 1) % n];
        let (ga, gb) = (g(a), g(b));
        if ga <= 0.0 {
            salida.push(a);
        }
        if (ga < 0.0 && gb > 0.0) || (ga > 0.0 && gb < 0.0) {
            let r = ga / (ga - gb);
            salida.push([a[0] + r * (b[0] - a[0]), a[1] + r * (b[1] - a[1])]);
        }
    }
    salida
}

/// Contorno antihorario sin vértices alineados (a menos de `tol` de la recta de
/// sus vecinos) y el índice, en el contorno dado, del lado original donde empieza
/// cada lado que queda.
fn normalizar(contorno: &[P2], tol: f64) -> (Vec<P2>, Vec<usize>) {
    let n = contorno.len();
    let antihorario = area_con_signo(contorno) > 0.0;
    // Vértices en sentido antihorario con el lado original que empieza en cada uno.
    let mut v: Vec<(P2, usize)> = if antihorario {
        (0..n).map(|k| (contorno[k], k)).collect()
    } else {
        // Al invertir, el lado que empieza en el vértice k (k → k-1) es el lado
        // original k-1 (de k-1 a k).
        (0..n)
            .rev()
            .map(|k| (contorno[k], (k + n - 1) % n))
            .collect()
    };
    loop {
        let m = v.len();
        if m < 3 {
            break;
        }
        let quitar = (0..m).find(|&k| {
            let a = v[(k + m - 1) % m].0;
            let b = v[k].0;
            let c = v[(k + 1) % m].0;
            let ac = resta(c, a);
            let largo = ac[0].hypot(ac[1]);
            largo == 0.0 || (cruz(ac, resta(b, a)) / largo).abs() <= tol
        });
        match quitar {
            Some(k) => {
                v.remove(k);
            }
            None => break,
        }
    }
    v.into_iter().unzip()
}

/// Tramos `[lo, hi]` de un lado (abscisas del lado) con el apoyo que los cubre, o
/// `None` si el lado no está apoyado entero. `parcial` dice si algún apoyo lo toca.
fn cobertura(
    lado: &Lado,
    apoyos: &[(usize, &ApoyoReparto)],
    tol: f64,
) -> (Option<Vec<Tramo>>, bool) {
    let mut tramos: Vec<Tramo> = Vec::new();
    for &(k, ap) in apoyos {
        if lado.t(ap.p1).abs() > tol || lado.t(ap.p2).abs() > tol {
            continue;
        }
        let (s1, s2) = (lado.s(ap.p1), lado.s(ap.p2));
        let lo = s1.min(s2).max(0.0);
        let hi = s1.max(s2).min(lado.largo);
        if hi - lo > tol {
            tramos.push((lo, hi, k));
        }
    }
    if tramos.is_empty() {
        return (None, false);
    }
    // ¿Cubren [0, largo] sin huecos mayores que tol?
    let mut orden = tramos.clone();
    orden.sort_by(|x, y| x.0.total_cmp(&y.0));
    let mut hasta = 0.0_f64;
    for &(lo, hi, _) in &orden {
        if lo > hasta + tol {
            return (None, true);
        }
        hasta = hasta.max(hi);
    }
    if hasta < lado.largo - tol {
        return (None, true);
    }
    // Cortes en los extremos de los tramos; cada subtramo va al primer apoyo (en
    // el orden dado) que lo cubre.
    let mut cortes: Vec<f64> = vec![0.0, lado.largo];
    for &(lo, hi, _) in &tramos {
        for x in [lo, hi] {
            if x > tol && x < lado.largo - tol {
                cortes.push(x);
            }
        }
    }
    cortes.sort_by(f64::total_cmp);
    cortes.dedup();
    let mut asignado: Vec<Tramo> = Vec::new();
    for par in cortes.windows(2) {
        let (lo, hi) = (par[0], par[1]);
        let medio = 0.5 * (lo + hi);
        let k = tramos
            .iter()
            .filter(|t| t.0 - tol <= medio && medio <= t.1 + tol)
            .map(|t| t.2)
            .min()
            .expect("el lado está cubierto");
        match asignado.last_mut() {
            Some(ultimo) if ultimo.2 == k => ultimo.1 = hi,
            _ => asignado.push((lo, hi, k)),
        }
    }
    (Some(asignado), true)
}

struct Salida {
    piezas: Vec<Pieza>,
    regiones: Vec<Region>,
    avisos: Vec<Aviso>,
    repartida: bool,
}

fn repartir_losa(
    indice: usize,
    losa: &LosaReparto,
    apoyos: &[(usize, &ApoyoReparto)],
    tol: f64,
) -> Salida {
    let mut salida = Salida {
        piezas: Vec::new(),
        regiones: Vec::new(),
        avisos: Vec::new(),
        repartida: false,
    };
    let aviso = |lado, motivo| Aviso {
        losa: indice,
        lado,
        motivo,
    };
    let (vertices, origen) = normalizar(&losa.contorno, tol);
    let n = vertices.len();
    let lados: Vec<Lado> = (0..n)
        .map(|k| Lado::new(vertices[k], vertices[(k + 1) % n]))
        .collect();
    if n < 3 || (0..n).any(|k| cruz(lados[k].u, lados[(k + 1) % n].u) < 0.0) {
        salida.avisos.push(aviso(None, Motivo::NoConvexa));
        return salida;
    }
    let mut apoyados: Vec<(usize, Vec<Tramo>)> = Vec::new();
    for (k, lado) in lados.iter().enumerate() {
        match cobertura(lado, apoyos, tol) {
            (Some(tramos), _) => apoyados.push((k, tramos)),
            (None, true) => salida
                .avisos
                .push(aviso(Some(origen[k]), Motivo::BordeParcial)),
            (None, false) => {}
        }
    }
    if apoyados.is_empty() {
        salida.avisos.push(aviso(None, Motivo::SinApoyos));
        return salida;
    }
    let mut piezas = Vec::new();
    let mut regiones = Vec::new();
    for (e, tramos) in &apoyados {
        let le = lados[*e];
        let mut zona = vertices.clone();
        for (f, _) in &apoyados {
            if f != e {
                let lf = lados[*f];
                zona = recortar(&zona, |p| le.t(p) - lf.t(p));
            }
        }
        if zona.len() < 3 || area_con_signo(&zona) <= 0.0 {
            continue; // zona vacía: el borde no recibe carga
        }
        // Coordenadas (s, t) de la zona respecto del borde.
        let st: Vec<P2> = zona.iter().map(|&p| [le.s(p), le.t(p)]).collect();
        let smin = st.iter().map(|q| q[0]).fold(f64::INFINITY, f64::min);
        let smax = st.iter().map(|q| q[0]).fold(f64::NEG_INFINITY, f64::max);
        if smin < -tol || smax > le.largo + tol {
            salida
                .avisos
                .push(aviso(Some(origen[*e]), Motivo::FueraDelBorde));
            return salida;
        }
        let mut cortes: Vec<f64> = st.iter().map(|q| q[0]).collect();
        for &(lo, hi, _) in tramos {
            for x in [lo, hi] {
                if x > smin && x < smax {
                    cortes.push(x);
                }
            }
        }
        cortes.sort_by(f64::total_cmp);
        cortes.dedup();
        let m = st.len();
        for par in cortes.windows(2) {
            let (sa, sb) = (par[0], par[1]);
            if sb <= sa {
                continue;
            }
            let medio = 0.5 * (sa + sb);
            // Los dos lados de la zona que cruza la perpendicular por `medio`; el
            // ancho en cada extremo sale de sus rectas (valores laterales exactos).
            let mut ta = (f64::INFINITY, f64::NEG_INFINITY);
            let mut tb = (f64::INFINITY, f64::NEG_INFINITY);
            for k in 0..m {
                let (p, q) = (st[k], st[(k + 1) % m]);
                if p[0].min(q[0]) < medio && medio < p[0].max(q[0]) {
                    let en = |s: f64| p[1] + (q[1] - p[1]) * (s - p[0]) / (q[0] - p[0]);
                    let (va, vb) = (en(sa), en(sb));
                    ta = (ta.0.min(va), ta.1.max(va));
                    tb = (tb.0.min(vb), tb.1.max(vb));
                }
            }
            let (ancho_a, ancho_b) = ((ta.1 - ta.0).max(0.0), (tb.1 - tb.0).max(0.0));
            let en_lado = medio.clamp(0.0, le.largo);
            let &(_, _, k) = tramos
                .iter()
                .find(|t| t.0 <= en_lado && en_lado <= t.1)
                .unwrap_or(&tramos[tramos.len() - 1]);
            // Abscisas en el apoyo, desde su p1.
            let ap = apoyos.iter().find(|x| x.0 == k).expect("apoyo del grupo").1;
            let la = Lado::new(ap.p1, ap.p2);
            let (a, b) = (la.s(le.en(sa)), la.s(le.en(sb)));
            let pieza = if a <= b {
                Pieza {
                    losa: indice,
                    apoyo: k,
                    a,
                    b,
                    ancho_a,
                    ancho_b,
                }
            } else {
                Pieza {
                    losa: indice,
                    apoyo: k,
                    a: b,
                    b: a,
                    ancho_a: ancho_b,
                    ancho_b: ancho_a,
                }
            };
            piezas.push(pieza);
        }
        regiones.push(Region {
            losa: indice,
            apoyos: tramos.iter().map(|t| t.2).collect(),
            poligono: zona,
        });
    }
    salida.piezas = piezas;
    salida.regiones = regiones;
    salida.repartida = true;
    salida
}

/// Reparte las losas a sus apoyos. `tol` es la tolerancia geométrica (en unidades
/// de longitud) con la que un apoyo se considera sobre un borde y un vértice
/// alineado con sus vecinos; no afecta la exactitud del reparto.
pub fn repartir(
    losas: &[LosaReparto],
    apoyos: &[ApoyoReparto],
    tol: f64,
) -> Result<Reparto, ErrorNervi> {
    if !(tol.is_finite() && tol > 0.0) {
        return Err(ErrorNervi::ModeloInvalido(
            "la tolerancia del reparto tiene que ser positiva".into(),
        ));
    }
    for (k, l) in losas.iter().enumerate() {
        if l.contorno.len() < 3 {
            return Err(ErrorNervi::ModeloInvalido(format!(
                "la losa {k} tiene menos de 3 puntos"
            )));
        }
        if l.contorno.iter().flatten().any(|c| !c.is_finite()) {
            return Err(ErrorNervi::ModeloInvalido(format!(
                "la losa {k} tiene coordenadas no finitas"
            )));
        }
        if area_con_signo(&l.contorno) == 0.0 {
            return Err(ErrorNervi::ModeloInvalido(format!(
                "la losa {k} no encierra área"
            )));
        }
    }
    for (k, a) in apoyos.iter().enumerate() {
        if a.p1.iter().chain(&a.p2).any(|c| !c.is_finite()) || a.p1 == a.p2 {
            return Err(ErrorNervi::ModeloInvalido(format!(
                "el apoyo {k} no es un segmento válido"
            )));
        }
    }
    let mut por_grupo: HashMap<usize, Vec<(usize, &ApoyoReparto)>> = HashMap::new();
    for (k, a) in apoyos.iter().enumerate() {
        por_grupo.entry(a.grupo).or_default().push((k, a));
    }
    let vacio = Vec::new();
    let salidas: Vec<Salida> = losas
        .par_iter()
        .enumerate()
        .map(|(k, l)| repartir_losa(k, l, por_grupo.get(&l.grupo).unwrap_or(&vacio), tol))
        .collect();
    let mut r = Reparto::default();
    for s in salidas {
        r.piezas.extend(s.piezas);
        r.regiones.extend(s.regiones);
        r.avisos.extend(s.avisos);
        r.repartida.push(s.repartida);
    }
    Ok(r)
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn normalizar_quita_alineados_y_conserva_lados() {
        // Cuadrado horario con un punto en el medio del lado inferior.
        let c = [[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0], [1.0, 0.0]];
        let (v, origen) = normalizar(&c, 1e-9);
        assert_eq!(v.len(), 4);
        assert!(area_con_signo(&v) > 0.0);
        assert_eq!(v.len(), origen.len());
    }

    #[test]
    fn recortar_por_la_mitad() {
        let c = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]];
        let r = recortar(&c, |p| p[0] - 1.0);
        assert!((area_con_signo(&r) - 2.0).abs() < 1e-15);
    }
}
