// SPDX-License-Identifier: GPL-3.0-or-later
//! Diagnóstico de mecanismos: qué nudo y qué GDL hacen inestable un modelo (issue #9).
//!
//! Solo se ejecuta cuando el análisis ya detectó que `K_ff` es singular o casi
//! singular, así que no cuesta nada en los modelos estables.
//!
//! Método: los modos de mecanismo son los vectores del núcleo de `K_ff`, es decir,
//! los autovectores de autovalor (casi) nulo. Se buscan con **iteración inversa
//! por subespacios con desplazamiento** sobre la matriz escalada por su diagonal
//! (escalado de Jacobi, `Â = S K S` con `S = diag(K)^-1/2`, para que traslaciones
//! y giros sean comparables):
//!
//! 1. `Â + εI` es definida positiva porque `Â` es semidefinida positiva; se
//!    factoriza con Cholesky disperso (la misma rutina que el análisis).
//! 2. `X ← (Â + εI)⁻¹ X` amplifica cada componente en `1/(λ + ε)`: las del núcleo
//!    (`λ ≈ 0`) dominan en pocas iteraciones.
//! 3. Rayleigh-Ritz: autovalores y autovectores de `Xᵀ Â X` (Jacobi cíclico).
//!    Los vectores de Ritz con `λ` menor que [`TOLERANCIA_MODO`] son modos de
//!    mecanismo; el desplazamiento físico es `x = S y`.
//!
//! Fuente: Y. Saad, *Numerical Methods for Large Eigenvalue Problems*, 2.ª ed.,
//! SIAM 2011, §5.1 (iteración por subespacios), §4.3.1 (iteración inversa con
//! desplazamiento) y §4.3 (proyección de Rayleigh-Ritz); G. H. Golub y
//! C. F. Van Loan, *Matrix Computations*, 4.ª ed., §8.5 (método de Jacobi).

use faer::linalg::solvers::Solve;
use faer::sparse::{SparseColMat, Triplet};
use faer::{Mat, Side};

use crate::error::{ComponenteModo, DiagnosticoMecanismo, Gdl};

/// Cantidad máxima de modos de mecanismo que se buscan a la vez.
const MAX_MODOS: usize = 6;
/// Iteraciones de la iteración inversa por subespacios.
const ITERACIONES: usize = 8;
/// Autovalor (de la matriz escalada, con diagonal unitaria) por debajo del cual
/// un modo se considera de mecanismo. Coherente con el límite de flexibilidad
/// `1e12` que usa el análisis para declarar la matriz singular.
const TOLERANCIA_MODO: f64 = 1e-10;
/// Componente mínima (relativa a la del GDL principal, que vale 1) para que un
/// GDL figure en el modo.
const COMPONENTE_MINIMA: f64 = 1e-6;

