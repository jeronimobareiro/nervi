// SPDX-License-Identifier: GPL-3.0-or-later
//! Barra de pórtico espacial: ejes locales, rigidez 12×12, transformación,
//! cargas nodales equivalentes y liberaciones por condensación estática.
//!
//! La flexión en cada plano principal es la misma que la de la barra plana y se
//! resuelve con las funciones de [`crate::elemento`]: el plano `x`–`y` (giro
//! `θz`) es idéntico al pórtico plano; el plano `x`–`z` se lleva a él con
//! `v → w` y `θ → -θy`, porque `θy = -dw/dx` (regla de la mano derecha).
//!
//! Fuentes: W. McGuire, R. H. Gallagher y R. D. Ziemian, *Matrix Structural
//! Analysis*, 2.ª ed., Wiley 2000, cap. 4 (rigidez del elemento de pórtico
//! espacial con flexión biaxial, axil y torsión de Saint-Venant) y cap. 5
//! (transformación con el vector de referencia y liberaciones); J. S.
//! Przemieniecki, *Theory of Matrix Structural Analysis*, McGraw-Hill 1968,
//! cap. 5 (elemento viga espacial) y cap. 6 (transformación de coordenadas).
//! Fórmulas implementadas a partir de esas fuentes, sin código de terceros.

use crate::elemento::{cargas_equivalentes, invertir, rigidez_local, CargaLocal, Vec6};
use crate::error::{ErrorNervi, Resultado};
use crate::espacial::modelo::{Barra3d, CargaBarra3d, TipoCargaBarra3d, TOLERANCIA_PARALELO};
use crate::modelo::Ejes;

pub type Mat12 = [[f64; 12]; 12];
pub type Vec12 = [f64; 12];
/// Matriz de rotación: sus filas son los versores locales `x, y, z` en globales.
pub type Rot = [[f64; 3]; 3];

fn cruz(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn norma(a: [f64; 3]) -> f64 {
    (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]).sqrt()
}

fn escalar(a: [f64; 3], k: f64) -> [f64; 3] {
    [a[0] * k, a[1] * k, a[2] * k]
}

/// Ejes locales de la barra de `pi` a `pj`.
///
/// - `x = (pj - pi) / L`.
/// - Con vector de referencia `v`: `z = x × v / |x × v|` e `y = z × x`, es decir,
///   `y` es la componente de `v` perpendicular a la barra (el plano `x`–`y`
///   contiene a `v`). Error si `v` es paralelo a la barra.
/// - Sin vector: `v = +Z` (en vigas horizontales `y` apunta hacia arriba). Si la
///   barra es vertical (proyección horizontal menor que `1e-6·L`), `z = -Y` e
///   `y = z × x`: una columna que sube tiene `y = -X`, igual que el eje `y` local
///   de una columna del pórtico plano dibujado en el plano XZ visto desde `-Y`.
pub fn ejes_locales(pi: [f64; 3], pj: [f64; 3], referencia: Option<[f64; 3]>) -> Resultado<Rot> {
    let d = [pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2]];
    let l = norma(d);
    if l.is_nan() || l <= 0.0 {
        return Err(ErrorNervi::ModeloInvalido("barra de longitud nula".into()));
    }
    let x = escalar(d, 1.0 / l);
    let z = match referencia {
        Some(v) => {
            let z = cruz(x, v);
            let nz = norma(z);
            if nz.is_nan() || nz <= TOLERANCIA_PARALELO * norma(v) {
                return Err(ErrorNervi::ModeloInvalido(
                    "el vector de referencia es nulo o paralelo a la barra".into(),
                ));
            }
            escalar(z, 1.0 / nz)
        }
        None => {
            if x[0].hypot(x[1]) <= TOLERANCIA_PARALELO {
                [0.0, -1.0, 0.0]
            } else {
                let z = cruz(x, [0.0, 0.0, 1.0]);
                escalar(z, 1.0 / norma(z))
            }
        }
    };
    let y = cruz(z, x);
    Ok([x, y, z])
}

