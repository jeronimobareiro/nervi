# 2026-11-16-02 · Flexión y cortante de vigas de hormigón según ACI 318-19

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-y030hr`
- **Fase de la hoja de ruta:** Fase 3, diseño de hormigón armado · issues [#22](https://github.com/jeronimobareiro/nervi/issues/22) y [#23](https://github.com/jeronimobareiro/nervi/issues/23)

## Qué se pidió

Implementar las combinaciones y envolventes (#21) y el diseño a flexión (#22) y cortante (#23) de vigas según ACI 318-19, en un solo PR, marcado como experimental. Antes de empezar se confirmó en `main`, `ESTADO.md` y la bitácora que #21 ya estaba hecho (entrada 2026-11-10-08), así que este aporte cubre #22 y #23 sobre esas envolventes.

## Qué se hizo

- Nuevo paquete `python/nervi/design/aci318/` (experimental, emite `ModuloExperimentalWarning`), en MPa y mm, con momentos en kN·m y cortantes en kN:
  - `materiales.py`: `Materiales` (`fc`, `fy`, `fyt`, `lam`) y `SeccionRectangular` (`b`, `h`, recubrimiento, estribo, agregado), con los límites de §19.2.1.1 y §20.2.2.4.
  - `flexion.py` (#22): `beta1` (§22.2.2.4.3), `phi_flexion` (§21.2.2), `armadura_minima` (§9.6.1.2), `resistencia_flexion` por compatibilidad de deformaciones (§22.2, la armadura comprimida puede no fluir), `armadura_flexion` con armadura simple o doble, `εt` controlado por tracción por defecto y mínimo 0.004 (§9.3.3.1), excepción de 4/3 (§9.6.1.3). `elegir_barras`: búsqueda discreta sobre 8 a 32 mm, uno o dos diámetros en una capa o un diámetro por capa en dos capas, separación libre de §25.2.1, 25 mm entre capas (§25.2.2) y la `d` real de cada disposición; elige la de menor área.
  - `cortante.py` (#23): `Vc` de §22.5.5.1 (opción a con estribos; opción c sin estribos, con `λs` de §22.5.5.1.3), límite de la sección §22.5.1.2, `Vs` de §22.5.8.5.3, `Av,min` de §9.6.3.4 donde lo pide §9.6.3.1, separaciones máximas de §9.7.6.2.2, `√f'c ≤ 8.3` y `fyt ≤ 420`. `elegir_estribos`: diámetro, ramas y separación múltiplo de 25 mm con el menor acero por metro.
  - `viga.py`: `disenar_viga(res, barra, seccion, mat)` toma la envolvente de la barra, arma la cara inferior con el momento positivo y la superior con el negativo, y diseña los estribos con el cortante en la sección crítica a `d` de la cara de cada apoyo (§9.4.3.2). Avisa si `|Nu| > 0.1 f'c Ag`.
- `examples/viga_hormigon_aci318.py`: viga continua de dos tramos con sobrecarga alternada.
- README (es, en, pt, ru), portada del sitio en los cuatro idiomas y glosario actualizados.

## Cómo se verificó

- `tests/test_design_vigas_aci318.py` (20 pruebas), con los valores esperados calculados a mano en la propia prueba: `β1` y `φ`; `As,min` con cada término gobernando; resistencia de una sección simple (bloque rectangular); la armadura simple es la inversa exacta de la resistencia (despeje cerrado); excepción de 4/3; doble armadura con acero comprimido sin fluir contra el cálculo paso a paso y contra la compatibilidad de deformaciones; zona de transición con `εt = 0.004`; ancho necesario y separaciones; elección de barras en una y dos capas con su `d`; cortante con estribos, separación máxima reducida, límite de la sección, sección sin estribos con `λs` y `ρw`, límite de `fyt`; viga simple (`Mu = wL²/8`, `Vu = wL/2 − w·d`, con y sin ancho de apoyo) y viga continua (`M_B = −wL²/8`) diseñadas desde el modelo; aviso de axil; doctest.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test -p nervi-core`, `pytest` (156 en verde; 180 después de traer la memoria de cálculo de `main`), `ruff check` y `ruff format --check`.

## Decisiones tomadas

- Implementación propia de los métodos de la norma, sin copiar código de otros programas y sin dependencias nuevas. `concreteproperties` (MIT) y `structuralcodes` (Apache-2.0) quedan como opción para secciones no rectangulares o para comparar resultados.
- Por defecto se exige sección **controlada por tracción** (φ = 0.90); bajar a `εt = 0.004` es una opción explícita.
- La resistencia se calcula por equilibrio con bisección sobre el eje neutro, en vez de suponer que el acero fluye, para que valga también con armadura comprimida elástica.
- Dos capas solo se prueban si ninguna disposición de una capa alcanza. En dos capas se usa un diámetro por capa, alineados. El criterio es el menor área provista (a igualdad, menos barras), que es el que más se parece a "mínimo exceso" cuando la `d` cambia con la disposición.
- `elegir_barras` no elige barras de compresión: con doble armadura `armadura_flexion` da las áreas y la elección queda para después.
- En cortante, si no se conoce la cuantía `ρw` se ponen estribos mínimos (no se puede verificar §22.5.5.1c). `disenar_viga` usa la menor `d` y la menor cuantía de las dos caras (conservador).
- No se aplican las excepciones de §9.6.3.1 (vigas bajas, losas) ni torsión, fisuración, anclajes, corte de barras ni flechas.

## Pendiente y problemas conocidos

- **Revisión de un ingeniero estructural** de `nervi/design/aci318/` antes de quitar la marca de experimental. Puntos a revisar: umbral de §9.6.3.1, uso de `Vc` simplificado con estribos, sección crítica a `d`, criterio de elección de barras y la combinación de diámetros muy distintos (por ejemplo Ø20 con Ø12).
- Comparar con **ejemplos resueltos publicados** con diferencia menor a 0.5 % (criterio de salida de la Fase 3); por ahora las pruebas son cálculos a mano independientes.
- No hay interfaz gráfica ni guardado en `.nrv` del diseño; cuando se agregue va en un módulo propio (`diseno`), no en `modelo.json`.
- Firma DCO: el usuario autorizó por escrito, el 2026-11-16 a las 23:47 UTC (opción "Sí, firmalos por mí" a "¿Firmo con tu DCO los commits de flexión y cortante de vigas?"), que el agente firme este aporte en su nombre como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Empezar por el docstring de `nervi/design/aci318/__init__.py` y el ejemplo `examples/viga_hormigon_aci318.py`.
- Lo natural después: barras de compresión en `elegir_barras`, estribos por zonas a lo largo de la viga, corte de barras y anclajes, y llevar el diseño a la memoria de cálculo en PDF.