/// Busca los modos de mecanismo de `K_ff`.
///
/// `tripletas` es el triángulo inferior de `K_ff` (con posibles repetidos, que se
/// suman) y `gdl_global[i]` el GDL global (`3·nudo + d`) del GDL libre `i`.
/// Devuelve `None` si no se pudo hacer el diagnóstico.
pub(crate) fn diagnosticar(
    n: usize,
    tripletas: &[Triplet<usize, usize, f64>],
    gdl_global: &[usize],
) -> Option<DiagnosticoMecanismo> {
    if n == 0 {
        return None;
    }
    // Escalado de Jacobi.
    let mut diag = vec![0.0; n];
    for t in tripletas {
        if t.row == t.col {
            diag[t.row] += t.val;
        }
    }
    let s: Vec<f64> = diag
        .iter()
        .map(|&d| if d > 0.0 { 1.0 / d.sqrt() } else { 1.0 })
        .collect();
    let escaladas: Vec<Triplet<usize, usize, f64>> = tripletas
        .iter()
        .map(|t| Triplet::new(t.row, t.col, t.val * s[t.row] * s[t.col]))
        .collect();
    let producto = |x: &[f64]| -> Vec<f64> {
        let mut y = vec![0.0; n];
        for t in &escaladas {
            y[t.row] += t.val * x[t.col];
            if t.row != t.col {
                y[t.col] += t.val * x[t.row];
            }
        }
        y
    };

    // Factorización de Â + εI; si el redondeo la hace fallar, se agranda ε.
    let mut llt = None;
    for eps in [1e-10, 1e-8, 1e-6] {
        let mut t = escaladas.clone();
        t.extend((0..n).map(|i| Triplet::new(i, i, eps)));
        let a = SparseColMat::<usize, f64>::try_new_from_triplets(n, n, &t).ok()?;
        if let Ok(f) = a.sp_cholesky(Side::Lower) {
            llt = Some(f);
            break;
        }
    }
    let llt = llt?;

    // Iteración inversa por subespacios desde un arranque pseudoaleatorio fijo
    // (determinista, para que el diagnóstico sea reproducible).
    let b = n.min(MAX_MODOS);
    let mut semilla: u64 = 0x9E37_79B9_7F4A_7C15;
    let mut x = Mat::<f64>::from_fn(n, b, |_, _| {
        semilla = semilla
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        ((semilla >> 11) as f64 / (1u64 << 53) as f64) * 2.0 - 1.0
    });
    for _ in 0..ITERACIONES {
        llt.solve_in_place(x.as_mut());
        ortonormalizar(&mut x);
    }

    // Rayleigh-Ritz.
    let columnas: Vec<Vec<f64>> = (0..b)
        .map(|j| (0..n).map(|i| x[(i, j)]).collect())
        .collect();
    let kx: Vec<Vec<f64>> = columnas.iter().map(|c| producto(c)).collect();
    let mut h = vec![vec![0.0; b]; b];
    for p in 0..b {
        for q in 0..b {
            h[p][q] = (0..n).map(|i| columnas[p][i] * kx[q][i]).sum();
        }
    }
    let (lambda, v) = jacobi_simetrico(h);
    let mut orden: Vec<usize> = (0..b).collect();
    orden.sort_by(|&i, &j| lambda[i].total_cmp(&lambda[j]));

    let mut elegidos: Vec<usize> = orden
        .iter()
        .copied()
        .filter(|&k| lambda[k] < TOLERANCIA_MODO)
        .collect();
    let seguro = !elegidos.is_empty();
    if !seguro {
        // Casi singular pero por encima de la tolerancia: se informa el modo más
        // flexible como ubicación probable.
        elegidos.push(orden[0]);
    }

    let mut modos = Vec::with_capacity(elegidos.len());
    let mut ubicacion = None;
    for &k in &elegidos {
        // x = S · (X v_k), desplazamiento físico del modo.
        let fisico: Vec<f64> = (0..n)
            .map(|i| s[i] * (0..b).map(|j| columnas[j][i] * v[j][k]).sum::<f64>())
            .collect();
        let (modo, principal) = describir_modo(&fisico, gdl_global);
        if ubicacion.is_none() {
            ubicacion = principal;
        }
        modos.push(modo);
    }

    let detalle = if !seguro {
        "la matriz de rigidez es casi singular; la ubicación es probable".to_string()
    } else if modos.len() == b && b == MAX_MODOS {
        format!("hay al menos {} modos de mecanismo", modos.len())
    } else if modos.len() > 1 {
        format!("hay {} modos de mecanismo", modos.len())
    } else {
        "hay 1 modo de mecanismo".to_string()
    };
    Some(DiagnosticoMecanismo {
        detalle,
        ubicacion,
        modos,
    })
}

/// Normaliza el modo para que su GDL principal valga 1 y devuelve sus
/// componentes significativas, ordenadas por nudo y GDL.
///
/// El GDL principal es la traslación de mayor valor absoluto (las traslaciones
/// son lo que el usuario ve moverse); si el modo no tiene traslaciones, el giro
/// de mayor valor absoluto.
fn describir_modo(x: &[f64], gdl_global: &[usize]) -> (Vec<ComponenteModo>, Option<(usize, Gdl)>) {
    let mayor = |traslacion: bool| -> Option<usize> {
        (0..x.len())
            .filter(|&i| (gdl_global[i] % 3 != 2) == traslacion)
            .filter(|&i| x[i] != 0.0)
            // Ante empates (dentro del redondeo) gana el GDL de menor índice.
            .fold(None, |m: Option<usize>, i| match m {
                Some(j) if x[i].abs() <= x[j].abs() * (1.0 + 1e-9) => Some(j),
                _ => Some(i),
            })
    };
    let max_abs = x.iter().fold(0.0_f64, |m, v| m.max(v.abs()));
    let principal = match mayor(true) {
        Some(i) if x[i].abs() > 1e-9 * max_abs => Some(i),
        _ => mayor(false),
    };
    let Some(p) = principal else {
        return (Vec::new(), None);
    };
    let escala = x[p];
    let mut componentes: Vec<ComponenteModo> = (0..x.len())
        .filter_map(|i| {
            let valor = x[i] / escala;
            (valor.abs() >= COMPONENTE_MINIMA).then(|| ComponenteModo {
                nudo: gdl_global[i] / 3,
                gdl: Gdl::desde_indice(gdl_global[i]),
                valor,
            })
        })
        .collect();
    componentes.sort_by_key(|c| (c.nudo, c.gdl as usize));
    let ubicacion = (gdl_global[p] / 3, Gdl::desde_indice(gdl_global[p]));
    (componentes, Some(ubicacion))
}