/// Matriz de rigidez local 12×12 sin liberaciones, GDL por extremo
/// `[u, v, w, θx, θy, θz]`.
///
/// Bloques desacoplados (McGuire, Gallagher y Ziemian, op. cit., cap. 4):
/// axil `EA/L`; torsión de Saint-Venant `GJ/L`; flexión en `x`–`y` con `EIz`
/// (la matriz 4×4 de la barra plana); flexión en `x`–`z` con `EIy`, que es la
/// misma matriz con los términos que acoplan `w` con `θy` cambiados de signo.
pub fn rigidez_local_3d(e: f64, g: f64, a: f64, iy: f64, iz: f64, j: f64, l: f64) -> Mat12 {
    let mut k = [[0.0; 12]; 12];
    let ea = e * a / l;
    let gj = g * j / l;
    for (p, q, s) in [(0, 0, 1.0), (0, 6, -1.0), (6, 0, -1.0), (6, 6, 1.0)] {
        k[p][q] = s * ea;
        k[p + 3][q + 3] = s * gj;
    }
    // Plano x–y: GDL (v, θz) = (1, 5) y (7, 11); la barra plana con I = Iz.
    let kxy = rigidez_local(e, a, iz, l);
    // Plano x–z: GDL (w, θy) = (2, 4) y (8, 10), con θ2D = -θy.
    let kxz = rigidez_local(e, a, iy, l);
    let flexion_2d = [1, 2, 4, 5];
    let gdl_xy = [1, 5, 7, 11];
    let gdl_xz = [2, 4, 8, 10];
    let signo_xz = [1.0, -1.0, 1.0, -1.0];
    for p in 0..4 {
        for q in 0..4 {
            let (pp, qq) = (flexion_2d[p], flexion_2d[q]);
            k[gdl_xy[p]][gdl_xy[q]] = kxy[pp][qq];
            k[gdl_xz[p]][gdl_xz[q]] = signo_xz[p] * signo_xz[q] * kxz[pp][qq];
        }
    }
    k
}

/// `{v_local} = [T]{v_global}` con `[T] = diag(λ, λ, λ, λ)`.
pub fn a_local_3d(r: &Rot, g: &Vec12) -> Vec12 {
    let mut out = [0.0; 12];
    for b in 0..4 {
        for i in 0..3 {
            out[3 * b + i] = (0..3).map(|j| r[i][j] * g[3 * b + j]).sum();
        }
    }
    out
}

/// `{v_global} = [T]^T{v_local}`.
pub fn a_global_3d(r: &Rot, v: &Vec12) -> Vec12 {
    let mut out = [0.0; 12];
    for b in 0..4 {
        for i in 0..3 {
            out[3 * b + i] = (0..3).map(|j| r[j][i] * v[3 * b + j]).sum();
        }
    }
    out
}

/// `[k_global] = [T]^T [k_local] [T]`.
pub fn rigidez_a_global_3d(r: &Rot, k: &Mat12) -> Mat12 {
    // Columna a columna: K_g e_c = T^T K (T e_c).
    let mut out = [[0.0; 12]; 12];
    for c in 0..12 {
        let mut e = [0.0; 12];
        e[c] = 1.0;
        let te = a_local_3d(r, &e);
        let mut kte = [0.0; 12];
        for p in 0..12 {
            kte[p] = (0..12).map(|q| k[p][q] * te[q]).sum();
        }
        let col = a_global_3d(r, &kte);
        for p in 0..12 {
            out[p][c] = col[p];
        }
    }
    // Simetrizar para eliminar el ruido de redondeo.
    for p in 0..12 {
        for q in (p + 1)..12 {
            let m = 0.5 * (out[p][q] + out[q][p]);
            out[p][q] = m;
            out[q][p] = m;
        }
    }
    out
}

/// Carga en el tramo de la barra espacial en ejes locales, separada en sus dos
/// planos de flexión, cada uno como carga de barra plana: `xy` lleva `(qx, qy)`
/// y `xz` lleva `(0, qz)` (el axil se cuenta una sola vez, en `xy`).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CargaLocal3d {
    pub xy: CargaLocal,
    pub xz: CargaLocal,
}

