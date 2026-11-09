//! Definición del modelo de pórtico plano.
//!
//! Convenciones (ver `docs/convenciones.md`):
//! - Ejes globales X (horizontal) e Y (vertical hacia arriba). Giros positivos antihorarios.
//! - 3 GDL por nudo: `[ux, uy, rz]`. El nudo `i` ocupa los índices globales `3i, 3i+1, 3i+2`.
//! - Ejes locales de barra: `x` de nudo `i` a nudo `j`, `y` a 90° antihorario.
//! - Unidades consistentes a elección del usuario (por ejemplo kN y m).

use crate::error::{ErrorNervi, Resultado};

/// Barra de pórtico plano (Euler-Bernoulli).
#[derive(Clone, Debug, PartialEq)]
pub struct Barra {
    pub nudo_i: usize,
    pub nudo_j: usize,
    /// Módulo de elasticidad.
    pub e: f64,
    /// Área de la sección.
    pub a: f64,
    /// Momento de inercia respecto al eje perpendicular al plano.
    pub i: f64,
    /// Liberaciones en ejes locales `[N_i, V_i, M_i, N_j, V_j, M_j]`.
    /// `true` significa que esa fuerza de extremo es nula (por ejemplo una articulación).
    pub liberaciones: [bool; 6],
}

impl Barra {
    pub fn new(nudo_i: usize, nudo_j: usize, e: f64, a: f64, i: f64) -> Self {
        Barra {
            nudo_i,
            nudo_j,
            e,
            a,
            i,
            liberaciones: [false; 6],
        }
    }

    /// Barra articulada en ambos extremos (biela de cercha).
    pub fn biarticulada(nudo_i: usize, nudo_j: usize, e: f64, a: f64, i: f64) -> Self {
        let mut b = Barra::new(nudo_i, nudo_j, e, a, i);
        b.liberaciones[2] = true;
        b.liberaciones[5] = true;
        b
    }
}

/// Sistema de ejes en que se expresa una carga en barra.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Ejes {
    Local,
    /// Ejes globales. Las cargas distribuidas se entienden por unidad de longitud
    /// de la barra (no proyectada).
    Global,
}

/// Tipo de carga aplicada en el tramo de una barra.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TipoCargaBarra {
    /// Carga uniforme en toda la luz: `(qx, qy)` por unidad de longitud.
    Uniforme { qx: f64, qy: f64 },
    /// Carga puntual `(px, py)` a la distancia `a` del nudo `i`, con `0 <= a <= L`.
    Puntual { a: f64, px: f64, py: f64 },
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CargaBarra {
    pub barra: usize,
    pub ejes: Ejes,
    pub tipo: TipoCargaBarra,
}

/// Una hipótesis (caso) de carga.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct CasoCarga {
    pub nombre: String,
    /// Cargas en nudos: `(nudo, [Fx, Fy, Mz])` en ejes globales.
    pub nodales: Vec<(usize, [f64; 3])>,
    pub en_barras: Vec<CargaBarra>,
    /// Desplazamientos impuestos (asentamientos): `(nudo, [ux, uy, rz])`.
    /// Solo se aplican en los GDL restringidos de ese nudo; en los demás se ignoran.
    pub desplazamientos_impuestos: Vec<(usize, [f64; 3])>,
}

impl CasoCarga {
    pub fn new(nombre: impl Into<String>) -> Self {
        CasoCarga {
            nombre: nombre.into(),
            ..Default::default()
        }
    }
}

/// Modelo completo de pórtico plano.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Modelo {
    /// Coordenadas `[x, y]` de cada nudo.
    pub nudos: Vec<[f64; 2]>,
    pub barras: Vec<Barra>,
    /// GDL restringidos por nudo `[ux, uy, rz]`. Si está vacío, ningún nudo tiene apoyo.
    pub restricciones: Vec<[bool; 3]>,
    /// Rigidez de apoyos elásticos por nudo `[kx, ky, krz]`. Si está vacío, no hay resortes.
    pub resortes: Vec<[f64; 3]>,
    pub casos: Vec<CasoCarga>,
}

