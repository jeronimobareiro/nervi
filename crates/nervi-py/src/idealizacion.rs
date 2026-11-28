// SPDX-License-Identifier: GPL-3.0-or-later
//! Puente PyO3 de la generación del modelo de cálculo desde el modelo físico
//! (`nervi_core::idealizacion`, issue #74). Contrato de datos, versión
//! [`VERSION_CONTRATO_IDEALIZACION`]: ver `docs/contrato-datos.md` §Modelo de
//! cálculo generado. Lo usa `nervi.idealizacion`; no es API pública.

use nervi_core::idealizacion::{
    idealizar, Cargado, ColumnaIdeal, Entrada, MotivoIdeal, MuroIdeal, TipoBarra, TramoIdeal,
    VigaIdeal,
};
use numpy::ndarray::{Array1, Array2};
use numpy::{IntoPyArray, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::verificar_forma;

/// Versión del contrato de datos del modelo de cálculo generado.
pub const VERSION_CONTRATO_IDEALIZACION: u32 = 1;

fn indice(nombre: &str, v: f64) -> PyResult<usize> {
    if v.fract() != 0.0 || v < 0.0 {
        return Err(PyValueError::new_err(format!(
            "'{nombre}' = {v} no es un índice válido"
        )));
    }
    Ok(v as usize)
}

fn tipo(t: TipoBarra) -> f64 {
    match t {
        TipoBarra::Columna => 0.0,
        TipoBarra::Muro => 1.0,
        TipoBarra::Viga => 2.0,
    }
}

fn motivo(m: MotivoIdeal) -> &'static str {
    match m {
        MotivoIdeal::VigaSobreMuro => "viga_sobre_muro",
        MotivoIdeal::BrazosSinLuz => "brazos_sin_luz",
    }
}