/// Convierte una carga de barra a ejes locales.
pub fn carga_a_local_3d(r: &Rot, carga: &CargaBarra3d) -> CargaLocal3d {
    let rot = |q: [f64; 3]| -> [f64; 3] {
        match carga.ejes {
            Ejes::Local => q,
            Ejes::Global => std::array::from_fn(|i| (0..3).map(|j| r[i][j] * q[j]).sum()),
        }
    };
    match carga.tipo {
        TipoCargaBarra3d::Uniforme { q } => {
            let q = rot(q);
            CargaLocal3d {
                xy: CargaLocal::Uniforme { qx: q[0], qy: q[1] },
                xz: CargaLocal::Uniforme { qx: 0.0, qy: q[2] },
            }
        }
        TipoCargaBarra3d::Puntual { a, p } => {
            let p = rot(p);
            CargaLocal3d {
                xy: CargaLocal::Puntual {
                    a,
                    px: p[0],
                    py: p[1],
                },
                xz: CargaLocal::Puntual {
                    a,
                    px: 0.0,
                    py: p[2],
                },
            }
        }
        TipoCargaBarra3d::Trapezoidal { a, b, q1, q2 } => {
            let (q1, q2) = (rot(q1), rot(q2));
            CargaLocal3d {
                xy: CargaLocal::Trapezoidal {
                    a,
                    b,
                    qx1: q1[0],
                    qy1: q1[1],
                    qx2: q2[0],
                    qy2: q2[1],
                },
                xz: CargaLocal::Trapezoidal {
                    a,
                    b,
                    qx1: 0.0,
                    qy1: q1[2],
                    qx2: 0.0,
                    qy2: q2[2],
                },
            }
        }
    }
}

/// Vector de 6 de la barra plana equivalente al plano `x`–`y`: `[u, v, θz]` por
/// extremo.
pub fn plano_xy(v: &Vec12) -> Vec6 {
    [v[0], v[1], v[5], v[6], v[7], v[11]]
}

/// Vector de 6 de la barra plana equivalente al plano `x`–`z`: `[0, w, -θy]`
/// por extremo (el axil está en [`plano_xy`]).
pub fn plano_xz(v: &Vec12) -> Vec6 {
    [0.0, v[2], -v[4], 0.0, v[8], -v[10]]
}

/// Cargas nodales equivalentes (empotramiento perfecto cambiado de signo) en
/// ejes locales, combinando los dos planos de flexión.
pub fn cargas_equivalentes_3d(l: f64, ea: f64, eiy: f64, eiz: f64, c: &CargaLocal3d) -> Vec12 {
    let fxy = cargas_equivalentes(l, ea, eiz, &c.xy);
    let fxz = cargas_equivalentes(l, ea, eiy, &c.xz);
    [
        fxy[0], fxy[1], fxz[1], 0.0, -fxz[2], fxy[2], fxy[3], fxy[4], fxz[4], 0.0, -fxz[5], fxy[5],
    ]
}

/// Barra espacial preparada para el análisis: rigidez condensada por las
/// liberaciones y datos para recuperar los desplazamientos de los GDL liberados.
#[derive(Clone, Debug)]
pub struct BarraAnalisis3d {
    pub l: f64,
    /// Ejes locales (filas `x, y, z` en globales).
    pub ejes: Rot,
    pub ea: f64,
    pub eiy: f64,
    pub eiz: f64,
    pub gj: f64,
    /// Rigidez local completa (sin condensar).
    pub k: Mat12,
    /// Rigidez local condensada (filas y columnas liberadas en cero).
    pub k_cond: Mat12,
    /// Rigidez condensada en ejes globales.
    pub k_global: Mat12,
    pub liberados: Vec<usize>,
    pub retenidos: Vec<usize>,
    krr_inv: Vec<Vec<f64>>,
}

