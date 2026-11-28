// SPDX-License-Identifier: GPL-3.0-or-later
//! Generación del modelo de cálculo desde el modelo físico del edificio (issue #74).
//!
//! Idealiza columnas, vigas y muros como barras sobre sus ejes y arma la
//! topología del pórtico espacial:
//!
//! * **Nudos** en los extremos de columnas y vigas, en los cruces de vigas del
//!   mismo nivel y en el centro de cada muro en cada nivel que alcanza. Dos
//!   puntos a menos de `tol` son el mismo nudo.
//! * **Barras**: cada elemento se parte en todos los nudos que caen sobre su eje
//!   (una viga que apoya en el tramo de otra, una columna que pasa por un piso).
//! * **Brazos rígidos** en los extremos de las vigas, hasta la cara de la
//!   columna o del muro donde llegan: el semiancho de la sección medido en la
//!   dirección de la viga, `(b/2)·|d·e_b| + (h/2)·|d·e_h|` en una sección
//!   rectangular girada y `D/2` en una circular (zonas rígidas de la unión; ver
//!   McGuire, Gallagher y Ziemian, *Matrix Structural Analysis*, 2.ª ed., §13.5).
//!   Las columnas no llevan brazos.
//! * **Apoyos**: empotramiento en la base de las columnas y los muros que
//!   arrancan del nivel más bajo.
//! * **Diafragmas rígidos**: uno por cada nivel pedido, con todos sus nudos.
//! * **Muros**, provisoriamente hasta las láminas (Fase 6): una columna ancha
//!   equivalente sobre su centro. Una viga apoyada en todo su largo sobre un
//!   muro no se idealiza como barra: su carga pasa al muro.
//!
//! Las cargas lineales (las de las losas repartidas, #78, y el peso propio de
//! las vigas) se pasan a las barras por estática exacta: lo que cae sobre la
//! parte flexible queda como carga trapezoidal y lo que cae sobre un brazo
//! rígido, o sobre una viga apoyada en un muro, pasa al nudo como una fuerza
//! vertical con el momento de su excentricidad. La fuerza y el momento totales
//! de las cargas no cambian, salvo el redondeo de la aritmética de doble
//! precisión.

use std::collections::HashMap;

use rayon::prelude::*;

use crate::error::ErrorNervi;

type P2 = [f64; 2];
type P3 = [f64; 3];

/// Columna: eje vertical en `punto` de `z1` a `z2`. Sección rectangular de ancho
/// `b` sobre la dirección girada `angulo` (radianes, antihorario desde X) y alto
/// `h` en la perpendicular, o circular de diámetro `b` (`circular`).
#[derive(Clone, Debug)]
pub struct ColumnaIdeal {
    pub punto: P2,
    pub z1: f64,
    pub z2: f64,
    pub b: f64,
    pub h: f64,
    pub angulo: f64,
    pub circular: bool,
}

/// Muro sobre el eje `p1`-`p2` (planta), de `z1` a `z2`, de `espesor`.
#[derive(Clone, Debug)]
pub struct MuroIdeal {
    pub p1: P2,
    pub p2: P2,
    pub z1: f64,
    pub z2: f64,
    pub espesor: f64,
}

/// Viga de `p1` a `p2` (planta) en el nivel `z`.
#[derive(Clone, Debug)]
pub struct VigaIdeal {
    pub p1: P2,
    pub p2: P2,
    pub z: f64,
}

/// Elemento que recibe un tramo de carga.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Cargado {
    Viga(usize),
    /// Muro y nivel (índice en [`Entrada::niveles`]) donde le llega la carga.
    Muro(usize, usize),
}

/// Carga lineal vertical (hacia abajo, positiva) sobre un elemento: varía
/// linealmente de `q[c][0]` en la abscisa `a` a `q[c][1]` en `b`, medidas desde
/// `p1` del elemento, en cada caso `c`.
#[derive(Clone, Debug)]
pub struct TramoIdeal {
    pub elemento: Cargado,
    pub a: f64,
    pub b: f64,
    pub q: Vec<[f64; 2]>,
}

