// SPDX-License-Identifier: GPL-3.0-or-later
//! Enganche de puntos para dibujar con el mouse en planta (Fase 5, #31; Fase 7, #73).
//!
//! Dado el cursor en coordenadas del modelo, busca el punto notable más cercano de
//! la geometría dibujada (extremos, puntos medios, cruces, pies de perpendicular,
//! columnas), o bien una guía (líneas polares desde el punto anterior y
//! prolongaciones de los segmentos recientes), o la grilla.
//!
//! Los tipos de enganche y su orden siguen el `Snapper` del banco Draft de FreeCAD
//! (`src/Mod/Draft/draftguitools/gui_snapper.py`, Yorik van Havre y colaboradores,
//! LGPL-2.1-or-later): primero los puntos notables del objeto bajo el cursor (gana
//! el más cercano), después las líneas polares (`snapToPolar`), las prolongaciones
//! de los objetos recientes (`snapToExtensions`) y su cruce
//! (`snapToCrossExtensions`), y por último la grilla (`snapToGrid`). Aquí se
//! reescribe en Rust para segmentos y puntos en planta, sin depender de la escena 3D:
//! los objetos cercanos salen de un índice espacial de grilla uniforme y no del
//! "objeto bajo el cursor" de la vista. Se agregan dos reglas propias:
//!
//! - el cruce de una línea polar con un segmento cercano es un punto notable, y
//! - el modo *Orto* (F8) obliga el punto sobre la línea polar más cercana cuando
//!   no hay un punto notable, con la distancia redondeada al paso de la grilla.
//!
//! Geometría de base (fórmulas cerradas): proyección de un punto sobre una recta
//! `t = (p − a)·(b − a) / |b − a|²` e intersección de dos segmentos por la regla de
//! Cramer (por ejemplo, O'Rourke, *Computational Geometry in C*, 2.ª ed., §1.5).
//!
//! Todo recorre solo los elementos cerca del cursor, así que una consulta cuesta lo
//! mismo con 100 que con 100 000 elementos (banco en `scripts/medir_enganche.py`).

use std::f64::consts::PI;

/// Tipo de enganche encontrado, de mayor a menor prioridad dentro de cada grupo.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Tipo {
    /// Un punto suelto (columna, nudo).
    Punto,
    /// Extremo de un segmento.
    Extremo,
    /// Cruce de dos segmentos, o de un segmento con una línea polar.
    Cruce,
    /// Punto medio de un segmento.
    Medio,
    /// Pie de la perpendicular desde el punto anterior a un segmento.
    Perpendicular,
    /// El punto más cercano sobre un segmento.
    Cerca,
    /// Cruce de dos guías (línea polar y prolongación, o dos prolongaciones).
    CruceGuias,
    /// Sobre una línea polar desde el punto anterior.
    Polar,
    /// Sobre la prolongación de un segmento reciente.
    Prolongacion,
    /// Nudo de la grilla.
    Grilla,
    /// Sin enganche: el cursor tal cual.
    Libre,
}

impl Tipo {
    /// Nombre en el contrato con Python.
    pub fn nombre(self) -> &'static str {
        match self {
            Tipo::Punto => "punto",
            Tipo::Extremo => "extremo",
            Tipo::Cruce => "cruce",
            Tipo::Medio => "medio",
            Tipo::Perpendicular => "perpendicular",
            Tipo::Cerca => "cerca",
            Tipo::CruceGuias => "cruce_guias",
            Tipo::Polar => "polar",
            Tipo::Prolongacion => "prolongacion",
            Tipo::Grilla => "grilla",
            Tipo::Libre => "libre",
        }
    }

    fn rango(self) -> u8 {
        self as u8
    }
}

/// Qué enganches están activos y con qué parámetros.
#[derive(Clone, Debug)]
pub struct Opciones {
    /// Radio de captura en unidades del modelo (los píxeles de tolerancia divididos
    /// por la escala de la vista).
    pub radio: f64,
    /// Punto anterior del trazo en curso, si lo hay (polar, perpendicular, orto).
    pub anterior: Option<[f64; 2]>,
    pub puntos: bool,
    pub extremos: bool,
    pub medios: bool,
    pub cruces: bool,
    pub perpendicular: bool,
    pub cerca: bool,
    /// Paso de las líneas polares en grados (90 = horizontal y vertical); 0 las apaga.
    pub paso_polar: f64,
    /// Orto (F8): sin punto notable, el punto va sobre la línea polar más cercana.
    pub orto: bool,
    /// Segmentos recientes cuya prolongación sirve de guía.
    pub recientes: Vec<usize>,
    /// Paso de la grilla (0 la apaga); la grilla pasa por el origen.
    pub paso_grilla: f64,
}