impl BarraAnalisis3d {
    /// Condensación estática de los GDL liberados (McGuire, Gallagher y
    /// Ziemian, op. cit., cap. 5; la misma que la barra plana con 12 GDL):
    /// `k_c = k_cc - k_cr k_rr⁻¹ k_rc`.
    pub fn new(barra: &Barra3d, l: f64, ejes: Rot) -> Resultado<Self> {
        let k = rigidez_local_3d(barra.e, barra.g, barra.a, barra.iy, barra.iz, barra.j, l);
        let liberados: Vec<usize> = (0..12).filter(|&d| barra.liberaciones[d]).collect();
        let retenidos: Vec<usize> = (0..12).filter(|&d| !barra.liberaciones[d]).collect();
        let krr: Vec<Vec<f64>> = liberados
            .iter()
            .map(|&r| liberados.iter().map(|&q| k[r][q]).collect())
            .collect();
        let krr_inv = invertir(krr).ok_or_else(|| {
            ErrorNervi::ModeloInvalido("combinación de liberaciones inestable en una barra".into())
        })?;
        let mut k_cond = [[0.0; 12]; 12];
        for &p in &retenidos {
            for &q in &retenidos {
                let mut v = k[p][q];
                for (a, &ra) in liberados.iter().enumerate() {
                    for (b, &rb) in liberados.iter().enumerate() {
                        v -= k[p][ra] * krr_inv[a][b] * k[rb][q];
                    }
                }
                k_cond[p][q] = v;
            }
        }
        for p in 0..12 {
            for q in (p + 1)..12 {
                let m = 0.5 * (k_cond[p][q] + k_cond[q][p]);
                k_cond[p][q] = m;
                k_cond[q][p] = m;
            }
        }
        let k_global = rigidez_a_global_3d(&ejes, &k_cond);
        Ok(BarraAnalisis3d {
            l,
            ejes,
            ea: barra.e * barra.a,
            eiy: barra.e * barra.iy,
            eiz: barra.e * barra.iz,
            gj: barra.g * barra.j,
            k,
            k_cond,
            k_global,
            liberados,
            retenidos,
            krr_inv,
        })
    }

    /// Cargas equivalentes condensadas (ejes locales): `F_c - k_cr k_rr⁻¹ F_r`.
    pub fn condensar_cargas(&self, feq: &Vec12) -> Vec12 {
        let mut out = [0.0; 12];
        for &p in &self.retenidos {
            let mut v = feq[p];
            for (a, &ra) in self.liberados.iter().enumerate() {
                for (b, &rb) in self.liberados.iter().enumerate() {
                    v -= self.k[p][ra] * self.krr_inv[a][b] * feq[rb];
                }
            }
            out[p] = v;
        }
        out
    }

