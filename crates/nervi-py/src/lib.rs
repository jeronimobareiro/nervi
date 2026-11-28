// SPDX-License-Identifier: GPL-3.0-or-later
//! Puente PyO3 entre el núcleo `nervi-core` y el paquete Python `nervi`.
//!
//! Contrato de datos v2: ver `docs/contrato-datos.md`. Todos los arreglos son
//! NumPy contiguos con forma fija; se validan aquí antes de llamar al núcleo.

use nervi_core::espacial::{
    analizar_3d, analizar_espectro_3d, analizar_modal_3d, Barra3d, CargaBarra3d, CasoCarga3d,
    CombinacionModal, Espectro, Masas3d, MetodoModal, Modelo3d, ResultadosModal3d,
    TipoCargaBarra3d, TipoMasa,
};
use nervi_core::{
    analizar, Barra, CargaBarra, CasoCarga, Ejes, ErrorNervi, Modelo, TipoCargaBarra,
};
use numpy::ndarray::{Array1, Array2, Array3};
use numpy::{IntoPyArray, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::create_exception;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod diseno;
mod enganche;
mod losas;

/// Versión del contrato de datos del pórtico plano que entiende este módulo.
const VERSION_CONTRATO: u32 = 2;
/// Versión del contrato de datos del pórtico espacial (`resolver_portico_3d`).
/// Se versiona aparte para no cambiar el contrato plano.
const VERSION_CONTRATO_3D: u32 = 2;
/// Versión del contrato de datos de la dinámica del pórtico espacial
/// (`resolver_modal_3d` y `espectro_3d`).
const VERSION_CONTRATO_DINAMICA: u32 = 2;

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

pub(crate) fn verificar_forma(nombre: &str, forma: &[usize], esperada: &[usize]) -> PyResult<()> {
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
        } else if v(2) == 4.0 {
            TipoCargaBarra::Momento { a: v(4), mz: v(5) }
        } else {
            return Err(PyValueError::new_err(format!(
                "cargas_barra fila {fila}: tipo {} desconocido \
                 (0 = uniforme, 1 = puntual, 2 = trapezoidal, 3 = térmica, 4 = momento)",
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

/// Arma el [`Modelo3d`] desde los arreglos del contrato de datos 3D.
#[allow(clippy::too_many_arguments)]
fn construir_modelo_3d(
    coords: &PyReadonlyArray2<'_, f64>,
    conectividad: &PyReadonlyArray2<'_, i64>,
    props: &PyReadonlyArray2<'_, f64>,
    referencias: &PyReadonlyArray2<'_, f64>,
    liberaciones: &PyReadonlyArray2<'_, u8>,
    restricciones: &PyReadonlyArray2<'_, u8>,
    resortes: &PyReadonlyArray2<'_, f64>,
    cargas_nodales: &PyReadonlyArray3<'_, f64>,
    cargas_barra: &PyReadonlyArray2<'_, f64>,
    despl_impuestos: &PyReadonlyArray3<'_, f64>,
    brazos: Option<&PyReadonlyArray2<'_, f64>>,
    diafragmas: Option<&PyReadonlyArray1<'_, i64>>,
    maestros: Option<&PyReadonlyArray1<'_, i64>>,
) -> PyResult<Modelo3d> {
    let coords = coords.as_array();
    let conectividad = conectividad.as_array();
    let props = props.as_array();
    let referencias = referencias.as_array();
    let liberaciones = liberaciones.as_array();
    let restricciones = restricciones.as_array();
    let resortes = resortes.as_array();
    let cargas_nodales = cargas_nodales.as_array();
    let cargas_barra = cargas_barra.as_array();
    let despl_impuestos = despl_impuestos.as_array();

    let n = coords.shape()[0];
    let m = conectividad.shape()[0];
    let nc = cargas_nodales.shape()[0];
    verificar_forma("coords", coords.shape(), &[n, 3])?;
    verificar_forma("conectividad", conectividad.shape(), &[m, 2])?;
    verificar_forma("props", props.shape(), &[m, 6])?;
    verificar_forma("referencias", referencias.shape(), &[m, 3])?;
    verificar_forma("liberaciones", liberaciones.shape(), &[m, 12])?;
    verificar_forma("restricciones", restricciones.shape(), &[n, 6])?;
    verificar_forma("resortes", resortes.shape(), &[n, 6])?;
    verificar_forma("cargas_nodales", cargas_nodales.shape(), &[nc, n, 6])?;
    verificar_forma("despl_impuestos", despl_impuestos.shape(), &[nc, n, 6])?;
    if cargas_barra.shape()[1] != 12 {
        return Err(PyValueError::new_err(format!(
            "'cargas_barra' tiene {} columnas; se esperaban 12 \
             [caso, barra, tipo, ejes, a, b, qx1, qy1, qz1, qx2, qy2, qz2]",
            cargas_barra.shape()[1]
        )));
    }

    let mut modelo = Modelo3d::new();
    for k in 0..n {
        modelo.agregar_nudo(coords[[k, 0]], coords[[k, 1]], coords[[k, 2]]);
    }
    for k in 0..m {
        let (i, j) = (conectividad[[k, 0]], conectividad[[k, 1]]);
        if i < 0 || j < 0 {
            return Err(PyValueError::new_err(format!(
                "la barra {k} tiene un índice de nudo negativo"
            )));
        }
        let p = |c: usize| props[[k, c]];
        let mut b = Barra3d::new(i as usize, j as usize, p(0), p(1), p(2), p(3), p(4), p(5));
        let v: [f64; 3] = std::array::from_fn(|d| referencias[[k, d]]);
        // Una fila de ceros pide la regla por defecto.
        if v.iter().any(|c| *c != 0.0) {
            b.referencia = Some(v);
        }
        for d in 0..12 {
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
        let mut caso = CasoCarga3d::new(format!("{c}"));
        for k in 0..n {
            let f: [f64; 6] = std::array::from_fn(|d| cargas_nodales[[c, k, d]]);
            if f.iter().any(|v| *v != 0.0) {
                caso.nodales.push((k, f));
            }
            let u: [f64; 6] = std::array::from_fn(|d| despl_impuestos[[c, k, d]]);
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
        let q1 = [v(6), v(7), v(8)];
        let q2 = [v(9), v(10), v(11)];
        let tipo = if v(2) == 0.0 {
            TipoCargaBarra3d::Uniforme { q: q1 }
        } else if v(2) == 1.0 {
            TipoCargaBarra3d::Puntual { a: v(4), p: q1 }
        } else if v(2) == 2.0 {
            TipoCargaBarra3d::Trapezoidal {
                a: v(4),
                b: v(5),
                q1,
                q2,
            }
        } else {
            return Err(PyValueError::new_err(format!(
                "cargas_barra fila {fila}: tipo {} desconocido \
                 (0 = uniforme, 1 = puntual, 2 = trapezoidal)",
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
            .push(CargaBarra3d { barra, ejes, tipo });
    }

    if let Some(brazos) = brazos {
        let brazos = brazos.as_array();
        verificar_forma("brazos", brazos.shape(), &[m, 6])?;
        for (k, b) in modelo.barras.iter_mut().enumerate() {
            b.brazo_i = std::array::from_fn(|d| brazos[[k, d]]);
            b.brazo_j = std::array::from_fn(|d| brazos[[k, 3 + d]]);
        }
    }
    match (diafragmas, maestros) {
        (None, None) => {}
        (Some(pertenece), Some(maestros)) => {
            let pertenece = pertenece.as_array();
            let maestros = maestros.as_array();
            verificar_forma("diafragmas", pertenece.shape(), &[n])?;
            let nd = maestros.len();
            let mut grupos = vec![Vec::new(); nd];
            for k in 0..n {
                let d = pertenece[k];
                if d >= 0 {
                    let d = indice("diafragmas", d as f64, nd)?;
                    grupos[d].push(k);
                }
            }
            for (d, nudos) in grupos.iter().enumerate() {
                let maestro = indice("maestros", maestros[d] as f64, n)?;
                modelo.agregar_diafragma(nudos, Some(maestro));
            }
        }
        _ => {
            return Err(PyValueError::new_err(
                "'diafragmas' y 'maestros' se dan juntos",
            ))
        }
    }

    Ok(modelo)
}

/// Resuelve un pórtico espacial lineal elástico para varios casos de carga.
///
/// Contrato de datos 3D, versión 2 (ver `docs/contrato-datos.md`): los
/// brazos rígidos `brazos (n_barras, 6)` y los diafragmas `diafragmas
/// (n_nudos,)` (índice del diafragma de cada nudo, -1 si no tiene) con
/// `maestros (n_diafragmas,)` son opcionales. Devuelve un
/// diccionario con `desplazamientos (n_casos, n_nudos, 6)`, `reacciones
/// (n_casos, n_nudos, 6)`, `fuerzas_extremo (n_casos, n_barras, 12)`, `ejes
/// (n_barras, 3, 3)` (filas `x, y, z` locales en globales), `gdl_sin_rigidez` y
/// `diagramas` (lista por caso de diccionarios con arreglos `barra, x, N, Vy,
/// Vz, T, My, Mz, u, v, w, rx`).
#[pyfunction]
#[pyo3(signature = (
    version, coords, conectividad, props, referencias, liberaciones, restricciones, resortes,
    cargas_nodales, cargas_barra, despl_impuestos, n_estaciones = 11, brazos = None,
    diafragmas = None, maestros = None
))]
#[allow(clippy::too_many_arguments)]
fn resolver_portico_3d<'py>(
    py: Python<'py>,
    version: u32,
    coords: PyReadonlyArray2<'py, f64>,
    conectividad: PyReadonlyArray2<'py, i64>,
    props: PyReadonlyArray2<'py, f64>,
    referencias: PyReadonlyArray2<'py, f64>,
    liberaciones: PyReadonlyArray2<'py, u8>,
    restricciones: PyReadonlyArray2<'py, u8>,
    resortes: PyReadonlyArray2<'py, f64>,
    cargas_nodales: PyReadonlyArray3<'py, f64>,
    cargas_barra: PyReadonlyArray2<'py, f64>,
    despl_impuestos: PyReadonlyArray3<'py, f64>,
    n_estaciones: usize,
    brazos: Option<PyReadonlyArray2<'py, f64>>,
    diafragmas: Option<PyReadonlyArray1<'py, i64>>,
    maestros: Option<PyReadonlyArray1<'py, i64>>,
) -> PyResult<Bound<'py, PyDict>> {
    if version != VERSION_CONTRATO_3D {
        return Err(PyValueError::new_err(format!(
            "versión de contrato 3D {version} no soportada (este motor usa la {VERSION_CONTRATO_3D})"
        )));
    }
    let modelo = construir_modelo_3d(
        &coords,
        &conectividad,
        &props,
        &referencias,
        &liberaciones,
        &restricciones,
        &resortes,
        &cargas_nodales,
        &cargas_barra,
        &despl_impuestos,
        brazos.as_ref(),
        diafragmas.as_ref(),
        maestros.as_ref(),
    )?;
    let (n, m, nc) = (modelo.nudos.len(), modelo.barras.len(), modelo.casos.len());
    let res = py
        .detach(|| analizar_3d(&modelo))
        .map_err(|e| error_a_python(py, e))?;

    let mut despl = Array3::<f64>::zeros((nc, n, 6));
    let mut reac = Array3::<f64>::zeros((nc, n, 6));
    let mut fext = Array3::<f64>::zeros((nc, m, 12));
    let diagramas = PyList::empty(py);
    for (c, rc) in res.casos.iter().enumerate() {
        for k in 0..n {
            for d in 0..6 {
                despl[[c, k, d]] = rc.desplazamientos[k][d];
                reac[[c, k, d]] = rc.reacciones[k][d];
            }
        }
        let mut cols: [Vec<f64>; 11] = Default::default();
        let mut barra_col: Vec<i64> = Vec::new();
        for k in 0..m {
            for d in 0..12 {
                fext[[c, k, d]] = rc.fuerzas_extremo[k][d];
            }
            for s in res.diagrama(c, k, n_estaciones) {
                barra_col.push(k as i64);
                for (col, val) in cols
                    .iter_mut()
                    .zip([s.x, s.n, s.vy, s.vz, s.t, s.my, s.mz, s.u, s.v, s.w, s.rx])
                {
                    col.push(val);
                }
            }
        }
        let dic = PyDict::new(py);
        dic.set_item("barra", barra_col.into_pyarray(py))?;
        for (nombre, col) in ["x", "N", "Vy", "Vz", "T", "My", "Mz", "u", "v", "w", "rx"]
            .iter()
            .zip(cols)
        {
            dic.set_item(*nombre, col.into_pyarray(py))?;
        }
        diagramas.append(dic)?;
    }
    let mut ejes = Array3::<f64>::zeros((m, 3, 3));
    for (k, ba) in res.barras.iter().enumerate() {
        for i in 0..3 {
            for j in 0..3 {
                ejes[[k, i, j]] = ba.ejes[i][j];
            }
        }
    }
    let sin_rigidez = PyList::empty(py);
    for (nudo, gdl) in &res.gdl_sin_rigidez {
        sin_rigidez.append((*nudo, gdl.to_string()))?;
    }

    let out = PyDict::new(py);
    out.set_item("desplazamientos", despl.into_pyarray(py))?;
    out.set_item("reacciones", reac.into_pyarray(py))?;
    out.set_item("fuerzas_extremo", fext.into_pyarray(py))?;
    out.set_item("ejes", ejes.into_pyarray(py))?;
    out.set_item("gdl_sin_rigidez", sin_rigidez)?;
    out.set_item("diagramas", diagramas)?;
    Ok(out)
}

fn verificar_version_dinamica(version: u32) -> PyResult<()> {
    if version != VERSION_CONTRATO_DINAMICA {
        return Err(PyValueError::new_err(format!(
            "versión de contrato de dinámica {version} no soportada \
             (este motor usa la {VERSION_CONTRATO_DINAMICA})"
        )));
    }
    Ok(())
}

/// Arma el modelo desde un diccionario con los arreglos del contrato 3D
/// (las mismas claves que los argumentos de `resolver_portico_3d`).
fn modelo_desde_dict(d: &Bound<'_, PyDict>) -> PyResult<Modelo3d> {
    let item = |k: &str| -> PyResult<Bound<'_, pyo3::PyAny>> {
        d.get_item(k)?
            .ok_or_else(|| PyValueError::new_err(format!("falta el arreglo '{k}' del modelo")))
    };
    fn opcional<'py, T: for<'a> pyo3::FromPyObject<'a, 'py>>(
        d: &Bound<'py, PyDict>,
        k: &str,
    ) -> PyResult<Option<T>> {
        match d.get_item(k)? {
            Some(v) if !v.is_none() => Ok(Some(v.extract().map_err(Into::into)?)),
            _ => Ok(None),
        }
    }
    construir_modelo_3d(
        &item("coords")?.extract()?,
        &item("conectividad")?.extract()?,
        &item("props")?.extract()?,
        &item("referencias")?.extract()?,
        &item("liberaciones")?.extract()?,
        &item("restricciones")?.extract()?,
        &item("resortes")?.extract()?,
        &item("cargas_nodales")?.extract()?,
        &item("cargas_barra")?.extract()?,
        &item("despl_impuestos")?.extract()?,
        opcional::<PyReadonlyArray2<'_, f64>>(d, "brazos")?.as_ref(),
        opcional::<PyReadonlyArray1<'_, i64>>(d, "diafragmas")?.as_ref(),
        opcional::<PyReadonlyArray1<'_, i64>>(d, "maestros")?.as_ref(),
    )
}

fn por_nudo(filas: &[Vec<[f64; 6]>], n: usize) -> Array3<f64> {
    let mut out = Array3::<f64>::zeros((filas.len(), n, 6));
    for (k, f) in filas.iter().enumerate() {
        for i in 0..n {
            for d in 0..6 {
                out[[k, i, d]] = f[i][d];
            }
        }
    }
    out
}

fn filas3(v: &[[f64; 3]]) -> Array2<f64> {
    Array2::from_shape_fn((v.len(), 3), |(i, d)| v[i][d])
}

/// Análisis modal del pórtico espacial (contrato de dinámica, versión 1).
///
/// `modelo` es el diccionario de arreglos del contrato 3D. Masas:
/// `masas_nodales (n_nudos, 6)` `[mx, my, mz, Jx, Jy, Jz]`, `masas_lineales
/// (n_barras,)` por unidad de longitud y `masas_casos (n_casos,)` con el factor
/// de cada caso para convertir sus cargas verticales en masa (dividido por
/// `gravedad`). `tipo_masa` 0 = concentrada, 1 = consistente; `metodo` 0 =
/// automático, 1 = denso, 2 = Lanczos. Devuelve `omegas, periodos, frecuencias
/// (n_modos,)`, `modos` e `inercias` `(n_modos, n_nudos, 6)`,
/// `factores_participacion` y `masas_efectivas (n_modos, 3)`, `masa_total
/// (3,)`, `n_gdl_masa`, `metodo`, `gdl_sin_rigidez` y `diafragmas` (lista de
/// diccionarios `maestro, masa [mx, my], centro_masa [x, y], inercia`).
#[pyfunction]
#[pyo3(signature = (
    version, modelo, masas_nodales, masas_lineales, masas_casos, gravedad, tipo_masa,
    n_modos, metodo = 0
))]
#[allow(clippy::too_many_arguments)]
fn resolver_modal_3d<'py>(
    py: Python<'py>,
    version: u32,
    modelo: &Bound<'py, PyDict>,
    masas_nodales: PyReadonlyArray2<'py, f64>,
    masas_lineales: PyReadonlyArray1<'py, f64>,
    masas_casos: PyReadonlyArray1<'py, f64>,
    gravedad: f64,
    tipo_masa: u8,
    n_modos: usize,
    metodo: u8,
) -> PyResult<Bound<'py, PyDict>> {
    verificar_version_dinamica(version)?;
    let modelo = modelo_desde_dict(modelo)?;
    let (n, m, nc) = (modelo.nudos.len(), modelo.barras.len(), modelo.casos.len());
    let masas_nodales = masas_nodales.as_array();
    let masas_lineales = masas_lineales.as_array();
    let masas_casos = masas_casos.as_array();
    verificar_forma("masas_nodales", masas_nodales.shape(), &[n, 6])?;
    verificar_forma("masas_lineales", masas_lineales.shape(), &[m])?;
    verificar_forma("masas_casos", masas_casos.shape(), &[nc])?;
    let mut masas = Masas3d::new();
    for k in 0..n {
        let v: [f64; 6] = std::array::from_fn(|d| masas_nodales[[k, d]]);
        if v.iter().any(|x| *x != 0.0) {
            masas.nodales.push((k, v));
        }
    }
    masas.lineales = (0..m)
        .filter(|&b| masas_lineales[b] != 0.0)
        .map(|b| (b, masas_lineales[b]))
        .collect();
    masas.desde_casos = (0..nc)
        .filter(|&c| masas_casos[c] != 0.0)
        .map(|c| (c, masas_casos[c]))
        .collect();
    masas.gravedad = gravedad;
    masas.tipo = match tipo_masa {
        0 => TipoMasa::Concentrada,
        1 => TipoMasa::Consistente,
        t => {
            return Err(PyValueError::new_err(format!(
                "tipo de masa {t} desconocido (0 = concentrada, 1 = consistente)"
            )))
        }
    };
    let metodo = match metodo {
        0 => MetodoModal::Automatico,
        1 => MetodoModal::Denso,
        2 => MetodoModal::Lanczos,
        t => {
            return Err(PyValueError::new_err(format!(
                "método {t} desconocido (0 = automático, 1 = denso, 2 = Lanczos)"
            )))
        }
    };
    let r = py
        .detach(|| analizar_modal_3d(&modelo, &masas, n_modos, metodo))
        .map_err(|e| error_a_python(py, e))?;
    let out = PyDict::new(py);
    out.set_item("omegas", Array1::from(r.omegas).into_pyarray(py))?;
    out.set_item("periodos", Array1::from(r.periodos).into_pyarray(py))?;
    out.set_item("frecuencias", Array1::from(r.frecuencias).into_pyarray(py))?;
    out.set_item("modos", por_nudo(&r.modos, n).into_pyarray(py))?;
    out.set_item("inercias", por_nudo(&r.inercias, n).into_pyarray(py))?;
    out.set_item(
        "factores_participacion",
        filas3(&r.factores_participacion).into_pyarray(py),
    )?;
    out.set_item(
        "masas_efectivas",
        filas3(&r.masas_efectivas).into_pyarray(py),
    )?;
    out.set_item(
        "masa_total",
        Array1::from(r.masa_total.to_vec()).into_pyarray(py),
    )?;
    out.set_item("n_gdl_masa", r.n_gdl_masa)?;
    out.set_item(
        "metodo",
        match r.metodo {
            MetodoModal::Lanczos => "lanczos",
            _ => "denso",
        },
    )?;
    let sin_rigidez = PyList::empty(py);
    for (nudo, gdl) in &r.gdl_sin_rigidez {
        sin_rigidez.append((*nudo, gdl.to_string()))?;
    }
    out.set_item("gdl_sin_rigidez", sin_rigidez)?;
    let diafragmas = PyList::empty(py);
    for d in &r.diafragmas {
        let dic = PyDict::new(py);
        dic.set_item("maestro", d.maestro)?;
        dic.set_item("masa", d.masa.to_vec())?;
        dic.set_item("centro_masa", d.centro_masa.to_vec())?;
        dic.set_item("inercia", d.inercia)?;
        diafragmas.append(dic)?;
    }
    out.set_item("diafragmas", diafragmas)?;
    Ok(out)
}

