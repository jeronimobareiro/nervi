// SPDX-License-Identifier: GPL-3.0-or-later
//! Masas, análisis modal y espectro de respuesta del pórtico espacial
//! (Fase 2b, issues #16, #17 y #18).
//!
//! **Masas** ([`Masas3d`]): masas nodales `[mx, my, mz, Jx, Jy, Jz]` en ejes
//! globales, masa por unidad de longitud de las barras (concentrada o
//! consistente, [`TipoMasa`]) y masa a partir de las cargas verticales de los
//! casos (`m = -Fz · factor / g`, repartida a los nudos por estática).
//!
//! **Modal** ([`analizar_modal_3d`]): `[K]{φ} = ω²[M]{φ}` sobre los GDL libres.
//! Los modos se normalizan a masa (`φᵀ M φ = 1`), con la componente traslacional
//! de mayor valor absoluto positiva. Dos métodos con el mismo resultado:
//!
//! - *Denso exacto* (modelos con hasta [`LIMITE_DENSO`] GDL con masa): la
//!   condensación de los GDL sin masa es exacta (la flexibilidad `F_ss` de los
//!   GDL con masa sale de la factorización dispersa de `K`), y el problema
//!   `F_ss M_ss φ = μ φ`, con `μ = 1/ω²`, se lleva a la forma simétrica
//!   `M½ F M½ y = μ y` y se resuelve completo.
//! - *Lanczos con transformación espectral* (`σ = 0`, operador `K⁻¹M`, producto
//!   interno de `M` y reortogonalización completa) para modelos más grandes;
//!   usa la misma factorización de Cholesky dispersa de `faer`.
//!
//! **Espectro** ([`analizar_espectro_3d`]): para la dirección de excitación `r`,
//! `Γₙ = φₙᵀ M r`, respuesta de cada modo como una estática con
//! `uₙ = Γₙ Sa(Tₙ)/ωₙ² φₙ` y fuerzas `fₙ = Γₙ Sa(Tₙ) M φₙ`, y combinación SRSS
//! o CQC de cada magnitud (desplazamientos, reacciones, fuerzas de extremo,
//! esfuerzos en cada sección y cortante basal por modo).
//!
//! Fuentes: A. K. Chopra, *Dynamics of Structures*, 4.ª ed., Prentice Hall
//! 2012: cap. 10 (problema de autovalores, normalización a masa), §13.2
//! (factor de participación `Γₙ = Lₙ/Mₙ` y masa modal efectiva `Lₙ²/Mₙ`, cuya
//! suma es la masa total) y §13.7 (SRSS y CQC, coeficiente de correlación de
//! Der Kiureghian para amortiguamiento igual, ec. 13.7.10). J. S. Przemieniecki,
//! *Theory of Matrix Structural Analysis*, McGraw-Hill 1968, cap. 11 (matriz de
//! masa consistente de la barra espacial). T. Ericsson y A. Ruhe, «The spectral
//! transformation Lanczos method», *Math. Comp.* 35 (1980) 1251-1268, y K.-J.
//! Bathe, *Finite Element Procedures*, 1996, §11.5 (Lanczos para `K φ = λ M φ`).
//! Fórmulas implementadas a partir de esas fuentes, sin código de terceros.

use std::collections::BTreeMap;

use faer::linalg::solvers::Solve;
use faer::sparse::{SparseColMat, Triplet};
use faer::{Mat, Side};

use crate::analisis::resolver_sistema;
use crate::error::{ErrorNervi, Gdl, Resultado};
use crate::espacial::analisis::{
    gdl_barra, recuperar_caso, rigidez_reducida, Resultados3d, Seccion3d,
};
use crate::espacial::elemento::{
    matriz_a_nudos, rigidez_a_global_3d, BarraAnalisis3d, Mat12, Vec12,
};
use crate::espacial::modelo::{Modelo3d, TipoCargaBarra3d};
use crate::espacial::restricciones::Restricciones;
use crate::modelo::Ejes;

/// Cantidad máxima de GDL con masa para usar el método denso exacto en
/// [`MetodoModal::Automatico`]; por encima se usa Lanczos.
pub const LIMITE_DENSO: usize = 1500;

/// Cómo se reparte la masa de las barras.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum TipoMasa {
    /// `m L / 2` traslacional en cada extremo, en las tres direcciones; se
    /// desprecia la inercia rotacional de la barra.
    #[default]
    Concentrada,
    /// Matriz de masa consistente (Przemieniecki, op. cit., cap. 11): axil y
    /// transversal con las funciones de forma de la rigidez, torsión con el
    /// momento polar `Iy + Iz` y sin inercia rotacional de flexión. Las barras
    /// con liberaciones usan masa concentrada.
    Consistente,
}

/// Masas del modelo para el análisis dinámico. Se dan aparte del
/// [`Modelo3d`] para no cambiar el análisis estático ni su contrato de datos.
#[derive(Clone, Debug, PartialEq)]
pub struct Masas3d {
    /// Masas nodales `(nudo, [mx, my, mz, Jx, Jy, Jz])` en ejes globales.
    pub nodales: Vec<(usize, [f64; 6])>,
    /// Masa por unidad de longitud `(barra, m)` (por ejemplo, `ρ A`).
    pub lineales: Vec<(usize, f64)>,
    /// Masa a partir de las cargas de un caso `(caso, factor)`: la componente
    /// vertical hacia abajo (`-Z` global) de sus cargas nodales y en barras,
    /// multiplicada por `factor` y dividida por [`Self::gravedad`], como masa
    /// traslacional en las tres direcciones de los nudos. Las cargas en barras
    /// se reparten a sus nudos por estática (como reacciones de una viga
    /// simplemente apoyada).
    pub desde_casos: Vec<(usize, f64)>,
    /// Aceleración de la gravedad en las unidades del modelo (9.80665 m/s² por
    /// defecto).
    pub gravedad: f64,
    pub tipo: TipoMasa,
}

