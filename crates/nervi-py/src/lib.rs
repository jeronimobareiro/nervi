// SPDX-License-Identifier: GPL-3.0-or-later
//! Puente PyO3 entre el núcleo `nervi-core` y el paquete Python `nervi`.
//!
//! Contrato de datos v2: ver `docs/contrato-datos.md`. Todos los arreglos son
//! NumPy contiguos con forma fija; se validan aquí antes de llamar al núcleo.

use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Modelo, TipoCargaBarra,
};
use numpy::ndarray::Array3;
use numpy::{IntoPyArray, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::create_exception;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// Versión del contrato de datos que entiende este módulo.
const VERSION_CONTRATO: u32 = 2;

create_exception!(
    _core,
    MecanismoError,
    PyRuntimeError,
    "La estructura es inestable o tiene GDL cargados sin rigidez."
);

/// Convierte el error del núcleo. `MecanismoError` lleva además los atributos
/// `nudo` y `gdl` (`None` si no se pudo localizar) y `modos`, una lista de modos,
/// cada uno una lista de `(nudo, gdl, valor)` (ver `docs/contrato-datos.md`).
fn error_a_python(py: Python<'_>, e: ErrorNervi) -> PyErr {
    let texto = e.to_string();
    let (ubicacion, modos) = match e {
        ErrorNervi::ModeloInvalido(_) => return PyValueError::new_err(texto),
        ErrorNervi::Numerico(_) => return PyRuntimeError::new_err(texto),
        ErrorNervi::CargaSinRigidez { nudo, gdl } => (Some((nudo, gdl)), Vec::new()),
        ErrorNervi::Mecanismo(d) => (d.ubicacion, d.modos),
    };
    let err = MecanismoError::new_err(texto);
    let atributos = || -> PyResult<()> {
        let valor = err.value(py);
        valor.setattr("nudo", ubicacion.map(|u| u.0))?;
        valor.setattr("gdl", ubicacion.map(|u| u.1.to_string()))?;
        let lista: Vec<Vec<(usize, String, f64)>> = modos
            .iter()
            .map(|m| {
                m.iter()
                    .map(|c| (c.nudo, c.gdl.to_string(), c.valor))
                    .collect()
            })
            .collect();
        valor.setattr("modos", lista)
    };
    match atributos() {
        Ok(()) => err,
        Err(fallo) => fallo,
    }
}

fn verificar_forma(nombre: &str, forma: &[usize], esperada: &[usize]) -> PyResult<()> {
    if forma != esperada {
        return Err(PyValueError::new_err(format!(
            "'{nombre}' tiene forma {forma:?}; se esperaba {esperada:?}"
        )));
    }
    Ok(())
}

fn indice(nombre: &str, v: f64, limite: usize) -> PyResult<usize> {
    if v.fract() != 0.0 || v < 0.0 || v >= limite as f64 {
        return Err(PyValueError::new_err(format!(
            "'{nombre}' = {v} no es un índice válido (0..{limite})"
        )));
    }
    Ok(v as usize)
}

/// Resuelve un pórtico plano lineal elástico para varios casos de carga.
///
/// Devuelve un diccionario con `desplazamientos (n_casos, n_nudos, 3)`,
/// `reacciones (n_casos, n_nudos, 3)`, `fuerzas_extremo (n_casos, n_barras, 6)`,
/// `gdl_sin_rigidez` (lista de `(nudo, gdl)`), `diagramas` (lista por caso de
/// diccionarios con arreglos `barra, x, N, V, M, u, v`) y
/// `diagramas_combinaciones` (lo mismo para cada fila de `combinaciones`, todas
/// en las mismas estaciones por barra; vacía si no se pasan combinaciones).
#[pyfunction]
#[pyo3(signature = (
    version, coords, conectividad, props, liberaciones, restricciones, resortes,
    cargas_nodales, cargas_barra, despl_impuestos, n_estaciones = 11, combinaciones = None
))]
#[allow(clippy::too_many_arguments)]
fn resolver_portico_2d<'py>(
    py: Python<'py>,
    version: u32,
    coords: PyReadonlyArray2<'py, f64>,
    conectividad: PyReadonlyArray2<'py, i64>,
    props: PyReadonlyArray2<'py, f64>,
    liberaciones: PyReadonlyArray2<'py, u8>,
    restricciones: PyReadonlyArray2<'py, u8>,
    resortes: PyReadonlyArray2<'py, f64>,
    cargas_nodales: PyReadonlyArray3<'py, f64>,
    cargas_barra: PyReadonlyArray2<'py, f64>,
    despl_impuestos: PyReadonlyArray3<'py, f64>,
    n_estaciones: usize,
    combinaciones: Option<PyReadonlyArray2<'py, f64>>,
) -> PyResult<Bound<'py, PyDict>> {
    if version != VERSION_CONTRATO {
        return Err(PyValueError::new_err(format!(
            "versión de contrato {version} no soportada (este motor usa la {VERSION_CONTRATO})"
        )));
    }
    let coords = coords.as_array();
    let conectividad = conectividad.as_array();
    let props = props.as_array();
    let liberaciones = liberaciones.as_array();
    let restricciones = restricciones.as_array();
    let resortes = resortes.as_array();
    let cargas_nodales = cargas_nodales.as_array();
    let cargas_barra = cargas_barra.as_array();
    let despl_impuestos = despl_impuestos.as_array();

    let n = coords.shape()[0];
    let m = conectividad.shape()[0];
    let nc = cargas_nodales.shape()[0];
    verificar_forma("coords", coords.shape(), &[n, 2])?;
    verificar_forma("conectividad", conectividad.shape(), &[m, 2])?;
    verificar_forma("props", props.shape(), &[m, 3])?;
    verificar_forma("liberaciones", liberaciones.shape(), &[m, 6])?;
    verificar_forma("restricciones", restricciones.shape(), &[n, 3])?;
    verificar_forma("resortes", resortes.shape(), &[n, 3])?;
    verificar_forma("cargas_nodales", cargas_nodales.shape(), &[nc, n, 3])?;
    verificar_forma("despl_impuestos", despl_impuestos.shape(), &[nc, n, 3])?;
    let combinaciones: Vec<Vec<f64>> = match &combinaciones {
        None => Vec::new(),
        Some(arr) => {
            let a = arr.as_array();
            if a.shape()[1] != nc {
                return Err(PyValueError::new_err(format!(
                    "'combinaciones' tiene {} columnas; se esperaba una por caso ({nc})",
                    a.shape()[1]
                )));
            }
            if a.iter().any(|v| !v.is_finite()) {
                return Err(PyValueError::new_err(
                    "'combinaciones' tiene factores no finitos",
                ));
            }
            a.outer_iter().map(|fila| fila.to_vec()).collect()
        }
    };
    if cargas_barra.shape()[1] != 10 {
        return Err(PyValueError::new_err(format!(
            "'cargas_barra' tiene {} columnas; se esperaban 10 \
             [caso, barra, tipo, ejes, a, vx, vy, b, vx2, vy2]",
            cargas_barra.shape()[1]
        )));
    }

    let mut modelo = Modelo::new();
    for k in 0..n {
        modelo.agregar_nudo(coords[[k, 0]], coords[[k, 1]]);
    }
    for k in 0..m {
        let (i, j) = (conectividad[[k, 0]], conectividad[[k, 1]]);
        if i < 0 || j < 0 {
            return Err(PyValueError::new_err(format!(
                "la barra {k} tiene un índice de nudo negativo"
            )));
        }
        let mut b = Barra::new(
            i as usize,
            j as usize,
            props[[k, 0]],
            props[[k, 1]],
            props[[k, 2]],
        );
        for d in 0..6 {
            b.liberaciones[d] = liberaciones[[k, d]] != 0;
        }
        modelo.agregar_barra(b);
    }
    modelo.restricciones = (0..n)
        .map(|k| std::array::from_fn(|d| restricciones[[k, d]] != 0))
        .collect();
    modelo.resortes = (0..n)
        .map(|k| std::array::from_fn(|d| resortes[[k, d]]))
        .collect();
    for c in 0..nc {
        let mut caso = CasoCarga::new(format!("{c}"));
        for k in 0..n {
            let f: [f64; 3] = std::array::from_fn(|d| cargas_nodales[[c, k, d]]);
            if f.iter().any(|v| *v != 0.0) {
                caso.nodales.push((k, f));
            }
            let u: [f64; 3] = std::array::from_fn(|d| despl_impuestos[[c, k, d]]);
            if u.iter().any(|v| *v != 0.0) {
                caso.desplazamientos_impuestos.push((k, u));
            }
        }
        modelo.agregar_caso(caso);
    }
    for fila in 0..cargas_barra.shape()[0] {
        let v = |col: usize| cargas_barra[[fila, col]];
        let caso = indice("cargas_barra[caso]", v(0), nc)?;
        let barra = indice("cargas_barra[barra]", v(1), m)?;
        let tipo = if v(2) == 0.0 {
            TipoCargaBarra::Uniforme { qx: v(5), qy: v(6) }
        } else if v(2) == 1.0 {
            TipoCargaBarra::Puntual {
                a: v(4),
                px: v(5),
                py: v(6),
            }
        } else if v(2) == 2.0 {
            TipoCargaBarra::Trapezoidal {
                a: v(4),
                b: v(7),
                qx1: v(5),
                qy1: v(6),
                qx2: v(8),
                qy2: v(9),
            }
        } else if v(2) == 3.0 {
            TipoCargaBarra::Termica {
                alfa: v(4),
                dt: v(5),
                gradiente: v(6),
                h: v(7),
            }
        } else {
            return Err(PyValueError::new_err(format!(
                "cargas_barra fila {fila}: tipo {} desconocido \
                 (0 = uniforme, 1 = puntual, 2 = trapezoidal, 3 = térmica)",
                v(2)
            )));
        };
        let ejes = if v(3) == 0.0 {
            Ejes::Local
        } else if v(3) == 1.0 {
            Ejes::Global
        } else {
            return Err(PyValueError::new_err(format!(
                "cargas_barra fila {fila}: ejes {} desconocidos (0 = local, 1 = global)",
                v(3)
            )));
        };
        modelo.casos[caso]
            .en_barras
            .push(CargaBarra { barra, ejes, tipo });
    }

    // El cálculo no necesita a Python: se libera el GIL.
    let res = py
        .detach(|| analizar(&modelo))
        .map_err(|e| error_a_python(py, e))?;

    let mut despl = Array3::<f64>::zeros((nc, n, 3));
    let mut reac = Array3::<f64>::zeros((nc, n, 3));
    let mut fext = Array3::<f64>::zeros((nc, m, 6));
    let diagramas = PyList::empty(py);
    for (c, rc) in res.casos.iter().enumerate() {
        for k in 0..n {
            for d in 0..3 {
                despl[[c, k, d]] = rc.desplazamientos[k][d];
                reac[[c, k, d]] = rc.reacciones[k][d];
            }
        }
        let mut cols: [Vec<f64>; 6] = Default::default();
        let mut barra_col: Vec<i64> = Vec::new();
        for k in 0..m {
            for d in 0..6 {
                fext[[c, k, d]] = rc.fuerzas_extremo[k][d];
            }
            for s in res.diagrama(c, k, n_estaciones) {
                barra_col.push(k as i64);
                for (col, val) in cols
                    .iter_mut()
                    .zip([s.x, s.n, s.v, s.m, s.u_local, s.v_local])
                {
                    col.push(val);
                }
            }
        }
        let dic = PyDict::new(py);
        dic.set_item("barra", barra_col.into_pyarray(py))?;
        for (nombre, col) in ["x", "N", "V", "M", "u", "v"].iter().zip(cols) {
            dic.set_item(*nombre, col.into_pyarray(py))?;
        }
        diagramas.append(dic)?;
    }
    // Diagramas de las combinaciones, todas en las mismas estaciones por barra
    // para poder compararlas punto a punto (envolventes).
    let diagramas_comb = PyList::empty(py);
    let estaciones: Vec<Vec<(f64, bool)>> = if combinaciones.is_empty() {
        Vec::new()
    } else {
        (0..m)
            .map(|k| res.estaciones_comunes(&combinaciones, k, n_estaciones))
            .collect()
    };
    for factores in &combinaciones {
        let mut cols: [Vec<f64>; 6] = Default::default();
        let mut barra_col: Vec<i64> = Vec::new();
        for (k, est) in estaciones.iter().enumerate() {
            for &(x, der) in est {
                let s = res.seccion_combinada(factores, k, x, der);
                barra_col.push(k as i64);
                for (col, val) in cols
                    .iter_mut()
                    .zip([s.x, s.n, s.v, s.m, s.u_local, s.v_local])
                {
                    col.push(val);
                }
            }
        }
        let dic = PyDict::new(py);
        dic.set_item("barra", barra_col.into_pyarray(py))?;
        for (nombre, col) in ["x", "N", "V", "M", "u", "v"].iter().zip(cols) {
            dic.set_item(*nombre, col.into_pyarray(py))?;
        }
        diagramas_comb.append(dic)?;
    }
    let sin_rigidez = PyList::empty(py);
    for (nudo, gdl) in &res.gdl_sin_rigidez {
        sin_rigidez.append((*nudo, gdl.to_string()))?;
    }

    let out = PyDict::new(py);
    out.set_item("desplazamientos", despl.into_pyarray(py))?;
    out.set_item("reacciones", reac.into_pyarray(py))?;
    out.set_item("fuerzas_extremo", fext.into_pyarray(py))?;
    out.set_item("gdl_sin_rigidez", sin_rigidez)?;
    out.set_item("diagramas", diagramas)?;
    out.set_item("diagramas_combinaciones", diagramas_comb)?;
    Ok(out)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VERSION_CONTRATO", VERSION_CONTRATO)?;
    m.add("MecanismoError", m.py().get_type::<MecanismoError>())?;
    m.add_function(wrap_pyfunction!(resolver_portico_2d, m)?)?;
    Ok(())
}
