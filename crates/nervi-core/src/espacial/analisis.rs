// SPDX-License-Identifier: GPL-3.0-or-later
//! Análisis lineal elástico de pórticos espaciales.
//!
//! El procedimiento es el mismo que el del pórtico plano ([`crate::analisis`]),
//! con 6 GDL por nudo: rigidez condensada de cada barra en globales, partición
//! en GDL libres y restringidos, una sola factorización de Cholesky dispersa para
//! todos los casos (compartida con el plano en [`crate::analisis`]), fuerzas de
//! extremo `f = k u - F_eq` y reacciones por equilibrio de nudos.

use faer::sparse::Triplet;
use faer::Mat;

use crate::analisis::{raices_cuadratica_en_intervalo, resolver_sistema, seccion_plana};
use crate::elemento::CargaLocal;
use crate::error::{ErrorNervi, Gdl, Resultado};
use crate::espacial::elemento::{
    a_global_3d, a_local_3d, carga_a_local_3d, cargas_equivalentes_3d, plano_xy, plano_xz,
    BarraAnalisis3d, CargaLocal3d, Vec12,
};
use crate::espacial::modelo::Modelo3d;

/// Resultados de un caso de carga del pórtico espacial.
#[derive(Clone, Debug)]
pub struct ResultadosCaso3d {
    /// Desplazamientos de nudos `[ux, uy, uz, rx, ry, rz]` en ejes globales.
    pub desplazamientos: Vec<[f64; 6]>,
    /// Reacciones `[Rx, Ry, Rz, Mx, My, Mz]` en ejes globales (fuerza del apoyo
    /// sobre la estructura); cero en los GDL libres.
    pub reacciones: Vec<[f64; 6]>,
    /// Fuerzas de extremo de cada barra en ejes locales, actuando sobre la barra:
    /// `[Fx, Fy, Fz, Mx, My, Mz]` en `i` y luego en `j`.
    pub fuerzas_extremo: Vec<Vec12>,
    /// Desplazamientos de extremo de cada barra en ejes locales (con los propios
    /// de la barra en los GDL liberados).
    pub desplazamientos_extremo: Vec<Vec12>,
    /// Cargas en tramo de cada barra, en ejes locales.
    pub cargas_locales: Vec<Vec<CargaLocal3d>>,
}

/// Esfuerzos y desplazamientos en una sección de una barra espacial.
///
/// Los esfuerzos son las componentes, en ejes locales, de la acción de la parte
/// `[x, L]` sobre la parte `[0, x]` (cara positiva), salvo los cortantes, que se
/// definen como en el plano para que `Vy = dMz/dx` y `Vz = dMy/dx`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Seccion3d {
    /// Distancia desde el nudo `i`.
    pub x: f64,
    /// Axil, positivo en tracción.
    pub n: f64,
    /// Cortante en `y`, `Vy = dMz/dx` (igual que `V` en el pórtico plano).
    pub vy: f64,
    /// Cortante en `z`, `Vz = dMy/dx`.
    pub vz: f64,
    /// Torsor, positivo según la regla de la mano derecha alrededor de `+x`.
    pub t: f64,
    /// Momento alrededor de `y`, positivo si tracciona la fibra del lado `+z`.
    pub my: f64,
    /// Momento alrededor de `z`, positivo si tracciona la fibra del lado `-y`
    /// (igual que `M` en el pórtico plano).
    pub mz: f64,
    /// Desplazamientos en ejes locales.
    pub u: f64,
    pub v: f64,
    pub w: f64,
    /// Giro de torsión alrededor del eje de la barra.
    pub rx: f64,
}

/// Resultados de todos los casos de carga del pórtico espacial.
#[derive(Clone, Debug)]
pub struct Resultados3d {
    pub casos: Vec<ResultadosCaso3d>,
    /// GDL libres sin ninguna rigidez (por ejemplo, los giros de los nudos de una
    /// cercha espacial) fijados automáticamente porque no tenían carga.
    pub gdl_sin_rigidez: Vec<(usize, Gdl)>,
    pub barras: Vec<BarraAnalisis3d>,
}