impl Default for Masas3d {
    fn default() -> Self {
        Masas3d {
            nodales: Vec::new(),
            lineales: Vec::new(),
            desde_casos: Vec::new(),
            gravedad: 9.80665,
            tipo: TipoMasa::Concentrada,
        }
    }
}

impl Masas3d {
    pub fn new() -> Self {
        Self::default()
    }

    fn validar(&self, modelo: &Modelo3d) -> Resultado<()> {
        let inv = |m: String| Err(ErrorNervi::ModeloInvalido(m));
        for (nudo, m) in &self.nodales {
            if *nudo >= modelo.nudos.len() {
                return inv(format!("masa en el nudo inexistente {nudo}"));
            }
            if m.iter().any(|v| !v.is_finite() || *v < 0.0) {
                return inv(format!(
                    "el nudo {nudo} tiene una masa negativa o no finita"
                ));
            }
        }
        for (barra, m) in &self.lineales {
            if *barra >= modelo.barras.len() {
                return inv(format!("masa en la barra inexistente {barra}"));
            }
            if !m.is_finite() || *m < 0.0 {
                return inv(format!(
                    "la barra {barra} tiene una masa por unidad de longitud negativa o no finita"
                ));
            }
        }
        for (caso, f) in &self.desde_casos {
            if *caso >= modelo.casos.len() {
                return inv(format!("masa desde el caso inexistente {caso}"));
            }
            if !f.is_finite() || *f < 0.0 {
                return inv(format!(
                    "el factor de masa del caso {caso} es negativo o no finito"
                ));
            }
        }
        if !self.desde_casos.is_empty() && !(self.gravedad.is_finite() && self.gravedad > 0.0) {
            return inv(format!(
                "la gravedad debe ser positiva (vale {})",
                self.gravedad
            ));
        }
        Ok(())
    }
}

/// Método de solución del problema de autovalores.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum MetodoModal {
    /// Denso exacto hasta [`LIMITE_DENSO`] GDL con masa y Lanczos por encima.
    #[default]
    Automatico,
    Denso,
    Lanczos,
}

/// Resultados del análisis modal.
#[derive(Clone, Debug)]
pub struct ResultadosModal3d {
    /// Frecuencias circulares `ω` (rad por unidad de tiempo), de menor a mayor.
    pub omegas: Vec<f64>,
    /// Periodos `T = 2π/ω`.
    pub periodos: Vec<f64>,
    /// Frecuencias `f = 1/T`.
    pub frecuencias: Vec<f64>,
    /// Formas modales normalizadas a masa, por nudo `[ux, uy, uz, rx, ry, rz]`
    /// (cero en los GDL restringidos).
    pub modos: Vec<Vec<[f64; 6]>>,
    /// Fuerzas de inercia unitarias `M φ` de cada modo, por nudo (solo en los
    /// GDL libres). Con ellas se calculan los factores de participación en
    /// cualquier dirección y la respuesta espectral.
    pub inercias: Vec<Vec<[f64; 6]>>,
    /// Factores de participación `Γ = φᵀ M r` en X, Y y Z.
    pub factores_participacion: Vec<[f64; 3]>,
    /// Masas modales efectivas `Γ²` en X, Y y Z.
    pub masas_efectivas: Vec<[f64; 3]>,
    /// Masa total que puede participar en X, Y y Z (`rᵀ M r` en los GDL libres):
    /// la suma de las masas efectivas de todos los modos.
    pub masa_total: [f64; 3],
    /// GDL libres sin rigidez ni masa fijados automáticamente.
    pub gdl_sin_rigidez: Vec<(usize, Gdl)>,
    /// GDL libres con masa: cota de la cantidad de modos con frecuencia finita.
    pub n_gdl_masa: usize,
    /// Método que se usó.
    pub metodo: MetodoModal,
    /// Masa de cada diafragma rígido, en el orden de [`Modelo3d::diafragmas`].
    pub diafragmas: Vec<MasaDiafragma>,
}

/// Masa de un diafragma rígido, concentrada en su maestro: la de sus nudos
/// (nodal, de las barras que llegan a ellos y desde los casos) con la inercia
/// de rotación de cada nudo respecto del maestro.
#[derive(Clone, Debug, PartialEq)]
pub struct MasaDiafragma {
    pub maestro: usize,
    /// Masa traslacional en X y en Y.
    pub masa: [f64; 2],
    /// Centro de masa `[x, y]` en ejes globales.
    pub centro_masa: [f64; 2],
    /// Inercia de rotación alrededor del eje vertical por el centro de masa.
    pub inercia: f64,
}

/// Matriz de masa consistente local 12×12 de una barra con masa `m` por unidad
/// de longitud, radio de giro polar `r2 = (Iy + Iz)/A` y largo `l`, GDL por
/// extremo `[u, v, w, θx, θy, θz]` (Przemieniecki, op. cit., cap. 11).
pub fn masa_consistente_local(m: f64, r2: f64, l: f64) -> Mat12 {
    let mut k = [[0.0; 12]; 12];
    let ax = m * l / 6.0;
    for (p, q, s) in [(0, 0, 2.0), (0, 6, 1.0), (6, 0, 1.0), (6, 6, 2.0)] {
        k[p][q] = s * ax;
        k[p + 3][q + 3] = s * ax * r2;
    }
    let c = m * l / 420.0;
    let flex = [
        [156.0, 22.0 * l, 54.0, -13.0 * l],
        [22.0 * l, 4.0 * l * l, 13.0 * l, -3.0 * l * l],
        [54.0, 13.0 * l, 156.0, -22.0 * l],
        [-13.0 * l, -3.0 * l * l, -22.0 * l, 4.0 * l * l],
    ];
    // Mismo mapeo que la rigidez: plano x–y (v, θz) igual que la barra plana;
    // plano x–z (w, θy) con θ2D = -θy.
    let gdl_xy = [1, 5, 7, 11];
    let gdl_xz = [2, 4, 8, 10];
    let signo_xz = [1.0, -1.0, 1.0, -1.0];
    for p in 0..4 {
        for q in 0..4 {
            k[gdl_xy[p]][gdl_xy[q]] = c * flex[p][q];
            k[gdl_xz[p]][gdl_xz[q]] = signo_xz[p] * signo_xz[q] * c * flex[p][q];
        }
    }
    k
}