/// Lo que se idealiza.
#[derive(Clone, Debug, Default)]
pub struct Entrada {
    pub columnas: Vec<ColumnaIdeal>,
    pub muros: Vec<MuroIdeal>,
    pub vigas: Vec<VigaIdeal>,
    /// Niveles de los pisos: los muros tienen un nudo en cada uno que alcanzan.
    pub niveles: Vec<f64>,
    /// Nivel de la base: se empotran las columnas y los muros que arrancan ahí.
    pub base: f64,
    /// Niveles (índices en `niveles`) con diafragma rígido.
    pub diafragmas: Vec<usize>,
    pub tramos: Vec<TramoIdeal>,
    pub n_casos: usize,
    pub tol: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TipoBarra {
    Columna,
    Muro,
    Viga,
}

/// Barra del modelo de cálculo y de dónde sale: el elemento `origen` (índice en
/// su lista) entre las abscisas `s0` y `s1` de su eje (desde `p1` en vigas y
/// muros, desde `z1` en columnas). Los brazos se miden desde cada nudo.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BarraIdeal {
    pub tipo: TipoBarra,
    pub origen: usize,
    pub i: usize,
    pub j: usize,
    pub s0: f64,
    pub s1: f64,
    pub brazo_i: f64,
    pub brazo_j: f64,
}

/// Carga trapezoidal vertical (hacia abajo, positiva) sobre la parte flexible de
/// una barra, de `a` a `b` medidas desde el fin del brazo del nudo `i`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CargaBarraIdeal {
    pub barra: usize,
    pub caso: usize,
    pub a: f64,
    pub b: f64,
    pub q_a: f64,
    pub q_b: f64,
}

