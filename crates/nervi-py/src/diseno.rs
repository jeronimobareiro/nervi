// SPDX-License-Identifier: GPL-3.0-or-later
//! Puente PyO3 del diseño según norma (`nervi_core::diseno`).
//!
//! Contrato de datos del diseño, versión [`VERSION_CONTRATO_DISENO`]: ver
//! `docs/contrato-datos.md` §Diseño. Se versiona aparte de los contratos del
//! análisis. Lo usan `nervi.design.aci318.columna` y `nervi.design.aci318.flexion`;
//! no es API pública.

use nervi_core::diseno::columna::{
    capacidades, elegir_armadura, seccion_en, verificar, Candidata, MaterialColumna,
    SeccionColumna, Solicitacion,
};
use nervi_core::diseno::viga::{
    armadura_simple, elegir_barras, resistencia, MaterialViga, ResistenciaFlexion, SeccionViga,
};
use numpy::ndarray::{Array1, ArrayView2};
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::verificar_forma;

/// Versión del contrato de datos del diseño.
pub const VERSION_CONTRATO_DISENO: u32 = 2;

fn verificar_version(version: u32) -> PyResult<()> {
    if version != VERSION_CONTRATO_DISENO {
        return Err(PyValueError::new_err(format!(
            "contrato de datos del diseño v{version} no soportado (el motor espera \
             v{VERSION_CONTRATO_DISENO})"
        )));
    }
    Ok(())
}

fn puntos(nombre: &str, a: ArrayView2<'_, f64>) -> PyResult<Vec<[f64; 2]>> {
    verificar_forma(nombre, a.shape(), &[a.nrows(), 2])?;
    Ok(a.rows().into_iter().map(|f| [f[0], f[1]]).collect())
}

fn seccion(
    contorno: &PyReadonlyArray2<'_, f64>,
    barras: &PyReadonlyArray2<'_, f64>,
    areas: &PyReadonlyArray1<'_, f64>,
) -> PyResult<SeccionColumna> {
    let barras = puntos("barras", barras.as_array())?;
    let areas = areas.as_array().to_vec();
    verificar_forma("areas", &[areas.len()], &[barras.len()])?;
    let contorno = puntos("contorno", contorno.as_array())?;
    if contorno.len() < 3 {
        return Err(PyValueError::new_err(
            "el contorno necesita al menos 3 vértices",
        ));
    }
    Ok(SeccionColumna {
        contorno,
        barras,
        areas,
    })
}

fn solicitaciones(a: &PyReadonlyArray2<'_, f64>) -> PyResult<Vec<Solicitacion>> {
    let a = a.as_array();
    verificar_forma("solicitaciones", a.shape(), &[a.nrows(), 3])?;
    Ok(a.rows().into_iter().map(|f| [f[0], f[1], f[2]]).collect())
}

fn material(fc: f64, fy: f64, zunchada: bool) -> PyResult<MaterialColumna> {
    if !(fc > 0.0 && fy > 0.0) {
        return Err(PyValueError::new_err("f'c y fy tienen que ser positivos"));
    }
    Ok(MaterialColumna { fc, fy, zunchada })
}

fn arreglo<'py>(py: Python<'py>, v: Vec<f64>) -> Bound<'py, PyArray1<f64>> {
    Array1::from(v).into_pyarray(py)
}

/// Resultantes nominales para los ejes neutros `(theta[i], c[i])`: diccionario con
/// `pn` (N), `mz`, `my` (N·mm), `eps_t` y `phi`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn columna_seccion_en<'py>(
    py: Python<'py>,
    version: u32,
    contorno: PyReadonlyArray2<'py, f64>,
    barras: PyReadonlyArray2<'py, f64>,
    areas: PyReadonlyArray1<'py, f64>,
    fc: f64,
    fy: f64,
    zunchada: bool,
    theta: PyReadonlyArray1<'py, f64>,
    c: PyReadonlyArray1<'py, f64>,
) -> PyResult<Bound<'py, PyDict>> {
    verificar_version(version)?;
    let sec = seccion(&contorno, &barras, &areas)?;
    let mat = material(fc, fy, zunchada)?;
    let (theta, c) = (theta.as_array(), c.as_array());
    verificar_forma("c", c.shape(), &[theta.len()])?;
    let r: Vec<_> = theta
        .iter()
        .zip(c.iter())
        .map(|(&t, &c)| seccion_en(&sec, &mat, t, c))
        .collect();
    let out = PyDict::new(py);
    out.set_item("pn", arreglo(py, r.iter().map(|x| x.pn).collect()))?;
    out.set_item("mz", arreglo(py, r.iter().map(|x| x.mz).collect()))?;
    out.set_item("my", arreglo(py, r.iter().map(|x| x.my).collect()))?;
    out.set_item("eps_t", arreglo(py, r.iter().map(|x| x.eps_t).collect()))?;
    out.set_item("phi", arreglo(py, r.iter().map(|x| x.phi).collect()))?;
    Ok(out)
}

