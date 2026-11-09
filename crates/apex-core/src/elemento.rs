//! Barra de pórtico plano Euler-Bernoulli: rigidez, transformación, cargas
//! nodales equivalentes, liberaciones y soluciones de empotramiento perfecto.

use crate::error::{ErrorApex, Resultado};
use crate::modelo::{Barra, CargaBarra, Ejes, TipoCargaBarra};

pub type Mat6 = [[f64; 6]; 6];
pub type Vec6 = [f64; 6];

/// Carga en el tramo expresada en ejes locales de la barra.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum CargaLocal {
    Uniforme { qx: f64, qy: f64 },
    Puntual { a: f64, px: f64, py: f64 },
}

/// Matriz de rigidez local 6×6 de la barra (sin liberaciones).
pub fn rigidez_local(e: f64, a: f64, i: f64, l: f64) -> Mat6 {
    let ea = e * a / l;
    let k1 = 12.0 * e * i / l.powi(3);
    let k2 = 6.0 * e * i / l.powi(2);
    let k3 = 4.0 * e * i / l;
    let k4 = 2.0 * e * i / l;
    [
        [ea, 0.0, 0.0, -ea, 0.0, 0.0],
        [0.0, k1, k2, 0.0, -k1, k2],
        [0.0, k2, k3, 0.0, -k2, k4],
        [-ea, 0.0, 0.0, ea, 0.0, 0.0],
        [0.0, -k1, -k2, 0.0, k1, -k2],
        [0.0, k2, k4, 0.0, -k2, k3],
    ]
}

/// `{v_local} = [T]{v_global}` con `[T] = diag(λ, λ)`.
pub fn a_local(c: f64, s: f64, g: &Vec6) -> Vec6 {
    [
        c * g[0] + s * g[1],
        -s * g[0] + c * g[1],
        g[2],
        c * g[3] + s * g[4],
        -s * g[3] + c * g[4],
        g[5],
    ]
}

/// `{v_global} = [T]^T{v_local}`.
pub fn a_global(c: f64, s: f64, v: &Vec6) -> Vec6 {
    [
        c * v[0] - s * v[1],
        s * v[0] + c * v[1],
        v[2],
        c * v[3] - s * v[4],
        s * v[3] + c * v[4],
        v[5],
    ]
}

/// `[k_global] = [T]^T [k_local] [T]`.
pub fn rigidez_a_global(c: f64, s: f64, k: &Mat6) -> Mat6 {
    // Primero K·T (por filas), luego T^T·(K·T) (por columnas).
    let mut kt = [[0.0; 6]; 6];
    for (fila_kt, fila_k) in kt.iter_mut().zip(k.iter()) {
        // fila de K por T: T actúa sobre los bloques de columnas.
        *fila_kt = a_local_fila(c, s, fila_k);
    }
    let mut out = [[0.0; 6]; 6];
    for col in 0..6 {
        let columna = [
            kt[0][col], kt[1][col], kt[2][col], kt[3][col], kt[4][col], kt[5][col],
        ];
        let g = a_global(c, s, &columna);
        for fila in 0..6 {
            out[fila][col] = g[fila];
        }
    }
    out
}

/// Fila de `K` multiplicada por `T` a la derecha: `(K T)_{r,·} = K_{r,·} T`.
fn a_local_fila(c: f64, s: f64, fila: &Vec6) -> Vec6 {
    // (row · T)_j = Σ_i row_i T_ij. Para el bloque λ: T = [[c, s, 0], [-s, c, 0], [0, 0, 1]].
    [
        fila[0] * c - fila[1] * s,
        fila[0] * s + fila[1] * c,
        fila[2],
        fila[3] * c - fila[4] * s,
        fila[3] * s + fila[4] * c,
        fila[5],
    ]
}

/// Convierte una carga de barra a ejes locales.
pub fn carga_a_local(c: f64, s: f64, carga: &CargaBarra) -> CargaLocal {
    let rot = |x: f64, y: f64| match carga.ejes {
        Ejes::Local => (x, y),
        Ejes::Global => (c * x + s * y, -s * x + c * y),
    };
    match carga.tipo {
        TipoCargaBarra::Uniforme { qx, qy } => {
            let (qx, qy) = rot(qx, qy);
            CargaLocal::Uniforme { qx, qy }
        }
        TipoCargaBarra::Puntual { a, px, py } => {
            let (px, py) = rot(px, py);
            CargaLocal::Puntual { a, px, py }
        }
    }
}

