# Convenciones de signos y unidades

## Unidades

El motor no impone unidades: hay que usar un sistema **consistente**. Recomendado: kN y m (E en kN/m², I en m⁴, cargas distribuidas en kN/m, momentos en kN·m).

## Ejes globales y grados de libertad

- X horizontal, Y vertical hacia arriba. Giros positivos antihorarios (regla de la mano derecha, eje Z saliendo del plano).
- **3 GDL por nudo**: `ux, uy, rz`. El nudo `i` ocupa los índices globales `3i, 3i+1, 3i+2`.
- Cada barra tiene 2 nudos: 6 GDL y matriz de rigidez 6×6.

## Ejes locales de barra

- `x` local va del nudo `i` al nudo `j`.
- `y` local está a 90° antihorario de `x`. En una viga dibujada de izquierda a derecha, `y` apunta hacia arriba.
- Cosenos directores `c = Δx/L`, `s = Δy/L`; transformación `{v_local} = [T]{v_global}` con `[T] = diag(λ, λ)`, `λ = [[c, s, 0], [-s, c, 0], [0, 0, 1]]`.

## Cargas

- **Nodales**: `[Fx, Fy, Mz]` en ejes globales.
- **En barra**, en ejes locales o globales:
  - Uniforme en toda la luz `(qx, qy)`. En ejes globales se entiende **por unidad de longitud de barra** (no proyectada). Para una carga de nieve o de cubierta dada por metro de proyección horizontal, multiplicar por `cos α` antes de cargarla.
  - Puntual `(px, py)` a la distancia `a` del nudo `i`.
  - Trapezoidal entre `a` y `b` (`0 ≤ a < b ≤ L`): vale `(qx1, qy1)` en `a` y `(qx2, qy2)` en `b` y varía linealmente entre ambos. Con intensidades iguales es una uniforme parcial; con `a = 0`, `b = L` y `q1 = 0`, una triangular. En ejes globales vale lo mismo que para la uniforme (por unidad de longitud de barra).
  - Momento concentrado `Mz` (antihorario positivo, igual que los momentos nodales) a la distancia `a` del nudo `i`, con `0 ≤ a ≤ L`. Es el mismo en ejes locales y globales. Con `a = 0` o `a = L` equivale a un momento nodal en el nudo de ese extremo de la barra.
  - Térmica en toda la barra: variación uniforme `ΔT` y diferencia `ΔT_g = T(cara -y) - T(cara +y)` entre caras de una sección de canto `h`, con coeficiente de dilatación `α`. Deformaciones libres `ε₀ = α·ΔT` y `κ₀ = α·ΔT_g/h`. Con `ΔT_g > 0` la cara `-y` (abajo en una viga de izquierda a derecha) está más caliente y la barra se curva como con momento positivo. Las cargas equivalentes son `[-EAε₀, 0, -EIκ₀, EAε₀, 0, EIκ₀]` (ejes locales) y no hay fuerzas en el tramo, así que los diagramas `N, V, M` muestran solo los esfuerzos mecánicos; una barra libre de deformarse queda sin esfuerzos.
- Una carga gravitatoria en una viga horizontal es `qy < 0`.

## Esfuerzos internos

| Esfuerzo | Signo positivo |
|---|---|
| Axil `N` | Tracción |
| Cortante `V` | Definido para que `V = dM/dx` |
| Momento `M` | Tracciona la fibra del lado `-y` local (abajo en una viga dibujada de izquierda a derecha) |

A partir de las fuerzas de extremo `{f} = [k]{u} - {F_eq}` (en ejes locales, actuando sobre la barra), para carga uniforme:

```
N(x) = -f1 - qx·x
V(x) =  f2 + qy·x
M(x) = -f3 + f2·x + qy·x²/2
```

Con una carga puntual en `a`, para `x > a` se suman `-px`, `+py` y `+py·(x - a)` respectivamente. En `x = a` los diagramas tienen dos estaciones (izquierda y derecha del salto).

