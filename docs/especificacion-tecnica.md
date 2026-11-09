# Nervi — Especificación técnica v2

**Estado del documento:** borrador de diseño, corregido a partir de la versión generada por Gemini.
**Estado del código:** la Fase 0 y la Fase 1 (pórtico plano) están implementadas en el repositorio `bareirojero/Apex-BIM`. El resto es diseño propuesto. Ver `docs/contrato-datos.md` en el repositorio para el contrato vigente.

---

## 1. Visión

Nervi es un software libre para análisis estructural por el Método de los Elementos Finitos (MEF), dimensionamiento según normas y flujo de trabajo BIM (IFC). Busca ser una alternativa abierta a programas comerciales de cálculo de estructuras, empezando por el mercado sudamericano.

Principios:

- **Ejecución local.** Todo el cálculo corre en el equipo del usuario: sin costos de nube, datos privados, uso sin conexión.
- **Correctitud verificable.** Ningún módulo se integra sin casos de verificación reproducibles en CI.
- **Crecimiento por fases.** Cada fase entrega algo usable por un ingeniero antes de empezar la siguiente.
- **Responsabilidad profesional.** El software asiste al ingeniero; no lo reemplaza. Cada módulo normativo debe ser revisado por un ingeniero estructural antes de publicarse.

Identidad visual: el isotipo es una **N isométrica** en tres tonos de azul: `#3B82F6` al frente, `#93C5FD` / `#00E5FF` arriba y `#1E3A8A` al costado. El logotipo usa **Archivo 600**. Fondos oscuros en azul noche `#0B132B` / `#0F172A`. Hay versiones monocromas (blanco y negro) para usos de alto contraste. Archivos en `docs/marca/`.

### 1.1 Licencia (decidida)

**GPL-3.0-or-later para todo el proyecto**, incluido `nervi-core` (decisión del 2026-11-09, entrada 07 de la bitácora). Motivos:

- Impide que el motor se integre en software cerrado, que es lo que se busca en un proyecto que compite con programas comerciales.
- No limita a universidades: pueden usarlo, enseñar con él, modificarlo y publicar investigación.
- Es compatible con las dependencias previstas (PyQt6, PySide6, IfcOpenShell, VTK, ezdxf).

Se descartó MPL-2.0 o LGPL-3.0 para `nervi-core`, que solo convendría si se quisiera que empresas lo integren en productos cerrados. Cambiar la licencia más adelante requiere el permiso de todos los contribuyentes. Los aportes se aceptan con certificado de origen (DCO), sin cesión de derechos; ver `CONTRIBUTING.md` y `GOVERNANCE.md`.

---|---|---|
| GPL-3.0 para todo | Simple; compatible con PyQt6 e IfcOpenShell | Nadie puede integrar el motor en software cerrado |
| MPL-2.0 o LGPL-3.0 para `nervi-core`, GPL-3.0 para la app | El motor puede adoptarse como biblioteca, lo que atrae contribuyentes | Dos licencias que gestionar |

Se decide al crear el repositorio, porque cambiarla después requiere el permiso de todos los contribuyentes.

---

## 2. Arquitectura

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| `nervi-core` (Rust) | Rust edición 2021 o 2024, `faer` (álgebra densa y dispersa) | Elementos, ensamblaje, solucionadores, esfuerzos internos. Sin dependencias de Python. |
| `nervi-py` (puente) | PyO3 ≥ 0.21 (API `Bound`), `numpy` crate, Maturin | Conversión de arreglos NumPy ↔ Rust, validación de entradas, errores como excepciones Python. |
| `nervi` (Python) | Python ≥ 3.11, NumPy, SciPy | Modelo, casos y combinaciones de carga, normas de diseño, IO. |
| `nervi.ifc` | IfcOpenShell | Importación / exportación IFC4 e IFC4.3. |
| `nervi.gui` (fase posterior) | PySide6 o PyQt6 según licencia; PyVista/VTK o VisPy | CAD 3D y visualización de resultados. |