/// Analiza el pórtico espacial para todos sus casos de carga.
pub fn analizar_3d(modelo: &Modelo3d) -> Resultado<Resultados3d> {
    modelo.validar()?;
    let n_gdl = modelo.n_gdl();
    let n_casos = modelo.casos.len();

    let barras: Vec<BarraAnalisis3d> = modelo
        .barras
        .iter()
        .map(|b| BarraAnalisis3d::new(b, modelo.longitud(b), modelo.ejes_barra(b)?))
        .collect::<Resultado<_>>()?;
    let gdl_barra = |k: usize| -> [usize; 12] {
        let (i, j) = (modelo.barras[k].nudo_i, modelo.barras[k].nudo_j);
        std::array::from_fn(|d| if d < 6 { 6 * i + d } else { 6 * j + d - 6 })
    };

    let mut cargas_locales = vec![vec![Vec::new(); barras.len()]; n_casos];
    let mut feq = vec![vec![[0.0; 12]; barras.len()]; n_casos];
    for (c, caso) in modelo.casos.iter().enumerate() {
        for cb in &caso.en_barras {
            let ba = &barras[cb.barra];
            let cl = carga_a_local_3d(&ba.ejes, cb);
            let f = cargas_equivalentes_3d(ba.l, ba.ea, ba.eiy, ba.eiz, &cl);
            for d in 0..12 {
                feq[c][cb.barra][d] += f[d];
            }
            cargas_locales[c][cb.barra].push(cl);
        }
    }

    let mut f_glob = vec![vec![0.0; n_gdl]; n_casos];
    for (c, caso) in modelo.casos.iter().enumerate() {
        for (nudo, f) in &caso.nodales {
            for d in 0..6 {
                f_glob[c][6 * nudo + d] += f[d];
            }
        }
        for (k, ba) in barras.iter().enumerate() {
            let g = a_global_3d(&ba.ejes, &ba.condensar_cargas(&feq[c][k]));
            for (d, &gd) in gdl_barra(k).iter().enumerate() {
                f_glob[c][gd] += g[d];
            }
        }
    }

    let mut diag = vec![0.0; n_gdl];
    for (k, ba) in barras.iter().enumerate() {
        for (d, &gd) in gdl_barra(k).iter().enumerate() {
            diag[gd] += ba.k_global[d][d];
        }
    }
    for (g, dg) in diag.iter_mut().enumerate() {
        *dg += modelo.rigidez_resorte(g / 6, g % 6);
    }
    let diag_max = diag.iter().fold(0.0_f64, |m, v| m.max(v.abs()));

    let mut restringido = vec![false; n_gdl];
    let mut gdl_sin_rigidez = Vec::new();
    let escala_f = f_glob
        .iter()
        .flat_map(|f| f.iter())
        .fold(0.0_f64, |m, v| m.max(v.abs()));
    for g in 0..n_gdl {
        let (nudo, d) = (g / 6, g % 6);
        if modelo.restringido(nudo, d) {
            restringido[g] = true;
        } else if diag[g] <= 1e-14 * diag_max {
            if f_glob
                .iter()
                .any(|f| f[g].abs() > 1e-14 * escala_f.max(f64::MIN_POSITIVE))
            {
                return Err(ErrorNervi::CargaSinRigidez {
                    nudo,
                    gdl: Gdl::desde_indice_3d(d),
                });
            }
            restringido[g] = true;
            gdl_sin_rigidez.push((nudo, Gdl::desde_indice_3d(d)));
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

    let mut u_imp = vec![vec![0.0; n_gdl]; n_casos];
    for (c, caso) in modelo.casos.iter().enumerate() {
        for (nudo, d) in &caso.desplazamientos_impuestos {
            for k in 0..6 {
                if modelo.restringido(*nudo, k) {
                    u_imp[c][6 * nudo + k] = d[k];
                }
            }
        }
    }

    let mut tripletas = Vec::with_capacity(78 * barras.len() + n_libres);
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
        for p in 0..12 {
            let lp = libre_idx[gdl[p]];
            if lp == usize::MAX {
                continue;
            }
            for q in 0..12 {
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
                    tripletas.push(Triplet::new(lp, lq, v));
                }
            }
        }
    }
    for g in 0..n_gdl {
        let lg = libre_idx[g];
        let ks = modelo.rigidez_resorte(g / 6, g % 6);
        if lg != usize::MAX && ks != 0.0 {
            tripletas.push(Triplet::new(lg, lg, ks));
        }
    }

    let gdl_global: Vec<usize> = (0..n_gdl).filter(|&g| libre_idx[g] != usize::MAX).collect();
    let diag_libre_max = gdl_global.iter().fold(0.0_f64, |m, &g| m.max(diag[g]));
    let u_libres = resolver_sistema(&tripletas, rhs, &gdl_global, diag_libre_max, 6)?;

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
            let ug: Vec12 = std::array::from_fn(|d| u[gdl[d]]);
            let ul = ba.completar_desplazamientos(&a_local_3d(&ba.ejes, &ug), &feq[c][k]);
            let mut f: Vec12 = [0.0; 12];
            for p in 0..12 {
                f[p] = (0..12).map(|q| ba.k[p][q] * ul[q]).sum::<f64>() - feq[c][k][p];
            }
            for &r in &ba.liberados {
                f[r] = 0.0;
            }
            let fg = a_global_3d(&ba.ejes, &f);
            for d in 0..12 {
                suma_fuerzas[gdl[d]] += fg[d];
            }
            fuerzas_extremo.push(f);
            desplazamientos_extremo.push(ul);
        }
        let mut f_nodal = vec![0.0; n_gdl];
        for (nudo, f) in &modelo.casos[c].nodales {
            for d in 0..6 {
                f_nodal[6 * nudo + d] += f[d];
            }
        }
        let mut reacciones = vec![[0.0; 6]; modelo.nudos.len()];
        for g in 0..n_gdl {
            let (nudo, d) = (g / 6, g % 6);
            if modelo.restringido(nudo, d) || modelo.rigidez_resorte(nudo, d) != 0.0 {
                reacciones[nudo][d] = suma_fuerzas[g] - f_nodal[g];
            }
        }
        let desplazamientos = (0..modelo.nudos.len())
            .map(|n| std::array::from_fn(|d| u[6 * n + d]))
            .collect();
        casos.push(ResultadosCaso3d {
            desplazamientos,
            reacciones,
            fuerzas_extremo,
            desplazamientos_extremo,
            cargas_locales: std::mem::take(&mut cargas_locales[c]),
        });
    }

    Ok(Resultados3d {
        casos,
        gdl_sin_rigidez,
        barras,
    })
}

