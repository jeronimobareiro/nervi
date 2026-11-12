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
