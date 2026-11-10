// SPDX-License-Identifier: GPL-3.0-or-later
//! Análisis lineal elástico de pórticos planos.
//!
//! Procedimiento:
//! 1. Rigidez de cada barra (condensada por sus liberaciones) en ejes globales.
//! 2. Partición de GDL en libres y restringidos (no se usa penalización).
//! 3. Factorización de Cholesky dispersa de `K_ff` (una sola para todos los casos).
//! 4. `K_ff U_f = F_f - K_fr U_r` para cada caso de carga.
//! 5. Fuerzas de extremo `f = k u - F_eq`, reacciones por equilibrio de nudos.

use faer::linalg::solvers::Solve;
use faer::sparse::{SparseColMat, Triplet};
use faer::{Mat, Side};

use crate::elemento::{
    a_global, a_local, carga_a_local, cargas_equivalentes, flecha_biempotrada, resultantes_hasta,
    BarraAnalisis, CargaLocal, Vec6,
};
use crate::error::{ErrorNervi, Gdl, Resultado};
use crate::modelo::Modelo;

/// Umbral del cociente `max|u| · max(K_ii) / max|F|` por encima del cual se
/// considera que la matriz es numéricamente singular (mecanismo).
const LIMITE_FLEXIBILIDAD: f64 = 1e12;

/// Resultados de un caso de carga.
#[derive(Clone, Debug)]
pub struct ResultadosCaso {
    /// Desplazamientos de nudos `[ux, uy, rz]` en ejes globales.
    pub desplazamientos: Vec<[f64; 3]>,
    /// Reacciones `[Rx, Ry, Mz]` en ejes globales (fuerza del apoyo sobre la estructura).
    /// Incluye apoyos rígidos y elásticos; es cero en los GDL libres.
    pub reacciones: Vec<[f64; 3]>,
    /// Fuerzas de extremo de cada barra en ejes locales `[f1..f6]`, actuando sobre la barra.
    pub fuerzas_extremo: Vec<Vec6>,
    /// Desplazamientos de extremo de cada barra en ejes locales (con los giros
    /// propios de la barra en los extremos liberados).
    pub desplazamientos_extremo: Vec<Vec6>,
    /// Cargas en tramo de cada barra, en ejes locales.
    pub cargas_locales: Vec<Vec<CargaLocal>>,
}

/// Esfuerzos y desplazamientos en una sección de la barra.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Seccion {
    /// Distancia desde el nudo `i`.
    pub x: f64,
    /// Axil, positivo en tracción.
    pub n: f64,
    /// Cortante, con `V = dM/dx`.
    pub v: f64,
    /// Momento flector, positivo si tracciona la fibra del lado `-y` local.
    pub m: f64,
    /// Desplazamiento axial en ejes locales.
    pub u_local: f64,
    /// Flecha transversal en ejes locales.
    pub v_local: f64,
}

/// Resultados de todos los casos de carga.
#[derive(Clone, Debug)]
pub struct Resultados {
    pub casos: Vec<ResultadosCaso>,
    /// GDL libres sin ninguna rigidez (por ejemplo, giros de nudos de cercha) que se
    /// fijaron automáticamente porque no tenían carga.
    pub gdl_sin_rigidez: Vec<(usize, Gdl)>,
    pub barras: Vec<BarraAnalisis>,
}