/// Respuesta por espectro en una dirección (contrato de dinámica, versión 1).
///
/// Toma los modos de `resolver_modal_3d` (`omegas (n_modos,)`, `modos` e
/// `inercias (n_modos, n_nudos, 6)`) y el espectro `periodos_espectro`,
/// `aceleraciones_espectro` (mismo largo, periodos crecientes). `combinacion`
/// 0 = SRSS, 1 = CQC. Devuelve las magnitudes combinadas (valores absolutos)
/// `desplazamientos, reacciones (n_nudos, 6)`, `fuerzas_extremo (n_barras,
/// 12)`, `cortante_basal (3,)`, `diagramas` (como un caso de
/// `resolver_portico_3d`, en estaciones equidistantes), y por modo
/// `aceleraciones`, `factores`, `cortante_basal_modal (n_modos, 3)` y
/// `correlacion (n_modos, n_modos)`.
#[pyfunction]
#[pyo3(signature = (
    version, modelo, omegas, modos, inercias, periodos_espectro, aceleraciones_espectro,
    direccion, amortiguamiento, combinacion, n_estaciones = 11
))]
#[allow(clippy::too_many_arguments)]
fn espectro_3d<'py>(
    py: Python<'py>,
    version: u32,
    modelo: &Bound<'py, PyDict>,
    omegas: PyReadonlyArray1<'py, f64>,
    modos: PyReadonlyArray3<'py, f64>,
    inercias: PyReadonlyArray3<'py, f64>,
    periodos_espectro: PyReadonlyArray1<'py, f64>,
    aceleraciones_espectro: PyReadonlyArray1<'py, f64>,
    direccion: PyReadonlyArray1<'py, f64>,
    amortiguamiento: f64,
    combinacion: u8,
    n_estaciones: usize,
) -> PyResult<Bound<'py, PyDict>> {
    verificar_version_dinamica(version)?;
    let modelo = modelo_desde_dict(modelo)?;
    let (n, m) = (modelo.nudos.len(), modelo.barras.len());
    let omegas = omegas.as_array();
    let modos = modos.as_array();
    let inercias = inercias.as_array();
    let direccion = direccion.as_array();
    let nm = omegas.len();
    verificar_forma("modos", modos.shape(), &[nm, n, 6])?;
    verificar_forma("inercias", inercias.shape(), &[nm, n, 6])?;
    verificar_forma("direccion", direccion.shape(), &[3])?;
    let leer = |a: &numpy::ndarray::ArrayView3<'_, f64>| -> Vec<Vec<[f64; 6]>> {
        (0..nm)
            .map(|k| {
                (0..n)
                    .map(|i| std::array::from_fn(|d| a[[k, i, d]]))
                    .collect()
            })
            .collect()
    };
    let modal = ResultadosModal3d {
        omegas: omegas.to_vec(),
        periodos: omegas
            .iter()
            .map(|w| 2.0 * std::f64::consts::PI / w)
            .collect(),
        frecuencias: omegas
            .iter()
            .map(|w| w / (2.0 * std::f64::consts::PI))
            .collect(),
        modos: leer(&modos),
        inercias: leer(&inercias),
        factores_participacion: Vec::new(),
        masas_efectivas: Vec::new(),
        masa_total: [0.0; 3],
        gdl_sin_rigidez: Vec::new(),
        n_gdl_masa: 0,
        metodo: MetodoModal::Automatico,
        diafragmas: Vec::new(),
    };
    let espectro = Espectro::new(
        periodos_espectro.as_array().to_vec(),
        aceleraciones_espectro.as_array().to_vec(),
    )
    .map_err(|e| error_a_python(py, e))?;
    let combinacion = match combinacion {
        0 => CombinacionModal::Srss,
        1 => CombinacionModal::Cqc,
        t => {
            return Err(PyValueError::new_err(format!(
                "combinación {t} desconocida (0 = SRSS, 1 = CQC)"
            )))
        }
    };
    let dir = [direccion[0], direccion[1], direccion[2]];
    let r = py
        .detach(|| {
            analizar_espectro_3d(
                &modelo,
                &modal,
                &espectro,
                dir,
                amortiguamiento,
                combinacion,
            )
        })
        .map_err(|e| error_a_python(py, e))?;

    let out = PyDict::new(py);
    out.set_item(
        "desplazamientos",
        Array2::from_shape_fn((n, 6), |(i, d)| r.desplazamientos[i][d]).into_pyarray(py),
    )?;
    out.set_item(
        "reacciones",
        Array2::from_shape_fn((n, 6), |(i, d)| r.reacciones[i][d]).into_pyarray(py),
    )?;
    out.set_item(
        "fuerzas_extremo",
        Array2::from_shape_fn((m, 12), |(i, d)| r.fuerzas_extremo[i][d]).into_pyarray(py),
    )?;
    out.set_item(
        "cortante_basal",
        Array1::from(r.cortante_basal.to_vec()).into_pyarray(py),
    )?;
    out.set_item(
        "cortante_basal_modal",
        filas3(&r.cortante_basal_modal).into_pyarray(py),
    )?;
    out.set_item(
        "aceleraciones",
        Array1::from(r.aceleraciones.clone()).into_pyarray(py),
    )?;
    out.set_item(
        "factores",
        Array1::from(r.factores.clone()).into_pyarray(py),
    )?;
    out.set_item(
        "correlacion",
        Array2::from_shape_fn((nm, nm), |(i, j)| r.correlacion[i][j]).into_pyarray(py),
    )?;
    let mut cols: [Vec<f64>; 11] = Default::default();
    let mut barra_col: Vec<i64> = Vec::new();
    for k in 0..m {
        for s in r.diagrama(k, n_estaciones) {
            barra_col.push(k as i64);
            for (col, val) in cols
                .iter_mut()
                .zip([s.x, s.n, s.vy, s.vz, s.t, s.my, s.mz, s.u, s.v, s.w, s.rx])
            {
                col.push(val);
            }
        }
    }
    let dic = PyDict::new(py);
    dic.set_item("barra", barra_col.into_pyarray(py))?;
    for (nombre, col) in ["x", "N", "Vy", "Vz", "T", "My", "Mz", "u", "v", "w", "rx"]
        .iter()
        .zip(cols)
    {
        dic.set_item(*nombre, col.into_pyarray(py))?;
    }
    out.set_item("diagramas", dic)?;
    Ok(out)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VERSION_CONTRATO", VERSION_CONTRATO)?;
    m.add("MecanismoError", m.py().get_type::<MecanismoError>())?;
    m.add("VERSION_CONTRATO_3D", VERSION_CONTRATO_3D)?;
    m.add_function(wrap_pyfunction!(resolver_portico_2d, m)?)?;
    m.add_function(wrap_pyfunction!(resolver_portico_3d, m)?)?;
    m.add("VERSION_CONTRATO_DINAMICA", VERSION_CONTRATO_DINAMICA)?;
    m.add_function(wrap_pyfunction!(resolver_modal_3d, m)?)?;
    m.add_function(wrap_pyfunction!(espectro_3d, m)?)?;
    m.add("VERSION_CONTRATO_DISENO", diseno::VERSION_CONTRATO_DISENO)?;
    m.add_function(wrap_pyfunction!(diseno::columna_seccion_en, m)?)?;
    m.add_function(wrap_pyfunction!(diseno::columna_capacidad, m)?)?;
    m.add_function(wrap_pyfunction!(diseno::columna_razones, m)?)?;
    m.add_function(wrap_pyfunction!(diseno::columna_elegir_armadura, m)?)?;
    m.add_function(wrap_pyfunction!(diseno::viga_resistencia, m)?)?;
    m.add_function(wrap_pyfunction!(diseno::viga_armadura_simple, m)?)?;
    m.add_function(wrap_pyfunction!(diseno::viga_elegir_barras, m)?)?;
    m.add("VERSION_CONTRATO_LOSAS", losas::VERSION_CONTRATO_LOSAS)?;
    m.add_function(wrap_pyfunction!(losas::repartir_losas, m)?)?;
    m.add_class::<enganche::IndiceEnganche>()?;
    m.add_function(wrap_pyfunction!(enganche::pano_en, m)?)?;
    m.add_function(wrap_pyfunction!(enganche::cruces, m)?)?;
    m.add_function(wrap_pyfunction!(enganche::partir, m)?)?;
    Ok(())
}