    /// Completa los desplazamientos locales de extremo: en los GDL liberados,
    /// `u_r = k_rr⁻¹ (F_r - k_rc u_c)`.
    pub fn completar_desplazamientos(&self, u_nudo_local: &Vec12, feq: &Vec12) -> Vec12 {
        let mut u = *u_nudo_local;
        if self.liberados.is_empty() {
            return u;
        }
        let rhs: Vec<f64> = self
            .liberados
            .iter()
            .map(|&r| {
                feq[r]
                    - self
                        .retenidos
                        .iter()
                        .map(|&c| self.k[r][c] * u_nudo_local[c])
                        .sum::<f64>()
            })
            .collect();
        for (a, &ra) in self.liberados.iter().enumerate() {
            u[ra] = (0..self.liberados.len())
                .map(|b| self.krr_inv[a][b] * rhs[b])
                .sum();
        }
        u
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn matvec(a: &Mat12, v: &Vec12) -> Vec12 {
        std::array::from_fn(|i| (0..12).map(|j| a[i][j] * v[j]).sum())
    }

    const PROPS: (f64, f64, f64, f64, f64, f64) = (2.1e8, 8.1e7, 0.012, 3.0e-5, 8.0e-5, 2.0e-6);

    fn k_ejemplo(l: f64) -> Mat12 {
        let (e, g, a, iy, iz, j) = PROPS;
        rigidez_local_3d(e, g, a, iy, iz, j, l)
    }

    #[test]
    fn rigidez_simetrica() {
        let k = k_ejemplo(3.7);
        for i in 0..12 {
            for j in 0..12 {
                assert_eq!(k[i][j], k[j][i], "k[{i}][{j}]");
            }
        }
    }

    #[test]
    fn ejes_ortonormales_y_regla_por_defecto() {
        let casos = [
            (
                [0.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
            ),
            (
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 3.0],
                [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]],
            ),
            (
                [0.0, 0.0, 3.0],
                [0.0, 0.0, 0.0],
                [[0.0, 0.0, -1.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]],
            ),
            (
                [0.0, 0.0, 0.0],
                [0.0, 5.0, 0.0],
                [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]],
            ),
        ];
        for (pi, pj, esperado) in casos {
            let r = ejes_locales(pi, pj, None).unwrap();
            for i in 0..3 {
                for j in 0..3 {
                    assert!(
                        (r[i][j] - esperado[i][j]).abs() < 1e-15,
                        "{pi:?}->{pj:?}: {r:?}"
                    );
                }
            }
        }
        // Barra oblicua con vector de referencia: base ortonormal derecha e y del
        // lado del vector.
        let v = [0.3, -1.0, 0.2];
        let r = ejes_locales([1.0, 2.0, 0.5], [3.0, -1.0, 4.0], Some(v)).unwrap();
        for i in 0..3 {
            for j in 0..3 {
                let p: f64 = (0..3).map(|k| r[i][k] * r[j][k]).sum();
                assert!((p - if i == j { 1.0 } else { 0.0 }).abs() < 1e-14);
            }
        }
        let z = cruz(r[0], r[1]);
        for k in 0..3 {
            assert!((z[k] - r[2][k]).abs() < 1e-14);
        }
        assert!((0..3).map(|k| r[1][k] * v[k]).sum::<f64>() > 0.0);
        assert!((0..3).map(|k| r[2][k] * v[k]).sum::<f64>().abs() < 1e-14);
        assert!(ejes_locales([0.0; 3], [1.0, 1.0, 1.0], Some([2.0, 2.0, 2.0])).is_err());
    }

    #[test]
    fn movimientos_de_solido_rigido_no_generan_fuerzas() {
        let (pi, pj) = ([0.5, -1.0, 2.0], [3.5, 1.0, 4.5]);
        let l = norma([pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2]]);
        let r = ejes_locales(pi, pj, Some([0.0, 1.0, 0.3])).unwrap();
        let kg = rigidez_a_global_3d(&r, &k_ejemplo(l));
        let escala = PROPS.0 * PROPS.2 / l;
        // Seis movimientos rígidos: tres traslaciones y tres giros alrededor de pi.
        for modo in 0..6 {
            let mut u = [0.0; 12];
            if modo < 3 {
                u[modo] = 1.0;
                u[6 + modo] = 1.0;
            } else {
                let mut w = [0.0; 3];
                w[modo - 3] = 1e-3;
                let d = [pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2]];
                let t = cruz(w, d);
                u[3..6].copy_from_slice(&w);
                u[6..9].copy_from_slice(&t);
                u[9..12].copy_from_slice(&w);
            }
            for f in matvec(&kg, &u) {
                assert!(f.abs() < 1e-9 * escala, "modo {modo}: fuerza residual {f}");
            }
        }
    }

    #[test]
    fn rango_seis() {
        // Seis modos rígidos (prueba anterior) y el bloque del extremo j de la
        // barra en voladizo definido positivo: el rango es exactamente 6.
        let k = k_ejemplo(2.5);
        let mut m: Vec<Vec<f64>> = (6..12)
            .map(|i| (6..12).map(|j| k[i][j]).collect())
            .collect();
        // Cholesky denso 6×6.
        for c in 0..6 {
            let mut d = m[c][c];
            for p in 0..c {
                d -= m[c][p] * m[c][p];
            }
            assert!(d > 0.0, "pivote {c} no positivo");
            m[c][c] = d.sqrt();
            for f in (c + 1)..6 {
                let mut s = m[f][c];
                for p in 0..c {
                    s -= m[f][p] * m[c][p];
                }
                m[f][c] = s / m[c][c];
            }
        }
    }

    #[test]
    fn transformacion_ida_y_vuelta() {
        let r = ejes_locales([0.0; 3], [1.0, 2.0, 3.0], None).unwrap();
        let g: Vec12 = std::array::from_fn(|i| (i as f64 - 5.0) * 0.7);
        let back = a_global_3d(&r, &a_local_3d(&r, &g));
        for i in 0..12 {
            assert!((back[i] - g[i]).abs() < 1e-14);
        }
    }

    #[test]
    fn biela_espacial_solo_tiene_rigidez_axial() {
        let (e, g, a, iy, iz, j) = PROPS;
        let b = Barra3d::new(0, 1, e, g, a, iy, iz, j).biela();
        let r = ejes_locales([0.0; 3], [2.0, 0.0, 0.0], None).unwrap();
        let ba = BarraAnalisis3d::new(&b, 2.0, r).unwrap();
        let ea_l = e * a / 2.0;
        for p in 0..12 {
            for q in 0..12 {
                let esperado = match (p, q) {
                    (0, 0) | (6, 6) => ea_l,
                    (0, 6) | (6, 0) => -ea_l,
                    _ => 0.0,
                };
                assert!(
                    (ba.k_cond[p][q] - esperado).abs() < 1e-9 * ea_l,
                    "k[{p}][{q}] = {}",
                    ba.k_cond[p][q]
                );
            }
        }
    }
}
