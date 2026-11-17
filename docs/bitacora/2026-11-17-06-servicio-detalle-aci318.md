# 2026-11-17-06 · Flechas, fisuración y detalle de armaduras de vigas según ACI 318-19

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-eim98d`
- **Fase de la hoja de ruta:** Fase 3, diseño de hormigón armado (paso 2 del plan: servicio y detalle)

## Qué se pidió

Sumar al diseño de vigas de hormigón armado (entrada 2026-11-17-02) las verificaciones de servicio y el detalle de armaduras según ACI 318-19: flechas inmediatas con inercia efectiva, flechas diferidas y sus límites (§24.2), control de fisuración por separación de barras (§24.3) y detalle (longitudes de desarrollo, empalmes, ganchos, separaciones y cuantías), integrado con la API de vigas, con ganchos para la interfaz y la memoria en PDF, y marcado como experimental.

## Qué se hizo

Se revisaron antes `main` y los PR abiertos (#54 columnas, #55 etapa Diseño en la interfaz) para no pisarlos: todo lo nuevo va en módulos propios y no se tocan `aci318/__init__.py`, `viga.py` ni `design/__init__.py`, que esos PR cambian. Los módulos se importan como `from nervi.design.aci318 import servicio, detalle`.

- `python/nervi/design/aci318/servicio.py` (MPa, mm, kN·m):
  - `modulo_elasticidad` (`Ec = 4700 √f'c`, §19.2.2.1b), `modulo_rotura` (`fr = 0.62 λ √f'c`, §19.2.3.1), `inercia_bruta`, `momento_fisuracion` (§24.2.3.5).
  - `seccion_fisurada`: eje neutro e `Icr` de la sección transformada, con armadura comprimida opcional como `(n − 1) As'`.
  - `inercia_efectiva`: la expresión de ACI 318-19 (§24.2.3.5), con `Ie = Ig` hasta `(2/3) Mcr`.
  - `factor_xi` y `factor_diferido` (`λΔ = ξ/(1 + 50 ρ')`, §24.2.4.1); `limite_flecha` y `LIMITES_FLECHA` (§24.2.2).
  - `separacion_maxima_fisuracion` (§24.3.2), `verificar_fisuracion` con `fs = (2/3) fy` (§24.3.2.1) o la tensión de la sección fisurada bajo el momento de servicio.
  - `verificar_servicio_viga(res, modelo, barra, diseno, seccion, mat, permanentes=..., sobrecargas=...)`: toma la deformada del análisis respecto de la cuerda de la barra, la reescala por `EI` del modelo / `Ec Ie` (con `Ie` para D y para D + L, y promedio de secciones críticas positiva y negativas en tramos continuos, §24.2.3.6), calcula la flecha por sobrecarga como diferencia, la sostenida con una fracción de la sobrecarga y la diferida con `λΔ`, y las compara con ℓ/180, ℓ/360, ℓ/480 o ℓ/240 según `uso` y `elementos`. Acepta modelos en otras unidades (`fuerza`, `longitud`). Avisa si `h > 900 mm` (armadura de piel, §9.7.2.3).
- `python/nervi/design/aci318/detalle.py` (MPa, mm):
  - `longitud_desarrollo` con la expresión general (§25.4.2.4), `(cb + Ktr)/db ≤ 2.5`, `Ktr` de los estribos (`indice_ktr`), factores `ψt, ψe, ψs, ψg` (§25.4.2.5, `ψt ψe ≤ 1.7`), `√f'c ≤ 8.3` (§25.4.1.4), mínimo de 300 mm y reducción opcional por armadura en exceso (§25.4.10). `longitud_desarrollo_simplificada` (§25.4.2.3).
  - `gancho_normal`: `ℓdh` de §25.4.3.1 con `ψe, ψr, ψo, ψc`, prolongación y diámetro de doblado (§25.3.1).
  - `longitud_desarrollo_compresion` (§25.4.9.2), `empalme_traccion` clase A/B (§25.5.2.1), `empalme_compresion` (§25.5.5.1).
  - `detallar_viga(diseno, seccion, mat, continua=..., luz_libre=...)`: para la armadura inferior y la superior de un `DisenoViga`, `ℓd` con la geometría real (`cb`, `Ktr` de los estribos diseñados, `ψt = 1.3` arriba), gancho, empalme clase B, prolongación de corte `max(d, 12 db)` (§9.7.3.3), barras que llegan al apoyo (§9.7.3.8.1) o pasan el punto de inflexión con `max(d, 12 db, ℓn/16)` (§9.7.3.8.4), y separación libre contra §25.2.1.
- Ganchos para la interfaz y la memoria: `FlechasViga.cumple`, `FlechasViga.filas_memoria()`, `DetalleViga.cumple`, `DetalleViga.filas_memoria()` (filas para `nervi.memoria.tabla_verificaciones`) y `DetalleViga.tabla_memoria()` (anclajes y empalmes en texto).
- `examples/viga_hormigon_servicio_aci318.py`: la viga continua del ejemplo de vigas, con flechas, fisuración y anclajes.
- README (es, en, pt, ru), portada del sitio en los cuatro idiomas y glosario actualizados.

