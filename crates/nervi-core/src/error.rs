// SPDX-License-Identifier: GPL-3.0-or-later
//! Errores del núcleo de análisis.

use std::fmt;

/// Grado de libertad de un nudo en el pórtico plano.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Gdl {
    Ux,
    Uy,
    Rz,
}

impl Gdl {
    pub fn desde_indice(i: usize) -> Gdl {
        match i % 3 {
            0 => Gdl::Ux,
            1 => Gdl::Uy,
            _ => Gdl::Rz,
        }
    }
}

impl fmt::Display for Gdl {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            Gdl::Ux => "ux",
            Gdl::Uy => "uy",
            Gdl::Rz => "rz",
        };
        f.write_str(s)
    }
}

/// Error devuelto por la validación del modelo o por el análisis.
#[derive(Clone, Debug, PartialEq)]
pub enum ErrorNervi {
    /// Los datos del modelo son inconsistentes o físicamente inválidos.
    ModeloInvalido(String),
    /// La estructura no tiene rigidez suficiente (mecanismo o inestabilidad).
    Mecanismo(String),
    /// Hay una carga aplicada sobre un grado de libertad que no tiene rigidez.
    CargaSinRigidez { nudo: usize, gdl: Gdl },
    /// Error numérico inesperado al resolver.
    Numerico(String),
}

impl fmt::Display for ErrorNervi {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ErrorNervi::ModeloInvalido(m) => write!(f, "modelo inválido: {m}"),
            ErrorNervi::Mecanismo(m) => write!(f, "estructura inestable (mecanismo): {m}"),
            ErrorNervi::CargaSinRigidez { nudo, gdl } => write!(
                f,
                "hay carga en el nudo {nudo}, GDL {gdl}, pero ninguna barra ni apoyo le da rigidez"
            ),
            ErrorNervi::Numerico(m) => write!(f, "error numérico: {m}"),
        }
    }
}

impl std::error::Error for ErrorNervi {}

pub type Resultado<T> = Result<T, ErrorNervi>;
