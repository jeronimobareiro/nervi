// SPDX-License-Identifier: GPL-3.0-or-later
//! Flexocompresión biaxial de columnas de hormigón armado (ACI 318-19).
//!
//! Núcleo numérico de `nervi.design.aci318.columna` (issue #24): resultantes de
//! la sección para un eje neutro dado, resistencia de diseño en una dirección del
//! plano `(Mz, My)` con `Pu` fijo, razones demanda/capacidad y búsqueda de la
//! armadura de menor área. **Experimental**: sin revisión de un ingeniero.
//!
//! Unidades: mm, MPa y N (N·mm en momentos); las conversiones a kN y kN·m las
//! hace quien llama, salvo en [`razones`], que recibe y devuelve kN y kN·m como la
//! API de Python. Ejes y signos como en el módulo de Python:
//!
//! - `Pn` positivo en compresión.
//! - `Mz` positivo si comprime la fibra `+y`; `My` positivo si comprime la `-z`.
//!
//! Método (se implementa el método y se cita el artículo):
//!
//! - Hipótesis de §22.2: secciones planas, `εcu = 0.003` (§22.2.2.1), bloque
//!   rectangular de `0.85 f'c` hasta `a = β1 c` medida en perpendicular al eje
//!   neutro (§22.2.2.4, `β1` de §22.2.2.4.3) y acero elastoplástico (§20.2.2.1).
//! - El bloque comprimido se integra exactamente recortando el contorno convexo
//!   con el semiplano `profundidad ≤ a`; las barras son fibras puntuales y las que
//!   caen en el bloque descuentan el hormigón que desplazan.
//! - `φ` según `εt` de la barra más traccionada (§21.2.2).
//! - La capacidad en una dirección se busca con `φPn = Pu` fijo: bisección
//!   logarítmica sobre la profundidad `c` y, sobre la inclinación del eje neutro,
//!   una búsqueda gruesa en [`N_THETA`] inclinaciones y después bisección.
//!
//! El algoritmo es el mismo que tenía la versión NumPy, paso por paso, para que
//! los resultados coincidan; `tests/test_columna_rust.py` lo compara con ella.

use rayon::prelude::*;
use std::f64::consts::PI;

/// Módulo de elasticidad del acero, MPa (§20.2.2.2).
pub const ES: f64 = 200_000.0;
/// Deformación última del hormigón a compresión (§22.2.2.1).
pub const EPS_CU: f64 = 0.003;
/// Inclinaciones del eje neutro en la búsqueda gruesa.
pub const N_THETA: usize = 48;
/// Bisecciones (en escala logarítmica) sobre la profundidad del eje neutro.
pub const IT_C: usize = 42;
/// Bisecciones sobre la inclinación del eje neutro.
pub const IT_THETA: usize = 22;

/// Hormigón y acero de la columna.
#[derive(Clone, Copy, Debug)]
pub struct MaterialColumna {
    /// `f'c`, MPa.
    pub fc: f64,
    /// `fy`, MPa.
    pub fy: f64,
    /// Armadura transversal en espiral (cambia `φ` en compresión controlada).
    pub zunchada: bool,
}

impl MaterialColumna {
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

    /// `φ` para flexocompresión sin pretensado según `εt` (§21.2.2).
    pub fn phi(&self, eps_t: f64) -> f64 {
        let phi_c = if self.zunchada { 0.75 } else { 0.65 };
        let t = ((eps_t - self.fy / ES) / 0.003).clamp(0.0, 1.0);
        phi_c + (0.90 - phi_c) * t
    }
}

/// Sección: contorno convexo antihorario `(y, z)` y barras `(y, z)` con su área,
/// en mm y mm², con el origen en el baricentro de la sección bruta. Las barras de
/// área nula se ignoran (sirven para completar arreglos de largo fijo).
#[derive(Clone, Debug)]
pub struct SeccionColumna {
    pub contorno: Vec<[f64; 2]>,
    pub barras: Vec<[f64; 2]>,
    pub areas: Vec<f64>,
}

/// Resultantes nominales de la sección para un eje neutro.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Resultante {
    /// N, compresión positiva.
    pub pn: f64,
    /// N·mm.
    pub mz: f64,
    /// N·mm.
    pub my: f64,
    /// Deformación de la barra más traccionada.
    pub eps_t: f64,
    pub phi: f64,
}