/// Analiza el modelo para todos sus casos de carga.
pub fn analizar(modelo: &Modelo) -> Resultado<Resultados> {
    modelo.validar()?;
    let n_gdl = modelo.n_gdl();
    let n_casos = modelo.casos.len();

    let barras: Vec<BarraAnalisis> = modelo
        .barras
        .iter()
        .map(|b| {
            let (l, c, s) = modelo.geometria_barra(b);
            BarraAnalisis::new(b, l, c, s)
        })
        .collect::<Resultado<_>>()?;
    let gdl_barra = |k: usize| -> [usize; 6] {
        let (i, j) = (modelo.barras[k].nudo_i, modelo.barras[k].nudo_j);
        [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]
    };

    // Cargas en tramo en ejes locales y sus cargas equivalentes (completas y condensadas).
    let mut cargas_locales = vec![vec![Vec::new(); barras.len()]; n_casos];
    let mut feq = vec![vec![[0.0; 6]; barras.len()]; n_casos];
    for (c, caso) in modelo.casos.iter().enumerate() {
        for cb in &caso.en_barras {
            let ba = &barras[cb.barra];
            let cl = carga_a_local(ba.c, ba.s, cb);
            let f = cargas_equivalentes(ba.l, &cl);
            for d in 0..6 {
                feq[c][cb.barra][d] += f[d];
            }
            cargas_locales[c][cb.barra].push(cl);
        }
    }

    // Vector global de cargas por caso: nodales + equivalentes condensadas.
    let mut f_glob = vec![vec![0.0; n_gdl]; n_casos];
    for (c, caso) in modelo.casos.iter().enumerate() {
        for (nudo, f) in &caso.nodales {
            for d in 0..3 {
                f_glob[c][3 * nudo + d] += f[d];
            }
        }
        for (k, ba) in barras.iter().enumerate() {
            let fc = ba.condensar_cargas(&feq[c][k]);
            let g = a_global(ba.c, ba.s, &fc);
            for (d, &gd) in gdl_barra(k).iter().enumerate() {
                f_glob[c][gd] += g[d];
            }
        }
    }

    // Diagonal de rigidez para detectar GDL sin rigidez.
    let mut diag = vec![0.0; n_gdl];
    for (k, ba) in barras.iter().enumerate() {
        for (d, &gd) in gdl_barra(k).iter().enumerate() {
            diag[gd] += ba.k_global[d][d];
        }
    }
    for (g, dg) in diag.iter_mut().enumerate() {
        *dg += modelo.rigidez_resorte(g / 3, g % 3);
    }
    let diag_max = diag.iter().fold(0.0_f64, |m, v| m.max(v.abs()));

    // Clasificación de GDL.
    let mut restringido = vec![false; n_gdl];
    let mut gdl_sin_rigidez = Vec::new();
    let escala_f = f_glob
        .iter()
        .flat_map(|f| f.iter())
        .fold(0.0_f64, |m, v| m.max(v.abs()));
    for g in 0..n_gdl {
        let (nudo, d) = (g / 3, g % 3);
        if modelo.restringido(nudo, d) {
            restringido[g] = true;
        } else if diag[g] <= 1e-14 * diag_max {
            if f_glob
                .iter()
                .any(|f| f[g].abs() > 1e-14 * escala_f.max(f64::MIN_POSITIVE))
            {
                return Err(ErrorNervi::CargaSinRigidez {
                    nudo,
                    gdl: Gdl::desde_indice(d),
                });
            }
            restringido[g] = true;
            gdl_sin_rigidez.push((nudo, Gdl::desde_indice(d)));
        }
    }
    let mut libre_idx = vec![usize::MAX; n_gdl];
    let mut n_libres = 0;
    for g in 0..n_gdl {
        if !restringido[g] {
            libre_idx[g] = n_libres;
            n_libres += 1;
        }
    }

    // Desplazamientos impuestos por caso (solo en GDL con restricción del usuario).
    let mut u_imp = vec![vec![0.0; n_gdl]; n_casos];
    for (c, caso) in modelo.casos.iter().enumerate() {
        for (nudo, d) in &caso.desplazamientos_impuestos {
            for k in 0..3 {
                if modelo.restringido(*nudo, k) {
                    u_imp[c][3 * nudo + k] = d[k];
                }
            }
        }
    }

    // Ensamblaje de K_ff y del término K_fr U_r.
    let mut tripletas = Vec::with_capacity(36 * barras.len() + n_libres);
    let mut rhs = Mat::<f64>::zeros(n_libres, n_casos);
    for (c, f) in f_glob.iter().enumerate() {
        for g in 0..n_gdl {
            if libre_idx[g] != usize::MAX {
                rhs[(libre_idx[g], c)] = f[g];
            }
        }
    }
    for (k, ba) in barras.iter().enumerate() {
        let gdl = gdl_barra(k);
        for p in 0..6 {
            let lp = libre_idx[gdl[p]];
            if lp == usize::MAX {
                continue;
            }
            for q in 0..6 {
                let v = ba.k_global[p][q];
                if v == 0.0 {
                    continue;
                }
                let lq = libre_idx[gdl[q]];
                if lq == usize::MAX {
                    for c in 0..n_casos {
                        rhs[(lp, c)] -= v * u_imp[c][gdl[q]];
                    }
                } else if lq <= lp {
                    // Solo el triángulo inferior: Cholesky lee `Side::Lower`.
                    tripletas.push(Triplet::new(lp, lq, v));
                }
            }
        }
    }
    for g in 0..n_gdl {
        let lg = libre_idx[g];
        let ks = modelo.rigidez_resorte(g / 3, g % 3);
        if lg != usize::MAX && ks != 0.0 {
            tripletas.push(Triplet::new(lg, lg, ks));
        }
    }

    // Solución.
    let mut u_libres = rhs.clone();
    if n_libres > 0 {
        let k_ff =
            SparseColMat::<usize, f64>::try_new_from_triplets(n_libres, n_libres, &tripletas)
                .map_err(|e| ErrorNervi::Numerico(format!("no se pudo armar la matriz: {e:?}")))?;
        let llt = k_ff.sp_cholesky(Side::Lower).map_err(|e| {
            ErrorNervi::Mecanismo(format!(
                "la matriz de rigidez no es definida positiva ({e:?}); revisar apoyos y articulaciones"
            ))
        })?;
        llt.solve_in_place(u_libres.as_mut());

        let diag_libre_max = (0..n_gdl)
            .filter(|&g| libre_idx[g] != usize::MAX)
            .fold(0.0_f64, |m, g| m.max(diag[g]));
        for c in 0..n_casos {
            let f_max = (0..n_libres).fold(0.0_f64, |m, i| m.max(rhs[(i, c)].abs()));
            let u_max = (0..n_libres).fold(0.0_f64, |m, i| m.max(u_libres[(i, c)].abs()));
            if !u_max.is_finite()
                || (f_max > 0.0 && u_max * diag_libre_max > LIMITE_FLEXIBILIDAD * f_max)
            {
                return Err(ErrorNervi::Mecanismo(format!(
                    "caso {c}: la matriz de rigidez es numéricamente singular; revisar apoyos y articulaciones"
                )));
            }
        }
    }

    // Post-proceso por caso.
    let mut casos = Vec::with_capacity(n_casos);
    for c in 0..n_casos {
        let mut u = u_imp[c].clone();
        for g in 0..n_gdl {
            if libre_idx[g] != usize::MAX {
                u[g] = u_libres[(libre_idx[g], c)];
            }
        }
        let mut suma_fuerzas = vec![0.0; n_gdl];
        let mut fuerzas_extremo = Vec::with_capacity(barras.len());
        let mut desplazamientos_extremo = Vec::with_capacity(barras.len());
        for (k, ba) in barras.iter().enumerate() {
            let gdl = gdl_barra(k);
            let ug: Vec6 = std::array::from_fn(|d| u[gdl[d]]);
            let ul = ba.completar_desplazamientos(&a_local(ba.c, ba.s, &ug), &feq[c][k]);
            let mut f: Vec6 = [0.0; 6];
            for p in 0..6 {
                f[p] = (0..6).map(|q| ba.k[p][q] * ul[q]).sum::<f64>() - feq[c][k][p];
            }
            for &r in &ba.liberados {
                f[r] = 0.0; // exactamente nulo por definición (elimina el redondeo)
            }
            let fg = a_global(ba.c, ba.s, &f);
            for d in 0..6 {
                suma_fuerzas[gdl[d]] += fg[d];
            }
            fuerzas_extremo.push(f);
            desplazamientos_extremo.push(ul);
        }
        let mut f_nodal = vec![0.0; n_gdl];
        for (nudo, f) in &modelo.casos[c].nodales {
            for d in 0..3 {
                f_nodal[3 * nudo + d] += f[d];
            }
        }
        let mut reacciones = vec![[0.0; 3]; modelo.nudos.len()];
        for g in 0..n_gdl {
            let (nudo, d) = (g / 3, g % 3);
            let apoyo = modelo.restringido(nudo, d) || modelo.rigidez_resorte(nudo, d) != 0.0;
            if apoyo {
                reacciones[nudo][d] = suma_fuerzas[g] - f_nodal[g];
            }
        }
        let desplazamientos = (0..modelo.nudos.len())
            .map(|n| [u[3 * n], u[3 * n + 1], u[3 * n + 2]])
            .collect();
        casos.push(ResultadosCaso {
            desplazamientos,
            reacciones,
            fuerzas_extremo,
            desplazamientos_extremo,
            cargas_locales: std::mem::take(&mut cargas_locales[c]),
        });
    }

    Ok(Resultados {
        casos,
        gdl_sin_rigidez,
        barras,
    })
}

