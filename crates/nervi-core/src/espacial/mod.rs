// SPDX-License-Identifier: GPL-3.0-or-later
//! Pórtico espacial lineal elástico (Fase 2a): barras de 12 GDL con flexión
//! biaxial, axil y torsión de Saint-Venant, 6 GDL por nudo (issue #11).
//!
//! Es un módulo aparte del pórtico plano para no tocar sus resultados ni su
//! contrato de datos; comparte con él la flexión de la barra en cada plano
//! ([`crate::elemento`]), la solución del sistema y el diagnóstico de
//! mecanismos ([`crate::analisis`]).
//!
//! ```
//! use nervi_core::espacial::{analizar_3d, Barra3d, CasoCarga3d, Modelo3d};
//!
//! // Voladizo horizontal de 2 m sobre X con una carga de 5 kN hacia abajo (-Z).
//! let mut m = Modelo3d::new();
//! let a = m.agregar_nudo(0.0, 0.0, 0.0);
//! let b = m.agregar_nudo(2.0, 0.0, 0.0);
//! m.agregar_barra(Barra3d::new(a, b, 2.0e8, 8.0e7, 0.01, 2.0e-5, 1.0e-4, 1.0e-5));
//! m.empotrar(a);
//! let mut caso = CasoCarga3d::new("P");
//! caso.nodales.push((b, [0.0, 0.0, -5.0, 0.0, 0.0, 0.0]));
//! m.agregar_caso(caso);
//!
//! let r = analizar_3d(&m).unwrap();
//! // Sin vector de referencia, en una viga horizontal el eje y local es +Z:
//! // la flexión vertical usa Iz.
//! let esperada = -5.0 * 2.0_f64.powi(3) / (3.0 * 2.0e8 * 1.0e-4);
//! assert!((r.casos[0].desplazamientos[b][2] - esperada).abs() < 1e-12);
//! ```

pub mod analisis;
pub mod dinamica;
pub mod elemento;
pub mod modelo;

pub use analisis::{analizar_3d, Resultados3d, ResultadosCaso3d, Seccion3d};
pub use dinamica::{
    analizar_espectro_3d, analizar_modal_3d, coeficiente_cqc, CombinacionModal, Espectro, Masas3d,
    MetodoModal, ResultadosEspectro3d, ResultadosModal3d, TipoMasa,
};
pub use elemento::{ejes_locales, CargaLocal3d};
pub use modelo::{Barra3d, CargaBarra3d, CasoCarga3d, Modelo3d, TipoCargaBarra3d};