/// Carga en un nudo, en ejes globales: fuerza vertical `fz` (positiva hacia
/// arriba) y momentos `mx`, `my`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CargaNudoIdeal {
    pub nudo: usize,
    pub caso: usize,
    pub fz: f64,
    pub mx: f64,
    pub my: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MotivoIdeal {
    /// La viga apoya en todo su largo sobre un muro (`otro`): su carga pasa al muro.
    VigaSobreMuro,
    /// Los brazos rígidos de una barra de la viga ocupan todo su largo: la barra
    /// queda sin brazos.
    BrazosSinLuz,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AvisoIdeal {
    pub viga: usize,
    pub otro: Option<usize>,
    pub motivo: MotivoIdeal,
}

/// Modelo de cálculo idealizado.
#[derive(Clone, Debug, Default)]
pub struct ModeloIdeal {
    pub nudos: Vec<P3>,
    pub barras: Vec<BarraIdeal>,
    pub apoyos: Vec<usize>,
    /// Nivel (índice en `niveles`) y nudos de cada diafragma.
    pub diafragmas: Vec<(usize, Vec<usize>)>,
    pub cargas_barra: Vec<CargaBarraIdeal>,
    pub cargas_nudo: Vec<CargaNudoIdeal>,
    pub avisos: Vec<AvisoIdeal>,
}

// --- Geometría -------------------------------------------------------------------

fn resta(a: P2, b: P2) -> P2 {
    [a[0] - b[0], a[1] - b[1]]
}

fn punto(a: P2, b: P2) -> f64 {
    a[0] * b[0] + a[1] * b[1]
}

fn cruz(a: P2, b: P2) -> f64 {
    a[0] * b[1] - a[1] * b[0]
}

fn largo(a: P2) -> f64 {
    a[0].hypot(a[1])
}

/// Dirección unitaria de `p1` a `p2` y largo.
fn direccion(p1: P2, p2: P2) -> (P2, f64) {
    let v = resta(p2, p1);
    let l = largo(v);
    ([v[0] / l, v[1] / l], l)
}

/// Semiancho de la columna medido en la dirección unitaria `d` (planta).
fn semiancho_columna(c: &ColumnaIdeal, d: P2) -> f64 {
    if c.circular {
        return 0.5 * c.b;
    }
    let (s, co) = c.angulo.sin_cos();
    let e_b = [co, s];
    let e_h = [-s, co];
    0.5 * c.b * punto(d, e_b).abs() + 0.5 * c.h * punto(d, e_h).abs()
}

/// Semiancho del muro (rectángulo de largo por espesor) en la dirección `d`.
fn semiancho_muro(m: &MuroIdeal, d: P2) -> f64 {
    let (e, l) = direccion(m.p1, m.p2);
    let n = [-e[1], e[0]];
    0.5 * l * punto(d, e).abs() + 0.5 * m.espesor * punto(d, n).abs()
}

fn centro_muro(m: &MuroIdeal) -> P2 {
    [0.5 * (m.p1[0] + m.p2[0]), 0.5 * (m.p1[1] + m.p2[1])]
}

// --- Registro de nudos con tolerancia ---------------------------------------------

/// Nudos únicos: dos puntos a menos de `tol` son el mismo. Una grilla de celdas de
/// lado `tol` deja la búsqueda en las 27 celdas vecinas.
struct Registro {
    tol: f64,
    puntos: Vec<P3>,
    celdas: HashMap<[i64; 3], Vec<usize>>,
}

impl Registro {
    fn new(tol: f64) -> Self {
        Registro {
            tol,
            puntos: Vec::new(),
            celdas: HashMap::new(),
        }
    }

    fn celda(&self, p: P3) -> [i64; 3] {
        [
            (p[0] / self.tol).floor() as i64,
            (p[1] / self.tol).floor() as i64,
            (p[2] / self.tol).floor() as i64,
        ]
    }

    fn buscar(&self, p: P3) -> Option<usize> {
        let c = self.celda(p);
        let mut mejor: Option<(f64, usize)> = None;
        for dx in -1..=1 {
            for dy in -1..=1 {
                for dz in -1..=1 {
                    if let Some(lista) = self.celdas.get(&[c[0] + dx, c[1] + dy, c[2] + dz]) {
                        for &k in lista {
                            let q = self.puntos[k];
                            let d = ((p[0] - q[0]).powi(2)
                                + (p[1] - q[1]).powi(2)
                                + (p[2] - q[2]).powi(2))
                            .sqrt();
                            if d <= self.tol && mejor.map_or(true, |(dm, km)| (d, k) < (dm, km)) {
                                mejor = Some((d, k));
                            }
                        }
                    }
                }
            }
        }
        mejor.map(|(_, k)| k)
    }

    fn nudo(&mut self, p: P3) -> usize {
        if let Some(k) = self.buscar(p) {
            return k;
        }
        let k = self.puntos.len();
        self.puntos.push(p);
        let c = self.celda(p);
        self.celdas.entry(c).or_default().push(k);
        k
    }
}

// --- Idealización ------------------------------------------------------------------

fn validar(e: &Entrada) -> Result<(), ErrorNervi> {
    let malo = |m: String| Err(ErrorNervi::ModeloInvalido(m));
    if !(e.tol > 0.0 && e.tol.is_finite()) {
        return malo("la tolerancia tiene que ser positiva".into());
    }
    for (k, c) in e.columnas.iter().enumerate() {
        if c.z2 - c.z1 <= e.tol {
            return malo(format!("la columna {k} no tiene altura"));
        }
        if !(c.b > 0.0 && (c.circular || c.h > 0.0)) {
            return malo(format!("la columna {k} no tiene sección"));
        }
    }
    for (k, m) in e.muros.iter().enumerate() {
        if m.z2 - m.z1 <= e.tol || largo(resta(m.p2, m.p1)) <= e.tol || m.espesor <= 0.0 {
            return malo(format!("el muro {k} no tiene altura, largo o espesor"));
        }
    }
    for (k, v) in e.vigas.iter().enumerate() {
        if largo(resta(v.p2, v.p1)) <= e.tol {
            return malo(format!("la viga {k} no tiene largo"));
        }
    }
    for &d in &e.diafragmas {
        if d >= e.niveles.len() {
            return malo(format!("el diafragma del nivel {d} no tiene nivel"));
        }
    }
    for t in &e.tramos {
        if t.q.len() != e.n_casos || t.b < t.a || t.a.is_nan() || t.b.is_nan() {
            return malo("un tramo de carga no tiene sus casos o está al revés".into());
        }
        match t.elemento {
            Cargado::Viga(v) if v >= e.vigas.len() => {
                return malo(format!("un tramo de carga referencia la viga {v}"))
            }
            Cargado::Muro(m, n) if m >= e.muros.len() || n >= e.niveles.len() => {
                return malo(format!("un tramo de carga referencia el muro {m}"))
            }
            _ => {}
        }
    }
    Ok(())
}

/// Muro sobre el que apoya cada viga en todo su largo, si hay uno.
fn vigas_sobre_muro(e: &Entrada) -> Vec<Option<usize>> {
    let tol = e.tol;
    e.vigas
        .par_iter()
        .map(|v| {
            e.muros.iter().position(|m| {
                if !(m.z1 + tol < v.z && v.z <= m.z2 + tol) {
                    return false;
                }
                let (d, l) = direccion(m.p1, m.p2);
                [v.p1, v.p2].iter().all(|&p| {
                    let r = resta(p, m.p1);
                    let t = punto(r, d);
                    cruz(d, r).abs() <= tol && t >= -tol && t <= l + tol
                })
            })
        })
        .collect()
}

/// Agrupa índices por nivel: dos niveles a menos de `tol` son el mismo.
fn por_nivel<T>(items: &[T], z: impl Fn(&T) -> f64, tol: f64) -> Vec<(f64, Vec<usize>)> {
    let mut orden: Vec<usize> = (0..items.len()).collect();
    orden.sort_by(|&a, &b| z(&items[a]).total_cmp(&z(&items[b])).then(a.cmp(&b)));
    let mut grupos: Vec<(f64, Vec<usize>)> = Vec::new();
    for k in orden {
        let zk = z(&items[k]);
        match grupos.last_mut() {
            Some((z0, g)) if zk - *z0 <= tol => g.push(k),
            _ => grupos.push((zk, vec![k])),
        }
    }
    grupos
}

/// Punto donde se cortan dos vigas en el interior de las dos, si se cortan.
fn cruce(a: &VigaIdeal, b: &VigaIdeal, tol: f64) -> Option<P2> {
    let r = resta(a.p2, a.p1);
    let s = resta(b.p2, b.p1);
    let den = cruz(r, s);
    let (la, lb) = (largo(r), largo(s));
    if den.abs() <= 1e-12 * la * lb {
        return None; // paralelas
    }
    let q = resta(b.p1, a.p1);
    let t = cruz(q, s) / den;
    let u = cruz(q, r) / den;
    let dentro = |t: f64, l: f64| t * l > tol && t * l < l - tol;
    if dentro(t, la) && dentro(u, lb) {
        Some([a.p1[0] + t * r[0], a.p1[1] + t * r[1]])
    } else {
        None
    }
}

/// Integrales de una carga lineal que va de `qa` en `a` a `qb` en `b`, recortada
/// a `[lo, hi]`: `(∫q ds, ∫q·(s − lo) ds, q(lo'), q(hi'), lo', hi')` con
/// `lo' = max(a, lo)` y `hi' = min(b, hi)`; `None` si no se tocan.
fn recorte(a: f64, b: f64, qa: f64, qb: f64, lo: f64, hi: f64) -> Option<[f64; 6]> {
    let (x0, x1) = (a.max(lo), b.min(hi));
    if x1 <= x0 {
        return None;
    }
    let q = |x: f64| {
        if b > a {
            qa + (qb - qa) * (x - a) / (b - a)
        } else {
            qa
        }
    };
    let (q0, q1) = (q(x0), q(x1));
    let l = x1 - x0;
    let fuerza = 0.5 * (q0 + q1) * l;
    // ∫ q (s − lo) ds = ∫ q (s − x0) ds + (x0 − lo) ∫ q ds
    let momento = l * l * (q0 / 6.0 + q1 / 3.0) + (x0 - lo) * fuerza;
    Some([fuerza, momento, q0, q1, x0, x1])
}

/// Carga en el nudo `nudo` (en `pn`) equivalente a la carga lineal vertical que
/// recorre la recta `origen + d·s` con fuerza `f = ∫q` y `m = ∫q·(s − s0)`,
/// medidas desde `s0`. Estática exacta: `F = −f·ẑ` y `M = ∫ r × dF`.
#[allow(clippy::too_many_arguments)]
fn a_nudo(
    nudo: usize,
    caso: usize,
    pn: P2,
    origen: P2,
    d: P2,
    s0: f64,
    f: f64,
    m: f64,
) -> CargaNudoIdeal {
    // W = ∫ q·r ds con r = P(s) − pn = (P(s0) − pn) + d·(s − s0)
    let r0 = resta([origen[0] + d[0] * s0, origen[1] + d[1] * s0], pn);
    let w = [r0[0] * f + d[0] * m, r0[1] * f + d[1] * m];
    // r × (0, 0, −q) = (−r_y q, r_x q, 0)
    CargaNudoIdeal {
        nudo,
        caso,
        fz: -f,
        mx: -w[1],
        my: w[0],
    }
}

/// Genera el modelo de cálculo.
pub fn idealizar(e: &Entrada) -> Result<ModeloIdeal, ErrorNervi> {
    validar(e)?;
    let tol = e.tol;
    let sobre_muro = vigas_sobre_muro(e);
    let mut avisos: Vec<AvisoIdeal> = sobre_muro
        .iter()
        .enumerate()
        .filter_map(|(v, m)| {
            m.map(|m| AvisoIdeal {
                viga: v,
                otro: Some(m),
                motivo: MotivoIdeal::VigaSobreMuro,
            })
        })
        .collect();
    let vigas_activas: Vec<usize> = (0..e.vigas.len())
        .filter(|&v| sobre_muro[v].is_none())
        .collect();

    // 1. Nudos: extremos, centros de muros por nivel y cruces de vigas.
    let mut reg = Registro::new(tol);
    for c in &e.columnas {
        reg.nudo([c.punto[0], c.punto[1], c.z1]);
        reg.nudo([c.punto[0], c.punto[1], c.z2]);
    }
    // Nudo del centro de cada muro en cada nivel que alcanza (índice del nivel).
    let mut nudos_muro: Vec<Vec<(usize, usize)>> = Vec::with_capacity(e.muros.len());
    for m in &e.muros {
        let c = centro_muro(m);
        let mut lista = vec![];
        for (k, &z) in e.niveles.iter().enumerate() {
            if z >= m.z1 - tol && z <= m.z2 + tol {
                lista.push((k, reg.nudo([c[0], c[1], z])));
            }
        }
        reg.nudo([c[0], c[1], m.z1]);
        reg.nudo([c[0], c[1], m.z2]);
        nudos_muro.push(lista);
    }
    for &v in &vigas_activas {
        let b = &e.vigas[v];
        reg.nudo([b.p1[0], b.p1[1], b.z]);
        reg.nudo([b.p2[0], b.p2[1], b.z]);
    }
    let activas: Vec<VigaIdeal> = vigas_activas.iter().map(|&v| e.vigas[v].clone()).collect();
    let cruces: Vec<P3> = por_nivel(&activas, |v| v.z, tol)
        .par_iter()
        .flat_map_iter(|(_, g)| {
            let mut salida = vec![];
            for (x, &a) in g.iter().enumerate() {
                for &b in &g[x + 1..] {
                    if let Some(p) = cruce(&activas[a], &activas[b], tol) {
                        salida.push([p[0], p[1], activas[a].z]);
                    }
                }
            }
            salida
        })
        .collect();
    for p in cruces {
        reg.nudo(p);
    }
    let nudos = reg.puntos.clone();

    // Nudos por nivel (para partir las vigas) y por columna vertical en planta.
    let niveles_nudos = por_nivel(&nudos, |p| p[2], tol);
    let mut planta: HashMap<[i64; 2], Vec<usize>> = HashMap::new();
    for (k, p) in nudos.iter().enumerate() {
        let c = [(p[0] / tol).floor() as i64, (p[1] / tol).floor() as i64];
        planta.entry(c).or_default().push(k);
    }
    let sobre_vertical = |x: f64, y: f64, z1: f64, z2: f64| -> Vec<(f64, usize)> {
        let c = [(x / tol).floor() as i64, (y / tol).floor() as i64];
        let mut v = vec![];
        for dx in -1..=1 {
            for dy in -1..=1 {
                if let Some(l) = planta.get(&[c[0] + dx, c[1] + dy]) {
                    for &k in l {
                        let p = nudos[k];
                        if (p[0] - x).hypot(p[1] - y) <= tol && p[2] >= z1 - tol && p[2] <= z2 + tol
                        {
                            v.push((p[2] - z1, k));
                        }
                    }
                }
            }
        }
        v.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
        v.dedup_by_key(|a| a.1);
        v
    };

    // 2. Barras de columnas y muros: se parten en los nudos de su eje.
    let mut barras: Vec<BarraIdeal> = Vec::new();
    let mut verticales = |tipo: TipoBarra, origen: usize, x: f64, y: f64, z1: f64, z2: f64| {
        let v = sobre_vertical(x, y, z1, z2);
        for par in v.windows(2) {
            barras.push(BarraIdeal {
                tipo,
                origen,
                i: par[0].1,
                j: par[1].1,
                s0: par[0].0,
                s1: par[1].0,
                brazo_i: 0.0,
                brazo_j: 0.0,
            });
        }
    };
    for (k, c) in e.columnas.iter().enumerate() {
        verticales(TipoBarra::Columna, k, c.punto[0], c.punto[1], c.z1, c.z2);
    }
    for (k, m) in e.muros.iter().enumerate() {
        let c = centro_muro(m);
        verticales(TipoBarra::Muro, k, c[0], c[1], m.z1, m.z2);
    }

    // Columnas y muros que llegan a cada nudo (para los brazos de las vigas).
    let mut de_nudo: HashMap<usize, (Vec<usize>, Vec<usize>)> = HashMap::new();
    for b in &barras {
        for n in [b.i, b.j] {
            let entrada = de_nudo.entry(n).or_default();
            match b.tipo {
                TipoBarra::Columna => entrada.0.push(b.origen),
                TipoBarra::Muro => entrada.1.push(b.origen),
                TipoBarra::Viga => {}
            }
        }
    }
    let brazo = |n: usize, d: P2| -> f64 {
        let Some((cols, muros)) = de_nudo.get(&n) else {
            return 0.0;
        };
        let a = cols
            .iter()
            .map(|&c| semiancho_columna(&e.columnas[c], d))
            .fold(0.0, f64::max);
        muros
            .iter()
            .map(|&m| semiancho_muro(&e.muros[m], d))
            .fold(a, f64::max)
    };

    // 3. Barras de vigas: se parten en los nudos de su nivel que caen sobre el eje.
    let nivel_de = |z: f64| -> Option<&Vec<usize>> {
        niveles_nudos
            .iter()
            .find(|(z0, _)| (z - *z0).abs() <= tol)
            .map(|(_, g)| g)
    };
    let partes: Vec<(usize, Vec<(f64, usize)>)> = vigas_activas
        .par_iter()
        .map(|&v| {
            let b = &e.vigas[v];
            let (d, l) = direccion(b.p1, b.p2);
            let (xmin, xmax) = (b.p1[0].min(b.p2[0]) - tol, b.p1[0].max(b.p2[0]) + tol);
            let (ymin, ymax) = (b.p1[1].min(b.p2[1]) - tol, b.p1[1].max(b.p2[1]) + tol);
            let mut s: Vec<(f64, usize)> = nivel_de(b.z)
                .into_iter()
                .flatten()
                .filter_map(|&k| {
                    let p = nudos[k];
                    if (p[2] - b.z).abs() > tol
                        || p[0] < xmin
                        || p[0] > xmax
                        || p[1] < ymin
                        || p[1] > ymax
                    {
                        return None;
                    }
                    let r = resta([p[0], p[1]], b.p1);
                    let t = punto(r, d);
                    (cruz(d, r).abs() <= tol && t >= -tol && t <= l + tol)
                        .then_some((t.clamp(0.0, l), k))
                })
                .collect();
            s.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
            s.dedup_by_key(|a| a.1);
            (v, s)
        })
        .collect();
    // Barras de cada viga, para pasar las cargas.
    let mut de_viga: HashMap<usize, Vec<usize>> = HashMap::new();
    for (v, s) in &partes {
        let (d, _) = direccion(e.vigas[*v].p1, e.vigas[*v].p2);
        for par in s.windows(2) {
            let (s0, s1) = (par[0].0, par[1].0);
            let (mut bi, mut bj) = (brazo(par[0].1, d), brazo(par[1].1, [-d[0], -d[1]]));
            if bi + bj >= (s1 - s0) - tol {
                avisos.push(AvisoIdeal {
                    viga: *v,
                    otro: None,
                    motivo: MotivoIdeal::BrazosSinLuz,
                });
                bi = 0.0;
                bj = 0.0;
            }
            de_viga.entry(*v).or_default().push(barras.len());
            barras.push(BarraIdeal {
                tipo: TipoBarra::Viga,
                origen: *v,
                i: par[0].1,
                j: par[1].1,
                s0,
                s1,
                brazo_i: bi,
                brazo_j: bj,
            });
        }
    }

    // 4. Apoyos: base de las columnas y los muros que arrancan del nivel más bajo.
    let mut apoyos: Vec<usize> = Vec::new();
    for b in &barras {
        let base = match b.tipo {
            TipoBarra::Columna => e.columnas[b.origen].z1,
            TipoBarra::Muro => e.muros[b.origen].z1,
            TipoBarra::Viga => continue,
        };
        if b.s0 <= tol && (base - e.base).abs() <= tol {
            apoyos.push(b.i);
        }
    }
    apoyos.sort_unstable();
    apoyos.dedup();

    // 5. Diafragmas: todos los nudos del nivel.
    let diafragmas: Vec<(usize, Vec<usize>)> = e
        .diafragmas
        .iter()
        .filter_map(|&k| {
            let z = e.niveles[k];
            let g: Vec<usize> = (0..nudos.len())
                .filter(|&n| (nudos[n][2] - z).abs() <= tol)
                .collect();
            (!g.is_empty()).then_some((k, g))
        })
        .collect();

    // 6. Cargas.
    let mut cargas_barra = Vec::new();
    let mut cargas_nudo = Vec::new();
    for t in &e.tramos {
        match t.elemento {
            Cargado::Viga(v) => {
                let viga = &e.vigas[v];
                let (d, _) = direccion(viga.p1, viga.p2);
                if let Some(m) = sobre_muro[v] {
                    // La viga apoyada en el muro: todo pasa al nudo del muro en su nivel.
                    let Some(&(_, n)) = nudos_muro[m]
                        .iter()
                        .find(|(k, _)| (e.niveles[*k] - viga.z).abs() <= tol)
                    else {
                        continue;
                    };
                    let pn = [nudos[n][0], nudos[n][1]];
                    for (c, q) in t.q.iter().enumerate() {
                        if let Some([f, mo, ..]) = recorte(t.a, t.b, q[0], q[1], t.a, t.b) {
                            cargas_nudo.push(a_nudo(n, c, pn, viga.p1, d, t.a, f, mo));
                        }
                    }
                    continue;
                }
                for &k in de_viga.get(&v).map(Vec::as_slice).unwrap_or(&[]) {
                    let b = barras[k];
                    let (f0, f1) = (b.s0 + b.brazo_i, b.s1 - b.brazo_j);
                    let pi = [nudos[b.i][0], nudos[b.i][1]];
                    let pj = [nudos[b.j][0], nudos[b.j][1]];
                    for (c, q) in t.q.iter().enumerate() {
                        if let Some([f, mo, ..]) = recorte(t.a, t.b, q[0], q[1], b.s0, f0) {
                            cargas_nudo.push(a_nudo(b.i, c, pi, viga.p1, d, b.s0, f, mo));
                        }
                        if let Some([_, _, q0, q1, x0, x1]) = recorte(t.a, t.b, q[0], q[1], f0, f1)
                        {
                            cargas_barra.push(CargaBarraIdeal {
                                barra: k,
                                caso: c,
                                a: x0 - f0,
                                b: x1 - f0,
                                q_a: q0,
                                q_b: q1,
                            });
                        }
                        if let Some([f, mo, ..]) = recorte(t.a, t.b, q[0], q[1], f1, b.s1) {
                            cargas_nudo.push(a_nudo(b.j, c, pj, viga.p1, d, f1, f, mo));
                        }
                    }
                }
            }
            Cargado::Muro(m, nivel) => {
                let muro = &e.muros[m];
                let Some(&(_, n)) = nudos_muro[m].iter().find(|(k, _)| *k == nivel) else {
                    continue;
                };
                let (d, _) = direccion(muro.p1, muro.p2);
                let pn = [nudos[n][0], nudos[n][1]];
                for (c, q) in t.q.iter().enumerate() {
                    if let Some([f, mo, ..]) = recorte(t.a, t.b, q[0], q[1], t.a, t.b) {
                        cargas_nudo.push(a_nudo(n, c, pn, muro.p1, d, t.a, f, mo));
                    }
                }
            }
        }
    }
    avisos.sort_by_key(|a| (a.viga, a.motivo as u8));
    avisos.dedup();
    Ok(ModeloIdeal {
        nudos,
        barras,
        apoyos,
        diafragmas,
        cargas_barra,
        cargas_nudo,
        avisos,
    })
}
