// SPDX-License-Identifier: GPL-3.0-or-later
//! Definición del modelo de pórtico espacial (Fase 2a, issue #11).
//!
//! Convenciones (ver `docs/convenciones.md`, sección «Pórtico espacial»):
//! - Ejes globales X, Y horizontales y Z vertical hacia arriba (terna derecha).
//! - 6 GDL por nudo: `[ux, uy, uz, rx, ry, rz]`. El nudo `i` ocupa los índices
//!   globales `6i .. 6i + 5`. Giros positivos según la regla de la mano derecha.
//! - Ejes locales de barra: `x` de nudo `i` a nudo `j`; `y` en el plano que forman
//!   `x` y el vector de referencia, del lado del vector; `z = x × y`. Sin vector
//!   de referencia, se usa `+Z` (en una viga horizontal, `y` apunta hacia arriba)
//!   y en las barras verticales el plano `x`–`y` es el XZ global con `z = -Y`.

use crate::error::{ErrorNervi, Resultado};
use crate::modelo::Ejes;

/// Tolerancia (relativa a la longitud) para considerar vertical una barra o
/// paralelo a ella el vector de referencia.
pub const TOLERANCIA_PARALELO: f64 = 1e-6;

/// Barra de pórtico espacial (Euler-Bernoulli, torsión de Saint-Venant).
#[derive(Clone, Debug, PartialEq)]
pub struct Barra3d {
    pub nudo_i: usize,
    pub nudo_j: usize,
    /// Módulo de elasticidad.
    pub e: f64,
    /// Módulo de elasticidad transversal.
    pub g: f64,
    /// Área de la sección.
    pub a: f64,
    /// Momento de inercia respecto al eje `y` local (flexión en el plano `x`–`z`).
    pub iy: f64,
    /// Momento de inercia respecto al eje `z` local (flexión en el plano `x`–`y`).
    pub iz: f64,
    /// Constante de torsión de Saint-Venant.
    pub j: f64,
    /// Vector de referencia en ejes globales que fija el plano `x`–`y` local.
    /// `None` aplica la regla por defecto (ver el módulo).
    pub referencia: Option<[f64; 3]>,
    /// Liberaciones en ejes locales `[N, Vy, Vz, T, My, Mz]` del extremo `i`
    /// seguidas de las del extremo `j`. `true` anula esa fuerza de extremo.
    pub liberaciones: [bool; 12],
    /// Brazo rígido del extremo `i`: vector en ejes globales desde el nudo `i`
    /// hasta el comienzo de la parte flexible (la cara de la unión). Cero si no
    /// hay brazo.
    pub brazo_i: [f64; 3],
    /// Brazo rígido del extremo `j`, desde el nudo `j` hasta el final de la
    /// parte flexible.
    pub brazo_j: [f64; 3],
}

impl Barra3d {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        nudo_i: usize,
        nudo_j: usize,
        e: f64,
        g: f64,
        a: f64,
        iy: f64,
        iz: f64,
        j: f64,
    ) -> Self {
        Barra3d {
            nudo_i,
            nudo_j,
            e,
            g,
            a,
            iy,
            iz,
            j,
            referencia: None,
            liberaciones: [false; 12],
            brazo_i: [0.0; 3],
            brazo_j: [0.0; 3],
        }
    }

    /// Fija los brazos rígidos de los extremos (vectores en ejes globales desde
    /// cada nudo hasta la cara de la unión).
    pub fn con_brazos(mut self, brazo_i: [f64; 3], brazo_j: [f64; 3]) -> Self {
        self.brazo_i = brazo_i;
        self.brazo_j = brazo_j;
        self
    }

    /// `true` si la barra tiene algún brazo rígido.
    pub fn tiene_brazos(&self) -> bool {
        self.brazo_i.iter().chain(&self.brazo_j).any(|v| *v != 0.0)
    }

    /// Fija el vector de referencia del plano `x`–`y` local.
    pub fn con_referencia(mut self, v: [f64; 3]) -> Self {
        self.referencia = Some(v);
        self
    }

    /// Articula la barra: libera `My` y `Mz` en los extremos indicados.
    pub fn articulada(mut self, en_i: bool, en_j: bool) -> Self {
        if en_i {
            self.liberaciones[4] = true;
            self.liberaciones[5] = true;
        }
        if en_j {
            self.liberaciones[10] = true;
            self.liberaciones[11] = true;
        }
        self
    }

    /// Biela de cercha espacial: articulada en los dos extremos y con la torsión
    /// liberada en el extremo `j` (si no, el giro alrededor de su eje quedaría
    /// indeterminado). Solo transmite axil.
    pub fn biela(self) -> Self {
        let mut b = self.articulada(true, true);
        b.liberaciones[9] = true;
        b
    }
}

