// SPDX-License-Identifier: GPL-3.0-or-later
//! Puente PyO3 del enganche de puntos en planta (`nervi_core::enganche`). Lo usa
//! `nervi.enganche`; no es API pública.

use nervi_core::enganche::{IndiceEnganche as Indice, Opciones};
use numpy::PyReadonlyArray2;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::verificar_forma;

/// Índice espacial de puntos y segmentos en planta para enganchar el cursor.
#[pyclass(module = "nervi._core", frozen)]
pub struct IndiceEnganche {
    indice: Indice,
}

#[pymethods]
impl IndiceEnganche {
    /// `puntos` (N×2) y `segmentos` (M×4, `x1 y1 x2 y2`).
    #[new]
    fn nuevo(
        py: Python<'_>,
        puntos: PyReadonlyArray2<'_, f64>,
        segmentos: PyReadonlyArray2<'_, f64>,
    ) -> PyResult<Self> {
        let p = puntos.as_array();
        let s = segmentos.as_array();
        verificar_forma("puntos", p.shape(), &[p.nrows(), 2])?;
        verificar_forma("segmentos", s.shape(), &[s.nrows(), 4])?;
        if p.iter().chain(s.iter()).any(|v| !v.is_finite()) {
            return Err(PyValueError::new_err("hay coordenadas que no son finitas"));
        }
        let pts: Vec<[f64; 2]> = (0..p.nrows()).map(|k| [p[[k, 0]], p[[k, 1]]]).collect();
        let segs: Vec<[[f64; 2]; 2]> = (0..s.nrows())
            .map(|k| [[s[[k, 0]], s[[k, 1]]], [s[[k, 2]], s[[k, 3]]]])
            .collect();
        let indice = py.detach(|| Indice::nuevo(pts, segs));
        Ok(Self { indice })
    }

    /// Engancha el cursor `(x, y)`. Devuelve un dict con `punto`, `tipo`,
    /// `elemento`, `otro` y `guia`.
    #[pyo3(signature = (
        x, y, radio, anterior=None, puntos=true, extremos=true, medios=true,
        cruces=true, perpendicular=true, cerca=true, paso_polar=90.0, orto=false,
        recientes=Vec::new(), paso_grilla=0.0, recorrer_todo=false
    ))]
    #[allow(clippy::too_many_arguments)]
    fn enganchar<'py>(
        &self,
        py: Python<'py>,
        x: f64,
        y: f64,
        radio: f64,
        anterior: Option<(f64, f64)>,
        puntos: bool,
        extremos: bool,
        medios: bool,
        cruces: bool,
        perpendicular: bool,
        cerca: bool,
        paso_polar: f64,
        orto: bool,
        recientes: Vec<usize>,
        paso_grilla: f64,
        recorrer_todo: bool,
    ) -> PyResult<Bound<'py, PyDict>> {
        if [radio, paso_grilla, paso_polar]
            .iter()
            .any(|v| v.is_nan() || *v < 0.0)
        {
            return Err(PyValueError::new_err(
                "radio, paso_grilla y paso_polar no pueden ser negativos",
            ));
        }
        let op = Opciones {
            radio,
            anterior: anterior.map(|(a, b)| [a, b]),
            puntos,
            extremos,
            medios,
            cruces,
            perpendicular,
            cerca,
            paso_polar,
            orto,
            recientes,
            paso_grilla,
        };
        let e = if recorrer_todo {
            self.indice.enganchar_sin_indice([x, y], &op)
        } else {
            self.indice.enganchar([x, y], &op)
        };
        let d = PyDict::new(py);
        d.set_item("punto", (e.punto[0], e.punto[1]))?;
        d.set_item("tipo", e.tipo.nombre())?;
        d.set_item("elemento", e.elemento)?;
        d.set_item("otro", e.otro)?;
        d.set_item("guia", e.guia.map(|[a, b]| ((a[0], a[1]), (b[0], b[1]))))?;
        Ok(d)
    }

    #[getter]
    fn cantidad(&self) -> (usize, usize) {
        (self.indice.puntos().len(), self.indice.segmentos().len())
    }
}