/// Gram-Schmidt modificado, dos pasadas (reortogonalización), sobre las columnas.
fn ortonormalizar(x: &mut Mat<f64>) {
    let (n, b) = (x.nrows(), x.ncols());
    for _ in 0..2 {
        for j in 0..b {
            for k in 0..j {
                let r: f64 = (0..n).map(|i| x[(i, k)] * x[(i, j)]).sum();
                for i in 0..n {
                    x[(i, j)] -= r * x[(i, k)];
                }
            }
            let norma = (0..n).map(|i| x[(i, j)] * x[(i, j)]).sum::<f64>().sqrt();
            if norma > 0.0 {
                for i in 0..n {
                    x[(i, j)] /= norma;
                }
            }
        }
    }
}

/// Autovalores y autovectores (por columnas) de una matriz simétrica pequeña por
/// el método de Jacobi cíclico (Golub y Van Loan, §8.5.3).
fn jacobi_simetrico(mut a: Vec<Vec<f64>>) -> (Vec<f64>, Vec<Vec<f64>>) {
    let n = a.len();
    let mut v = vec![vec![0.0; n]; n];
    for i in 0..n {
        v[i][i] = 1.0;
    }
    for _ in 0..100 {
        let fuera: f64 = (0..n)
            .flat_map(|p| (0..n).filter(move |&q| q != p).map(move |q| (p, q)))
            .map(|(p, q)| a[p][q] * a[p][q])
            .sum();
        let total: f64 = fuera + (0..n).map(|i| a[i][i] * a[i][i]).sum::<f64>();
        if fuera <= 1e-30 * total.max(f64::MIN_POSITIVE) {
            break;
        }
        for p in 0..n {
            for q in p + 1..n {
                if a[p][q] == 0.0 {
                    continue;
                }
                let theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q]);
                let t = theta.signum() / (theta.abs() + (theta * theta + 1.0).sqrt());
                let c = 1.0 / (t * t + 1.0).sqrt();
                let s = t * c;
                for k in 0..n {
                    let (akp, akq) = (a[k][p], a[k][q]);
                    a[k][p] = c * akp - s * akq;
                    a[k][q] = s * akp + c * akq;
                }
                for k in 0..n {
                    let (apk, aqk) = (a[p][k], a[q][k]);
                    a[p][k] = c * apk - s * aqk;
                    a[q][k] = s * apk + c * aqk;
                }
                for k in 0..n {
                    let (vkp, vkq) = (v[k][p], v[k][q]);
                    v[k][p] = c * vkp - s * vkq;
                    v[k][q] = s * vkp + c * vkq;
                }
            }
        }
    }
    ((0..n).map(|i| a[i][i]).collect(), v)
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn jacobi_matriz_conocida() {
        // [[2, 1], [1, 2]] → autovalores 1 y 3.
        let (l, v) = jacobi_simetrico(vec![vec![2.0, 1.0], vec![1.0, 2.0]]);
        let mut l2 = l.clone();
        l2.sort_by(f64::total_cmp);
        assert!((l2[0] - 1.0).abs() < 1e-14 && (l2[1] - 3.0).abs() < 1e-14);
        for k in 0..2 {
            let av0 = 2.0 * v[0][k] + v[1][k];
            assert!((av0 - l[k] * v[0][k]).abs() < 1e-13);
        }
    }
}