/// Resistencia de diseño con `φPn = p_obj[i]` (N) en la dirección `alfa[i]`:
/// `(phi_mn (N·mm), theta, c, ok)`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[allow(clippy::type_complexity)]
pub fn columna_capacidad<'py>(
    py: Python<'py>,
    version: u32,
    contorno: PyReadonlyArray2<'py, f64>,
    barras: PyReadonlyArray2<'py, f64>,
    areas: PyReadonlyArray1<'py, f64>,
    fc: f64,
    fy: f64,
    zunchada: bool,
    p_obj: PyReadonlyArray1<'py, f64>,
    alfa: PyReadonlyArray1<'py, f64>,
) -> PyResult<(
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<bool>>,
)> {
    verificar_version(version)?;
    let sec = seccion(&contorno, &barras, &areas)?;
    let mat = material(fc, fy, zunchada)?;
    let pares: Vec<(f64, f64)> = p_obj
        .as_array()
        .iter()
        .copied()
        .zip(alfa.as_array().iter().copied())
        .collect();
    verificar_forma("alfa", &[alfa.as_array().len()], &[p_obj.as_array().len()])?;
    let r = py.detach(|| capacidades(&sec, &mat, &pares));
    Ok((
        arreglo(py, r.iter().map(|x| x.phi_mn).collect()),
        arreglo(py, r.iter().map(|x| x.theta).collect()),
        arreglo(py, r.iter().map(|x| x.c).collect()),
        Array1::from(r.iter().map(|x| x.ok).collect::<Vec<_>>()).into_pyarray(py),
    ))
}

/// Razones demanda/capacidad de `solicitaciones (m, 3)` = `(Pu, Mz, My)` en kN y
/// kN·m: `(phi_mn (kN·m), razon_momento, razon_axial, razon)`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[allow(clippy::type_complexity)]
pub fn columna_razones<'py>(
    py: Python<'py>,
    version: u32,
    contorno: PyReadonlyArray2<'py, f64>,
    barras: PyReadonlyArray2<'py, f64>,
    areas: PyReadonlyArray1<'py, f64>,
    fc: f64,
    fy: f64,
    zunchada: bool,
    solicitaciones_kn: PyReadonlyArray2<'py, f64>,
    phi_pn_max: f64,
    phi_pnt: f64,
) -> PyResult<(
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
)> {
    verificar_version(version)?;
    let sec = seccion(&contorno, &barras, &areas)?;
    let mat = material(fc, fy, zunchada)?;
    let s = solicitaciones(&solicitaciones_kn)?;
    let r = py.detach(|| verificar(&sec, &mat, &s, phi_pn_max, phi_pnt));
    Ok((
        arreglo(py, r.iter().map(|x| x.phi_mn).collect()),
        arreglo(py, r.iter().map(|x| x.momento).collect()),
        arreglo(py, r.iter().map(|x| x.axial).collect()),
        arreglo(py, r.iter().map(|x| x.razon).collect()),
    ))
}

/// Índice de la primera armadura candidata que resiste todas las solicitaciones,
/// o `None`. `barras (K, n, 2)` y `areas (K, n)` traen las K candidatas completadas
/// con barras de área nula; `phi_pn_max` y `phi_pnt` (K,) en kN.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn columna_elegir_armadura(
    py: Python<'_>,
    version: u32,
    contorno: PyReadonlyArray2<'_, f64>,
    barras: PyReadonlyArray3<'_, f64>,
    areas: PyReadonlyArray2<'_, f64>,
    phi_pn_max: PyReadonlyArray1<'_, f64>,
    phi_pnt: PyReadonlyArray1<'_, f64>,
    fc: f64,
    fy: f64,
    zunchada: bool,
    solicitaciones_kn: PyReadonlyArray2<'_, f64>,
) -> PyResult<Option<usize>> {
    verificar_version(version)?;
    let contorno = puntos("contorno", contorno.as_array())?;
    let mat = material(fc, fy, zunchada)?;
    let (barras, areas) = (barras.as_array(), areas.as_array());
    let (pmax, pnt) = (phi_pn_max.as_array(), phi_pnt.as_array());
    let (k, n) = (areas.nrows(), areas.ncols());
    verificar_forma("barras", barras.shape(), &[k, n, 2])?;
    verificar_forma("phi_pn_max", pmax.shape(), &[k])?;
    verificar_forma("phi_pnt", pnt.shape(), &[k])?;
    let candidatas: Vec<Candidata> = (0..k)
        .map(|i| Candidata {
            seccion: SeccionColumna {
                contorno: contorno.clone(),
                barras: (0..n)
                    .map(|j| [barras[[i, j, 0]], barras[[i, j, 1]]])
                    .collect(),
                areas: areas.row(i).to_vec(),
            },
            phi_pn_max: pmax[i],
            phi_pnt: pnt[i],
        })
        .collect();
    let s = solicitaciones(&solicitaciones_kn)?;
    Ok(py.detach(|| elegir_armadura(&candidatas, &mat, &s)))
}