Motivo de `faer` sobre `nalgebra-sparse`: ofrece Cholesky y LU dispersos con reordenamiento para reducir el relleno, y rinde mucho mejor en sistemas grandes. `nalgebra` se puede usar para matrices pequeñas fijas si se prefiere, pero no hace falta mezclar con `ndarray`.

Estructura objetivo del repositorio:

```
nervi/
├── crates/
│   ├── nervi-core/        # motor MEF puro Rust
│   │   ├── src/{elements,assembly,solver,results,loads}.rs
│   │   └── tests/        # verificación analítica
│   └── nervi-py/          # binding PyO3
├── python/nervi/          # paquete Python
│   ├── model.py
│   ├── loads.py
│   ├── design/           # normas (fase 3)
│   └── ifc/              # fase 4
├── verification/         # casos de referencia (JSON + resultado esperado + fuente)
├── docs/
└── .github/workflows/ci.yml
```

---

## 3. Formulación del motor (Fase 1: pórtico plano)

### 3.1 Grados de libertad

- Pórtico plano: **3 GDL por nudo**, $\{u_x, u_y, \theta_z\}$. El nudo $i$ ocupa los índices globales $3i,\ 3i+1,\ 3i+2$.
- Cada barra tiene 2 nudos, por lo tanto **6 GDL por barra** y matriz de rigidez **6×6**.
- (Fase 2) Pórtico espacial: 6 GDL por nudo, matriz **12×12** por barra.

### 3.2 Rigidez local de la barra Euler-Bernoulli

$$
[k_{local}] =
\begin{bmatrix}
\frac{EA}{L} & 0 & 0 & -\frac{EA}{L} & 0 & 0 \\
0 & \frac{12EI}{L^3} & \frac{6EI}{L^2} & 0 & -\frac{12EI}{L^3} & \frac{6EI}{L^2} \\
0 & \frac{6EI}{L^2} & \frac{4EI}{L} & 0 & -\frac{6EI}{L^2} & \frac{2EI}{L} \\
-\frac{EA}{L} & 0 & 0 & \frac{EA}{L} & 0 & 0 \\
0 & -\frac{12EI}{L^3} & -\frac{6EI}{L^2} & 0 & \frac{12EI}{L^3} & -\frac{6EI}{L^2} \\
0 & \frac{6EI}{L^2} & \frac{2EI}{L} & 0 & -\frac{6EI}{L^2} & \frac{4EI}{L}
\end{bmatrix}
$$

**Liberaciones de extremo** (articulaciones): se aplican por condensación estática del GDL liberado sobre $[k_{local}]$ y $\{F_{eq}\}$ antes de transformar.

**Fase 2:** opción Timoshenko (deformación por cortante, $\Phi = \frac{12EI}{\kappa G A L^2}$) y brazos rígidos.

### 3.3 Transformación a coordenadas globales

Con $c = \cos\alpha = \frac{\Delta x}{L}$ y $s = \sin\alpha = \frac{\Delta y}{L}$:

$$
[\lambda] = \begin{bmatrix} c & s & 0 \\ -s & c & 0 \\ 0 & 0 & 1 \end{bmatrix},
\qquad
[T] = \begin{bmatrix} \lambda & 0 \\ 0 & \lambda \end{bmatrix},
\qquad
[k_{global}] = [T]^T [k_{local}] [T]
$$

En 3D (Fase 2), los ejes locales se definen con el eje $x$ a lo largo de la barra y un **vector de referencia** (o ángulo β) que fija el plano $x$–$y$ local. Las barras verticales necesitan una regla por defecto explícita.

### 3.4 Cargas en barras y convención de signos

**Convención:** ejes locales $x$ (de nudo $i$ a $j$), $y$ a 90° antihorario. Cargas $q_x$, $q_y$ positivas en sentido $+x$, $+y$ local. Esfuerzo axial $N$ positivo en tracción. Momento $M$ positivo si tracciona la fibra $-y$ (la de abajo en una viga horizontal). $V = dM/dx$.

**Cargas nodales equivalentes** (empotramiento perfecto) para carga uniforme en toda la luz:

$$
\{F_{eq}\} = \left\{ \tfrac{q_x L}{2},\ \tfrac{q_y L}{2},\ \tfrac{q_y L^2}{12},\ \tfrac{q_x L}{2},\ \tfrac{q_y L}{2},\ -\tfrac{q_y L^2}{12} \right\}^T
$$

Se transforman ($[T]^T \{F_{eq}\}$) y se suman al vector global de cargas. Fase 1 también incluye carga puntual en el tramo y carga trapezoidal parcial.

**Fuerzas de extremo de barra** (sobre la barra, en ejes locales):

$$
\{f\} = [k_{local}]\,[T]\,\{u_{global}\} - \{F_{eq}\}
$$

**Esfuerzos internos** a una distancia $x$ del nudo $i$ (carga uniforme):

$$
N(x) = -f_1 - q_x x, \qquad
V(x) = f_2 + q_y x, \qquad
M(x) = -f_3 + f_2\,x + \tfrac{1}{2} q_y x^2
$$

Comprobación: viga biapoyada con $q_y = -q$: $f_2 = qL/2$, $f_3 = 0$, $M(L/2) = qL^2/8$. ✓

Se evalúan en $N_{est}$ estaciones (por defecto 11) más los puntos de cargas puntuales y el punto de $V = 0$, para no perder el máximo del momento.

### 3.5 Ensamblaje, condiciones de contorno y solución

1. Cada barra aporta sus 36 términos a una matriz en formato COO; se convierte a CSC/CSR (los duplicados se suman).
2. **Partición de GDL**: se numeran primero los GDL libres $f$ y luego los restringidos $r$:
$$
\begin{bmatrix} K_{ff} & K_{fr} \\ K_{rf} & K_{rr} \end{bmatrix}
\begin{Bmatrix} U_f \\ U_r \end{Bmatrix} =
\begin{Bmatrix} F_f \\ F_r + R \end{Bmatrix}
$$
3. Se resuelve $K_{ff}\,U_f = F_f - K_{fr}\,U_r$ por **Cholesky disperso** con reordenamiento. $U_r$ son los desplazamientos impuestos (cero, o asentamientos).
4. Reacciones exactas: $R = K_{rf}\,U_f + K_{rr}\,U_r - F_r$.
5. **Apoyos elásticos** (resortes): se suman a la diagonal de $K$ como un elemento más.
6. **Mecanismos**: si la factorización encuentra un pivote nulo o negativo, se informa qué GDL y qué nudo están sin rigidez, en lugar de devolver resultados basura.
7. Se resuelven varios casos de carga con una sola factorización (varios vectores $F$).

No se usa penalización ($K_{ii} + 10^{20}$): da reacciones imprecisas y degrada el condicionamiento.

### 3.6 Fase 2 en adelante (resumen de formulación)

- **Masa:** concentrada ($m = \tfrac12 \rho A L$ en cada nudo, traslacional; inercia rotacional despreciada, a documentar) y consistente.
- **Modal:** $[K]\{\phi\} = \omega^2 [M]\{\phi\}$ por Lanczos con desplazamiento (*shift-invert*) sobre la factorización de `faer`; se implementa propio o con binding a ARPACK/Spectra. Reporta participación de masa por dirección.
- **Espectro de respuesta:** combinación CQC y SRSS, espectro según la norma sísmica elegida, excentricidad accidental.
- **Diafragma rígido:** restricción maestro-esclavo por piso.
- **P-Δ:** matriz geométrica $[K_g]$ iterativa (Newton-Raphson) con control de carga.
- **Láminas:** MITC4 (gruesa) y/o DKT (delgada) más GDL de giro en el plano (*drilling*) para llegar a 6 GDL por nudo. Formulación a fijar en su propia especificación.

---

## 4. Contrato de datos Rust ↔ Python (v1)

Reglas: arreglos planos contiguos (`float64`, `int64`, `uint8`), stride fijo y documentado, número de versión en cada llamada, Rust valida todos los tamaños y devuelve `ValueError` con un mensaje claro.