/// Resistencia de diseño en una dirección del plano `(Mz, My)`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Capacidad {
    /// `φMn` en la dirección pedida, N·mm (0 si no hay solución).
    pub phi_mn: f64,
    /// Inclinación del eje neutro, rad.
    pub theta: f64,
    /// Profundidad del eje neutro, mm.
    pub c: f64,
    /// Si se encontró la solución.
    pub ok: bool,
}

/// Razones demanda/capacidad de una solicitación (kN·m y adimensionales).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Razon {
    /// `φMn` con `Pu` fijo en la dirección de `Mu`, kN·m.
    pub phi_mn: f64,
    /// `|Mu|/φMn`; infinita si `Pu` queda fuera de la superficie de interacción.
    pub momento: f64,
    /// `Pu/φPn,max` en compresión o `|Pu|/φPnt` en tracción.
    pub axial: f64,
    /// La mayor de las dos.
    pub razon: f64,
}

/// Solicitación `(Pu, Mz, My)` en kN y kN·m, `Pu` positivo en compresión.
pub type Solicitacion = [f64; 3];

/// Área y momentos estáticos `∫y dA`, `∫z dA` de `{p ∈ polígono : u·p ≥ s}`.
///
/// Recorte exacto del polígono convexo con el semiplano: los lados dentro del
/// bloque más el tramo del corte, integrados con la fórmula de la lazada.
fn bloque(v: &[[f64; 2]], u: [f64; 2], s: f64) -> (f64, f64, f64) {
    let k = v.len();
    let (mut area, mut sy, mut sz) = (0.0, 0.0, 0.0);
    let mut pe = [0.0, 0.0]; // donde el contorno sale del bloque
    let mut pn = [0.0, 0.0]; // donde vuelve a entrar
    let mut acumular = |a: [f64; 2], b: [f64; 2]| {
        let cr = a[0] * b[1] - b[0] * a[1];
        area += 0.5 * cr;
        sy += (a[0] + b[0]) * cr / 6.0;
        sz += (a[1] + b[1]) * cr / 6.0;
    };
    for i in 0..k {
        let p0 = v[i];
        let p1 = v[(i + 1) % k];
        let d0 = u[0] * p0[0] + u[1] * p0[1] - s;
        let d1 = u[0] * p1[0] + u[1] * p1[1] - s;
        let (in0, in1) = (d0 >= 0.0, d1 >= 0.0);
        if !in0 && !in1 {
            continue;
        }
        let x = if in0 != in1 {
            let t = d0 / (d0 - d1);
            [p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])]
        } else {
            p0
        };
        let a = if in0 { p0 } else { x };
        let b = if in1 { p1 } else { x };
        if in0 && !in1 {
            pe = [pe[0] + x[0], pe[1] + x[1]];
        }
        if !in0 && in1 {
            pn = [pn[0] + x[0], pn[1] + x[1]];
        }
        acumular(a, b);
    }
    acumular(pe, pn);
    (area, sy, sz)
}

/// Proyecciones extremas del contorno sobre `u`: `(mínima, máxima)`.
fn extremos(v: &[[f64; 2]], u: [f64; 2]) -> (f64, f64) {
    v.iter()
        .map(|p| u[0] * p[0] + u[1] * p[1])
        .fold((f64::INFINITY, f64::NEG_INFINITY), |(lo, hi), x| {
            (lo.min(x), hi.max(x))
        })
}

/// Resultantes nominales para el eje neutro de inclinación `theta` y profundidad
/// `c` (mm). `u = (cos θ, sin θ)` apunta hacia la fibra más comprimida.
pub fn seccion_en(sec: &SeccionColumna, mat: &MaterialColumna, theta: f64, c: f64) -> Resultante {
    let u = [theta.cos(), theta.sin()];
    let (s_min, s_max) = extremos(&sec.contorno, u);
    let a = (mat.beta1() * c).min(s_max - s_min);
    let (area, sy, sz) = bloque(&sec.contorno, u, s_max - a);
    let fc85 = 0.85 * mat.fc;
    let (mut pn, mut mz, mut my) = (fc85 * area, fc85 * sy, fc85 * sz);
    let mut dt = f64::NEG_INFINITY;
    for (p, &ab) in sec.barras.iter().zip(&sec.areas) {
        if ab <= 0.0 {
            continue;
        }
        let prof = s_max - (u[0] * p[0] + u[1] * p[1]);
        let eps = EPS_CU * (c - prof) / c;
        let desplazado = if prof <= a { fc85 } else { 0.0 };
        let f = ((ES * eps).clamp(-mat.fy, mat.fy) - desplazado) * ab;
        pn += f;
        mz += f * p[0];
        my += f * p[1];
        dt = dt.max(prof);
    }
    let eps_t = EPS_CU * (dt - c) / c;
    Resultante {
        pn,
        mz,
        my: -my,
        eps_t,
        phi: mat.phi(eps_t),
    }
}

