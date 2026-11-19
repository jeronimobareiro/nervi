// SPDX-License-Identifier: GPL-3.0-or-later
//! Flexión de vigas rectangulares de hormigón armado (ACI 318-19).
//!
//! Núcleo numérico de `nervi.design.aci318.flexion` (issue #22): resistencia por
//! compatibilidad de deformaciones, armadura simple necesaria y elección de
//! barras comerciales. **Experimental**: sin revisión de un ingeniero.
//!
//! Unidades: mm, mm² y MPa; momentos en kN·m, como la API de Python. La
//! validación de los datos y los mensajes de error quedan en Python.
//!
//! Método (se implementa el método y se cita el artículo):
//!
//! - Hipótesis de §22.2: secciones planas, `εcu = 0.003` (§22.2.2.1), bloque
//!   rectangular de `0.85 f'c` y profundidad `a = β1 c` (§22.2.2.4.1, `β1` de
//!   §22.2.2.4.3) y acero elastoplástico (§20.2.2.1). El equilibrio se resuelve
//!   por bisección sobre `c`, así que vale también si la armadura comprimida no
//!   fluye.
//! - `φ` según `εt` (§21.2.2) y `εt ≥ 0.004` en vigas (§9.3.3.1).
//! - Armadura mínima (§9.6.1.2) y su excepción de 4/3 de la requerida (§9.6.1.3).
//! - Separación libre mínima en una capa (§25.2.1) y entre capas (§25.2.2).
//!
//! El algoritmo es el mismo que tenía la versión en Python, paso por paso, para
//! que los resultados coincidan; `tests/test_viga_rust.py` lo compara con ella.

use super::columna::{EPS_CU, ES};
use std::collections::HashMap;
use std::f64::consts::PI;

/// Separación libre mínima entre capas de barras, mm (§25.2.2).
pub const SEPARACION_ENTRE_CAPAS: f64 = 25.0;

/// Hormigón y acero longitudinal de la viga, MPa.
#[derive(Clone, Copy, Debug)]
pub struct MaterialViga {
    pub fc: f64,
    pub fy: f64,
}

impl MaterialViga {
    /// Factor `β1` del bloque rectangular equivalente (§22.2.2.4.3).
    pub fn beta1(&self) -> f64 {
        if self.fc <= 28.0 {
            0.85
        } else if self.fc >= 55.0 {
            0.65
        } else {
            0.85 - 0.05 * (self.fc - 28.0) / 7.0
        }
    }

    /// `φ` para momento sin pretensado según `εt` (§21.2.2).
    pub fn phi(&self, eps_t: f64) -> f64 {
        let eps_ty = self.fy / ES;
        if eps_t >= eps_ty + 0.003 {
            0.90
        } else if eps_t <= eps_ty {
            0.65
        } else {
            0.65 + 0.25 * (eps_t - eps_ty) / 0.003
        }
    }

    /// `As,min` de vigas no pretensadas, mm² (§9.6.1.2).
    pub fn armadura_minima(&self, b: f64, d: f64) -> f64 {
        (0.25 * self.fc.sqrt() / self.fy).max(1.4 / self.fy) * b * d
    }
}

/// Resistencia a flexión de una sección rectangular.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ResistenciaFlexion {
    /// Momento nominal, kN·m.
    pub mn: f64,
    pub phi: f64,
    /// Momento de diseño, kN·m.
    pub phi_mn: f64,
    /// Profundidad del eje neutro y del bloque, mm.
    pub c: f64,
    pub a: f64,
    /// Deformación de la capa más traccionada.
    pub eps_t: f64,
    /// Tensión en la armadura traccionada y en la comprimida, MPa.
    pub fs: f64,
    pub fs_comp: f64,
}