/// Cargas nodales equivalentes (reacciones de empotramiento perfecto cambiadas de
/// signo) en ejes locales, para una barra biempotrada.
pub fn cargas_equivalentes(l: f64, carga: &CargaLocal) -> Vec6 {
    match *carga {
        CargaLocal::Uniforme { qx, qy } => [
            qx * l / 2.0,
            qy * l / 2.0,
            qy * l * l / 12.0,
            qx * l / 2.0,
            qy * l / 2.0,
            -qy * l * l / 12.0,
        ],
        CargaLocal::Puntual { a, px, py } => {
            let b = l - a;
            let l2 = l * l;
            let l3 = l2 * l;
            [
                px * b / l,
                py * b * b * (3.0 * a + b) / l3,
                py * a * b * b / l2,
                px * a / l,
                py * a * a * (a + 3.0 * b) / l3,
                -py * a * a * b / l2,
            ]
        }
    }
}

/// Desplazamientos `(u, v)` en ejes locales de una barra biempotrada (extremos con
/// desplazamientos y giros nulos) bajo la carga, a la distancia `x` del nudo `i`.
pub fn flecha_biempotrada(l: f64, ea: f64, ei: f64, carga: &CargaLocal, x: f64) -> (f64, f64) {
    match *carga {
        CargaLocal::Uniforme { qx, qy } => {
            let u = qx * x * (l - x) / (2.0 * ea);
            let v = qy * x * x * (l - x) * (l - x) / (24.0 * ei);
            (u, v)
        }
        CargaLocal::Puntual { a, px, py } => {
            let b = l - a;
            let u = if x <= a {
                px * b * x / (ea * l)
            } else {
                px * a * (l - x) / (ea * l)
            };
            // Fórmula para x <= a; para x > a se usa la simetría (x' = L - x, a ↔ b).
            let tramo = |p: f64, a: f64, b: f64, x: f64| {
                p * b * b * x * x * (3.0 * a * l - x * (3.0 * a + b)) / (6.0 * ei * l.powi(3))
            };
            let v = if x <= a {
                tramo(py, a, b, x)
            } else {
                tramo(py, b, a, l - x)
            };
            (u, v)
        }
    }
}

/// Barra preparada para el análisis: rigidez condensada por las liberaciones y
/// datos para recuperar los desplazamientos internos de los GDL liberados.
#[derive(Clone, Debug)]
pub struct BarraAnalisis {
    pub l: f64,
    pub c: f64,
    pub s: f64,
    pub ea: f64,
    pub ei: f64,
    /// Rigidez local completa (sin condensar).
    pub k: Mat6,
    /// Rigidez local condensada (filas y columnas liberadas en cero).
    pub k_cond: Mat6,
    /// Rigidez condensada en ejes globales.
    pub k_global: Mat6,
    pub liberados: Vec<usize>,
    pub retenidos: Vec<usize>,
    /// Inversa de `k_rr`, tamaño `liberados.len()`.
    krr_inv: Vec<Vec<f64>>,
}

impl BarraAnalisis {
    pub fn new(barra: &Barra, l: f64, c: f64, s: f64) -> Resultado<Self> {
        let k = rigidez_local(barra.e, barra.a, barra.i, l);
        let liberados: Vec<usize> = (0..6).filter(|&d| barra.liberaciones[d]).collect();
        let retenidos: Vec<usize> = (0..6).filter(|&d| !barra.liberaciones[d]).collect();
        let krr: Vec<Vec<f64>> = liberados
            .iter()
            .map(|&r| liberados.iter().map(|&q| k[r][q]).collect())
            .collect();
        let krr_inv = invertir(krr).ok_or_else(|| {
            ErrorApex::ModeloInvalido("combinación de liberaciones inestable en una barra".into())
        })?;
        let mut k_cond = [[0.0; 6]; 6];
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
        // Simetrizar para eliminar el ruido de redondeo.
        for p in 0..6 {
            for q in (p + 1)..6 {
                let m = 0.5 * (k_cond[p][q] + k_cond[q][p]);
                k_cond[p][q] = m;
                k_cond[q][p] = m;
            }
        }
        let k_global = rigidez_a_global(c, s, &k_cond);
        Ok(BarraAnalisis {
            l,
            c,
            s,
            ea: barra.e * barra.a,
            ei: barra.e * barra.i,
            k,
            k_cond,
            k_global,
            liberados,
            retenidos,
            krr_inv,
        })
    }