/// Genera el modelo de cálculo.
///
/// Entradas: `columnas` (C×8: `x y z1 z2 b h angulo circular`), `muros` (M×7:
/// `x1 y1 x2 y2 z1 z2 espesor`), `vigas` (V×5: `x1 y1 x2 y2 z`), `niveles` (L),
/// `base`, `diafragmas` (índices de nivel), `tramos` (T×5: `tipo` 0 viga y 1 muro,
/// `elemento`, `nivel`, `a`, `b`), `cargas` (T×K×2: carga en `a` y en `b` de cada
/// caso, hacia abajo) y `tol`. Devuelve `nudos` (N×3), `barras` (B×8: `tipo` 0
/// columna, 1 muro y 2 viga, `origen i j s0 s1 brazo_i brazo_j`), `apoyos`,
/// `diafragmas` (lista de `(nivel, nudos)`), `cargas_barra` (×6: `barra caso a b
/// q_a q_b`), `cargas_nudo` (×5: `nudo caso fz mx my`) y `avisos` (lista de
/// `(viga, otro o None, motivo)`).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn idealizar_edificio<'py>(
    py: Python<'py>,
    version: u32,
    columnas: PyReadonlyArray2<'py, f64>,
    muros: PyReadonlyArray2<'py, f64>,
    vigas: PyReadonlyArray2<'py, f64>,
    niveles: PyReadonlyArray1<'py, f64>,
    base: f64,
    diafragmas: PyReadonlyArray1<'py, i64>,
    tramos: PyReadonlyArray2<'py, f64>,
    cargas: PyReadonlyArray3<'py, f64>,
    tol: f64,
) -> PyResult<Bound<'py, PyDict>> {
    if version != VERSION_CONTRATO_IDEALIZACION {
        return Err(PyValueError::new_err(format!(
            "contrato de datos del modelo de cálculo v{version} no soportado (el motor \
             espera v{VERSION_CONTRATO_IDEALIZACION})"
        )));
    }
    let (c, m, v, t, q) = (
        columnas.as_array(),
        muros.as_array(),
        vigas.as_array(),
        tramos.as_array(),
        cargas.as_array(),
    );
    verificar_forma("columnas", c.shape(), &[c.nrows(), 8])?;
    verificar_forma("muros", m.shape(), &[m.nrows(), 7])?;
    verificar_forma("vigas", v.shape(), &[v.nrows(), 5])?;
    verificar_forma("tramos", t.shape(), &[t.nrows(), 5])?;
    let n_casos = q.shape()[1];
    verificar_forma("cargas", q.shape(), &[t.nrows(), n_casos, 2])?;
    let mut e = Entrada {
        columnas: (0..c.nrows())
            .map(|k| ColumnaIdeal {
                punto: [c[[k, 0]], c[[k, 1]]],
                z1: c[[k, 2]],
                z2: c[[k, 3]],
                b: c[[k, 4]],
                h: c[[k, 5]],
                angulo: c[[k, 6]],
                circular: c[[k, 7]] != 0.0,
            })
            .collect(),
        muros: (0..m.nrows())
            .map(|k| MuroIdeal {
                p1: [m[[k, 0]], m[[k, 1]]],
                p2: [m[[k, 2]], m[[k, 3]]],
                z1: m[[k, 4]],
                z2: m[[k, 5]],
                espesor: m[[k, 6]],
            })
            .collect(),
        vigas: (0..v.nrows())
            .map(|k| VigaIdeal {
                p1: [v[[k, 0]], v[[k, 1]]],
                p2: [v[[k, 2]], v[[k, 3]]],
                z: v[[k, 4]],
            })
            .collect(),
        niveles: niveles.as_array().to_vec(),
        base,
        diafragmas: diafragmas
            .as_array()
            .iter()
            .map(|&k| indice("diafragmas", k as f64))
            .collect::<PyResult<_>>()?,
        tramos: Vec::with_capacity(t.nrows()),
        n_casos,
        tol,
    };
    for k in 0..t.nrows() {
        let el = indice("tramos", t[[k, 1]])?;
        let elemento = match t[[k, 0]] {
            0.0 => Cargado::Viga(el),
            1.0 => Cargado::Muro(el, indice("tramos", t[[k, 2]])?),
            x => {
                return Err(PyValueError::new_err(format!(
                    "tipo de tramo {x} desconocido"
                )))
            }
        };
        e.tramos.push(TramoIdeal {
            elemento,
            a: t[[k, 3]],
            b: t[[k, 4]],
            q: (0..n_casos).map(|j| [q[[k, j, 0]], q[[k, j, 1]]]).collect(),
        });
    }
    let r = py
        .detach(|| idealizar(&e))
        .map_err(|e| PyValueError::new_err(e.to_string()))?;

    let mut nudos = Array2::<f64>::zeros((r.nudos.len(), 3));
    for (k, p) in r.nudos.iter().enumerate() {
        for j in 0..3 {
            nudos[[k, j]] = p[j];
        }
    }
    let mut barras = Array2::<f64>::zeros((r.barras.len(), 8));
    for (k, b) in r.barras.iter().enumerate() {
        let fila = [
            tipo(b.tipo),
            b.origen as f64,
            b.i as f64,
            b.j as f64,
            b.s0,
            b.s1,
            b.brazo_i,
            b.brazo_j,
        ];
        for (j, x) in fila.into_iter().enumerate() {
            barras[[k, j]] = x;
        }
    }
    let mut cb = Array2::<f64>::zeros((r.cargas_barra.len(), 6));
    for (k, x) in r.cargas_barra.iter().enumerate() {
        for (j, y) in [x.barra as f64, x.caso as f64, x.a, x.b, x.q_a, x.q_b]
            .into_iter()
            .enumerate()
        {
            cb[[k, j]] = y;
        }
    }
    let mut cn = Array2::<f64>::zeros((r.cargas_nudo.len(), 5));
    for (k, x) in r.cargas_nudo.iter().enumerate() {
        for (j, y) in [x.nudo as f64, x.caso as f64, x.fz, x.mx, x.my]
            .into_iter()
            .enumerate()
        {
            cn[[k, j]] = y;
        }
    }
    let diafragmas: Vec<(usize, Vec<usize>)> = r.diafragmas;
    let avisos: Vec<(usize, Option<usize>, &str)> = r
        .avisos
        .iter()
        .map(|a| (a.viga, a.otro, motivo(a.motivo)))
        .collect();
    let out = PyDict::new(py);
    out.set_item("nudos", nudos.into_pyarray(py))?;
    out.set_item("barras", barras.into_pyarray(py))?;
    out.set_item(
        "apoyos",
        Array1::from_iter(r.apoyos.iter().map(|&k| k as i64)).into_pyarray(py),
    )?;
    out.set_item("diafragmas", diafragmas)?;
    out.set_item("cargas_barra", cb.into_pyarray(py))?;
    out.set_item("cargas_nudo", cn.into_pyarray(py))?;
    out.set_item("avisos", avisos)?;
    Ok(out)
}