Con un momento concentrado `Mz` en `a`, para `x > a` se suma `-Mz` al momento flector: un par antihorario a la izquierda del corte resta, igual que el momento de extremo `f3`. El diagrama de `M` salta en `-Mz` en `a` (dos estaciones, como bajo una carga puntual) y `N` y `V` no cambian. Las cargas equivalentes son `Mz·dN/dx(a)` con las funciones de Hermite: con `ξ = a/L`, `[0, -6Mz·ξ(1-ξ)/L, Mz·(1 - 4ξ + 3ξ²), 0, 6Mz·ξ(1-ξ)/L, Mz·(3ξ² - 2ξ)]`.

Con una carga trapezoidal se suman las resultantes de la parte de la carga que está en `[a, min(x, b)]`: `-∫qx ds`, `+∫qy ds` y `+∫qy·(x - s) ds`. Los diagramas tienen estaciones en `a` y en `b`, y como entre ellos `V` es cuadrático el punto de cortante nulo (momento extremo) se calcula exactamente.

Las cargas nodales equivalentes de la trapezoidal son el vector de cargas consistente `F = ∫ Nᵀ q ds` con las funciones de forma lineales (axil) y de Hermite (flexión), que en la barra de Euler-Bernoulli coincide con las reacciones de empotramiento exactas. Las integrales se hacen con Gauss-Legendre de 3 puntos, exacta para estos polinomios (grado ≤ 4).

Ejemplo: viga biapoyada con `qy = -q` → `M(L/2) = +qL²/8` (positivo, tracciona abajo).

## Reacciones

Fuerza que el apoyo ejerce **sobre** la estructura, en ejes globales. En un apoyo elástico es `-k·u`.

## Liberaciones

Cada barra tiene seis liberaciones `(N_i, V_i, M_i, N_j, V_j, M_j)`. Una articulación es `M = 0` en ese extremo. Se aplican por condensación estática; la barra conserva su giro propio en el extremo liberado, que se usa para la deformada.

Si en un nudo todas las barras están articuladas y no hay apoyo al giro (nudos de cercha), ese giro no tiene rigidez: el motor lo fija automáticamente y lo informa en `gdl_sin_rigidez`. Si además hay un momento aplicado en ese nudo, el análisis se detiene con un error.

## Pórtico espacial (Fase 2a)