    /// Cargas equivalentes condensadas (en ejes locales): `F_c - k_cr k_rr⁻¹ F_r`.
    pub fn condensar_cargas(&self, feq: &Vec6) -> Vec6 {
        let mut out = [0.0; 6];
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

    /// Completa los desplazamientos locales de extremo de la barra: en los GDL
    /// liberados reemplaza el valor del nudo por el propio de la barra,
    /// `u_r = k_rr⁻¹ (F_r - k_rc u_c)`.
    pub fn completar_desplazamientos(&self, u_nudo_local: &Vec6, feq: &Vec6) -> Vec6 {
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

/// Inversa de una matriz pequeña por Gauss-Jordan con pivoteo parcial.
fn invertir(mut m: Vec<Vec<f64>>) -> Option<Vec<Vec<f64>>> {
    let n = m.len();
    let escala = m
        .iter()
        .flat_map(|f| f.iter())
        .fold(0.0_f64, |a, v| a.max(v.abs()));
    let mut inv: Vec<Vec<f64>> = (0..n)
        .map(|i| (0..n).map(|j| if i == j { 1.0 } else { 0.0 }).collect())
        .collect();
    for col in 0..n {
        let piv = (col..n).max_by(|&a, &b| m[a][col].abs().total_cmp(&m[b][col].abs()))?;
        if m[piv][col].abs() <= 1e-12 * escala {
            return None;
        }
        m.swap(col, piv);
        inv.swap(col, piv);
        let p = m[col][col];
        for j in 0..n {
            m[col][j] /= p;
            inv[col][j] /= p;
        }
        for fila in 0..n {
            if fila != col {
                let f = m[fila][col];
                if f != 0.0 {
                    for j in 0..n {
                        m[fila][j] -= f * m[col][j];
                        inv[fila][j] -= f * inv[col][j];
                    }
                }
            }
        }
    }
    Some(inv)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn matmul(a: &Mat6, v: &Vec6) -> Vec6 {
        let mut o = [0.0; 6];
        for i in 0..6 {
            o[i] = (0..6).map(|j| a[i][j] * v[j]).sum();
        }
        o
    }

    #[test]
    fn rigidez_simetrica() {
        let k = rigidez_local(2.0e8, 0.01, 1e-4, 3.0);
        for i in 0..6 {
            for j in 0..6 {
                assert_eq!(k[i][j], k[j][i]);
            }
        }
    }

    #[test]
    fn movimiento_de_solido_rigido_no_genera_fuerzas() {
        let (l, c, s) = (5.0, 0.6, 0.8);
        let kg = rigidez_a_global(c, s, &rigidez_local(2.0e8, 0.02, 3e-4, l));
        // Traslación (1, 2) y giro θ alrededor del nudo i: el nudo j se mueve θ·(-dy, dx).
        let th = 1e-3;
        let (dx, dy) = (l * c, l * s);
        let u = [1.0, 2.0, th, 1.0 - th * dy, 2.0 + th * dx, th];
        let f = matmul(&kg, &u);
        let escala = 2.0e8 * 0.02 / l;
        for v in f {
            assert!(v.abs() < 1e-9 * escala, "fuerza residual {v}");
        }
    }

    #[test]
    fn transformacion_ida_y_vuelta() {
        let (c, s) = (0.28, 0.96);
        let g = [1.0, -2.0, 3.0, 4.0, 5.0, -6.0];
        let back = a_global(c, s, &a_local(c, s, &g));
        for i in 0..6 {
            assert!((back[i] - g[i]).abs() < 1e-14);
        }
    }

    #[test]
    fn rigidez_global_equivale_a_tt_k_t() {
        let (l, c, s) = (4.0, 0.6, -0.8);
        let k = rigidez_local(3.0e7, 0.1, 2e-3, l);
        let kg = rigidez_a_global(c, s, &k);
        // Comprobar contra K_g u = T^T K T u para un vector arbitrario.
        let u = [0.3, -1.2, 0.01, 0.7, 0.4, -0.02];
        let directo = a_global(c, s, &matmul(&k, &a_local(c, s, &u)));
        let via_kg = matmul(&kg, &u);
        for i in 0..6 {
            assert!((directo[i] - via_kg[i]).abs() < 1e-6 * directo[i].abs().max(1.0));
        }
    }

    #[test]
    fn cargas_equivalentes_puntual_al_centro() {
        let (l, p) = (6.0, -10.0);
        let f = cargas_equivalentes(
            l,
            &CargaLocal::Puntual {
                a: 3.0,
                px: 0.0,
                py: p,
            },
        );
        assert!((f[1] - p / 2.0).abs() < 1e-12);
        assert!((f[2] - p * l / 8.0).abs() < 1e-12);
        assert!((f[5] + p * l / 8.0).abs() < 1e-12);
    }

    #[test]
    fn biela_condensada_solo_tiene_rigidez_axial() {
        let b = Barra::biarticulada(0, 1, 2e8, 0.01, 1e-4);
        let ba = BarraAnalisis::new(&b, 2.0, 1.0, 0.0).unwrap();
        let ea_l = 2e8 * 0.01 / 2.0;
        assert!((ba.k_cond[0][0] - ea_l).abs() < 1e-9 * ea_l);
        // Transversal: una biela no tiene rigidez a flexión.
        for p in [1, 2, 4, 5] {
            for q in 0..6 {
                assert!(
                    ba.k_cond[p][q].abs() < 1e-9 * ea_l,
                    "k[{p}][{q}] = {}",
                    ba.k_cond[p][q]
                );
            }
        }
    }
}