/// Resistencia de la sección `b` × `d` con `as_` traccionada, `as_comp` comprimida a
/// `d_comp` de la fibra comprimida y la capa más traccionada a `dt` (§22.2).
pub fn resistencia(
    b: f64,
    d: f64,
    as_: f64,
    mat: &MaterialViga,
    as_comp: f64,
    d_comp: f64,
    dt: f64,
) -> ResistenciaFlexion {
    if as_ == 0.0 {
        return ResistenciaFlexion {
            mn: 0.0,
            phi: 0.9,
            phi_mn: 0.0,
            c: 0.0,
            a: 0.0,
            eps_t: f64::INFINITY,
            fs: 0.0,
            fs_comp: 0.0,
        };
    }
    let (fc, fy, b1) = (mat.fc, mat.fy, mat.beta1());
    let tension = |eps: f64| (ES * eps).min(fy).max(-fy); // §20.2.2.1
    let desplazado = |a: f64| if a > d_comp { 0.85 * fc } else { 0.0 };
    let fuerzas = |c: f64| {
        let a = b1 * c;
        let cc = 0.85 * fc * b * a; // §22.2.2.4.1
        let fs = tension(EPS_CU * (d - c) / c);
        let fsc = if as_comp != 0.0 {
            tension(EPS_CU * (c - d_comp) / c)
        } else {
            0.0
        };
        let cs = as_comp * (fsc - desplazado(a));
        (cc + cs - as_ * fs, a, fs, fsc)
    };
    let (mut lo, mut hi) = (1e-9 * d, d);
    while fuerzas(hi).0 < 0.0 {
        hi *= 2.0; // en secciones muy armadas el eje neutro baja de d
    }
    for _ in 0..200 {
        let mid = 0.5 * (lo + hi);
        if fuerzas(mid).0 < 0.0 {
            lo = mid;
        } else {
            hi = mid;
        }
        if hi - lo < 1e-10 * d {
            break;
        }
    }
    let c = 0.5 * (lo + hi);
    let (_, a, fs, fsc) = fuerzas(c);
    let cc = 0.85 * fc * b * a;
    let cs = as_comp * (fsc - desplazado(a));
    let mn = (cc * (d - a / 2.0) + cs * (d - d_comp)) / 1e6;
    let eps_t = EPS_CU * (dt - c) / c;
    let phi = mat.phi(eps_t);
    ResistenciaFlexion {
        mn,
        phi,
        phi_mn: phi * mn,
        c,
        a,
        eps_t,
        fs,
        fs_comp: fsc,
    }
}

/// Armadura simple para `mu` (kN·m) con `εt ≥ lim` en la capa extrema.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ArmaduraSimple {
    /// Por resistencia, mm².
    pub as_req: f64,
    /// De diseño: `max(As_req, min(As_min, 4/3·As_req))` (§9.6.1.2 y §9.6.1.3).
    pub as_dis: f64,
    /// Resistencia con `as_dis`.
    pub resistencia: ResistenciaFlexion,
}

/// Resultado de [`armadura_simple`]: la resistencia con la armadura que deja
/// `εt = lim` y, si alcanza para `mu`, la armadura simple.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Flexion {
    pub as_lim: f64,
    pub c_lim: f64,
    pub limite: ResistenciaFlexion,
    pub simple: Option<ArmaduraSimple>,
}

/// Armadura traccionada para `mu` (kN·m, en valor absoluto) en la sección `b` ×
/// `d` con la capa extrema a `dt`, por bisección sobre el área.
pub fn armadura_simple(mu: f64, b: f64, d: f64, dt: f64, mat: &MaterialViga, lim: f64) -> Flexion {
    let c_lim = EPS_CU * dt / (EPS_CU + lim);
    let as_lim = 0.85 * mat.fc * b * mat.beta1() * c_lim / mat.fy;
    let limite = resistencia(b, d, as_lim, mat, 0.0, 0.0, dt);
    let mut simple = None;
    if mu <= limite.phi_mn {
        let (mut lo, mut hi) = (0.0, as_lim);
        for _ in 0..200 {
            let mid = 0.5 * (lo + hi);
            if resistencia(b, d, mid, mat, 0.0, 0.0, dt).phi_mn < mu {
                lo = mid;
            } else {
                hi = mid;
            }
            if hi - lo < 1e-9 * as_lim {
                break;
            }
        }
        let as_req = hi;
        let as_dis = as_req.max(mat.armadura_minima(b, d).min(4.0 / 3.0 * as_req));
        simple = Some(ArmaduraSimple {
            as_req,
            as_dis,
            resistencia: resistencia(b, d, as_dis, mat, 0.0, 0.0, dt),
        });
    }
    Flexion {
        as_lim,
        c_lim,
        limite,
        simple,
    }
}

/// Geometría de la viga para ubicar las barras, mm.
#[derive(Clone, Copy, Debug)]
pub struct SeccionViga {
    pub b: f64,
    pub h: f64,
    /// Recubrimiento libre hasta el estribo.
    pub recubrimiento: f64,
    pub d_estribo: f64,
    pub d_agregado: f64,
}

