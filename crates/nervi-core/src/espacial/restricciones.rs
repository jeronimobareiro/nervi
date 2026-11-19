// SPDX-License-Identifier: GPL-3.0-or-later
//! Diafragmas rígidos de piso por transformación maestro-esclavo (issue #14).
//!
//! Cada GDL global se escribe como combinación lineal de GDL independientes,
//! `u = T û`. En un diafragma (plano XY), los GDL `ux`, `uy` y `rz` de un
//! esclavo con `(dx, dy) = (x - x_m, y - y_m)` respecto del maestro son
//!
//! ```text
//! ux = ux_m - dy rz_m,    uy = uy_m + dx rz_m,    rz = rz_m,
//! ```
//!
//! y todos los demás GDL son independientes (`T` es la identidad). La rigidez,
//! la masa y las cargas se llevan a los GDL independientes con `Tᵀ K T`,
//! `Tᵀ M T` y `Tᵀ F`: los GDL esclavos se eliminan del sistema (no hay
//! penalización) y la masa de los nudos del piso queda concentrada en el
//! maestro, con su inercia de rotación `Σ m (dx² + dy²)`.
//!
//! Fuentes: E. L. Wilson, *Three-Dimensional Static and Dynamic Analysis of
//! Structures*, 3.ª ed., Computers and Structures 2002, capítulo «Boundary
//! Conditions and General Constraints» (ecuaciones del diafragma rígido), y
//! R. D. Cook, D. S. Malkus, M. E. Plesha y R. J. Witt, *Concepts and
//! Applications of Finite Element Analysis*, 4.ª ed., Wiley 2002, capítulo de
//! restricciones («constraints», eliminación por transformación). Es
//! cinemática de cuerpo rígido en el plano con giros pequeños; implementación
//! propia.

use crate::espacial::modelo::Modelo3d;

/// Relación `u = T û` entre los GDL globales y los independientes.
#[derive(Clone, Debug)]
pub(crate) struct Restricciones {
    /// Para cada GDL global, la lista `(GDL independiente, coeficiente)`. Un GDL
    /// independiente se tiene a sí mismo con coeficiente 1.
    pub mapa: Vec<Vec<(usize, f64)>>,
    /// `true` en los GDL esclavos (eliminados del sistema).
    pub dependiente: Vec<bool>,
}

impl Restricciones {
    /// Arma la transformación de un modelo ya validado.
    pub fn new(modelo: &Modelo3d) -> Self {
        let n_gdl = modelo.n_gdl();
        let mut mapa: Vec<Vec<(usize, f64)>> = (0..n_gdl).map(|g| vec![(g, 1.0)]).collect();
        let mut dependiente = vec![false; n_gdl];
        for d in &modelo.diafragmas {
            let m = d.maestro;
            let pm = modelo.nudos[m];
            for &e in &d.esclavos {
                let pe = modelo.nudos[e];
                let (dx, dy) = (pe[0] - pm[0], pe[1] - pm[1]);
                let rz = 6 * m + 5;
                mapa[6 * e] = vec![(6 * m, 1.0), (rz, -dy)];
                mapa[6 * e + 1] = vec![(6 * m + 1, 1.0), (rz, dx)];
                mapa[6 * e + 5] = vec![(rz, 1.0)];
                for g in [0, 1, 5] {
                    dependiente[6 * e + g] = true;
                }
            }
        }
        // Un coeficiente nulo (esclavo alineado con el maestro) no aporta.
        for fila in &mut mapa {
            fila.retain(|&(_, c)| c != 0.0);
        }
        Restricciones { mapa, dependiente }
    }

    /// Completa los GDL esclavos de `u` a partir de los independientes.
    pub fn expandir(&self, u: &mut [f64]) {
        for g in 0..u.len() {
            if self.dependiente[g] {
                u[g] = self.mapa[g].iter().map(|&(a, c)| c * u[a]).sum();
            }
        }
    }

    /// `Tᵀ f`: suma lo de cada GDL esclavo en sus independientes. Los GDL
    /// esclavos quedan en cero.
    pub fn reducir(&self, f: &[f64]) -> Vec<f64> {
        let mut out = vec![0.0; f.len()];
        for (g, &v) in f.iter().enumerate() {
            if v != 0.0 {
                for &(a, c) in &self.mapa[g] {
                    out[a] += c * v;
                }
            }
        }
        out
    }

    /// Suma `v` en la posición `(p, q)` de una matriz global, llevada a los GDL
    /// independientes: `agregar(a, b, cₐ c_b v)` para cada par de `T`.
    pub fn transformar(
        &self,
        p: usize,
        q: usize,
        v: f64,
        agregar: &mut impl FnMut(usize, usize, f64),
    ) {
        for &(a, ca) in &self.mapa[p] {
            for &(b, cb) in &self.mapa[q] {
                agregar(a, b, ca * cb * v);
            }
        }
    }
}
