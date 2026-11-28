// SPDX-License-Identifier: GPL-3.0-or-later
//! Geometría en planta para las herramientas de dibujo del edificio (#73, #31).
//!
//! - [`pano_en`]: el paño cerrado por vigas y muros que contiene un punto (la
//!   herramienta *Losa* crea la losa con un clic adentro).
//! - [`cruces`]: los cruces entre segmentos (columnas en los cruces de los ejes).
//! - [`partir`]: dónde cortar un segmento en los puntos que caen sobre él (una viga
//!   dibujada de punta a punta se parte en cada columna).
//!
//! El paño se busca en el grafo plano de los segmentos partidos en sus cruces: se
//! quitan las puntas sueltas (vértices de grado 1), se tira un rayo desde el punto
//! hasta el primer lado que toca y se recorre la cara que queda a la izquierda,
//! tomando en cada vértice el lado siguiente en sentido horario desde el que se
//! llegó (recorrido de caras de una subdivisión plana; de Berg, Cheong, van Kreveld
//! y Overmars, *Computational Geometry*, 3.ª ed., §2.2). Si la cara es la exterior
//! (área con signo negativa) no hay paño. Las islas dentro del paño no cuentan.

use std::collections::HashMap;

fn sub(a: [f64; 2], b: [f64; 2]) -> [f64; 2] {
    [a[0] - b[0], a[1] - b[1]]
}

fn cruz(a: [f64; 2], b: [f64; 2]) -> f64 {
    a[0] * b[1] - a[1] * b[0]
}

fn largo(a: [f64; 2]) -> f64 {
    a[0].hypot(a[1])
}

/// Parámetros `(t, u)` del cruce de los segmentos `a` y `b`, si se cruzan (con los
/// extremos incluidos, a menos de `tol` en largo).
fn cruce(a: [[f64; 2]; 2], b: [[f64; 2]; 2], tol: f64) -> Option<(f64, f64)> {
    let r = sub(a[1], a[0]);
    let s = sub(b[1], b[0]);
    let (lr, ls) = (largo(r), largo(s));
    let den = cruz(r, s);
    if lr == 0.0 || ls == 0.0 || den.abs() <= 1e-12 * lr * ls {
        return None;
    }
    let q = sub(b[0], a[0]);
    let t = cruz(q, s) / den;
    let u = cruz(q, r) / den;
    let (et, eu) = (tol / lr, tol / ls);
    ((-et..=1.0 + et).contains(&t) && (-eu..=1.0 + eu).contains(&u))
        .then(|| (t.clamp(0.0, 1.0), u.clamp(0.0, 1.0)))
}

/// Parámetro del punto `p` sobre el segmento `s` si está a menos de `tol` de él.
fn sobre(p: [f64; 2], s: [[f64; 2]; 2], tol: f64) -> Option<f64> {
    let d = sub(s[1], s[0]);
    let l2 = d[0] * d[0] + d[1] * d[1];
    if l2 == 0.0 {
        return None;
    }
    let t = (sub(p, s[0])[0] * d[0] + sub(p, s[0])[1] * d[1]) / l2;
    let q = [s[0][0] + t * d[0], s[0][1] + t * d[1]];
    let et = tol / l2.sqrt();
    ((-et..=1.0 + et).contains(&t) && largo(sub(p, q)) <= tol).then(|| t.clamp(0.0, 1.0))
}

/// Dónde partir el segmento `s` en los `puntos` que caen sobre él (a menos de `tol`),
/// sin contar sus extremos: parámetros entre 0 y 1, ordenados y sin repetir.
pub fn partir(s: [[f64; 2]; 2], puntos: &[[f64; 2]], tol: f64) -> Vec<f64> {
    let l = largo(sub(s[1], s[0]));
    if l == 0.0 {
        return Vec::new();
    }
    let et = tol / l;
    let mut ts: Vec<f64> = puntos
        .iter()
        .filter_map(|&p| sobre(p, s, tol))
        .filter(|&t| t > et && t < 1.0 - et)
        .collect();
    ts.sort_by(f64::total_cmp);
    ts.dedup_by(|a, b| (*a - *b) <= et);
    ts
}