impl Default for Opciones {
    fn default() -> Self {
        Self {
            radio: 0.0,
            anterior: None,
            puntos: true,
            extremos: true,
            medios: true,
            cruces: true,
            perpendicular: true,
            cerca: true,
            paso_polar: 90.0,
            orto: false,
            recientes: Vec::new(),
            paso_grilla: 0.0,
        }
    }
}

/// Resultado de una consulta.
#[derive(Clone, Debug, PartialEq)]
pub struct Enganche {
    pub punto: [f64; 2],
    pub tipo: Tipo,
    /// Índice del punto (para [`Tipo::Punto`]) o del segmento enganchado; en un
    /// cruce, el primero de los dos.
    pub elemento: Option<usize>,
    /// Segundo segmento de un cruce.
    pub otro: Option<usize>,
    /// Guía a dibujar (de dónde sale la línea polar o la prolongación hasta el punto).
    pub guia: Option<[[f64; 2]; 2]>,
}

/// Índice espacial de la geometría en planta: puntos sueltos y segmentos.
#[derive(Clone, Debug)]
pub struct IndiceEnganche {
    puntos: Vec<[f64; 2]>,
    segmentos: Vec<[[f64; 2]; 2]>,
    origen: [f64; 2],
    celda: f64,
    nx: usize,
    ny: usize,
    /// Para cada celda, los puntos y segmentos que la tocan.
    celdas_puntos: Vec<Vec<u32>>,
    celdas_segmentos: Vec<Vec<u32>>,
}

const MAX_CELDAS: usize = 1 << 20;

fn sub(a: [f64; 2], b: [f64; 2]) -> [f64; 2] {
    [a[0] - b[0], a[1] - b[1]]
}

fn dist(a: [f64; 2], b: [f64; 2]) -> f64 {
    (a[0] - b[0]).hypot(a[1] - b[1])
}

fn cruz(a: [f64; 2], b: [f64; 2]) -> f64 {
    a[0] * b[1] - a[1] * b[0]
}

/// Parámetro de la proyección de `p` sobre la recta `a`→`b` (0 en `a`, 1 en `b`).
fn parametro(p: [f64; 2], a: [f64; 2], b: [f64; 2]) -> Option<f64> {
    let d = sub(b, a);
    let l2 = d[0] * d[0] + d[1] * d[1];
    if l2 == 0.0 {
        return None;
    }
    let q = sub(p, a);
    Some((q[0] * d[0] + q[1] * d[1]) / l2)
}