/// Disposición de barras elegida por [`elegir_barras`]. Las capas son índices en
/// la lista de diámetros, empezando por la más cercana a la cara traccionada.
#[derive(Clone, Debug, PartialEq)]
pub struct Disposicion {
    pub capas: Vec<Vec<usize>>,
    pub area: f64,
    pub d: f64,
    pub dt: f64,
    pub b_nec: f64,
    pub s_libre: f64,
    pub as_req: f64,
    pub resistencia: ResistenciaFlexion,
}

/// Separación libre mínima entre barras de una capa, mm (§25.2.1).
pub fn separacion_libre_minima(d_b: f64, d_agregado: f64) -> f64 {
    25.0_f64.max(d_b).max(4.0 / 3.0 * d_agregado)
}

fn area_barra(d: f64) -> f64 {
    PI * d * d / 4.0
}

/// Ancho mínimo de viga para una capa de barras, mm.
fn ancho_necesario(capa: &[f64], s: &SeccionViga) -> f64 {
    let dmax = capa.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let sep = separacion_libre_minima(dmax, s.d_agregado);
    let suma: f64 = capa.iter().sum();
    2.0 * (s.recubrimiento + s.d_estribo) + suma + (capa.len() as f64 - 1.0) * sep
}

/// Área, altura útil al centroide y a la capa extrema; capas alineadas (§25.2.2).
fn geometria(capas: &[Vec<f64>], s: &SeccionViga) -> (f64, f64, f64) {
    let (mut area, mut momento, mut y_min) = (0.0, 0.0, f64::INFINITY);
    let mut y_capa = s.recubrimiento + s.d_estribo;
    for capa in capas {
        let dmax = capa.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        for &db in capa {
            let y = y_capa + db / 2.0;
            let a = area_barra(db);
            area += a;
            momento += a * y;
            y_min = y_min.min(y);
        }
        y_capa += dmax + SEPARACION_ENTRE_CAPAS;
    }
    (area, s.h - momento / area, s.h - y_min)
}

/// Un diámetro, o dos con el mayor en las esquinas (al menos dos barras).
fn candidatas_una_capa(diametros: &[f64], max_barras: usize) -> Vec<Vec<Vec<usize>>> {
    let mut salida = Vec::new();
    for i in 0..diametros.len() {
        for n in 2..=max_barras {
            salida.push(vec![vec![i; n]]);
        }
    }
    // Pares de diámetros en el orden de itertools.combinations sobre la lista ordenada
    // de mayor a menor (estable, como sorted(reverse=True)).
    let mut orden: Vec<usize> = (0..diametros.len()).collect();
    orden.sort_by(|&a, &b| diametros[b].total_cmp(&diametros[a]));
    for p in 0..orden.len() {
        for q in p + 1..orden.len() {
            let (i1, i2) = (orden[p], orden[q]);
            for n1 in 2..max_barras {
                for n2 in 1..=max_barras - n1 {
                    let mut capa = vec![i1; n1];
                    capa.extend(vec![i2; n2]);
                    salida.push(vec![capa]);
                }
            }
        }
    }
    salida
}

/// Un diámetro por capa, el de la segunda no mayor; la segunda alineada sobre la
/// primera, con al menos dos barras y no más que la primera.
fn candidatas_dos_capas(diametros: &[f64], max_barras: usize) -> Vec<Vec<Vec<usize>>> {
    let mut salida = Vec::new();
    for i1 in 0..diametros.len() {
        for i2 in 0..diametros.len() {
            if diametros[i2] > diametros[i1] {
                continue;
            }
            for n1 in 2..max_barras.saturating_sub(1) {
                for n2 in 2..=n1.min(max_barras - n1) {
                    salida.push(vec![vec![i1; n1], vec![i2; n2]]);
                }
            }
        }
    }
    salida
}

/// Candidata: área, cantidad de barras, capas (índices y diámetros), `d` y `dt`.
type Candidata = (f64, usize, Vec<Vec<usize>>, Vec<Vec<f64>>, f64, f64);