/// Tipo de carga aplicada en el tramo de una barra espacial.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TipoCargaBarra3d {
    /// Carga uniforme en toda la luz `[qx, qy, qz]` por unidad de longitud.
    Uniforme { q: [f64; 3] },
    /// Carga puntual `[px, py, pz]` a la distancia `a` del nudo `i`.
    Puntual { a: f64, p: [f64; 3] },
    /// Carga que varía linealmente de `q1` en `a` a `q2` en `b` (`0 <= a < b <= L`).
    Trapezoidal {
        a: f64,
        b: f64,
        q1: [f64; 3],
        q2: [f64; 3],
    },
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CargaBarra3d {
    pub barra: usize,
    /// En ejes globales las cargas distribuidas se entienden por unidad de
    /// longitud de barra (no proyectada), igual que en el pórtico plano.
    pub ejes: Ejes,
    pub tipo: TipoCargaBarra3d,
}

/// Diafragma rígido en su plano (horizontal, XY): los nudos `esclavos` se
/// mueven con el `maestro` como un cuerpo rígido en el plano, es decir,
/// `ux = ux_m - (y - y_m) rz_m`, `uy = uy_m + (x - x_m) rz_m` y `rz = rz_m`.
/// `uz`, `rx` y `ry` de cada nudo quedan independientes (la losa no tiene
/// rigidez fuera de su plano).
#[derive(Clone, Debug, PartialEq)]
pub struct Diafragma {
    pub maestro: usize,
    pub esclavos: Vec<usize>,
}

/// Una hipótesis (caso) de carga del pórtico espacial.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct CasoCarga3d {
    pub nombre: String,
    /// Cargas en nudos `(nudo, [Fx, Fy, Fz, Mx, My, Mz])` en ejes globales.
    pub nodales: Vec<(usize, [f64; 6])>,
    pub en_barras: Vec<CargaBarra3d>,
    /// Desplazamientos impuestos `(nudo, [ux, uy, uz, rx, ry, rz])`; solo actúan
    /// en los GDL restringidos de ese nudo.
    pub desplazamientos_impuestos: Vec<(usize, [f64; 6])>,
}

impl CasoCarga3d {
    pub fn new(nombre: impl Into<String>) -> Self {
        CasoCarga3d {
            nombre: nombre.into(),
            ..Default::default()
        }
    }
}

/// Modelo completo de pórtico espacial.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Modelo3d {
    /// Coordenadas `[x, y, z]` de cada nudo.
    pub nudos: Vec<[f64; 3]>,
    pub barras: Vec<Barra3d>,
    /// GDL restringidos por nudo `[ux, uy, uz, rx, ry, rz]`.
    pub restricciones: Vec<[bool; 6]>,
    /// Rigidez de apoyos elásticos por nudo `[kx, ky, kz, krx, kry, krz]`.
    pub resortes: Vec<[f64; 6]>,
    pub casos: Vec<CasoCarga3d>,
    /// Diafragmas rígidos de piso.
    pub diafragmas: Vec<Diafragma>,
}