/// Matriz de masa global como mapa disperso simétrico `(fila, columna) → valor`
/// sobre los GDL globales (incluidos los restringidos).
pub fn ensamblar_masa(
    modelo: &Modelo3d,
    masas: &Masas3d,
) -> Resultado<BTreeMap<(usize, usize), f64>> {
    modelo.validar()?;
    masas.validar(modelo)?;
    let mut mm: BTreeMap<(usize, usize), f64> = BTreeMap::new();
    let mut sumar = |p: usize, q: usize, v: f64| {
        if v != 0.0 {
            *mm.entry((p, q)).or_insert(0.0) += v;
        }
    };
    for (nudo, m) in &masas.nodales {
        for d in 0..6 {
            sumar(6 * nudo + d, 6 * nudo + d, m[d]);
        }
    }
    let mut lineal = vec![0.0; modelo.barras.len()];
    for (b, m) in &masas.lineales {
        lineal[*b] += m;
    }
    for (k, b) in modelo.barras.iter().enumerate() {
        let m = lineal[k];
        if m == 0.0 {
            continue;
        }
        let l = modelo.longitud(b);
        let gdl = gdl_barra(modelo, k);
        let consistente = masas.tipo == TipoMasa::Consistente && !b.liberaciones.iter().any(|x| *x);
        let brazos = [b.brazo_i, b.brazo_j];
        let mg = if consistente {
            let ejes = modelo.ejes_barra(b)?;
            rigidez_a_global_3d(&ejes, &masa_consistente_local(m, (b.iy + b.iz) / b.a, l))
        } else {
            let mut mc = [[0.0; 12]; 12];
            for d in [0, 1, 2, 6, 7, 8] {
                mc[d][d] = 0.5 * m * l;
            }
            mc
        };
        // Con brazos rígidos la masa está en las caras y se lleva a los nudos
        // con la misma transformación que la rigidez.
        let mg = matriz_a_nudos(&brazos, &mg);
        for p in 0..12 {
            for q in 0..12 {
                sumar(gdl[p], gdl[q], mg[p][q]);
            }
        }
    }
    // Masa desde las cargas verticales de los casos.
    let mut desde_cargas = vec![0.0; modelo.nudos.len()];
    for &(c, factor) in &masas.desde_casos {
        let escala = factor / masas.gravedad;
        let caso = &modelo.casos[c];
        for (nudo, f) in &caso.nodales {
            desde_cargas[*nudo] -= f[2] * escala;
        }
        for cb in &caso.en_barras {
            let b = &modelo.barras[cb.barra];
            let l = modelo.longitud(b);
            let ejes = modelo.ejes_barra(b)?;
            // Componente global Z de un vector dado en los ejes de la carga.
            let z = |q: [f64; 3]| match cb.ejes {
                Ejes::Global => q[2],
                Ejes::Local => (0..3).map(|i| ejes[i][2] * q[i]).sum(),
            };
            // Resultante vertical W y su momento respecto del nudo i.
            let (w, mom) = match cb.tipo {
                TipoCargaBarra3d::Uniforme { q } => {
                    let qz = z(q);
                    (qz * l, qz * l * l / 2.0)
                }
                TipoCargaBarra3d::Puntual { a, p } => {
                    let pz = z(p);
                    (pz, pz * a)
                }
                TipoCargaBarra3d::Trapezoidal { a, b: fin, q1, q2 } => {
                    let (z1, z2) = (z(q1), z(q2));
                    let d = fin - a;
                    (
                        0.5 * (z1 + z2) * d,
                        d * (z1 * (2.0 * a + fin) + z2 * (a + 2.0 * fin)) / 6.0,
                    )
                }
            };
            // Punto de la resultante sobre la parte flexible, repartido entre
            // los nudos según su posición en la recta que los une (con brazos
            // rígidos la parte flexible no empieza en el nudo).
            let wj = if w == 0.0 {
                0.0
            } else if b.tiene_brazos() {
                let (pi, _) = modelo.extremos(b);
                let (ni, nj) = (modelo.nudos[b.nudo_i], modelo.nudos[b.nudo_j]);
                let s = mom / w;
                let p: [f64; 3] = std::array::from_fn(|d| pi[d] + s * ejes[0][d] - ni[d]);
                let e: [f64; 3] = std::array::from_fn(|d| nj[d] - ni[d]);
                let t = (0..3).map(|d| p[d] * e[d]).sum::<f64>()
                    / (0..3).map(|d| e[d] * e[d]).sum::<f64>();
                w * t.clamp(0.0, 1.0)
            } else {
                mom / l
            };
            desde_cargas[b.nudo_i] -= (w - wj) * escala;
            desde_cargas[b.nudo_j] -= wj * escala;
        }
    }
    let escala_m = desde_cargas.iter().fold(0.0_f64, |a, v| a.max(v.abs()));
    for (nudo, m) in desde_cargas.iter().enumerate() {
        if *m < -1e-12 * escala_m {
            return Err(ErrorNervi::ModeloInvalido(format!(
                "las cargas de los casos dan masa negativa en el nudo {nudo} \
                 (cargas netas hacia arriba)"
            )));
        }
        if *m > 0.0 {
            for d in 0..3 {
                sumar(6 * nudo + d, 6 * nudo + d, *m);
            }
        }
    }
    Ok(mm)
}