/// Elige barras comerciales para `mu` (kN·m) con armadura simple: la disposición
/// válida de menor área (a igualdad, menos barras), primero en una capa y, solo si
/// ninguna alcanza y `max_capas` es 2, en dos. Válida: entra en el ancho con la
/// separación de §25.2.1, `φMn ≥ mu` con su `d` real, `εt ≥ lim` y armadura
/// mínima (§9.6.1.2-3). `None` si ninguna sirve.
pub fn elegir_barras(
    mu: f64,
    seccion: &SeccionViga,
    mat: &MaterialViga,
    lim: f64,
    diametros: &[f64],
    max_capas: usize,
    max_barras: usize,
) -> Option<Disposicion> {
    let mut familias = vec![candidatas_una_capa(diametros, max_barras)];
    if max_capas == 2 {
        familias.push(candidatas_dos_capas(diametros, max_barras));
    }
    // Armadura requerida por altura útil (redondeada a 1e-6 mm), compartida.
    let mut requerida: HashMap<(i64, i64), Option<ArmaduraSimple>> = HashMap::new();
    for familia in familias {
        let mut cands: Vec<Candidata> = familia
            .into_iter()
            .map(|capas| {
                let mm: Vec<Vec<f64>> = capas
                    .iter()
                    .map(|c| c.iter().map(|&i| diametros[i]).collect())
                    .collect();
                let (area, d, dt) = geometria(&mm, seccion);
                let n = capas.iter().map(Vec::len).sum();
                (area, n, capas, mm, d, dt)
            })
            .collect();
        cands.sort_by(|x, y| x.0.total_cmp(&y.0).then(x.1.cmp(&y.1)));
        for (area, _, capas, mm, d, dt) in cands {
            let b_nec = mm
                .iter()
                .map(|c| ancho_necesario(c, seccion))
                .fold(f64::NEG_INFINITY, f64::max);
            if b_nec > seccion.b + 1e-9 {
                continue;
            }
            let clave = ((d * 1e6).round() as i64, (dt * 1e6).round() as i64);
            let req = *requerida
                .entry(clave)
                .or_insert_with(|| armadura_simple(mu, seccion.b, d, dt, mat, lim).simple);
            let Some(req) = req else { continue };
            if area < req.as_dis - 1e-9 {
                continue;
            }
            let r = resistencia(seccion.b, d, area, mat, 0.0, 0.0, dt);
            if r.phi_mn < mu - 1e-9 || r.eps_t < lim - 1e-12 {
                continue;
            }
            let dmax = mm
                .iter()
                .flatten()
                .cloned()
                .fold(f64::NEG_INFINITY, f64::max);
            return Some(Disposicion {
                capas,
                area,
                d,
                dt,
                b_nec,
                s_libre: separacion_libre_minima(dmax, seccion.d_agregado),
                as_req: req.as_req,
                resistencia: r,
            });
        }
    }
    None
}

#[cfg(test)]
mod pruebas {
    use super::*;

    const MAT: MaterialViga = MaterialViga {
        fc: 25.0,
        fy: 420.0,
    };

    #[test]
    fn armadura_simple_contra_bloque_rectangular() {
        // Con la armadura fluyendo: a = As fy / (0.85 f'c b), Mn = As fy (d − a/2) (§22.2).
        let (b, d, as_) = (300.0, 450.0, 1200.0);
        let r = resistencia(b, d, as_, &MAT, 0.0, 0.0, d);
        let a = as_ * 420.0 / (0.85 * 25.0 * b);
        let mn = as_ * 420.0 * (d - a / 2.0) / 1e6;
        assert!((r.mn - mn).abs() < 1e-7 * mn);
        assert!((r.a - a).abs() < 1e-6);
        assert_eq!(r.phi, 0.9);
        // La armadura necesaria para ese φMn es la misma.
        let f = armadura_simple(r.phi_mn, b, d, d, &MAT, 0.005);
        let s = f.simple.unwrap();
        assert!((s.as_req - as_).abs() < 1e-5 * as_);
    }

    #[test]
    fn eleccion_de_barras_cumple() {
        let s = SeccionViga {
            b: 300.0,
            h: 500.0,
            recubrimiento: 40.0,
            d_estribo: 10.0,
            d_agregado: 19.0,
        };
        let diametros = [8.0, 10.0, 12.0, 16.0, 20.0, 25.0, 32.0];
        let lim = 420.0 / ES + 0.003;
        let disp = elegir_barras(150.0, &s, &MAT, lim, &diametros, 2, 12).unwrap();
        assert!(disp.resistencia.phi_mn >= 150.0);
        assert!(disp.b_nec <= s.b);
        assert!(disp.area >= disp.as_req);
        // Un momento imposible no tiene disposición.
        assert!(elegir_barras(5000.0, &s, &MAT, lim, &diametros, 2, 12).is_none());
    }
}