impl Resultados {
    /// Esfuerzos y desplazamientos en la sección `x` de una barra.
    ///
    /// En una carga puntual ubicada exactamente en `x`, `lado_derecho` indica si se
    /// devuelve el valor inmediatamente a la derecha (`true`) o a la izquierda.
    pub fn seccion(&self, caso: usize, barra: usize, x: f64, lado_derecho: bool) -> Seccion {
        let rc = &self.casos[caso];
        let ba = &self.barras[barra];
        let f = &rc.fuerzas_extremo[barra];
        let ue = &rc.desplazamientos_extremo[barra];
        let l = ba.l;

        let mut n = -f[0];
        let mut v = f[1];
        let mut m = -f[2] + f[1] * x;

        let xi = x / l;
        let (h1, h2) = (
            1.0 - 3.0 * xi * xi + 2.0 * xi.powi(3),
            l * (xi - 2.0 * xi * xi + xi.powi(3)),
        );
        let (h3, h4) = (
            3.0 * xi * xi - 2.0 * xi.powi(3),
            l * (-xi * xi + xi.powi(3)),
        );
        let mut u_local = (1.0 - xi) * ue[0] + xi * ue[3];
        let mut v_local = h1 * ue[1] + h2 * ue[2] + h3 * ue[4] + h4 * ue[5];

        for carga in &rc.cargas_locales[barra] {
            let (rx, ry, mom) = resultantes_hasta(carga, x, lado_derecho);
            n -= rx;
            v += ry;
            m += mom;
            let (du, dv) = flecha_biempotrada(l, ba.ea, ba.ei, carga, x);
            u_local += du;
            v_local += dv;
        }
        Seccion {
            x,
            n,
            v,
            m,
            u_local,
            v_local,
        }
    }