| Arreglo | Tipo | Forma / stride | Contenido |
|---|---|---|---|
| `coords` | f64 | `n_nudos × 2` | `[x, y]` (Fase 1; 3D usa stride 3) |
| `conectividad` | i64 | `n_barras × 2` | `[nudo_i, nudo_j]` |
| `props` | f64 | `n_barras × 3` | `[E, A, I]` (3D: `[E, G, A, Iy, Iz, J]` + vector de referencia) |
| `liberaciones` | u8 | `n_barras × 6` | 1 = GDL de extremo liberado |
| `restricciones` | u8 | `n_nudos × 3` | 1 = GDL restringido |
| `despl_impuestos` | f64 | `n_casos × n_nudos × 3` | asentamientos por caso (solo se leen donde hay restricción) |
| `resortes` | f64 | `n_nudos × 3` | rigidez de apoyo elástico |
| `cargas_nodales` | f64 | `n_casos × n_nudos × 3` | `[Fx, Fy, Mz]` en ejes globales |
| `cargas_barra` | f64 | `n_cargas × 7` | `[caso, barra, tipo, ejes, a, vx, vy]`; tipo 0 = uniforme (`vx, vy` = `qx, qy`), 1 = puntual a distancia `a`; ejes 0 = local, 1 = global |

Salida (diccionario de arreglos NumPy): `desplazamientos (n_casos × n_nudos × 3)`, `reacciones (n_casos × n_nudos × 3)`, `fuerzas_extremo (n_casos × n_barras × 6)`, `estaciones` con `x, N, V, M, flecha`.

La implementación está en `crates/nervi-py/src/lib.rs` (`resolver_portico_2d`), con PyO3 0.30 y la API `Bound`.

El cálculo pesado se hace con el GIL liberado (`py.detach`) para no bloquear la interfaz.

---

## 5. Normas de diseño (Fase 3)

Primera norma: **ACI 318-19**, porque es la base de varias normas regionales. Después, la normativa vigente en **Paraguay** (a confirmar cuál se usa en la práctica local) y luego CIRSOC 201 (Argentina), NBR 6118 (Brasil), NCh 430 / NCh 433 (Chile), EN 1992-1-1 y AISC 360.

### 5.1 Vigas de hormigón armado, flexión (ACI 318-19)

Unidades: MPa y mm.