impl Modelo3d {
    pub fn new() -> Self {
        Modelo3d::default()
    }

    pub fn agregar_nudo(&mut self, x: f64, y: f64, z: f64) -> usize {
        self.nudos.push([x, y, z]);
        self.nudos.len() - 1
    }

    pub fn agregar_barra(&mut self, barra: Barra3d) -> usize {
        self.barras.push(barra);
        self.barras.len() - 1
    }

    /// Restringe los GDL indicados del nudo (se suman a los ya restringidos).
    pub fn apoyar(&mut self, nudo: usize, gdl: [bool; 6]) {
        if self.restricciones.len() < self.nudos.len() {
            self.restricciones.resize(self.nudos.len(), [false; 6]);
        }
        for (r, g) in self.restricciones[nudo].iter_mut().zip(gdl) {
            *r |= g;
        }
    }

    /// Empotra el nudo (los seis GDL restringidos).
    pub fn empotrar(&mut self, nudo: usize) {
        self.apoyar(nudo, [true; 6]);
    }

    pub fn resorte(&mut self, nudo: usize, k: [f64; 6]) {
        if self.resortes.len() < self.nudos.len() {
            self.resortes.resize(self.nudos.len(), [0.0; 6]);
        }
        self.resortes[nudo] = k;
    }

    /// Declara un diafragma rígido con los `nudos` de un piso y devuelve el nudo
    /// maestro. Si `maestro` es `None` se crea un nudo nuevo en el centroide de
    /// los nudos (a su altura media), con `uz`, `rx` y `ry` restringidos porque
    /// no lo toca ninguna barra; ahí se reportan los desplazamientos del piso y
    /// se pueden aplicar las fuerzas de piso. El maestro puede estar o no en
    /// `nudos`.
    pub fn agregar_diafragma(&mut self, nudos: &[usize], maestro: Option<usize>) -> usize {
        let maestro = match maestro {
            Some(m) => m,
            None => {
                let n = nudos.len().max(1) as f64;
                let mut c = [0.0; 3];
                for &k in nudos {
                    if let Some(p) = self.nudos.get(k) {
                        for d in 0..3 {
                            c[d] += p[d] / n;
                        }
                    }
                }
                let m = self.agregar_nudo(c[0], c[1], c[2]);
                self.apoyar(m, [false, false, true, true, true, false]);
                m
            }
        };
        let mut esclavos: Vec<usize> = nudos.iter().copied().filter(|&k| k != maestro).collect();
        esclavos.sort_unstable();
        esclavos.dedup();
        self.diafragmas.push(Diafragma { maestro, esclavos });
        maestro
    }

    pub fn agregar_caso(&mut self, caso: CasoCarga3d) -> usize {
        self.casos.push(caso);
        self.casos.len() - 1
    }

    pub fn n_gdl(&self) -> usize {
        6 * self.nudos.len()
    }

    pub(crate) fn restringido(&self, nudo: usize, k: usize) -> bool {
        self.restricciones.get(nudo).is_some_and(|r| r[k])
    }

    pub(crate) fn rigidez_resorte(&self, nudo: usize, k: usize) -> f64 {
        self.resortes.get(nudo).map_or(0.0, |r| r[k])
    }

    /// Extremos de la parte flexible de una barra: cada nudo más su brazo
    /// rígido. Sin brazos son las coordenadas de los nudos.
    pub fn extremos(&self, b: &Barra3d) -> ([f64; 3], [f64; 3]) {
        let (pi, pj) = (self.nudos[b.nudo_i], self.nudos[b.nudo_j]);
        (
            std::array::from_fn(|d| pi[d] + b.brazo_i[d]),
            std::array::from_fn(|d| pj[d] + b.brazo_j[d]),
        )
    }