// --- Vigas: flexión ----------------------------------------------------------------

type Resistencia8 = (f64, f64, f64, f64, f64, f64, f64, f64);

fn tupla(r: &ResistenciaFlexion) -> Resistencia8 {
    (r.mn, r.phi, r.phi_mn, r.c, r.a, r.eps_t, r.fs, r.fs_comp)
}

/// Resistencia a flexión de una sección rectangular (mm, mm², MPa):
/// `(Mn, φ, φMn, c, a, εt, fs, fs_comp)` con los momentos en kN·m.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn viga_resistencia(
    version: u32,
    b: f64,
    d: f64,
    as_: f64,
    fc: f64,
    fy: f64,
    as_comp: f64,
    d_comp: f64,
    dt: f64,
) -> PyResult<Resistencia8> {
    verificar_version(version)?;
    let mat = material_viga(fc, fy)?;
    Ok(tupla(&resistencia(b, d, as_, &mat, as_comp, d_comp, dt)))
}

/// Armadura simple para `mu` (kN·m) con `εt ≥ lim`: `(As_lim, c_lim, resistencia
/// límite, simple)`, donde `simple` es `None` o `(As_req, As, resistencia)`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[allow(clippy::type_complexity)]
pub fn viga_armadura_simple(
    version: u32,
    mu: f64,
    b: f64,
    d: f64,
    dt: f64,
    fc: f64,
    fy: f64,
    lim: f64,
) -> PyResult<(f64, f64, Resistencia8, Option<(f64, f64, Resistencia8)>)> {
    verificar_version(version)?;
    let mat = material_viga(fc, fy)?;
    let f = armadura_simple(mu, b, d, dt, &mat, lim);
    Ok((
        f.as_lim,
        f.c_lim,
        tupla(&f.limite),
        f.simple
            .map(|s| (s.as_req, s.as_dis, tupla(&s.resistencia))),
    ))
}

/// Disposición de barras para `mu` (kN·m), o `None`: `(capas, As, d, dt, b_nec,
/// s_libre, As_req, resistencia)`, con las capas como listas de índices en
/// `diametros`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[allow(clippy::type_complexity)]
pub fn viga_elegir_barras(
    py: Python<'_>,
    version: u32,
    mu: f64,
    b: f64,
    h: f64,
    recubrimiento: f64,
    d_estribo: f64,
    d_agregado: f64,
    fc: f64,
    fy: f64,
    lim: f64,
    diametros: PyReadonlyArray1<'_, f64>,
    max_capas: usize,
    max_barras: usize,
) -> PyResult<Option<(Vec<Vec<usize>>, f64, f64, f64, f64, f64, f64, Resistencia8)>> {
    verificar_version(version)?;
    let mat = material_viga(fc, fy)?;
    let diametros = diametros.as_array().to_vec();
    if diametros.is_empty() || diametros.iter().any(|&x| x.is_nan() || x <= 0.0) {
        return Err(PyValueError::new_err(
            "los diámetros tienen que ser positivos",
        ));
    }
    let seccion = SeccionViga {
        b,
        h,
        recubrimiento,
        d_estribo,
        d_agregado,
    };
    let r = py.detach(|| elegir_barras(mu, &seccion, &mat, lim, &diametros, max_capas, max_barras));
    Ok(r.map(|x| {
        (
            x.capas,
            x.area,
            x.d,
            x.dt,
            x.b_nec,
            x.s_libre,
            x.as_req,
            tupla(&x.resistencia),
        )
    }))
}

fn material_viga(fc: f64, fy: f64) -> PyResult<MaterialViga> {
    if !(fc > 0.0 && fy > 0.0) {
        return Err(PyValueError::new_err("f'c y fy tienen que ser positivos"));
    }
    Ok(MaterialViga { fc, fy })
}