fn en(a: [f64; 2], b: [f64; 2], t: f64) -> [f64; 2] {
    [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
}

/// Intersección de las rectas `a1`→`a2` y `b1`→`b2`: parámetros `(t, u)` sobre cada una.
fn interseccion(a1: [f64; 2], a2: [f64; 2], b1: [f64; 2], b2: [f64; 2]) -> Option<(f64, f64)> {
    let r = sub(a2, a1);
    let s = sub(b2, b1);
    let den = cruz(r, s);
    let escala = (r[0].hypot(r[1])) * (s[0].hypot(s[1]));
    if den.abs() <= 1e-12 * escala || escala == 0.0 {
        return None; // paralelas o degeneradas
    }
    let q = sub(b1, a1);
    Some((cruz(q, s) / den, cruz(q, r) / den))
}

const TOL_PARAM: f64 = 1e-9;

/// Guía: recta por dos puntos, su tipo y el segmento del que sale, si lo hay.
type Guia = ([f64; 2], [f64; 2], Tipo, Option<usize>);

fn dentro(t: f64) -> bool {
    (-TOL_PARAM..=1.0 + TOL_PARAM).contains(&t)
}

impl IndiceEnganche {
    /// Arma el índice. Los segmentos de largo cero se tratan como puntos de sus extremos.
    pub fn nuevo(puntos: Vec<[f64; 2]>, segmentos: Vec<[[f64; 2]; 2]>) -> Self {
        let mut x0 = f64::INFINITY;
        let mut y0 = f64::INFINITY;
        let mut x1 = f64::NEG_INFINITY;
        let mut y1 = f64::NEG_INFINITY;
        let mut suma = 0.0;
        for p in puntos.iter().chain(segmentos.iter().flatten()) {
            x0 = x0.min(p[0]);
            y0 = y0.min(p[1]);
            x1 = x1.max(p[0]);
            y1 = y1.max(p[1]);
        }
        for s in &segmentos {
            suma += dist(s[0], s[1]);
        }
        let n = puntos.len() + segmentos.len();
        if n == 0 || !x0.is_finite() {
            return Self {
                puntos,
                segmentos,
                origen: [0.0, 0.0],
                celda: 1.0,
                nx: 0,
                ny: 0,
                celdas_puntos: Vec::new(),
                celdas_segmentos: Vec::new(),
            };
        }
        let ancho = (x1 - x0).max(y1 - y0).max(1e-9);
        // Celda del orden del largo medio de los segmentos, sin pasar de MAX_CELDAS.
        let medio = if segmentos.is_empty() {
            ancho / (n as f64).sqrt().max(1.0)
        } else {
            suma / segmentos.len() as f64
        };
        let mut celda = medio.max(ancho / 1024.0).max(1e-9);
        let mut nx = ((x1 - x0) / celda).floor() as usize + 1;
        let mut ny = ((y1 - y0) / celda).floor() as usize + 1;
        while nx * ny > MAX_CELDAS {
            celda *= 2.0;
            nx = ((x1 - x0) / celda).floor() as usize + 1;
            ny = ((y1 - y0) / celda).floor() as usize + 1;
        }
        let mut idx = Self {
            puntos,
            segmentos,
            origen: [x0, y0],
            celda,
            nx,
            ny,
            celdas_puntos: vec![Vec::new(); nx * ny],
            celdas_segmentos: vec![Vec::new(); nx * ny],
        };
        for (k, p) in idx.puntos.iter().enumerate() {
            let (i, j) = idx.celda_de(*p);
            idx.celdas_puntos[j * nx + i].push(k as u32);
        }
        for k in 0..idx.segmentos.len() {
            let [a, b] = idx.segmentos[k];
            let (i0, j0) = idx.celda_de([a[0].min(b[0]), a[1].min(b[1])]);
            let (i1, j1) = idx.celda_de([a[0].max(b[0]), a[1].max(b[1])]);
            for j in j0..=j1 {
                for i in i0..=i1 {
                    if idx.toca_celda(a, b, i, j) {
                        idx.celdas_segmentos[j * nx + i].push(k as u32);
                    }
                }
            }
        }
        idx
    }

    pub fn puntos(&self) -> &[[f64; 2]] {
        &self.puntos
    }

    pub fn segmentos(&self) -> &[[[f64; 2]; 2]] {
        &self.segmentos
    }

    fn celda_de(&self, p: [f64; 2]) -> (usize, usize) {
        let i = ((p[0] - self.origen[0]) / self.celda).floor();
        let j = ((p[1] - self.origen[1]) / self.celda).floor();
        (
            (i.max(0.0) as usize).min(self.nx - 1),
            (j.max(0.0) as usize).min(self.ny - 1),
        )
    }

    /// ¿El segmento pasa por la celda (i, j)? Prueba de separación del segmento con
    /// la caja de la celda (agrandada un poco por el redondeo).
    fn toca_celda(&self, a: [f64; 2], b: [f64; 2], i: usize, j: usize) -> bool {
        let m = self.celda * 1e-9;
        let cx0 = self.origen[0] + i as f64 * self.celda - m;
        let cy0 = self.origen[1] + j as f64 * self.celda - m;
        let cx1 = cx0 + self.celda + 2.0 * m;
        let cy1 = cy0 + self.celda + 2.0 * m;
        let d = sub(b, a);
        let esquinas = [[cx0, cy0], [cx1, cy0], [cx1, cy1], [cx0, cy1]];
        let lados: Vec<f64> = esquinas.iter().map(|c| cruz(d, sub(*c, a))).collect();
        let todos_pos = lados.iter().all(|&v| v > 0.0);
        let todos_neg = lados.iter().all(|&v| v < 0.0);
        !(todos_pos || todos_neg)
    }

    /// Puntos y segmentos de las celdas que tocan el cuadrado de lado 2r alrededor de `c`.
    fn cercanos(&self, c: [f64; 2], r: f64) -> (Vec<u32>, Vec<u32>) {
        if self.nx == 0 {
            return (Vec::new(), Vec::new());
        }
        let x0 = c[0] - r;
        let y0 = c[1] - r;
        let x1 = c[0] + r;
        let y1 = c[1] + r;
        let fuera = x1 < self.origen[0]
            || y1 < self.origen[1]
            || x0 > self.origen[0] + self.nx as f64 * self.celda
            || y0 > self.origen[1] + self.ny as f64 * self.celda;
        if fuera {
            return (Vec::new(), Vec::new());
        }
        let (i0, j0) = self.celda_de([x0, y0]);
        let (i1, j1) = self.celda_de([x1, y1]);
        let mut pts = Vec::new();
        let mut segs = Vec::new();
        for j in j0..=j1 {
            for i in i0..=i1 {
                pts.extend_from_slice(&self.celdas_puntos[j * self.nx + i]);
                segs.extend_from_slice(&self.celdas_segmentos[j * self.nx + i]);
            }
        }
        segs.sort_unstable();
        segs.dedup();
        (pts, segs)
    }

    /// Engancha el cursor `c` según `op`.
    pub fn enganchar(&self, c: [f64; 2], op: &Opciones) -> Enganche {
        let r = op.radio;
        let (pts, segs) = self.cercanos(c, r);
        let mut mejor: Option<(f64, Enganche)> = None;
        let proponer = |d: f64, e: Enganche, mejor: &mut Option<(f64, Enganche)>| {
            if d > r {
                return;
            }
            let gana = match mejor {
                None => true,
                Some((dm, em)) => d < *dm || (d == *dm && e.tipo.rango() < em.tipo.rango()),
            };
            if gana {
                *mejor = Some((d, e));
            }
        };
        let enganche = |punto, tipo, elemento, otro, guia| Enganche {
            punto,
            tipo,
            elemento,
            otro,
            guia,
        };

        // 1. Puntos notables (snapToObject): gana el más cercano al cursor.
        if op.puntos {
            for &k in &pts {
                let p = self.puntos[k as usize];
                proponer(
                    dist(p, c),
                    enganche(p, Tipo::Punto, Some(k as usize), None, None),
                    &mut mejor,
                );
            }
        }
        // Segmentos que pasan a menos de r del cursor.
        let mut cerca: Vec<(u32, f64, [f64; 2])> = Vec::new();
        for &k in &segs {
            let [a, b] = self.segmentos[k as usize];
            let Some(t) = parametro(c, a, b) else {
                continue;
            };
            let q = en(a, b, t.clamp(0.0, 1.0));
            let d = dist(q, c);
            if d <= r {
                cerca.push((k, d, q));
            }
        }
        for &(k, _, _) in &cerca {
            let ku = k as usize;
            let [a, b] = self.segmentos[ku];
            if op.extremos {
                for p in [a, b] {
                    proponer(
                        dist(p, c),
                        enganche(p, Tipo::Extremo, Some(ku), None, None),
                        &mut mejor,
                    );
                }
            }
            if op.medios {
                let m = en(a, b, 0.5);
                proponer(
                    dist(m, c),
                    enganche(m, Tipo::Medio, Some(ku), None, None),
                    &mut mejor,
                );
            }
            if op.perpendicular {
                if let Some(ant) = op.anterior {
                    if let Some(t) = parametro(ant, a, b) {
                        if dentro(t) {
                            let p = en(a, b, t);
                            proponer(
                                dist(p, c),
                                enganche(p, Tipo::Perpendicular, Some(ku), None, Some([ant, p])),
                                &mut mejor,
                            );
                        }
                    }
                }
            }
        }
        if op.cruces {
            for (n, &(k1, _, _)) in cerca.iter().enumerate() {
                let [a1, a2] = self.segmentos[k1 as usize];
                for &(k2, _, _) in &cerca[n + 1..] {
                    let [b1, b2] = self.segmentos[k2 as usize];
                    if let Some((t, u)) = interseccion(a1, a2, b1, b2) {
                        if dentro(t) && dentro(u) {
                            let p = en(a1, a2, t);
                            proponer(
                                dist(p, c),
                                enganche(
                                    p,
                                    Tipo::Cruce,
                                    Some(k1 as usize),
                                    Some(k2 as usize),
                                    None,
                                ),
                                &mut mejor,
                            );
                        }
                    }
                }
            }
        }
        // Líneas polares desde el punto anterior (snapToPolar).
        let polares = self.polares(op);
        // Cruce de una línea polar con un segmento cercano: punto notable.
        if op.cruces {
            if let Some(ant) = op.anterior {
                for &dir in &polares {
                    let fin = [ant[0] + dir[0], ant[1] + dir[1]];
                    for &(k, _, _) in &cerca {
                        let [a, b] = self.segmentos[k as usize];
                        if let Some((t, u)) = interseccion(ant, fin, a, b) {
                            if t > TOL_PARAM && dentro(u) {
                                let p = en(ant, fin, t);
                                proponer(
                                    dist(p, c),
                                    enganche(
                                        p,
                                        Tipo::Cruce,
                                        Some(k as usize),
                                        None,
                                        Some([ant, p]),
                                    ),
                                    &mut mejor,
                                );
                            }
                        }
                    }
                }
            }
        }
        if let Some((_, e)) = mejor {
            return e;
        }

        // 2. Orto: obliga el punto sobre la línea polar más cercana.
        if op.orto {
            if let Some(ant) = op.anterior {
                if let Some(e) = self.orto(c, ant, &polares, op) {
                    return e;
                }
            }
        }

        // 3. El punto más cercano sobre un segmento.
        if op.cerca {
            if let Some(&(k, _, q)) = cerca
                .iter()
                .min_by(|x, y| x.1.total_cmp(&y.1).then(x.0.cmp(&y.0)))
            {
                return enganche(q, Tipo::Cerca, Some(k as usize), None, None);
            }
        }

        // 4. Guías: líneas polares y prolongaciones de los segmentos recientes.
        let mut guias: Vec<Guia> = Vec::new();
        if let Some(ant) = op.anterior {
            for &dir in &polares {
                guias.push((ant, [ant[0] + dir[0], ant[1] + dir[1]], Tipo::Polar, None));
            }
        }
        for &k in &op.recientes {
            if let Some(&[a, b]) = self.segmentos.get(k) {
                if dist(a, b) > 0.0 {
                    guias.push((a, b, Tipo::Prolongacion, Some(k)));
                }
            }
        }
        // Las guías que pasan a menos de r del cursor (una prolongación, solo fuera
        // del segmento, como en snapToExtensions).
        let mut activas: Vec<(usize, f64, [f64; 2])> = Vec::new();
        for (n, &(a, b, tipo, _)) in guias.iter().enumerate() {
            let Some(t) = parametro(c, a, b) else {
                continue;
            };
            if tipo == Tipo::Polar && t <= 0.0 {
                continue;
            }
            if tipo == Tipo::Prolongacion && dentro(t) {
                continue;
            }
            let q = en(a, b, t);
            let d = dist(q, c);
            if d <= r {
                activas.push((n, d, q));
            }
        }
        // Cruce de dos guías (snapToCrossExtensions).
        let mut mejor_cruce: Option<(f64, Enganche)> = None;
        for (i, &(n1, _, _)) in activas.iter().enumerate() {
            for &(n2, _, _) in &activas[i + 1..] {
                let (a1, b1, _, k1) = guias[n1];
                let (a2, b2, _, k2) = guias[n2];
                if let Some((t, _)) = interseccion(a1, b1, a2, b2) {
                    let p = en(a1, b1, t);
                    let d = dist(p, c);
                    let gana = d <= r && mejor_cruce.as_ref().map_or(true, |(dm, _)| d < *dm);
                    if gana {
                        let desde = if guias[n1].2 == Tipo::Polar { a1 } else { a2 };
                        mejor_cruce = Some((
                            d,
                            enganche(p, Tipo::CruceGuias, k1.or(k2), k2.and(k1), Some([desde, p])),
                        ));
                    }
                }
            }
        }
        if let Some((_, e)) = mejor_cruce {
            return e;
        }
        if let Some(&(n, _, q)) = activas
            .iter()
            .min_by(|x, y| x.1.total_cmp(&y.1).then(x.0.cmp(&y.0)))
        {
            let (a, b, tipo, k) = guias[n];
            // La guía de una prolongación sale del extremo más cercano al punto.
            let desde = if tipo == Tipo::Prolongacion && dist(a, q) > dist(b, q) {
                b
            } else {
                a
            };
            let q = if tipo == Tipo::Polar {
                self.redondear_sobre(a, [b[0] - a[0], b[1] - a[1]], q, op.paso_grilla)
            } else {
                q
            };
            return enganche(q, tipo, k, None, Some([desde, q]));
        }

        // 5. Grilla (snapToGrid), o el cursor tal cual.
        if op.paso_grilla > 0.0 {
            let g = op.paso_grilla;
            let p = [(c[0] / g).round() * g, (c[1] / g).round() * g];
            return enganche(p, Tipo::Grilla, None, None, None);
        }
        enganche(c, Tipo::Libre, None, None, None)
    }

    /// Direcciones unitarias de las líneas polares (todas las vueltas de `paso_polar`).
    fn polares(&self, op: &Opciones) -> Vec<[f64; 2]> {
        if op.anterior.is_none() || op.paso_polar.is_nan() || op.paso_polar <= 0.0 {
            return Vec::new();
        }
        let n = (360.0 / op.paso_polar).round().max(1.0) as usize;
        (0..n)
            .map(|k| {
                let ang = (k as f64) * op.paso_polar * PI / 180.0;
                // Los múltiplos de 90° van exactos (cos 90° no da 0 en coma flotante).
                let grados = (k as f64) * op.paso_polar;
                if (grados % 90.0).abs() < 1e-9 {
                    match ((grados / 90.0).round() as i64).rem_euclid(4) {
                        0 => [1.0, 0.0],
                        1 => [0.0, 1.0],
                        2 => [-1.0, 0.0],
                        _ => [0.0, -1.0],
                    }
                } else {
                    [ang.cos(), ang.sin()]
                }
            })
            .collect()
    }

    /// Punto a la distancia de `ant` redondeada al paso de la grilla, sobre `dir`.
    fn redondear_sobre(&self, ant: [f64; 2], dir: [f64; 2], q: [f64; 2], paso: f64) -> [f64; 2] {
        if paso <= 0.0 {
            return q;
        }
        let l = dir[0].hypot(dir[1]);
        let t = ((q[0] - ant[0]) * dir[0] + (q[1] - ant[1]) * dir[1]) / l;
        let t = (t / paso).round() * paso;
        [ant[0] + t * dir[0] / l, ant[1] + t * dir[1] / l]
    }

    fn orto(
        &self,
        c: [f64; 2],
        ant: [f64; 2],
        polares: &[[f64; 2]],
        op: &Opciones,
    ) -> Option<Enganche> {
        // La línea polar de menor ángulo con la dirección del cursor.
        let v = sub(c, ant);
        let dir = polares
            .iter()
            .max_by(|a, b| (a[0] * v[0] + a[1] * v[1]).total_cmp(&(b[0] * v[0] + b[1] * v[1])))?;
        let t = v[0] * dir[0] + v[1] * dir[1];
        let q = [ant[0] + t * dir[0], ant[1] + t * dir[1]];
        let q = self.redondear_sobre(ant, *dir, q, op.paso_grilla);
        Some(Enganche {
            punto: q,
            tipo: Tipo::Polar,
            elemento: None,
            otro: None,
            guia: Some([ant, q]),
        })
    }

    /// Lo mismo que [`enganchar`](Self::enganchar) pero recorriendo todos los
    /// elementos, sin el índice. Sirve para comprobar el índice en las pruebas.
    pub fn enganchar_sin_indice(&self, c: [f64; 2], op: &Opciones) -> Enganche {
        // Un índice de una sola celda enorme con todo adentro: recorre todo.
        let uno = Self {
            puntos: self.puntos.clone(),
            segmentos: self.segmentos.clone(),
            origen: [f64::MIN / 4.0, f64::MIN / 4.0],
            celda: f64::MAX,
            nx: 1,
            ny: 1,
            celdas_puntos: vec![(0..self.puntos.len() as u32).collect()],
            celdas_segmentos: vec![(0..self.segmentos.len() as u32).collect()],
        };
        uno.enganchar(c, op)
    }
}