## Cómo se verificó

- `tests/test_design_servicio_aci318.py` (23 pruebas), con los valores esperados calculados a mano en la propia prueba:
  - `Ec`, `fr`, `Ig` y `Mcr` de una sección de 300 × 500 (41.01 kN·m); `Icr` de una sección con `n = 8` resolviendo la cuadrática a mano (x = 153.907 mm, `Icr` = 1.4167e9 mm⁴) y con armadura comprimida (equilibrio de momentos estáticos); `Ie` en sus límites (`Ig` hasta `(2/3) Mcr`, valor en `Ma = Mcr`, tendencia a `Icr`).
  - Viga simplemente apoyada desde el modelo contra `5 w L⁴ / 384 Ec Ie` con `Ie` para D y para D + L, flecha sostenida y diferida, y límites; da lo mismo con dos `E` distintos en el modelo y con el modelo en N y mm.
  - Viga continua de dos tramos: momento en el apoyo `w L²/8`, `Ie` promedio, y flecha contra `w L⁴ / 185 EI` a 0.4215 L (1 %).
  - Fisuración con `fs = (2/3) fy` y con `fs` de la sección fisurada (comparada también con `Ms / (As · 0.9 d)`).
  - Longitudes de desarrollo, ganchos, compresión y empalmes paso a paso. Además, contra la forma en unidades inglesas de las mismas expresiones de la norma: `ℓd = fy/(25 √f'c) db` y `fy/(20 √f'c) db` (37.9 db y 47.4 db para grado 60 y 4000 psi), `ℓdh = fy ψ/(55 √f'c) db^1.5` para una barra No. 8 y `0.0005 fy db` para el empalme comprimido. Las constantes SI de la norma están redondeadas, así que la comparación tiene tolerancia de 1 a 3 %.
  - Detalle de la viga continua diseñada: separación libre, `cb`, `Ktr`, `ℓd`, empalme, prolongación de corte y barras continuas.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test -p nervi-core`, `pytest` (220 en verde y 4 saltadas por no tener PyVista en el entorno), `ruff check`, `ruff format --check` y `verificar_bitacora.py`.

## Decisiones tomadas

- Implementación propia de los métodos de la norma citando los artículos; no se copia código de otros programas ni se transcriben tablas o ejemplos, y no hay dependencias nuevas.
- La flecha sale del análisis elástico del modelo (que ya incluye continuidad, cargas puntuales, etc.) reescalada por la rigidez fisurada, en vez de fórmulas cerradas por tipo de tramo. Supone que la barra tiene rigidez uniforme en el análisis y que los momentos no se redistribuyen al fisurarse, como admite la norma para el cálculo con `Ie`.
- `Ie` promedio en tramos continuos: promedio simple entre la sección de momento positivo y el promedio de los extremos con momento negativo (§24.2.3.6). La ponderación 0.70/0.15 del comentario no se usó.
- La flecha que se compara con ℓ/480 o ℓ/240 es, del lado seguro, toda la diferida más la inmediata por sobrecarga (no se resta la parte que ocurre antes de colocar los tabiques).
- `ρ'` del multiplicador diferido es 0 por defecto (las barras superiores de `disenar_viga` son de los apoyos); se puede pasar `As_comp_centro`.
- `cc` del control de fisuración es el recubrimiento libre hasta el estribo, que es la barra más cercana a la cara traccionada.
- Las sobrecargas se aplican todas juntas en servicio; no se buscan patrones alternados para la flecha.
- No se modificaron `aci318/__init__.py`, `viga.py` ni `design/__init__.py` para no chocar con los PR #54 y #55; cuando entren, conviene exportar `servicio` y `detalle` desde `aci318` y llamarlos desde `design.proyecto`.

## Pendiente y problemas conocidos

- **Revisión de un ingeniero estructural** de `servicio.py` y `detalle.py` antes de quitar la marca de experimental. Puntos a revisar: escalado de la deformada del modelo, promedio de `Ie`, flecha posterior a los tabiques, `cc` con estribos, `ψt` de barras superiores, el número de barras que pasan el punto de inflexión.
- Comparar con **ejemplos resueltos publicados** con diferencia menor a 0.5 % (criterio de salida de la Fase 3).
- No hay voladizos en `verificar_servicio_viga` (la flecha se mide respecto de la cuerda); losas en una dirección, vigas T y espesores mínimos de la tabla 9.3.1.1 tampoco.
- La armadura de piel solo se avisa; no se dimensiona.
- Falta conectarlo con la etapa Diseño de la interfaz (PR #55) y con el capítulo de diseño de la memoria; los ganchos `filas_memoria()` ya están.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-17 a las 10:01 UTC (opción "Sí, firmá en mi nombre" a "¿Firmo los commits de este PR con tu nombre (DCO)?"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Empezar por los docstrings de `servicio.py` y `detalle.py` y por `examples/viga_hormigon_servicio_aci318.py`.
- Lo natural después: llamar a `verificar_servicio_viga` y `detallar_viga` desde `nervi.design.proyecto` (PR #55) para mostrarlos en la interfaz y sumarlos a la memoria, voladizos y vigas T, y el despiece con largos de barra.
