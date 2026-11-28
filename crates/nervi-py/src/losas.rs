// SPDX-License-Identifier: GPL-3.0-or-later
//! Puente PyO3 del reparto de las cargas de las losas a sus apoyos
//! (`nervi_core::losas`). Contrato de datos de las losas, versión
//! [`VERSION_CONTRATO_LOSAS`]: ver `docs/contrato-datos.md` §Reparto de losas. Lo
//! usa `nervi.fisico`; no es API pública.

use nervi_core::losas::{repartir, ApoyoReparto, LosaReparto, Motivo};
use numpy::ndarray::{Array1, Array2, Array3};
use numpy::{IntoPyArray, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::verificar_forma;

/// Versión del contrato de datos del reparto de losas.
pub const VERSION_CONTRATO_LOSAS: u32 = 1;

fn motivo(m: Motivo) -> &'static str {
    match m {
        Motivo::NoConvexa => "no_convexa",
        Motivo::SinApoyos => "sin_apoyos",
        Motivo::BordeParcial => "borde_parcial",
        Motivo::FueraDelBorde => "fuera_del_borde",
    }
}

fn indice(nombre: &str, v: i64) -> PyResult<usize> {
    usize::try_from(v)
        .map_err(|_| PyValueError::new_err(format!("'{nombre}' tiene un índice negativo")))
}

/// Reparte las losas a sus apoyos.
///
/// Entradas: `vertices` (V×2) con los contornos seguidos y `inicio` (L+1) con
/// dónde empieza cada uno; `grupos_losas` (L); `apoyos` (M×4, `x1 y1 x2 y2`);
/// `grupos_apoyos` (M); `cargas` (L×C, carga de superficie de cada losa en cada
/// caso) y `tol`. Devuelve `piezas` (K×6: losa, apoyo, a, b, ancho_a, ancho_b),
/// `cargas` (K×C×2: carga lineal en a y en b de cada caso), `regiones` (lista de
/// `(losa, [apoyos], vértices R×2)`), `avisos` (lista de `(losa, lado o None,
/// motivo)`) y `repartida` (L booleanos).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn repartir_losas<'py>(
    py: Python<'py>,
    version: u32,
    vertices: PyReadonlyArray2<'py, f64>,
    inicio: PyReadonlyArray1<'py, i64>,
    grupos_losas: PyReadonlyArray1<'py, i64>,
    apoyos: PyReadonlyArray2<'py, f64>,
    grupos_apoyos: PyReadonlyArray1<'py, i64>,
    cargas: PyReadonlyArray2<'py, f64>,
    tol: f64,
) -> PyResult<Bound<'py, PyDict>> {
    if version != VERSION_CONTRATO_LOSAS {
        return Err(PyValueError::new_err(format!(
            "contrato de datos de las losas v{version} no soportado (el motor espera \
             v{VERSION_CONTRATO_LOSAS})"
        )));
    }
    let vertices = vertices.as_array();
    let inicio = inicio.as_array();
    let grupos_losas = grupos_losas.as_array();
    let apoyos = apoyos.as_array();
    let grupos_apoyos = grupos_apoyos.as_array();
    let cargas = cargas.as_array();
    let n_losas = grupos_losas.len();
    let n_casos = cargas.ncols();
    verificar_forma("vertices", vertices.shape(), &[vertices.nrows(), 2])?;
    verificar_forma("inicio", inicio.shape(), &[n_losas + 1])?;
    verificar_forma("apoyos", apoyos.shape(), &[grupos_apoyos.len(), 4])?;
    verificar_forma("cargas", cargas.shape(), &[n_losas, n_casos])?;
    let mut losas = Vec::with_capacity(n_losas);
    for k in 0..n_losas {
        let (a, b) = (
            indice("inicio", inicio[k])?,
            indice("inicio", inicio[k + 1])?,
        );
        if a > b || b > vertices.nrows() {
            return Err(PyValueError::new_err("'inicio' no está en orden"));
        }
        losas.push(LosaReparto {
            grupo: indice("grupos_losas", grupos_losas[k])?,
            contorno: (a..b)
                .map(|i| [vertices[[i, 0]], vertices[[i, 1]]])
                .collect(),
        });
    }
    let lista_apoyos = (0..apoyos.nrows())
        .map(|k| {
            Ok(ApoyoReparto {
                grupo: indice("grupos_apoyos", grupos_apoyos[k])?,
                p1: [apoyos[[k, 0]], apoyos[[k, 1]]],
                p2: [apoyos[[k, 2]], apoyos[[k, 3]]],
            })
        })
        .collect::<PyResult<Vec<_>>>()?;
    let r = py
        .detach(|| repartir(&losas, &lista_apoyos, tol))
        .map_err(|e| PyValueError::new_err(e.to_string()))?;

    let k = r.piezas.len();
    let mut piezas = Array2::<f64>::zeros((k, 6));
    let mut lineales = Array3::<f64>::zeros((k, n_casos, 2));
    for (i, p) in r.piezas.iter().enumerate() {
        for (j, v) in [
            p.losa as f64,
            p.apoyo as f64,
            p.a,
            p.b,
            p.ancho_a,
            p.ancho_b,
        ]
        .into_iter()
        .enumerate()
        {
            piezas[[i, j]] = v;
        }
        for c in 0..n_casos {
            let q = cargas[[p.losa, c]];
            lineales[[i, c, 0]] = q * p.ancho_a;
            lineales[[i, c, 1]] = q * p.ancho_b;
        }
    }
    let regiones: Vec<(usize, Vec<usize>, Bound<'py, numpy::PyArray2<f64>>)> = r
        .regiones
        .iter()
        .map(|g| {
            let mut a = Array2::<f64>::zeros((g.poligono.len(), 2));
            for (i, p) in g.poligono.iter().enumerate() {
                a[[i, 0]] = p[0];
                a[[i, 1]] = p[1];
            }
            (g.losa, g.apoyos.clone(), a.into_pyarray(py))
        })
        .collect();
    let avisos: Vec<(usize, Option<usize>, &str)> = r
        .avisos
        .iter()
        .map(|a| (a.losa, a.lado, motivo(a.motivo)))
        .collect();
    let out = PyDict::new(py);
    out.set_item("piezas", piezas.into_pyarray(py))?;
    out.set_item("cargas", lineales.into_pyarray(py))?;
    out.set_item("regiones", regiones)?;
    out.set_item("avisos", avisos)?;
    out.set_item("repartida", Array1::from(r.repartida).into_pyarray(py))?;
    Ok(out)
}
