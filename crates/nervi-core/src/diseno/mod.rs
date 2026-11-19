// SPDX-License-Identifier: GPL-3.0-or-later
//! Diseño según norma: los cálculos que recorren secciones, solicitaciones y
//! armaduras candidatas. La API pública, los datos de entrada y la presentación
//! siguen en Python (`nervi.design`); aquí va solo el cálculo pesado.
//!
//! **Experimental**: implementa métodos de ACI 318-19 y todavía no fue revisado
//! por un ingeniero estructural.

pub mod columna;