Módulo `nervi_core::espacial` en Rust y `nervi.Modelo3D` en Python (issue #11). Es aparte del pórtico plano: nada de lo anterior cambia.

### Ejes globales y grados de libertad

- X e Y horizontales, **Z vertical hacia arriba** (terna derecha). El peso propio es `qz < 0` en ejes globales.
- **6 GDL por nudo**: `ux, uy, uz, rx, ry, rz`, giros por la regla de la mano derecha. El nudo `i` ocupa los índices globales `6i … 6i + 5`.
- Cada barra tiene 12 GDL y matriz de rigidez 12×12. Por extremo, en ejes locales: `[u, v, w, θx, θy, θz]`.

### Ejes locales de barra

- `x` local va del nudo `i` al nudo `j`.
- El plano `x`–`y` local lo fija un **vector de referencia** `v` en globales: `z = x × v / |x × v|` e `y = z × x`, o sea, `y` es la componente de `v` perpendicular a la barra. Si `v` es nulo o paralelo a la barra, el modelo es inválido.
- **Regla por defecto** (sin vector): `v = +Z`, así que en vigas y barras inclinadas `y` apunta hacia arriba y `z` queda horizontal. En una viga sobre X: `y = +Z`, `z = -Y`; sobre Y: `y = +Z`, `z = +X`.
- **Barras verticales** (proyección horizontal menor que `1e-6·L`): `z = -Y` e `y = z × x`. Una columna que sube tiene `y = -X`; una que baja, `y = +X`.
- Con esta regla, un pórtico plano dibujado en el plano XZ (visto desde `-Y`, con X a la derecha y Z hacia arriba) tiene en todas sus columnas y en las vigas dibujadas de izquierda a derecha los mismos ejes locales que en el motor plano, con `z = -Y`. Para barras dibujadas de derecha a izquierda, el vector de referencia `(-sen α, 0, cos α)` reproduce el eje `y` plano. El giro plano `rz` equivale a `-ry` y el momento plano `Mz` a `-My` global.
- Transformación `{v_local} = [T]{v_global}` con `[T] = diag(λ, λ, λ, λ)` y `λ` la matriz cuyas filas son los versores `x, y, z` locales en globales.

### Propiedades

`E, G, A, Iy, Iz, J`: `Iz` es la inercia de la flexión en el plano `x`–`y` (giro `θz`, desplazamiento `v`) e `Iy` la del plano `x`–`z`. Con los ejes por defecto, la flexión de una viga por cargas gravitatorias usa **`Iz`**. En `nervi.secciones` el canto `h` se mide sobre `y` y el ancho `b` sobre `z`, así que una viga rectangular tiene `Iz = b·h³/12`. `J` es la constante de torsión de Saint-Venant (sin alabeo).

### Cargas

- **Nodales**: `[Fx, Fy, Fz, Mx, My, Mz]` en ejes globales.
- **En barra**, en ejes locales o globales (las distribuidas, por unidad de longitud de barra): uniforme `(qx, qy, qz)`, puntual `(px, py, pz)` a la distancia `a` y trapezoidal entre `a` y `b`, igual que en el plano pero con tres componentes. Todavía no hay momentos en el tramo, cargas térmicas ni torsores distribuidos en 3D.
- Las cargas equivalentes de cada plano de flexión son las de la barra plana: el plano `x`–`y` es idéntico al pórtico plano y el `x`–`z` se lleva a él con `v → w` y `θ → -θy` (porque `θy = -dw/dx`).

### Esfuerzos internos

Componentes, en ejes locales, de la acción de la parte `[x, L]` de la barra sobre la parte `[0, x]` (la cara positiva), salvo los cortantes:

| Esfuerzo | Signo positivo |
|---|---|
| Axil `N` | Tracción |
| Torsor `T` | Momento alrededor de `+x` en la cara positiva (regla de la mano derecha) |
| Momento `Mz` | Tracciona la fibra del lado `-y` (igual que `M` del pórtico plano) |
| Momento `My` | Tracciona la fibra del lado `+z` (momento alrededor de `+y` en la cara positiva) |
| Cortante `Vy` | `Vy = dMz/dx` (igual que `V` del pórtico plano) |
| Cortante `Vz` | `Vz = dMy/dx` |

Con las fuerzas de extremo `{f}` sobre la barra (doce componentes `[Fx, Fy, Fz, Mx, My, Mz]` en `i` y en `j`) y sin cargas en el tramo: `N = -f1`, `T = -f4`, `Vy = f2`, `Mz = -f6 + f2·x`, `Vz = -f3`, `My = -f5 - f3·x`. Ejemplos: en un voladizo sobre X empotrado en `x = 0` con una carga `Py` (local) en la punta, `Mz(x) = Py·(L - x)`; con `Pz`, `My(x) = -Pz·(L - x)`. En una viga biapoyada con `qz = -q` (local), `My(L/2) = -qL²/8`.

### Liberaciones

Doce liberaciones por barra, `(N, Vy, Vz, T, My, Mz)` en `i` y luego en `j`, por condensación estática como en el plano. Una articulación esférica libera `My` y `Mz`; una biela de cercha espacial libera además `T` en un extremo (si no, el giro alrededor de su eje queda indeterminado). Son inestables y se rechazan: `N`, `Vy`, `Vz` o `T` liberados en los dos extremos, y `Vy` con `Mz` o `Vz` con `My` en el mismo extremo. Los giros de nudos sin rigidez (nudos de cercha) se fijan solos y se informan en `gdl_sin_rigidez`, como en el plano.

## Dinámica: masas, modal y espectro (Fase 2b)

Módulo `nervi_core::espacial::dinamica` en Rust y `Modelo3D.modal` / `nervi.dinamica` en Python (issues #16, #17 y #18). Solo para el pórtico espacial; las masas se dan aparte del modelo estático, así que el análisis estático y su contrato no cambian.

### Unidades

Las del modelo: con fuerzas en kN y longitudes en m, la masa va en **t** (kN·s²/m), las inercias de rotación en t·m², la gravedad en m/s² (9.80665 por defecto; en cm, 980.665) y la aceleración espectral `Sa` en m/s². Los periodos, en s.

### Masas

- **Nodales**: `[mx, my, mz, Jx, Jy, Jz]` en ejes globales (`masa_nodal(nudo, m)` pone `m` en las tres traslaciones).
- **De las barras**: masa por unidad de longitud `m` (por ejemplo `ρ·A`). **Concentrada** (por defecto): `m L/2` en las tres traslaciones de cada extremo; se **desprecia la inercia rotacional**. **Consistente**: matriz 12×12 de Przemieniecki (cap. 11) con las mismas funciones de forma de la rigidez; la torsión usa el momento polar `Iy + Iz` y no hay inercia rotacional de flexión. Las barras con liberaciones usan siempre masa concentrada.
- **Desde los casos de carga**: `m = -Fz · factor / g` con la componente vertical global de las cargas (las que apuntan hacia abajo dan masa positiva). Las cargas en barras se reparten a sus nudos como las reacciones de una viga simplemente apoyada. Va como masa traslacional en X, Y y Z. Si las cargas netas de un nudo apuntan hacia arriba, el modelo es inválido.
- La masa de los GDL restringidos no participa. Un GDL libre con masa y sin rigidez es un error (`MecanismoError`).

### Modos

- `[K]{φ} = ω²[M]{φ}` en los GDL libres. Se devuelven los `n_modos` de menor frecuencia, ordenados de menor a mayor `ω` (o menos, si el modelo tiene menos GDL con masa).
- **Normalización a masa**: `φᵀ M φ = 1`. **Signo**: la componente traslacional de mayor valor absoluto de cada modo es positiva.
- Factor de participación `Γ = φᵀ M r`, con `r` la traslación rígida unitaria en X, Y o Z (los giros de `r` valen cero); masa modal efectiva `Γ²`; masa total `rᵀ M r` en los GDL libres. Con todos los modos, la suma de masas efectivas es la masa total.
- Métodos: **denso exacto** hasta 1500 GDL con masa (la condensación de los GDL sin masa es exacta) y **Lanczos** con transformación espectral (`σ = 0`) y bloqueo de los modos hallados por encima; los dos dan el mismo resultado, incluidas las frecuencias repetidas.

### Espectro de respuesta

- Espectro dado como pares `(T, Sa)` con periodos crecientes, interpolado linealmente; fuera del rango se toma el extremo más cercano.
- Dirección de la excitación: un vector en globales, usado tal cual (`"X"` es `(1, 0, 0)`).
- Respuesta de cada modo: la estática con `uₙ = Γₙ Sa(Tₙ)/ωₙ² φₙ` y fuerzas `fₙ = Γₙ Sa(Tₙ) M φₙ`. Cortante basal del modo: suma de sus reacciones.
- **Combinación** de cada magnitud por separado (desplazamientos, reacciones, fuerzas de extremo, cada esfuerzo en cada estación y el cortante basal de cada modo): SRSS o CQC con el coeficiente de Der Kiureghian para amortiguamiento igual en todos los modos (Chopra, ec. 13.7.10). El resultado es un **valor absoluto**, sin signo: no se suma con signo a otros casos.
- Los diagramas combinados se dan en estaciones equidistantes, porque la combinación no es lineal entre ellas.