    /// Longitud de la parte flexible de una barra (entre las caras de las
    /// uniones si tiene brazos rígidos). Las cargas en el tramo, las estaciones
    /// de los diagramas y la masa lineal se miden sobre ella.
    pub fn longitud(&self, b: &Barra3d) -> f64 {
        let (pi, pj) = self.extremos(b);
        let d = [pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2]];
        (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]).sqrt()
    }

    /// Ejes locales de una barra, según su parte flexible (ver
    /// [`crate::espacial::ejes_locales`]).
    pub fn ejes_barra(&self, b: &Barra3d) -> Resultado<[[f64; 3]; 3]> {
        let (pi, pj) = self.extremos(b);
        crate::espacial::elemento::ejes_locales(pi, pj, b.referencia)
    }

    /// Verifica que el modelo sea consistente antes de analizarlo.
    pub fn validar(&self) -> Resultado<()> {
        let inv = |m: String| Err(ErrorNervi::ModeloInvalido(m));
        let n = self.nudos.len();
        if n == 0 {
            return inv("el modelo no tiene nudos".into());
        }
        for (k, p) in self.nudos.iter().enumerate() {
            if !p.iter().all(|v| v.is_finite()) {
                return inv(format!("el nudo {k} tiene coordenadas no finitas"));
            }
        }
        if self.restricciones.len() > n {
            return inv("hay más filas de restricciones que nudos".into());
        }
        if self.resortes.len() > n {
            return inv("hay más filas de resortes que nudos".into());
        }
        for (k, r) in self.resortes.iter().enumerate() {
            if r.iter().any(|v| !v.is_finite() || *v < 0.0) {
                return inv(format!(
                    "el nudo {k} tiene un resorte con rigidez negativa o no finita"
                ));
            }
        }
        for (k, b) in self.barras.iter().enumerate() {
            if b.nudo_i >= n || b.nudo_j >= n {
                return inv(format!("la barra {k} referencia un nudo inexistente"));
            }
            if b.nudo_i == b.nudo_j {
                return inv(format!("la barra {k} une un nudo consigo mismo"));
            }
            for (nombre, v) in [
                ("E", b.e),
                ("G", b.g),
                ("A", b.a),
                ("Iy", b.iy),
                ("Iz", b.iz),
                ("J", b.j),
            ] {
                if !(v.is_finite() && v > 0.0) {
                    return inv(format!(
                        "la barra {k} tiene {nombre} = {v}; debe ser positivo"
                    ));
                }
            }
            if !b.brazo_i.iter().chain(&b.brazo_j).all(|v| v.is_finite()) {
                return inv(format!("la barra {k} tiene un brazo rígido no finito"));
            }
            let l = self.longitud(b);
            let escala = self.nudos[b.nudo_i]
                .iter()
                .chain(self.nudos[b.nudo_j].iter())
                .fold(1.0_f64, |m, v| m.max(v.abs()));
            if l <= 1e-12 * escala {
                return inv(format!(
                    "la barra {k} tiene longitud nula{}",
                    if b.tiene_brazos() {
                        " (los brazos rígidos se tocan)"
                    } else {
                        ""
                    }
                ));
            }
            if let Some(v) = b.referencia {
                if !v.iter().all(|c| c.is_finite()) {
                    return inv(format!(
                        "la barra {k} tiene un vector de referencia no finito"
                    ));
                }
            }
            if let Err(ErrorNervi::ModeloInvalido(m)) = self.ejes_barra(b) {
                return inv(format!("la barra {k}: {m}"));
            }
            // Pares de liberaciones que dejan la barra inestable: el axil, un
            // cortante o el torsor en los dos extremos, o un cortante y el momento
            // que lo equilibra en el mismo extremo (Vy con Mz, Vz con My). Los
            // momentos flectores sí pueden liberarse en ambos extremos (bielas).
            let lib = &b.liberaciones;
            let nombres = ["N", "Vy", "Vz", "T"];
            for d in 0..4 {
                if lib[d] && lib[6 + d] {
                    return inv(format!(
                        "la barra {k} tiene liberado {} en ambos extremos (es inestable)",
                        nombres[d]
                    ));
                }
            }
            for o in [0, 6] {
                if (lib[o + 1] && lib[o + 5]) || (lib[o + 2] && lib[o + 4]) {
                    return inv(format!(
                        "la barra {k} tiene liberados un cortante y su momento en el mismo \
                         extremo (es inestable)"
                    ));
                }
            }
        }
        let mut en_diafragma = vec![usize::MAX; n];
        for (k, d) in self.diafragmas.iter().enumerate() {
            if d.maestro >= n || d.esclavos.iter().any(|&e| e >= n) {
                return inv(format!("el diafragma {k} referencia un nudo inexistente"));
            }
            if d.esclavos.is_empty() {
                return inv(format!(
                    "el diafragma {k} no tiene nudos además del maestro"
                ));
            }
            for &e in std::iter::once(&d.maestro).chain(&d.esclavos) {
                if en_diafragma[e] != usize::MAX {
                    return inv(format!(
                        "el nudo {e} está en los diafragmas {} y {k}; cada nudo puede estar \
                         en uno solo",
                        en_diafragma[e]
                    ));
                }
                en_diafragma[e] = k;
            }
            for &e in &d.esclavos {
                if [0, 1, 5].iter().any(|&g| self.restringido(e, g)) {
                    return inv(format!(
                        "el nudo {e} del diafragma {k} tiene restringido ux, uy o rz; en un \
                         diafragma esos GDL solo se pueden restringir en el maestro ({})",
                        d.maestro
                    ));
                }
            }
        }
        for (c, caso) in self.casos.iter().enumerate() {
            for (nudo, f) in &caso.nodales {
                if *nudo >= n {
                    return inv(format!("caso {c}: carga en nudo inexistente {nudo}"));
                }
                if !f.iter().all(|v| v.is_finite()) {
                    return inv(format!("caso {c}: carga no finita en el nudo {nudo}"));
                }
            }
            for (nudo, d) in &caso.desplazamientos_impuestos {
                if *nudo >= n {
                    return inv(format!(
                        "caso {c}: desplazamiento impuesto en nudo inexistente {nudo}"
                    ));
                }
                if !d.iter().all(|v| v.is_finite()) {
                    return inv(format!(
                        "caso {c}: desplazamiento impuesto no finito en el nudo {nudo}"
                    ));
                }
            }
            for cb in &caso.en_barras {
                let Some(b) = self.barras.get(cb.barra) else {
                    return inv(format!("caso {c}: carga en barra inexistente {}", cb.barra));
                };
                let l = self.longitud(b);
                let valores: Vec<f64> = match cb.tipo {
                    TipoCargaBarra3d::Uniforme { q } => q.to_vec(),
                    TipoCargaBarra3d::Puntual { a, p } => {
                        if !(a.is_finite() && a >= 0.0 && a <= l * (1.0 + 1e-12)) {
                            return inv(format!(
                                "caso {c}: carga puntual en la barra {} fuera de la luz \
                                 (a = {a}, L = {l})",
                                cb.barra
                            ));
                        }
                        p.to_vec()
                    }
                    TipoCargaBarra3d::Trapezoidal { a, b: fin, q1, q2 } => {
                        if !(a.is_finite()
                            && fin.is_finite()
                            && a >= 0.0
                            && a < fin
                            && fin <= l * (1.0 + 1e-12))
                        {
                            return inv(format!(
                                "caso {c}: carga trapezoidal en la barra {} con tramo inválido \
                                 (a = {a}, b = {fin}, L = {l}; se requiere 0 <= a < b <= L)",
                                cb.barra
                            ));
                        }
                        q1.iter().chain(q2.iter()).copied().collect()
                    }
                };
                if !valores.iter().all(|v| v.is_finite()) {
                    return inv(format!(
                        "caso {c}: carga no finita en la barra {}",
                        cb.barra
                    ));
                }
            }
        }
        Ok(())
    }
}