/// Cruces entre los segmentos (cada par una vez), sin repetir puntos a menos de `tol`.
pub fn cruces(segmentos: &[[[f64; 2]; 2]], tol: f64) -> Vec<[f64; 2]> {
    let mut salida = Vertices::new(tol);
    for i in 0..segmentos.len() {
        for j in i + 1..segmentos.len() {
            if let Some((t, _)) = cruce(segmentos[i], segmentos[j], tol) {
                let [a, b] = segmentos[i];
                salida.indice([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
            }
        }
    }
    salida.puntos
}

/// Vértices únicos a menos de `tol` (grilla de celdas de lado `tol`).
struct Vertices {
    tol: f64,
    puntos: Vec<[f64; 2]>,
    celdas: HashMap<(i64, i64), Vec<usize>>,
}

impl Vertices {
    fn new(tol: f64) -> Self {
        Self {
            tol: tol.max(f64::MIN_POSITIVE),
            puntos: Vec::new(),
            celdas: HashMap::new(),
        }
    }

    fn celda(&self, p: [f64; 2]) -> (i64, i64) {
        (
            (p[0] / self.tol).floor() as i64,
            (p[1] / self.tol).floor() as i64,
        )
    }

    fn indice(&mut self, p: [f64; 2]) -> usize {
        let (i, j) = self.celda(p);
        for di in -1..=1 {
            for dj in -1..=1 {
                if let Some(v) = self.celdas.get(&(i + di, j + dj)) {
                    for &k in v {
                        if largo(sub(self.puntos[k], p)) <= self.tol {
                            return k;
                        }
                    }
                }
            }
        }
        let k = self.puntos.len();
        self.puntos.push(p);
        self.celdas.entry((i, j)).or_default().push(k);
        k
    }
}

/// El paño cerrado por los `segmentos` que contiene `p`, como polígono antihorario
/// sin vértices alineados, empezando por el de más abajo (y más a la izquierda);
/// `None` si `p` no está dentro de ninguno. `tol` es la
/// distancia a la que dos puntos se consideran el mismo.
pub fn pano_en(segmentos: &[[[f64; 2]; 2]], p: [f64; 2], tol: f64) -> Option<Vec<[f64; 2]>> {
    // 1. Partir cada segmento en sus cruces con los demás.
    let n = segmentos.len();
    let mut cortes: Vec<Vec<f64>> = vec![vec![0.0, 1.0]; n];
    for i in 0..n {
        let [a, b] = segmentos[i];
        let (x0, x1) = (a[0].min(b[0]) - tol, a[0].max(b[0]) + tol);
        let (y0, y1) = (a[1].min(b[1]) - tol, a[1].max(b[1]) + tol);
        for j in i + 1..n {
            let [c, d] = segmentos[j];
            if c[0].max(d[0]) < x0
                || c[0].min(d[0]) > x1
                || c[1].max(d[1]) < y0
                || c[1].min(d[1]) > y1
            {
                continue;
            }
            if let Some((t, u)) = cruce(segmentos[i], segmentos[j], tol) {
                cortes[i].push(t);
                cortes[j].push(u);
            } else {
                // Superpuestos o colineales: los extremos de uno parten al otro.
                for q in [c, d] {
                    if let Some(t) = sobre(q, segmentos[i], tol) {
                        cortes[i].push(t);
                    }
                }
                for q in [a, b] {
                    if let Some(u) = sobre(q, segmentos[j], tol) {
                        cortes[j].push(u);
                    }
                }
            }
        }
    }
    // 2. Vértices y lados únicos.
    let mut vert = Vertices::new(tol);
    let mut lados: Vec<(usize, usize)> = Vec::new();
    for (i, ts) in cortes.iter_mut().enumerate() {
        ts.sort_by(f64::total_cmp);
        let [a, b] = segmentos[i];
        let mut anterior: Option<usize> = None;
        for &t in ts.iter() {
            let k = vert.indice([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
            if let Some(j) = anterior {
                if j != k {
                    lados.push((j.min(k), j.max(k)));
                }
            }
            anterior = Some(k);
        }
    }
    lados.sort_unstable();
    lados.dedup();
    let pts = vert.puntos;
    let nv = pts.len();
    // 3. Quitar las puntas sueltas (grado 1) hasta que no quede ninguna.
    let mut vecinos: Vec<Vec<usize>> = vec![Vec::new(); nv];
    for &(a, b) in &lados {
        vecinos[a].push(b);
        vecinos[b].push(a);
    }
    let mut pila: Vec<usize> = (0..nv).filter(|&v| vecinos[v].len() == 1).collect();
    while let Some(v) = pila.pop() {
        if vecinos[v].len() != 1 {
            continue;
        }
        let w = vecinos[v][0];
        vecinos[v].clear();
        vecinos[w].retain(|&x| x != v);
        if vecinos[w].len() == 1 {
            pila.push(w);
        }
    }
    // 4. Vecinos ordenados por ángulo (antihorario).
    for (v, vs) in vecinos.iter_mut().enumerate() {
        vs.sort_by(|&a, &b| {
            let da = sub(pts[a], pts[v]);
            let db = sub(pts[b], pts[v]);
            da[1].atan2(da[0]).total_cmp(&db[1].atan2(db[0]))
        });
    }
    // 5. Rayo desde p en una dirección cualquiera (no paralela a los ejes, para no
    //    pasar justo por un vértice en los casos comunes): el primer lado que toca.
    let dir = [0.937_212_3_f64.cos(), 0.937_212_3_f64.sin()];
    let mut primero: Option<(f64, usize, usize)> = None;
    for (a, vs) in vecinos.iter().enumerate() {
        for &b in vs {
            if a > b {
                continue;
            }
            let s = sub(pts[b], pts[a]);
            let den = cruz(dir, s);
            if den == 0.0 {
                continue;
            }
            let q = sub(pts[a], p);
            let t = cruz(q, s) / den; // distancia sobre el rayo
            let u = cruz(q, dir) / den; // parámetro sobre el lado
            if t > 0.0 && (0.0..=1.0).contains(&u) && primero.map_or(true, |(tm, _, _)| t < tm) {
                primero = Some((t, a, b));
            }
        }
    }
    let (_, a, b) = primero?;
    // El semilado que deja a p a su izquierda.
    let (mut desde, mut hasta) = if cruz(sub(pts[b], pts[a]), sub(p, pts[a])) > 0.0 {
        (a, b)
    } else {
        (b, a)
    };
    let inicio = (desde, hasta);
    let mut cara = vec![desde];
    for _ in 0..=2 * lados.len() {
        // Siguiente lado: el anterior en sentido antihorario al de vuelta (hasta→desde).
        let vs = &vecinos[hasta];
        let k = vs.iter().position(|&x| x == desde)?;
        let siguiente = vs[(k + vs.len() - 1) % vs.len()];
        desde = hasta;
        hasta = siguiente;
        if (desde, hasta) == inicio {
            break;
        }
        cara.push(desde);
    }
    if (desde, hasta) != inicio {
        return None;
    }
    let poligono: Vec<[f64; 2]> = cara.iter().map(|&v| pts[v]).collect();
    let area: f64 = (0..poligono.len())
        .map(|k| cruz(poligono[k], poligono[(k + 1) % poligono.len()]))
        .sum::<f64>()
        / 2.0;
    if area <= 0.0 {
        return None;
    }
    // 6. Sin vértices alineados (la viga partida en una columna deja uno).
    let m = poligono.len();
    let limpio: Vec<[f64; 2]> = (0..m)
        .filter(|&k| {
            let a = poligono[(k + m - 1) % m];
            let b = poligono[k];
            let c = poligono[(k + 1) % m];
            let (u, w) = (sub(b, a), sub(c, b));
            cruz(u, w).abs() > tol * largo(u).max(largo(w)) || (u[0] * w[0] + u[1] * w[1]) < 0.0
        })
        .map(|k| poligono[k])
        .collect();
    if limpio.len() < 3 {
        return None;
    }
    // Empieza en el vértice de abajo a la izquierda, para que el resultado no dependa
    // del orden de los segmentos.
    let k = (0..limpio.len())
        .min_by(|&i, &j| {
            limpio[i][1]
                .total_cmp(&limpio[j][1])
                .then(limpio[i][0].total_cmp(&limpio[j][0]))
        })
        .unwrap_or(0);
    let mut salida = limpio[k..].to_vec();
    salida.extend_from_slice(&limpio[..k]);
    Some(salida)
}