/// Análisis modal: los `n_modos` modos de menor frecuencia (o todos los que
/// tengan frecuencia finita, si son menos).
pub fn analizar_modal_3d(
    modelo: &Modelo3d,
    masas: &Masas3d,
    n_modos: usize,
    metodo: MetodoModal,
) -> Resultado<ResultadosModal3d> {
    let mm = ensamblar_masa(modelo, masas)?;
    if n_modos == 0 {
        return Err(ErrorNervi::ModeloInvalido(
            "hay que pedir al menos un modo".into(),
        ));
    }
    let n_gdl = modelo.n_gdl();
    let barras: Vec<BarraAnalisis3d> = modelo
        .barras
        .iter()
        .map(|b| BarraAnalisis3d::new(b, modelo.longitud(b), modelo.ejes_barra(b)?))
        .collect::<Resultado<_>>()?;

    // Rigidez y masa llevadas a los GDL independientes (diafragmas rígidos).
    let rest = Restricciones::new(modelo);
    let rigidez = rigidez_reducida(modelo, &barras, &rest);
    let mut m_red: BTreeMap<(usize, usize), f64> = BTreeMap::new();
    for (&(p, q), &v) in &mm {
        rest.transformar(p, q, v, &mut |a, b, x| {
            if x != 0.0 {
                *m_red.entry((a, b)).or_insert(0.0) += x;
            }
        });
    }

    // Diagonal de rigidez y de masa para decidir qué GDL quedan libres.
    let mut diag = vec![0.0; n_gdl];
    for &(a, b, v) in &rigidez {
        if a == b {
            diag[a] += v;
        }
    }
    let diag_max = diag.iter().fold(0.0_f64, |m, v| m.max(v.abs()));
    let mut masa_diag = vec![0.0; n_gdl];
    for (&(p, q), &v) in &m_red {
        if p == q {
            masa_diag[p] += v;
        }
    }
    let mut restringido = vec![false; n_gdl];
    let mut gdl_sin_rigidez = Vec::new();
    for g in 0..n_gdl {
        let (nudo, d) = (g / 6, g % 6);
        if rest.dependiente[g] || modelo.restringido(nudo, d) {
            restringido[g] = true;
        } else if diag[g] <= 1e-14 * diag_max {
            if masa_diag[g] > 0.0 {
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
    let mut gdl_global = Vec::new();
    for g in 0..n_gdl {
        if !restringido[g] {
            libre_idx[g] = gdl_global.len();
            gdl_global.push(g);
        }
    }
    let n_libres = gdl_global.len();

    let mut tripletas = Vec::with_capacity(rigidez.len() / 2 + n_libres);
    for &(a, b, v) in &rigidez {
        let (la, lb) = (libre_idx[a], libre_idx[b]);
        if la != usize::MAX && lb != usize::MAX && lb <= la {
            tripletas.push(Triplet::new(la, lb, v));
        }
    }
    let diag_libre_max = gdl_global.iter().fold(0.0_f64, |m, &g| m.max(diag[g]));

    // Masa sobre los GDL libres, por filas.
    let mut filas_m: Vec<Vec<(usize, f64)>> = vec![Vec::new(); n_libres];
    for (&(p, q), &v) in &m_red {
        let (lp, lq) = (libre_idx[p], libre_idx[q]);
        if lp != usize::MAX && lq != usize::MAX {
            filas_m[lp].push((lq, v));
        }
    }
    let con_masa: Vec<usize> = (0..n_libres).filter(|&i| !filas_m[i].is_empty()).collect();
    let s = con_masa.len();
    if s == 0 {
        return Err(ErrorNervi::ModeloInvalido(
            "el modelo no tiene masa en ningún GDL libre".into(),
        ));
    }
    let metodo = match metodo {
        MetodoModal::Automatico if s <= LIMITE_DENSO => MetodoModal::Denso,
        MetodoModal::Automatico => MetodoModal::Lanczos,
        otro => otro,
    };
    let producto_m = |v: &[f64]| -> Vec<f64> {
        filas_m
            .iter()
            .map(|fila| fila.iter().map(|&(q, m)| m * v[q]).sum())
            .collect()
    };

    // Pares (μ = 1/ω², φ en GDL libres, M φ en GDL libres), μ de mayor a menor.
    let pares: Vec<ParModal> = match metodo {
        MetodoModal::Denso => {
            let mut rhs = Mat::<f64>::zeros(n_libres, s);
            for (a, &i) in con_masa.iter().enumerate() {
                rhs[(i, a)] = 1.0;
            }
            let x = resolver_sistema(&tripletas, rhs, &gdl_global, diag_libre_max, 6)?;
            modal_denso(&x, &con_masa, &filas_m)?
        }
        _ => {
            // Primero se resuelve un sistema con resolver_sistema, que da el
            // diagnóstico de mecanismo si K no es definida positiva.
            let mut prueba = Mat::<f64>::zeros(n_libres, 1);
            for &i in &con_masa {
                prueba[(i, 0)] = filas_m[i].iter().map(|x| x.1).sum();
            }
            resolver_sistema(&tripletas, prueba, &gdl_global, diag_libre_max, 6)?;
            let k_ff = SparseColMat::<usize, f64>::try_new_from_triplets(
                n_libres, n_libres, &tripletas,
            )
            .map_err(|e| ErrorNervi::Numerico(format!("no se pudo armar la matriz: {e:?}")))?;
            let llt = k_ff.sp_cholesky(Side::Lower).map_err(|_| {
                ErrorNervi::Numerico("la matriz de rigidez no es definida positiva".into())
            })?;
            let resolver = |v: &[f64]| -> Vec<f64> {
                let mut x = Mat::<f64>::from_fn(n_libres, 1, |i, _| v[i]);
                llt.solve_in_place(x.as_mut());
                (0..n_libres).map(|i| x[(i, 0)]).collect()
            };
            lanczos(n_libres, s, n_modos, &resolver, &producto_m)?
        }
    };

    let mu_max = pares.first().map_or(0.0, |p| p.0);
    let mut omegas = Vec::new();
    let mut modos = Vec::new();
    let mut inercias = Vec::new();
    let mut factores = Vec::new();
    let mut efectivas = Vec::new();
    for (mu, mut phi, mut mphi) in pares.into_iter() {
        if omegas.len() == n_modos || mu.is_nan() || mu <= 1e-12 * mu_max {
            break;
        }
        // Normalizar a masa y fijar el signo con la traslación de mayor valor.
        let norma: f64 = phi
            .iter()
            .zip(&mphi)
            .map(|(a, b)| a * b)
            .sum::<f64>()
            .sqrt();
        let mut mayor = (0.0_f64, 1.0);
        for (i, &g) in gdl_global.iter().enumerate() {
            if g % 6 < 3 && phi[i].abs() > mayor.0 {
                mayor = (phi[i].abs(), phi[i].signum());
            }
        }
        let signo = mayor.1 / norma;
        phi.iter_mut().for_each(|v| *v *= signo);
        mphi.iter_mut().for_each(|v| *v *= signo);
        let mut u = vec![0.0; n_gdl];
        let mut inercia = vec![[0.0; 6]; modelo.nudos.len()];
        let mut gamma = [0.0; 3];
        for (i, &g) in gdl_global.iter().enumerate() {
            u[g] = phi[i];
            inercia[g / 6][g % 6] = mphi[i];
            if g % 6 < 3 {
                gamma[g % 6] += mphi[i];
            }
        }
        rest.expandir(&mut u);
        let modo: Vec<[f64; 6]> = (0..modelo.nudos.len())
            .map(|n| std::array::from_fn(|d| u[6 * n + d]))
            .collect();
        omegas.push(1.0 / mu.sqrt());
        modos.push(modo);
        inercias.push(inercia);
        factores.push(gamma);
        efectivas.push(gamma.map(|x| x * x));
    }
    let mut masa_total = [0.0; 3];
    for (&(p, q), &v) in &m_red {
        if p % 6 == q % 6 && p % 6 < 3 && libre_idx[p] != usize::MAX && libre_idx[q] != usize::MAX {
            masa_total[p % 6] += v;
        }
    }
    let periodos: Vec<f64> = omegas
        .iter()
        .map(|w| 2.0 * std::f64::consts::PI / w)
        .collect();
    let diafragmas = modelo
        .diafragmas
        .iter()
        .map(|d| {
            let m = d.maestro;
            let pm = modelo.nudos[m];
            let val =
                |a: usize, b: usize| m_red.get(&(6 * m + a, 6 * m + b)).copied().unwrap_or(0.0);
            let (mx, my, jz) = (val(0, 0), val(1, 1), val(5, 5));
            // M̂(ux, rz) = -Σ m dy y M̂(uy, rz) = Σ m dx.
            let ex = if my > 0.0 { val(1, 5) / my } else { 0.0 };
            let ey = if mx > 0.0 { -val(0, 5) / mx } else { 0.0 };
            MasaDiafragma {
                maestro: m,
                masa: [mx, my],
                centro_masa: [pm[0] + ex, pm[1] + ey],
                inercia: jz - 0.5 * (mx + my) * (ex * ex + ey * ey),
            }
        })
        .collect();
    Ok(ResultadosModal3d {
        diafragmas,
        frecuencias: periodos.iter().map(|t| 1.0 / t).collect(),
        periodos,
        omegas,
        modos,
        inercias,
        factores_participacion: factores,
        masas_efectivas: efectivas,
        masa_total,
        gdl_sin_rigidez,
        n_gdl_masa: s,
        metodo,
    })
}

/// `(μ = 1/ω², φ, M φ)` sobre los GDL libres.
type ParModal = (f64, Vec<f64>, Vec<f64>);

/// Autovalores y autovectores de una matriz simétrica densa, de menor a mayor.
fn autovalores_simetrica(a: &Mat<f64>) -> Resultado<(Vec<f64>, Mat<f64>)> {
    let evd = a.self_adjoint_eigen(Side::Lower).map_err(|e| {
        ErrorNervi::Numerico(format!("no convergió el cálculo de autovalores: {e:?}"))
    })?;
    let n = a.nrows();
    let vals = (0..n).map(|i| evd.S().column_vector()[i]).collect();
    Ok((vals, evd.U().to_owned()))
}

/// Método denso exacto. `x` son las columnas de `K⁻¹` de los GDL con masa.
fn modal_denso(
    x: &Mat<f64>,
    con_masa: &[usize],
    filas_m: &[Vec<(usize, f64)>],
) -> Resultado<Vec<ParModal>> {
    let s = con_masa.len();
    let n = x.nrows();
    let mut pos = vec![usize::MAX; n];
    for (a, &i) in con_masa.iter().enumerate() {
        pos[i] = a;
    }
    let f = Mat::<f64>::from_fn(s, s, |a, b| {
        0.5 * (x[(con_masa[a], b)] + x[(con_masa[b], a)])
    });
    let mut m_ss = Mat::<f64>::zeros(s, s);
    for (a, &i) in con_masa.iter().enumerate() {
        for &(q, v) in &filas_m[i] {
            m_ss[(a, pos[q])] = v;
        }
    }
    // M½ por descomposición espectral (M es semidefinida positiva).
    let (lm, qm) = autovalores_simetrica(&m_ss)?;
    let lm_max = lm.iter().fold(0.0_f64, |a, v| a.max(*v));
    let raiz: Vec<f64> = lm
        .iter()
        .map(|v| if *v > 1e-14 * lm_max { v.sqrt() } else { 0.0 })
        .collect();
    let mh = Mat::<f64>::from_fn(s, s, |a, b| {
        (0..s).map(|k| qm[(a, k)] * raiz[k] * qm[(b, k)]).sum()
    });
    let b = &mh * &f * &mh;
    let b = Mat::<f64>::from_fn(s, s, |i, j| 0.5 * (b[(i, j)] + b[(j, i)]));
    let (mu, y) = autovalores_simetrica(&b)?;
    // φ = X M½ y / μ (normalizado a masa) y M φ = E_S M½ y.
    let w = &mh * &y;
    let phi_todos = x * &w;
    let mut pares = Vec::with_capacity(s);
    for k in (0..s).rev() {
        let mut mphi = vec![0.0; n];
        for (a, &i) in con_masa.iter().enumerate() {
            mphi[i] = w[(a, k)];
        }
        let phi = (0..n)
            .map(|i| phi_todos[(i, k)] / mu[k].max(f64::MIN_POSITIVE))
            .collect();
        pares.push((mu[k], phi, mphi));
    }
    Ok(pares)
}

/// Lanczos con transformación espectral (σ = 0) sobre `K⁻¹ M` con el producto
/// interno de `M`, reortogonalización completa y bloqueo de los modos ya
/// hallados (Ericsson y Ruhe, op. cit.; Bathe, op. cit., §11.5).
///
/// El Lanczos de un solo vector encuentra una sola copia de cada autovalor
/// repetido (frecuencias iguales en X e Y de un edificio simétrico, por
/// ejemplo). Por eso se repite con un vector inicial nuevo, ortogonal en `M` a
/// los modos ya hallados, hasta que una corrida no aporta ningún modo entre los
/// `n_modos` de menor frecuencia.
fn lanczos(
    n: usize,
    rango: usize,
    n_modos: usize,
    resolver: &dyn Fn(&[f64]) -> Vec<f64>,
    producto_m: &dyn Fn(&[f64]) -> Vec<f64>,
) -> Resultado<Vec<ParModal>> {
    let mut hallados: Vec<ParModal> = Vec::new();
    let mut semilla: u64 = 0x9E37_79B9_7F4A_7C15;
    while hallados.len() < rango {
        let nuevos = corrida_lanczos(
            n,
            rango - hallados.len(),
            n_modos,
            resolver,
            producto_m,
            &hallados,
            &mut semilla,
        )?;
        let umbral = if hallados.len() >= n_modos {
            hallados[n_modos - 1].0
        } else {
            0.0
        };
        if !nuevos.iter().any(|p| p.0 > umbral) {
            break;
        }
        hallados.extend(nuevos);
        hallados.sort_by(|a, b| b.0.total_cmp(&a.0));
    }
    Ok(hallados)
}

/// Una corrida de Lanczos en el complemento (ortogonal en `M`) de los modos
/// `bloqueados`. Agranda el subespacio hasta que convergen los autovalores
/// mayores de `K⁻¹M` pedidos y devuelve solo los pares convergidos.
#[allow(clippy::too_many_arguments)]
fn corrida_lanczos(
    n: usize,
    rango: usize,
    n_modos: usize,
    resolver: &dyn Fn(&[f64]) -> Vec<f64>,
    producto_m: &dyn Fn(&[f64]) -> Vec<f64>,
    bloqueados: &[ParModal],
    semilla: &mut u64,
) -> Resultado<Vec<ParModal>> {
    let punto = |a: &[f64], b: &[f64]| -> f64 { a.iter().zip(b).map(|(x, y)| x * y).sum() };
    // Quita de w sus componentes en los vectores (q, M q) dados.
    let ortogonalizar = |w: &mut Vec<f64>, q: &[Vec<f64>], mq: &[Vec<f64>]| {
        for (qi, mqi) in q.iter().zip(mq) {
            let c = punto(mqi, w);
            for (x, y) in w.iter_mut().zip(qi) {
                *x -= c * y;
            }
        }
    };
    let qb: Vec<Vec<f64>> = bloqueados.iter().map(|p| p.1.clone()).collect();
    let mqb: Vec<Vec<f64>> = bloqueados.iter().map(|p| p.2.clone()).collect();
    // Vector inicial seudoaleatorio determinista, llevado al rango de K⁻¹M.
    let r0: Vec<f64> = (0..n)
        .map(|_| {
            *semilla ^= *semilla << 13;
            *semilla ^= *semilla >> 7;
            *semilla ^= *semilla << 17;
            (*semilla >> 11) as f64 / (1u64 << 53) as f64 + 0.5
        })
        .collect();
    let mut v0 = resolver(&producto_m(&r0));
    for _ in 0..2 {
        ortogonalizar(&mut v0, &qb, &mqb);
    }
    let mut pasos = rango.min((2 * n_modos).max(n_modos + 20));
    loop {
        let mut q: Vec<Vec<f64>> = Vec::with_capacity(pasos);
        let mut mq: Vec<Vec<f64>> = Vec::with_capacity(pasos);
        let mut alfa: Vec<f64> = Vec::new();
        let mut beta: Vec<f64> = Vec::new();
        let mv = producto_m(&v0);
        let nv = punto(&v0, &mv).max(0.0).sqrt();
        let escala_v0 = v0.iter().fold(0.0_f64, |m, x| m.max(x.abs()));
        if nv.is_nan() || nv <= 1e-12 * escala_v0 || nv == 0.0 {
            // El complemento no tiene masa: no quedan modos.
            return Ok(Vec::new());
        }
        q.push(v0.iter().map(|x| x / nv).collect());
        mq.push(mv.iter().map(|x| x / nv).collect());
        let mut beta_final = 0.0;
        let mut invariante = false;
        for j in 0..pasos {
            let mut w = resolver(&mq[j]);
            let a = punto(&mq[j], &w);
            alfa.push(a);
            for (k, x) in w.iter_mut().enumerate() {
                *x -= a * q[j][k];
                if j > 0 {
                    *x -= beta[j - 1] * q[j - 1][k];
                }
            }
            for _ in 0..2 {
                ortogonalizar(&mut w, &q, &mq);
                ortogonalizar(&mut w, &qb, &mqb);
            }
            let mw = producto_m(&w);
            let b = punto(&w, &mw).max(0.0).sqrt();
            let escala = alfa.iter().fold(0.0_f64, |m, v| m.max(v.abs()));
            if j + 1 == pasos {
                beta_final = b;
                break;
            }
            if b <= 1e-12 * escala {
                invariante = true;
                break;
            }
            beta.push(b);
            q.push(w.iter().map(|x| x / b).collect());
            mq.push(mw.iter().map(|x| x / b).collect());
        }
        let m = alfa.len();
        let t = Mat::<f64>::from_fn(m, m, |i, j| {
            if i == j {
                alfa[i]
            } else if i == j + 1 {
                beta[j]
            } else if j == i + 1 {
                beta[i]
            } else {
                0.0
            }
        });
        let (theta, y) = autovalores_simetrica(&t)?;
        let theta_max = theta.iter().fold(0.0_f64, |a, v| a.max(v.abs()));
        let residuo_ok =
            |c: usize| invariante || (beta_final * y[(m - 1, c)]).abs() <= 1e-10 * theta_max;
        let quiero = n_modos.min(m);
        let convergido = (0..quiero).all(|k| residuo_ok(m - 1 - k));
        if convergido || invariante || pasos >= rango {
            let exacto = invariante || pasos >= rango;
            let mut pares = Vec::with_capacity(m);
            for c in (0..m).rev() {
                if !(exacto || residuo_ok(c)) {
                    continue;
                }
                let mut phi = vec![0.0; n];
                for (i, qi) in q.iter().enumerate() {
                    let yi = y[(i, c)];
                    for (k, x) in phi.iter_mut().enumerate() {
                        *x += yi * qi[k];
                    }
                }
                let mphi = producto_m(&phi);
                pares.push((theta[c], phi, mphi));
            }
            return Ok(pares);
        }
        pasos = rango.min(2 * pasos);
    }
}

/// Espectro de respuesta de diseño: aceleración espectral `Sa` en función del
/// periodo, interpolada linealmente entre los puntos dados. Fuera del rango se
/// toma el valor del extremo más cercano.
#[derive(Clone, Debug, PartialEq)]
pub struct Espectro {
    pub periodos: Vec<f64>,
    pub aceleraciones: Vec<f64>,
}

impl Espectro {
    pub fn new(periodos: Vec<f64>, aceleraciones: Vec<f64>) -> Resultado<Self> {
        let inv = |m: &str| Err(ErrorNervi::ModeloInvalido(m.into()));
        if periodos.is_empty() || periodos.len() != aceleraciones.len() {
            return inv(
                "el espectro necesita la misma cantidad (no nula) de periodos y aceleraciones",
            );
        }
        if periodos.iter().any(|t| !t.is_finite() || *t < 0.0)
            || periodos.windows(2).any(|w| w[1] <= w[0])
        {
            return inv(
                "los periodos del espectro deben ser no negativos y estrictamente crecientes",
            );
        }
        if aceleraciones.iter().any(|a| !a.is_finite() || *a < 0.0) {
            return inv("las aceleraciones del espectro deben ser no negativas y finitas");
        }
        Ok(Espectro {
            periodos,
            aceleraciones,
        })
    }

    /// Aceleración espectral para el periodo `t`.
    pub fn sa(&self, t: f64) -> f64 {
        let (p, a) = (&self.periodos, &self.aceleraciones);
        if t <= p[0] {
            return a[0];
        }
        for k in 1..p.len() {
            if t <= p[k] {
                let s = (t - p[k - 1]) / (p[k] - p[k - 1]);
                return a[k - 1] + s * (a[k] - a[k - 1]);
            }
        }
        a[a.len() - 1]
    }
}

/// Regla de combinación modal.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum CombinacionModal {
    /// Raíz de la suma de los cuadrados.
    Srss,
    /// Combinación cuadrática completa con el coeficiente de Der Kiureghian.
    #[default]
    Cqc,
}

/// Coeficiente de correlación CQC entre dos modos de frecuencias `wi`, `wj` con
/// el mismo amortiguamiento `zeta` (Chopra, op. cit., ec. 13.7.10):
/// `ρ = 8ζ² (1 + β) β^1.5 / ((1 - β²)² + 4ζ² β (1 + β)²)`, `β = ωi/ωj`.
pub fn coeficiente_cqc(wi: f64, wj: f64, zeta: f64) -> f64 {
    if wi == wj {
        return 1.0;
    }
    let b = wi / wj;
    let z2 = zeta * zeta;
    8.0 * z2 * (1.0 + b) * b.powf(1.5) / ((1.0 - b * b).powi(2) + 4.0 * z2 * b * (1.0 + b).powi(2))
}

/// Resultados de un análisis por espectro de respuesta en una dirección.
#[derive(Clone, Debug)]
pub struct ResultadosEspectro3d {
    /// Aceleración espectral `Sa(Tₙ)` de cada modo.
    pub aceleraciones: Vec<f64>,
    /// Factor de participación de cada modo en la dirección de excitación.
    pub factores: Vec<f64>,
    /// Coeficientes de correlación `ρᵢⱼ` (identidad en SRSS).
    pub correlacion: Vec<Vec<f64>>,
    /// Respuesta de cada modo, con signo, como un caso por modo (sirve para
    /// [`Resultados3d::seccion`] y [`Resultados3d::diagrama`]).
    pub modal: Resultados3d,
    /// Cortante basal `[Vx, Vy, Vz]` de cada modo, con signo: suma de las
    /// reacciones.
    pub cortante_basal_modal: Vec<[f64; 3]>,
    /// Magnitudes combinadas (valores absolutos).
    pub desplazamientos: Vec<[f64; 6]>,
    pub reacciones: Vec<[f64; 6]>,
    pub fuerzas_extremo: Vec<Vec12>,
    pub cortante_basal: [f64; 3],
}

impl ResultadosEspectro3d {
    /// Combina los valores modales de una magnitud: `√(Σᵢ Σⱼ ρᵢⱼ rᵢ rⱼ)`.
    pub fn combinar(&self, r: &[f64]) -> f64 {
        combinar(&self.correlacion, r)
    }

    /// Esfuerzos y desplazamientos combinados (valores absolutos) en la
    /// sección `x` de una barra.
    pub fn seccion(&self, barra: usize, x: f64) -> Seccion3d {
        let ss: Vec<Seccion3d> = (0..self.modal.casos.len())
            .map(|c| self.modal.seccion(c, barra, x, false))
            .collect();
        let comb = |f: fn(&Seccion3d) -> f64| -> f64 {
            let r: Vec<f64> = ss.iter().map(f).collect();
            self.combinar(&r)
        };
        Seccion3d {
            x,
            n: comb(|s| s.n),
            vy: comb(|s| s.vy),
            vz: comb(|s| s.vz),
            t: comb(|s| s.t),
            my: comb(|s| s.my),
            mz: comb(|s| s.mz),
            u: comb(|s| s.u),
            v: comb(|s| s.v),
            w: comb(|s| s.w),
            rx: comb(|s| s.rx),
        }
    }

    /// Diagrama combinado en `n_estaciones` puntos equidistantes (mínimo 2).
    pub fn diagrama(&self, barra: usize, n_estaciones: usize) -> Vec<Seccion3d> {
        let l = self.modal.barras[barra].l;
        let n = n_estaciones.max(2);
        (0..n)
            .map(|k| self.seccion(barra, l * k as f64 / (n - 1) as f64))
            .collect()
    }
}

fn combinar(rho: &[Vec<f64>], r: &[f64]) -> f64 {
    let mut s = 0.0;
    for i in 0..r.len() {
        s += r[i] * r[i];
        for j in (i + 1)..r.len() {
            s += 2.0 * rho[i][j] * r[i] * r[j];
        }
    }
    s.max(0.0).sqrt()
}

/// Análisis por espectro de respuesta con los modos de `modal` (calculados con
/// el mismo modelo). `direccion` es el vector de la excitación en ejes globales
/// (`[1, 0, 0]` para X; se usa tal cual, sin normalizar).
pub fn analizar_espectro_3d(
    modelo: &Modelo3d,
    modal: &ResultadosModal3d,
    espectro: &Espectro,
    direccion: [f64; 3],
    amortiguamiento: f64,
    combinacion: CombinacionModal,
) -> Resultado<ResultadosEspectro3d> {
    modelo.validar()?;
    let inv = |m: String| Err(ErrorNervi::ModeloInvalido(m));
    let n_nudos = modelo.nudos.len();
    let n_modos = modal.omegas.len();
    if n_modos == 0 {
        return inv("no hay modos para el análisis espectral".into());
    }
    if modal.modos.len() != n_modos
        || modal.inercias.len() != n_modos
        || modal
            .modos
            .iter()
            .chain(&modal.inercias)
            .any(|m| m.len() != n_nudos)
    {
        return inv("los modos no corresponden al modelo".into());
    }
    if modal.omegas.iter().any(|w| !(w.is_finite() && *w > 0.0)) {
        return inv("las frecuencias de los modos deben ser positivas".into());
    }
    if !direccion.iter().all(|v| v.is_finite()) || direccion.iter().all(|v| *v == 0.0) {
        return inv("la dirección de la excitación debe ser un vector no nulo".into());
    }
    if !(amortiguamiento.is_finite() && (0.0..1.0).contains(&amortiguamiento)) {
        return inv(format!(
            "el amortiguamiento debe estar en [0, 1) (vale {amortiguamiento})"
        ));
    }
    let barras: Vec<BarraAnalisis3d> = modelo
        .barras
        .iter()
        .map(|b| BarraAnalisis3d::new(b, modelo.longitud(b), modelo.ejes_barra(b)?))
        .collect::<Resultado<_>>()?;
    let n_gdl = modelo.n_gdl();
    let feq = vec![[0.0; 12]; barras.len()];
    let rest = Restricciones::new(modelo);

    let mut aceleraciones = Vec::with_capacity(n_modos);
    let mut factores = Vec::with_capacity(n_modos);
    let mut casos = Vec::with_capacity(n_modos);
    let mut cortante_basal_modal = Vec::with_capacity(n_modos);
    for k in 0..n_modos {
        let w = modal.omegas[k];
        let sa = espectro.sa(2.0 * std::f64::consts::PI / w);
        let gamma: f64 = modal.inercias[k]
            .iter()
            .map(|m| (0..3).map(|d| m[d] * direccion[d]).sum::<f64>())
            .sum();
        let escala_f = gamma * sa;
        let escala_u = escala_f / (w * w);
        let mut u = vec![0.0; n_gdl];
        let mut f = vec![0.0; n_gdl];
        for n in 0..n_nudos {
            for d in 0..6 {
                u[6 * n + d] = modal.modos[k][n][d] * escala_u;
                f[6 * n + d] = modal.inercias[k][n][d] * escala_f;
            }
        }
        let rc = recuperar_caso(
            modelo,
            &barras,
            &rest,
            &u,
            &feq,
            &f,
            vec![Vec::new(); barras.len()],
        );
        let mut v = [0.0; 3];
        for r in &rc.reacciones {
            for d in 0..3 {
                v[d] += r[d];
            }
        }
        cortante_basal_modal.push(v);
        aceleraciones.push(sa);
        factores.push(gamma);
        casos.push(rc);
    }
    let correlacion: Vec<Vec<f64>> = (0..n_modos)
        .map(|i| {
            (0..n_modos)
                .map(|j| match combinacion {
                    CombinacionModal::Srss => (i == j) as u8 as f64,
                    CombinacionModal::Cqc => {
                        coeficiente_cqc(modal.omegas[i], modal.omegas[j], amortiguamiento)
                    }
                })
                .collect()
        })
        .collect();
    let comb = |r: &dyn Fn(usize) -> f64| -> f64 {
        let v: Vec<f64> = (0..n_modos).map(r).collect();
        combinar(&correlacion, &v)
    };
    let desplazamientos = (0..n_nudos)
        .map(|n| std::array::from_fn(|d| comb(&|k| casos[k].desplazamientos[n][d])))
        .collect();
    let reacciones = (0..n_nudos)
        .map(|n| std::array::from_fn(|d| comb(&|k| casos[k].reacciones[n][d])))
        .collect();
    let fuerzas_extremo = (0..barras.len())
        .map(|b| std::array::from_fn(|d| comb(&|k| casos[k].fuerzas_extremo[b][d])))
        .collect();
    let cortante_basal = std::array::from_fn(|d| comb(&|k| cortante_basal_modal[k][d]));
    Ok(ResultadosEspectro3d {
        aceleraciones,
        factores,
        correlacion,
        modal: Resultados3d {
            casos,
            gdl_sin_rigidez: modal.gdl_sin_rigidez.clone(),
            barras,
        },
        cortante_basal_modal,
        desplazamientos,
        reacciones,
        fuerzas_extremo,
        cortante_basal,
    })
}