    /// Diagrama de esfuerzos de una barra en `n_estaciones` puntos equidistantes
    /// (mínimo 2), más los puntos de cargas puntuales (a ambos lados), los
    /// extremos de las cargas trapezoidales y los puntos de cortante nulo, donde el
    /// momento es extremo.
    pub fn diagrama(&self, caso: usize, barra: usize, n_estaciones: usize) -> Vec<Seccion> {
        let l = self.barras[barra].l;
        let n_est = n_estaciones.max(2);
        let mut xs: Vec<(f64, bool)> = (0..n_est)
            .map(|k| (l * k as f64 / (n_est - 1) as f64, false))
            .collect();
        let mut quiebres = vec![0.0, l];
        for carga in &self.casos[caso].cargas_locales[barra] {
            match *carga {
                CargaLocal::Puntual { a, .. } => {
                    xs.push((a, false));
                    xs.push((a, true));
                    quiebres.push(a);
                }
                CargaLocal::Trapezoidal { a, b, .. } => {
                    xs.push((a, false));
                    xs.push((b, false));
                    quiebres.push(a);
                    quiebres.push(b);
                }
                CargaLocal::Uniforme { .. } => {}
            }
        }
        quiebres.sort_by(f64::total_cmp);
        quiebres.dedup();
        // Cortante nulo: entre quiebres V es un polinomio de grado 2 como máximo
        // (lineal con cargas uniformes, cuadrático con trapezoidales), así que tres
        // valores lo determinan exactamente.
        for w in quiebres.windows(2) {
            let (x0, x1) = (w[0], w[1]);
            if x1 - x0 <= 0.0 {
                continue;
            }
            let v0 = self.seccion(caso, barra, x0, true).v;
            let vm = self.seccion(caso, barra, 0.5 * (x0 + x1), false).v;
            let v1 = self.seccion(caso, barra, x1, false).v;
            for t in raices_cuadratica_en_intervalo(v0, vm, v1) {
                xs.push((x0 + (x1 - x0) * t, false));
            }
        }
        xs.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
        xs.dedup_by(|a, b| a.0 == b.0 && a.1 == b.1);
        xs.into_iter()
            .map(|(x, der)| self.seccion(caso, barra, x, der))
            .collect()
    }
}

/// Raíces en el intervalo abierto `(0, 1)` del polinomio de grado ≤ 2 que vale
/// `f0`, `fm` y `f1` en `t = 0`, `1/2` y `1`.
fn raices_cuadratica_en_intervalo(f0: f64, fm: f64, f1: f64) -> Vec<f64> {
    // f(t) = f0 + p·t + q·t² (interpolación de Lagrange en 0, 1/2, 1).
    let p = -3.0 * f0 + 4.0 * fm - f1;
    let q = 2.0 * f0 - 4.0 * fm + 2.0 * f1;
    let escala = f0.abs().max(fm.abs()).max(f1.abs());
    if escala == 0.0 {
        return Vec::new();
    }
    let dentro = |t: f64| t > 0.0 && t < 1.0;
    if q.abs() <= 1e-12 * escala {
        // Lineal.
        if p.abs() <= 1e-12 * escala {
            return Vec::new();
        }
        let t = -f0 / p;
        return if dentro(t) { vec![t] } else { Vec::new() };
    }
    let disc = p * p - 4.0 * q * f0;
    if disc < 0.0 {
        return Vec::new();
    }
    // Fórmula estable (evita la cancelación de -p ± √disc).
    let raiz = disc.sqrt();
    let w = -0.5 * (p + p.signum() * raiz);
    let mut out = Vec::new();
    for t in [w / q, if w != 0.0 { f0 / w } else { f64::NAN }] {
        if dentro(t) && !out.iter().any(|&o: &f64| (o - t).abs() < 1e-12) {
            out.push(t);
        }
    }
    out.sort_by(f64::total_cmp);
    out
}
