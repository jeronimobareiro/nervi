# Casos de verificación

Esta carpeta es la biblioteca de casos de referencia de Nervi. Cada archivo `.toml` es un caso: un modelo, los resultados esperados y la **fuente** de donde salen (fórmula cerrada, libro con página o ejemplo publicado). El CI resuelve todos los casos en cada aporte y falla si algún valor se aleja del esperado más que la tolerancia.

Para aportar un caso **no hace falta saber Rust ni tocar el motor**: alcanza con escribir un archivo de texto.

## Cómo agregar un caso

1. Copiá un caso parecido (por ejemplo `vigas/biempotrada-carga-uniforme.toml`) a la subcarpeta que corresponda (`vigas/`, `porticos/`, `cerchas/`, o una nueva) con un nombre corto en minúsculas y con guiones.
2. Cambiá el título, la fuente, el modelo y los valores esperados.
3. Corré las pruebas: `pytest tests/test_verificacion.py` (después de `maturin develop --release`).
4. Mandá el PR con su entrada en `docs/bitacora/` (ver `CONTRIBUTING.md`).

Si el ejemplo es de un libro, citá autor, título, edición, página y número de ejemplo, y escribí los datos y resultados con tus palabras y números: **no copies el enunciado ni las figuras** (derechos de autor). Si el libro da resultados redondeados, poné la tolerancia que corresponda (por ejemplo `tolerancia = 1e-3`).

## Formato

```toml
titulo = "Viga biempotrada con carga uniforme"
fuente = "Roark's Formulas for Stress and Strain, 8.ª ed., tabla 8.1"
descripcion = "M_extremos = -qL²/12, M_centro = qL²/24"   # opcional
unidades = "kN, m"                                      # informativo
estaciones = 11      # opcional: puntos del diagrama por barra (11 por defecto)
tolerancia = 1e-9    # opcional: tolerancia relativa (1e-9 por defecto)
tolerancia_abs = 1e-12  # opcional: tolerancia absoluta, útil si el esperado es 0

[parametros]         # opcional: nombres que se pueden usar en cualquier número
E = 2.0e8
I = 1.0e-4
L = 5.0
q = 8.0
k = "q*L**2"         # un parámetro puede usar los anteriores

[modelo]
nudos = [[0, 0], ["L", 0]]                          # [x, y]
barras = [{ i = 0, j = 1, E = "E", A = 0.01, I = "I" }]
# Opcional en cada barra: articulada_i = true, articulada_j = true
apoyos = [
    { nudo = 0, ux = true, uy = true, rz = true },  # empotramiento
    { nudo = 1, uy = true },                        # carrito
]
resortes = [{ nudo = 1, kx = 1.0e5 }]               # opcional: kx, ky, krz

[[cargas]]           # una tabla por carga
caso = "q"
tipo = "uniforme"
barra = 0
qy = "-q"

[[esperado]]         # una tabla por valor a comparar
caso = "q"
que = "seccion"
barra = 0
x = "L/2"
componente = "M"
valor = "q*L**2/24"
```

Cualquier número puede escribirse como expresión entre comillas: `+ - * / **`, paréntesis, los parámetros, `pi` y las funciones `sqrt`, `sin`, `cos`, `tan`, `radianes` y `abs`. Así el valor esperado queda escrito igual que la fórmula del libro.

### Cargas

| `tipo` | Claves | Significado |
|---|---|---|
| `nodal` | `nudo`, `fx`, `fy`, `mz` | Fuerzas en ejes globales |
| `uniforme` | `barra`, `qx`, `qy`, `ejes` | En toda la luz |
| `puntual` | `barra`, `a`, `px`, `py`, `ejes` | A la distancia `a` del nudo i |
| `trapezoidal` | `barra`, `a`, `b`, `qx1`, `qy1`, `qx2`, `qy2`, `ejes` | Lineal de `a` a `b` (sin `a` = 0, sin `b` = hasta el nudo j) |
| `momento` | `barra`, `a`, `mz` | Momento concentrado antihorario a la distancia `a` del nudo i |
| `termica` | `barra`, `alfa`, `dt`, `gradiente`, `h` | `ΔT` uniforme y `T(cara -y) - T(cara +y)` en una sección de canto `h` |
| `desplazamiento_impuesto` | `nudo`, `ux`, `uy`, `rz` | Asentamiento de un apoyo |

`ejes` es `"local"` (por defecto) o `"global"`. Las convenciones de signos están en [`docs/convenciones.md`](../docs/convenciones.md): `y` hacia arriba, giros antihorarios positivos, momento positivo si tracciona la fibra de abajo, axil positivo en tracción, reacciones como fuerzas del apoyo sobre la estructura.

### Valores esperados

| `que` | Claves | `componente` |
|---|---|---|
| `desplazamiento` | `nudo` | `ux`, `uy`, `rz` |
| `reaccion` | `nudo` | `Rx`, `Ry`, `Mz` |
| `seccion` | `barra` y `x` (distancia desde el nudo i) **o** `extremo = "max"` / `"min"` | `N`, `V`, `M`, `u`, `v` (`u`, `v` en ejes locales) |

- `x` tiene que caer en una estación del diagrama: los extremos de la barra, las `estaciones` equidistantes, los puntos de cargas puntuales y momentos, los extremos de las trapezoidales y los de cortante nulo. Si no cae, el ejecutor lo dice; ajustá `estaciones`.
- Bajo una carga puntual o un momento concentrado hay dos valores; `lado = "izquierda"` (por defecto) o `lado = "derecha"` elige cuál.
- `extremo` toma el máximo o el mínimo del diagrama de la barra, útil para `M_máx` y flechas máximas.
- Cada valor esperado puede tener su propia `tolerancia`, `tolerancia_abs` y una `descripcion` que aparece si falla.

## Cómo se ejecuta

`tests/test_verificacion.py` lee todos los `.toml` de esta carpeta (también en subcarpetas), arma el modelo con la API Python, lo resuelve y compara. Un valor pasa si `|calculado - esperado| ≤ tolerancia·|esperado| + tolerancia_abs`. La misma prueba comprueba que, si se altera un valor esperado, el caso falla.

En Python 3.10 hace falta el paquete `tomli` (`pip install tomli`); desde 3.11 viene incluido como `tomllib`.