- Armadura mínima (§9.6.1.2):
$$
A_{s,min} = \max\left( \frac{0.25\sqrt{f'_c}}{f_y},\ \frac{1.4}{f_y} \right) b_w\, d
$$
- Límite superior: no hay $\rho_{max}$ explícito. Se controla la **deformación de la armadura traccionada** $\varepsilon_t$ (mínimo de §9.3.3.1) y $\phi$ según la Tabla 21.2.2 (controlada por tracción si $\varepsilon_t \ge \varepsilon_{ty} + 0.003$).
- Separación **libre** mínima entre barras paralelas de una capa (§25.2.1):
$$
s_{libre} \ge \max\left( 25\ \text{mm},\ d_b,\ \tfrac{4}{3} d_{agg} \right)
$$
- Ancho necesario para $n_b$ barras en una capa:
$$
b_{nec} = 2\,c_{rec} + 2\,d_{estribo} + n_b\, d_b + (n_b - 1)\, s_{libre} \le b_w
$$
- Optimización: búsqueda discreta sobre diámetros comerciales (8, 10, 12, 16, 20, 25, 32 mm), una o dos capas y combinaciones de dos diámetros. Criterio: mínimo exceso de $A_s$ sobre $A_{s,req}$ con restricciones de separación y $\varepsilon_t$. Considerar el efecto de la segunda capa sobre $d$.

### 5.2 Otros módulos de la Fase 3

- Cortante en vigas (ACI §22.5), estribos y separaciones máximas.
- Columnas: diagrama de interacción $P_u$–$M_{ux}$–$M_{uy}$ por fibras, cuantía entre 1 % y 8 % (§10.6.1.1), esbeltez.
- Combinaciones de carga (ACI/ASCE 7 y las regionales) y envolventes.
- EN 1992-1-1: flexión, cortante, torsión, fisuración ($w_k$, §7.3.4) y flechas (§7.4). Bielas y tirantes solo para regiones D.
- AISC 360-16/22: pandeo por flexión, torsional y lateral-torsional.

---

## 6. Interoperabilidad IFC (Fase 4)

### 6.1 Importación

1. **Caso fácil**: si el archivo trae `IfcStructuralAnalysisModel`, leer `IfcStructuralPointConnection`, `IfcStructuralCurveMember`, `IfcStructuralSurfaceMember`, `IfcBoundaryNodeCondition`, `IfcStructuralLoadGroup`, `IfcStructuralPointAction`, `IfcStructuralLinearAction`.
2. **Caso habitual**: el archivo solo trae elementos físicos (`IfcBeam`, `IfcColumn`, `IfcSlab`, `IfcWall`). Hay que **idealizar el modelo analítico**: extraer ejes, unir nudos cercanos con tolerancia, resolver excentricidades con brazos rígidos y avisar al usuario de lo que no se pudo interpretar. Este es un submódulo propio y el más costoso de IFC.
3. Secciones: `IfcRectangleProfileDef`, `IfcCircleProfileDef`, `IfcIShapeProfileDef`, etc. → $A$, $I_y$, $I_z$, $J$.
4. Materiales: leer los property sets de material cuando existan; si faltan $f'_c$, $f_y$ o $E$, pedirlos al usuario en lugar de suponerlos.

### 6.2 Exportación de armaduras

- Entidad **`IfcReinforcingBar`** (no existe `IfcRebar`) con diámetro nominal, área, longitud y tipo de barra.
- Geometría con **`IfcSweptDiskSolid`** a lo largo de una directriz (polilínea con radios de doblado).
- Relación con el elemento anfitrión (`IfcBeam` / `IfcColumn`) para cómputos por elemento; verificar contra la documentación IFC4.3 qué relación usan Revit, Tekla y Allplan al importar.

---

## 7. Hoja de ruta por fases

| Fase | Entregable | Criterio de salida |
|---|---|---|
| **0. Repositorio** | Repo, licencia, estructura, CI (`cargo test`, `pytest`, `maturin build`), guía de contribución | CI verde con una prueba trivial |
| **1. MVP pórtico 2D** | Motor 2D (§3), binding Python, cargas nodales y en barra, liberaciones, asentamientos, resortes, varios casos | Batería de verificación ≥ 8 casos analíticos con error relativo < $10^{-9}$; pórtico de 10 000 barras en < 1 s |
| **2. Pórtico 3D y dinámica** | Barra 12×12, ejes locales, brazos rígidos, diafragma rígido, masa, modal, espectro de respuesta, P-Δ | Verificación contra ejemplos publicados de referencia |
| **3. Diseño** | ACI 318-19 vigas y columnas, combinaciones, primera norma regional | Ejemplos resueltos de libros/manuales reproducidos con < 0.5 % |
| **4. IFC y salida** | Importación IFC (ambos casos), exportación de armaduras, memoria de cálculo PDF, planos DXF (`ezdxf`), planilla de doblado | Ida y vuelta IFC con un modelo real abierto en Revit/Tekla |
| **5. GUI** | Visor 3D, edición de modelo, diagramas de esfuerzos | Un usuario modela y calcula un edificio de 3 pisos sin escribir código |
| **6. Láminas** | Losas y muros por elementos finitos | Placas de referencia (Timoshenko) dentro de la tolerancia |

---

## 8. Verificación y estándares de código

- **Rust:** `cargo test` con pruebas unitarias de cada matriz (simetría, rango, movimientos de sólido rígido producen fuerza cero) y pruebas de integración con solución cerrada.
- **Python:** `pytest`, incluyendo pruebas de propiedades (por ejemplo, equilibrio global $\sum R + \sum F = 0$ en todo modelo aleatorio).
- **Casos de referencia** en `verification/`: cada uno con modelo, resultado esperado y **fuente citada** (fórmula, libro o manual de verificación publicado). Se ejecutan en CI.
- **Formato:** `rustfmt`, `clippy -D warnings`, `ruff`, `mypy`.
- **Contribuciones de agentes de IA:** cada PR debe incluir pruebas, citar la fuente de cada fórmula y ser revisado por una persona. Ningún módulo normativo se publica sin revisión de un ingeniero estructural.