impl Resultados3d {
    /// Esfuerzos y desplazamientos en la sección `x` de una barra. En una carga
    /// puntual ubicada exactamente en `x`, `lado_derecho` elige el lado del salto.
    pub fn seccion(&self, caso: usize, barra: usize, x: f64, lado_derecho: bool) -> Seccion3d {
        let rc = &self.casos[caso];
        let ba = &self.barras[barra];
        let f = &rc.fuerzas_extremo[barra];
        let ue = &rc.desplazamientos_extremo[barra];
        let cargas = &rc.cargas_locales[barra];
        let xy: Vec<CargaLocal> = cargas.iter().map(|c| c.xy).collect();
        let xz: Vec<CargaLocal> = cargas.iter().map(|c| c.xz).collect();
        let s_xy = seccion_plana(
            ba.l,
            ba.ea,
            ba.eiz,
            &plano_xy(f),
            &plano_xy(ue),
            &xy,
            x,
            lado_derecho,
        );
        let s_xz = seccion_plana(
            ba.l,
            ba.ea,
            ba.eiy,
            &plano_xz(f),
            &plano_xz(ue),
            &xz,
            x,
            lado_derecho,
        );
        let xi = x / ba.l;
        // En el plano x–z la barra plana equivalente tiene su eje z en -y local:
        // su momento es -My y su cortante, dM/dx, es -Vz.
        Seccion3d {
            x,
            n: s_xy.n,
            vy: s_xy.v,
            vz: -s_xz.v,
            t: -f[3],
            my: -s_xz.m,
            mz: s_xy.m,
            u: s_xy.u_local,
            v: s_xy.v_local,
            w: s_xz.v_local,
            rx: (1.0 - xi) * ue[3] + xi * ue[9],
        }
    }

    /// Diagrama de esfuerzos de una barra en `n_estaciones` puntos equidistantes
    /// (mínimo 2), más los puntos de las cargas puntuales (a ambos lados), los
    /// extremos de las trapezoidales y los puntos donde `Vy` o `Vz` se anulan,
    /// donde `Mz` o `My` son extremos.
    pub fn diagrama(&self, caso: usize, barra: usize, n_estaciones: usize) -> Vec<Seccion3d> {
        let l = self.barras[barra].l;
        let n_est = n_estaciones.max(2);
        let mut xs: Vec<(f64, bool)> = (0..n_est)
            .map(|k| (l * k as f64 / (n_est - 1) as f64, false))
            .collect();
        let mut quiebres = vec![0.0, l];
        for carga in &self.casos[caso].cargas_locales[barra] {
            match carga.xy {
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
                _ => {}
            }
        }
        quiebres.sort_by(f64::total_cmp);
        quiebres.dedup();
        for w in quiebres.windows(2) {
            let (x0, x1) = (w[0], w[1]);
            if x1 - x0 <= 0.0 {
                continue;
            }
            let s0 = self.seccion(caso, barra, x0, true);
            let sm = self.seccion(caso, barra, 0.5 * (x0 + x1), false);
            let s1 = self.seccion(caso, barra, x1, false);
            for t in raices_cuadratica_en_intervalo(s0.vy, sm.vy, s1.vy)
                .into_iter()
                .chain(raices_cuadratica_en_intervalo(s0.vz, sm.vz, s1.vz))
            {
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
