// SPDX-License-Identifier: GPL-3.0-or-later
//! # nervi-core
//!
//! Núcleo de análisis estructural de Nervi. Fase 1: pórtico plano lineal
//! elástico (barras Euler-Bernoulli, 3 GDL por nudo).
//!
//! ```
//! use nervi_core::{analizar, Barra, CasoCarga, Modelo};
//!
//! // Voladizo de 3 m con carga puntual de 10 kN hacia abajo en el extremo.
//! let mut m = Modelo::new();
//! let a = m.agregar_nudo(0.0, 0.0);
//! let b = m.agregar_nudo(3.0, 0.0);
//! m.agregar_barra(Barra::new(a, b, 2.0e8, 0.01, 1.0e-4));
//! m.apoyar(a, true, true, true);
//! let mut caso = CasoCarga::new("P");
//! caso.nodales.push((b, [0.0, -10.0, 0.0]));
//! m.agregar_caso(caso);
//!
//! let r = analizar(&m).unwrap();
//! let flecha = r.casos[0].desplazamientos[b][1];
//! let esperada = -10.0 * 3.0_f64.powi(3) / (3.0 * 2.0e8 * 1.0e-4);
//! assert!((flecha - esperada).abs() < 1e-12);
//! ```

// En código numérico los índices explícitos son más legibles que los iteradores.
#![allow(clippy::needless_range_loop)]

pub mod analisis;
pub mod elemento;
pub mod error;
mod mecanismo;
pub mod modelo;

pub use analisis::{analizar, Resultados, ResultadosCaso, Seccion};
pub use elemento::CargaLocal;
pub use error::{ComponenteModo, DiagnosticoMecanismo, ErrorNervi, Gdl};
pub use modelo::{Barra, CargaBarra, CasoCarga, Ejes, Modelo, TipoCargaBarra};