impl Modelo {
    pub fn new() -> Self {
        Modelo::default()
    }

    pub fn agregar_nudo(&mut self, x: f64, y: f64) -> usize {
        self.nudos.push([x, y]);
        self.nudos.len() - 1
    }

    pub fn agregar_barra(&mut self, barra: Barra) -> usize {
        self.barras.push(barra);
        self.barras.len() - 1
    }

    /// Restringe los GDL indicados del nudo (se suman a los ya restringidos).
    pub fn apoyar(&mut self, nudo: usize, ux: bool, uy: bool, rz: bool) {
        if self.restricciones.len() < self.nudos.len() {
            self.restricciones.resize(self.nudos.len(), [false; 3]);
        }
        let r = &mut self.restricciones[nudo];
        r[0] |= ux;
        r[1] |= uy;
        r[2] |= rz;
    }

    pub fn resorte(&mut self, nudo: usize, kx: f64, ky: f64, krz: f64) {
        if self.resortes.len() < self.nudos.len() {
            self.resortes.resize(self.nudos.len(), [0.0; 3]);
        }
        self.resortes[nudo] = [kx, ky, krz];
    }

    pub fn agregar_caso(&mut self, caso: CasoCarga) -> usize {
        self.casos.push(caso);
        self.casos.len() - 1
    }

    pub fn n_gdl(&self) -> usize {
        3 * self.nudos.len()
    }

    pub(crate) fn restringido(&self, nudo: usize, k: usize) -> bool {
        self.restricciones.get(nudo).is_some_and(|r| r[k])
    }

    pub(crate) fn rigidez_resorte(&self, nudo: usize, k: usize) -> f64 {
        self.resortes.get(nudo).map_or(0.0, |r| r[k])
    }

    /// Longitud y cosenos directores `(L, c, s)` de una barra.
    pub fn geometria_barra(&self, b: &Barra) -> (f64, f64, f64) {
        let [xi, yi] = self.nudos[b.nudo_i];
        let [xj, yj] = self.nudos[b.nudo_j];
        let (dx, dy) = (xj - xi, yj - yi);
        let l = dx.hypot(dy);
        (l, dx / l, dy / l)
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
            for (nombre, v) in [("E", b.e), ("A", b.a), ("I", b.i)] {
                if !(v.is_finite() && v > 0.0) {
                    return inv(format!(
                        "la barra {k} tiene {nombre} = {v}; debe ser positivo"
                    ));
                }
            }
            let (l, _, _) = self.geometria_barra(b);
            let escala = self.nudos[b.nudo_i]
                .iter()
                .chain(self.nudos[b.nudo_j].iter())
                .fold(1.0_f64, |m, v| m.max(v.abs()));
            if l <= 1e-12 * escala {
                return inv(format!("la barra {k} tiene longitud nula"));
            }
            if b.liberaciones[0] && b.liberaciones[3] {
                return inv(format!(
                    "la barra {k} tiene liberado el axil en ambos extremos (es inestable)"
                ));
            }
            if b.liberaciones[1] && b.liberaciones[4] {
                return inv(format!(
                    "la barra {k} tiene liberado el cortante en ambos extremos (es inestable)"
                ));
            }
            if (b.liberaciones[1] && b.liberaciones[2]) || (b.liberaciones[4] && b.liberaciones[5])
            {
                return inv(format!(
                    "la barra {k} tiene liberados cortante y momento en el mismo extremo (es inestable)"
                ));
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
                let (l, _, _) = self.geometria_barra(b);
                let valores = match cb.tipo {
                    TipoCargaBarra::Uniforme { qx, qy } => [qx, qy, 0.0],
                    TipoCargaBarra::Puntual { a, px, py } => {
                        if !(a.is_finite() && a >= 0.0 && a <= l * (1.0 + 1e-12)) {
                            return inv(format!(
                                "caso {c}: carga puntual en la barra {} fuera de la luz (a = {a}, L = {l})",
                                cb.barra
                            ));
                        }
                        [px, py, a]
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
