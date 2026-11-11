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

/// Componente de un modo de mecanismo: cuánto se mueve el GDL `gdl` del nudo
/// `nudo` cuando el GDL principal del modo se mueve 1.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ComponenteModo {
    pub nudo: usize,
    pub gdl: Gdl,
    pub valor: f64,
}

/// Diagnóstico de una estructura inestable (issue #9).
#[derive(Clone, Debug, PartialEq)]
pub struct DiagnosticoMecanismo {
    /// Explicación breve (caso de carga, cantidad de modos).
    pub detalle: String,
    /// Nudo y GDL que más se mueven en el primer modo de mecanismo (la
    /// traslación mayor; un giro solo si el modo no traslada nada). `None` si no
    /// se pudo localizar.
    pub ubicacion: Option<(usize, Gdl)>,
    /// Modos de mecanismo, cada uno normalizado para que su GDL principal valga 1.
    /// Incluye solo las componentes con valor absoluto de al menos 1e-6.
    pub modos: Vec<Vec<ComponenteModo>>,
}

impl DiagnosticoMecanismo {
    /// Nudos que se mueven en algún modo, ordenados y sin repetir.
    pub fn nudos(&self) -> Vec<usize> {
        let mut v: Vec<usize> = self.modos.iter().flatten().map(|c| c.nudo).collect();
        v.sort_unstable();
        v.dedup();
        v
    }
}

/// Error devuelto por la validación del modelo o por el análisis.
#[derive(Clone, Debug, PartialEq)]
pub enum ErrorNervi {
    /// Los datos del modelo son inconsistentes o físicamente inválidos.
    ModeloInvalido(String),
    /// La estructura no tiene rigidez suficiente (mecanismo o inestabilidad), con
    /// el nudo y el GDL donde está el problema cuando se pudieron localizar.
    Mecanismo(DiagnosticoMecanismo),
    /// Hay una carga aplicada sobre un grado de libertad que no tiene rigidez.
    CargaSinRigidez { nudo: usize, gdl: Gdl },
    /// Error numérico inesperado al resolver.
    Numerico(String),
}

impl fmt::Display for ErrorNervi {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ErrorNervi::ModeloInvalido(m) => write!(f, "modelo inválido: {m}"),
            ErrorNervi::Mecanismo(d) => {
                write!(f, "estructura inestable (mecanismo): {}", d.detalle)?;
                if let Some((nudo, gdl)) = d.ubicacion {
                    write!(
                        f,
                        "; el nudo {nudo} se puede mover en {gdl} sin que nada lo impida"
                    )?;
                }
                let nudos = d.nudos();
                if !nudos.is_empty() {
                    const MAX: usize = 12;
                    let lista: Vec<String> =
                        nudos.iter().take(MAX).map(|n| n.to_string()).collect();
                    let resto = if nudos.len() > MAX { ", …" } else { "" };
                    write!(f, " (nudos que se mueven: {}{resto})", lista.join(", "))?;
                }
                f.write_str("; revisar apoyos y articulaciones")
            }
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