/// Profundidad `c` del eje neutro con `φPn = p_obj` (N), por bisección
/// logarítmica. Devuelve `c` y si hay solución en el intervalo de búsqueda.
pub fn profundidad_para(
    sec: &SeccionColumna,
    mat: &MaterialColumna,
    theta: f64,
    p_obj: f64,
) -> (f64, bool) {
    let u = [theta.cos(), theta.sin()];
    let (s_min, s_max) = extremos(&sec.contorno, u);
    let h = s_max - s_min;
    let mut lo = (1e-6 * h).ln();
    let mut hi = (1e4 * h).ln();
    let f = |logc: f64| {
        let r = seccion_en(sec, mat, theta, logc.exp());
        r.phi * r.pn - p_obj
    };
    let ok = f(lo) <= 0.0 && f(hi) >= 0.0;
    for _ in 0..IT_C {
        let mid = 0.5 * (lo + hi);
        if f(mid) < 0.0 {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    ((0.5 * (lo + hi)).exp(), ok)
}

/// Signo como `numpy.sign`: 0 para el cero.
fn signo(x: f64) -> f64 {
    if x > 0.0 {
        1.0
    } else if x < 0.0 {
        -1.0
    } else {
        0.0
    }
}

/// Resistencia de diseño con `φPn = p_obj` (N) en la dirección `alfa` (rad) del
/// plano `(Mz, My)`: `alfa = 0` es `+Mz` y `π/2` es `+My`.
///
/// Primero recorre [`N_THETA`] inclinaciones del eje neutro hasta encontrar dos
/// vecinas cuyo momento resistente queda a cada lado de `alfa`; después ajusta la
/// inclinación por bisección.
pub fn capacidad_en_direccion(
    sec: &SeccionColumna,
    mat: &MaterialColumna,
    p_obj: f64,
    alfa: f64,
) -> Capacidad {
    let (dz, dy) = (alfa.cos(), alfa.sin());
    let paso = 2.0 * PI / N_THETA as f64;
    let mut cruz = [0.0; N_THETA];
    let mut punto = [0.0; N_THETA];
    let mut ok = [false; N_THETA];
    for j in 0..N_THETA {
        let th = 2.0 * PI * j as f64 / N_THETA as f64;
        let (c, okj) = profundidad_para(sec, mat, th, p_obj);
        let r = seccion_en(sec, mat, th, c);
        let (mz, my) = (r.phi * r.mz, r.phi * r.my);
        cruz[j] = mz * dy - my * dz;
        punto[j] = mz * dz + my * dy;
        ok[j] = okj;
    }
    let candidata = (0..N_THETA).find(|&j| {
        let j1 = (j + 1) % N_THETA;
        ok[j] && ok[j1] && signo(cruz[j]) != signo(cruz[j1]) && punto[j] > 0.0
    });
    let j = candidata.unwrap_or(0);
    let mut t0 = j as f64 * paso;
    let mut t1 = t0 + paso;
    let mut f0 = cruz[j];
    for _ in 0..IT_THETA {
        let tm = 0.5 * (t0 + t1);
        let (cm, _) = profundidad_para(sec, mat, tm, p_obj);
        let r = seccion_en(sec, mat, tm, cm);
        let fm = r.phi * (r.mz * dy - r.my * dz);
        if signo(fm) == signo(f0) {
            t0 = tm;
            f0 = fm;
        } else {
            t1 = tm;
        }
    }
    let tf = 0.5 * (t0 + t1);
    let (cf, okf) = profundidad_para(sec, mat, tf, p_obj);
    let r = seccion_en(sec, mat, tf, cf);
    let valido = candidata.is_some() && okf;
    Capacidad {
        phi_mn: if valido {
            r.phi * (r.mz * dz + r.my * dy)
        } else {
            0.0
        },
        theta: tf,
        c: cf,
        ok: valido,
    }
}

/// [`capacidad_en_direccion`] para varios pares `(p_obj, alfa)`, en paralelo.
pub fn capacidades(
    sec: &SeccionColumna,
    mat: &MaterialColumna,
    pares: &[(f64, f64)],
) -> Vec<Capacidad> {
    pares
        .par_iter()
        .map(|&(p, a)| capacidad_en_direccion(sec, mat, p, a))
        .collect()
}

/// Razones demanda/capacidad de una solicitación en kN y kN·m. `phi_pn_max` y
/// `phi_pnt` son `φPn,max` (§22.4.2.1) y `φPnt` (§22.4.3.1) en kN.
pub fn razones(
    sec: &SeccionColumna,
    mat: &MaterialColumna,
    s: Solicitacion,
    phi_pn_max: f64,
    phi_pnt: f64,
) -> Razon {
    let [pu, mz, my] = s;
    let mu = mz.hypot(my);
    let cap = capacidad_en_direccion(sec, mat, pu * 1e3, my.atan2(mz));
    let phi_mn = if cap.ok { cap.phi_mn / 1e6 } else { 0.0 };
    // Sin momento manda la razón axial; con momento y una carga fuera de la
    // superficie de interacción, la razón es infinita.
    let momento = if mu <= 1e-9 {
        0.0
    } else if cap.ok && phi_mn > 0.0 {
        mu / phi_mn
    } else {
        f64::INFINITY
    };
    let axial = if pu >= 0.0 {
        pu / phi_pn_max
    } else {
        -pu / phi_pnt
    };
    Razon {
        phi_mn,
        momento,
        axial,
        razon: momento.max(axial),
    }
}

/// [`razones`] de varias solicitaciones, en paralelo.
pub fn verificar(
    sec: &SeccionColumna,
    mat: &MaterialColumna,
    solicitaciones: &[Solicitacion],
    phi_pn_max: f64,
    phi_pnt: f64,
) -> Vec<Razon> {
    solicitaciones
        .par_iter()
        .map(|&s| razones(sec, mat, s, phi_pn_max, phi_pnt))
        .collect()
}

/// Una armadura candidata para [`elegir_armadura`]: la sección y sus
/// resistencias axiales de diseño `φPn,max` y `φPnt` en kN.
#[derive(Clone, Debug)]
pub struct Candidata {
    pub seccion: SeccionColumna,
    pub phi_pn_max: f64,
    pub phi_pnt: f64,
}

/// Índice de la primera candidata (vienen ordenadas por área de acero) que
/// resiste todas las solicitaciones, o `None` si ninguna alcanza.
///
/// Se descartan candidatas contra un grupo chico de solicitaciones que crece con
/// la que hace fallar a la mejor sobreviviente; esa se verifica con todas.
pub fn elegir_armadura(
    candidatas: &[Candidata],
    mat: &MaterialColumna,
    solicitaciones: &[Solicitacion],
) -> Option<usize> {
    if solicitaciones.is_empty() {
        return None;
    }
    // Primer índice del máximo, como numpy.argmax.
    let argmax = |valores: &mut dyn Iterator<Item = f64>| -> usize {
        let mut mejor = (0, f64::NEG_INFINITY);
        for (i, x) in valores.enumerate() {
            if x > mejor.1 {
                mejor = (i, x);
            }
        }
        mejor.0
    };
    let mut grupo = vec![
        argmax(&mut solicitaciones.iter().map(|s| s[1].hypot(s[2]))),
        argmax(&mut solicitaciones.iter().map(|s| s[0])),
    ];
    grupo.sort_unstable();
    grupo.dedup();
    let mut vivas: Vec<usize> = (0..candidatas.len()).collect();
    while !vivas.is_empty() {
        let pares: Vec<(usize, usize)> = vivas
            .iter()
            .flat_map(|&c| grupo.iter().map(move |&g| (c, g)))
            .collect();
        let cumple: Vec<bool> = pares
            .par_iter()
            .map(|&(c, g)| {
                let k = &candidatas[c];
                razones(&k.seccion, mat, solicitaciones[g], k.phi_pn_max, k.phi_pnt).razon <= 1.0
            })
            .collect();
        let n = grupo.len();
        vivas = vivas
            .iter()
            .enumerate()
            .filter(|(i, _)| cumple[i * n..(i + 1) * n].iter().all(|&x| x))
            .map(|(_, &c)| c)
            .collect();
        let Some(&mejor) = vivas.first() else {
            break;
        };
        let k = &candidatas[mejor];
        let r = verificar(&k.seccion, mat, solicitaciones, k.phi_pn_max, k.phi_pnt);
        if r.iter().all(|x| x.razon <= 1.0) {
            return Some(mejor);
        }
        let peor = argmax(&mut r.iter().map(|x| x.razon));
        if let Err(pos) = grupo.binary_search(&peor) {
            grupo.insert(pos, peor);
        }
        vivas.remove(0);
    }
    None
}

#[cfg(test)]
mod pruebas {
    use super::*;

    fn rectangulo(b: f64, h: f64) -> Vec<[f64; 2]> {
        vec![
            [-h / 2.0, -b / 2.0],
            [h / 2.0, -b / 2.0],
            [h / 2.0, b / 2.0],
            [-h / 2.0, b / 2.0],
        ]
    }

    #[test]
    fn bloque_de_un_rectangulo() {
        // Rectángulo 400 (y) × 300 (z), corte paralelo a z a 100 mm del borde +y.
        let v = rectangulo(300.0, 400.0);
        let (a, sy, sz) = bloque(&v, [1.0, 0.0], 100.0);
        assert!((a - 100.0 * 300.0).abs() < 1e-6);
        assert!((sy - 100.0 * 300.0 * 150.0).abs() < 1e-3);
        assert!(sz.abs() < 1e-6);
        // Todo el polígono y nada.
        assert!((bloque(&v, [1.0, 0.0], -1e9).0 - 120_000.0).abs() < 1e-6);
        assert_eq!(bloque(&v, [1.0, 0.0], 1e9).0, 0.0);
    }

    #[test]
    fn flexion_simple_contra_bloque_rectangular() {
        // Sin barras comprimidas que pesen: una sola capa traccionada. Con Pn = 0
        // el bloque equilibra As·fy y Mn = As·fy·(d − a/2) (§22.2).
        let (b, h, d, as_) = (300.0, 500.0, 440.0, 1000.0);
        let sec = SeccionColumna {
            contorno: rectangulo(b, h),
            barras: vec![[h / 2.0 - d, 0.0]],
            areas: vec![as_],
        };
        let mat = MaterialColumna {
            fc: 25.0,
            fy: 420.0,
            zunchada: false,
        };
        let cap = capacidad_en_direccion(&sec, &mat, 0.0, 0.0);
        assert!(cap.ok);
        let a = as_ * 420.0 / (0.85 * 25.0 * b);
        let mn = as_ * 420.0 * (d - a / 2.0);
        let r = seccion_en(&sec, &mat, cap.theta, cap.c);
        assert!((r.mz - mn).abs() < 1e-6 * mn, "{} vs {}", r.mz, mn);
        assert!((cap.phi_mn - r.phi * mn).abs() < 1e-6 * mn);
    }

    #[test]
    fn razones_axiales_y_sin_momento() {
        let sec = SeccionColumna {
            contorno: rectangulo(400.0, 400.0),
            barras: vec![
                [-150.0, -150.0],
                [150.0, -150.0],
                [150.0, 150.0],
                [-150.0, 150.0],
            ],
            areas: vec![314.159; 4],
        };
        let mat = MaterialColumna {
            fc: 25.0,
            fy: 420.0,
            zunchada: false,
        };
        let r = razones(&sec, &mat, [1000.0, 0.0, 0.0], 2000.0, 400.0);
        assert_eq!(r.momento, 0.0);
        assert!((r.razon - 0.5).abs() < 1e-12);
        let r = razones(&sec, &mat, [-200.0, 0.0, 0.0], 2000.0, 400.0);
        assert!((r.axial - 0.5).abs() < 1e-12);
        // Simetría: la capacidad con Mz y con My es la misma en una sección cuadrada.
        let a = razones(&sec, &mat, [500.0, 50.0, 0.0], 2000.0, 400.0);
        let b = razones(&sec, &mat, [500.0, 0.0, 50.0], 2000.0, 400.0);
        assert!((a.phi_mn - b.phi_mn).abs() < 1e-6 * a.phi_mn);
    }
}
