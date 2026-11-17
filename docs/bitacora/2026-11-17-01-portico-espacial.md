# 2026-11-17-01 · Pórtico espacial: barra 12×12 y API Python 3D

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-idzqek`
- **Fase de la hoja de ruta:** Fase 2a · Pórtico espacial (issues #11 y #12)

## Qué se pidió

"Algo pesado" para programar: arrancar la Fase 2a con la barra espacial de 12 GDL (#11) y su contrato de datos y API Python (#12), verificada contra soluciones cerradas con error menor que 1e-9. Condición del usuario: cero riesgo legal con código de terceros.

## Qué se hizo

- **Motor** (`crates/nervi-core/src/espacial/`), módulo aparte del pórtico plano:
  - `modelo.rs`: `Modelo3d`, `Barra3d` (`E, G, A, Iy, Iz, J`, vector de referencia opcional, 12 liberaciones, atajos `articulada` y `biela`), cargas nodales de 6 componentes, cargas en barra uniformes, puntuales y trapezoidales en ejes locales o globales, apoyos, resortes y asentamientos de 6 GDL, y validación con mensajes claros.
  - `elemento.rs`: ejes locales con vector de referencia y regla por defecto (Z vertical; en barras verticales `z = -Y`), rigidez local 12×12, transformación `diag(λ, λ, λ, λ)`, cargas equivalentes y condensación estática de liberaciones. La flexión de cada plano reutiliza las funciones de la barra plana: el plano `x`–`y` es idéntico y el `x`–`z` se lleva a él con `v → w`, `θ → -θy`.
  - `analisis.rs`: `analizar_3d`, resultados por caso y `seccion`/`diagrama` con `N, Vy, Vz, T, My, Mz`, desplazamientos locales `u, v, w` y giro de torsión, con estaciones en los puntos de carga y donde `Vy` o `Vz` se anulan.
- **Código compartido**, sin cambiar resultados del plano: `analisis.rs` extrae `resolver_sistema` (Cholesky, control de flexibilidad y diagnóstico de mecanismos) y `seccion_plana`; `mecanismo.rs` acepta 3 o 6 GDL por nudo; `Gdl` suma `Uz`, `Rx` y `Ry`.
- **Puente Python** (`crates/nervi-py/src/lib.rs`): `resolver_portico_3d` con validación de formas y GIL liberado, versionado aparte con `VERSION_CONTRATO_3D = 1`.
- **Python**: `python/nervi/modelo3d.py` (`Modelo3D`, `Resultados3D`, `ResultadoCaso3D`, con `combinar`) y `python/nervi/secciones.py` (rectangular con la constante de torsión por la serie exacta de Timoshenko y Goodier, circular y tubo circular).
- **Documentación**: `docs/convenciones.md` §Pórtico espacial (ejes, regla por defecto, signos de los seis esfuerzos), `docs/contrato-datos.md` (contrato 3D), `docs/glosario.md`, los cuatro `README` y el sitio (portada en los cuatro idiomas y primeros pasos con un ejemplo 3D). Ejemplo nuevo `examples/portico_espacial.py`.

## Cómo se verificó

- `crates/nervi-core/tests/portico_3d.rs`, 8 casos con tolerancia 1e-9:
  - Voladizo oblicuo en el espacio, con vector de referencia, carga axial, flexión en los dos planos y torsión: desplazamientos y giros de punta, reacciones y diagramas completos contra las fórmulas cerradas.
  - Pórtico plano en el plano XZ con articulación, barra inclinada dibujada de derecha a izquierda, resorte, asentamiento y cargas uniformes, puntuales y trapezoidales en ejes locales y globales: desplazamientos, reacciones, fuerzas de extremo y diagramas iguales a los del motor plano estación por estación (criterio de aceptación de la Fase 2a).
  - Emparrillado en L: flecha `Pa³/3EI + Pb³/3EI + Pb²a/GJ`, torsor y reacciones.
  - Trípode de bielas: axil `-PL/3h` y descenso `PL³/3h²EA` por trabajos virtuales; los 12 giros sin rigidez se fijan solos.
  - Viga biapoyada con carga en `z` local: `My(L/2) = -qL²/8`, `Vz(0) = -qL/2` y flecha `5qL⁴/384EIy`, con la estación de cortante nulo agregada sola.
  - Equilibrio global (ΣF = 0, ΣM = 0) de un pórtico de dos niveles con barra diagonal, vectores de referencia arbitrarios y todos los tipos de carga.
  - Mecanismo de torsión (`Rx`) localizado y vector de referencia paralelo rechazado.
- Pruebas unitarias de la barra (`espacial/elemento.rs`): simetría, seis movimientos de sólido rígido sin fuerzas, rango 6, ejes ortonormales y regla por defecto, transformación ida y vuelta y biela con solo rigidez axial.
- `tests/test_portico_3d.py`: 7 pruebas de la API, el contrato (versión y formas incorrectas) y las secciones (tabla de Timoshenko y Goodier y límite de sección delgada).
- `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test -p nervi-core` (70 pruebas, doctests incluidos), `maturin develop --release && pytest` (143 pruebas, la GUI incluida), `ruff check` y `ruff format --check`, en verde.

## Decisiones tomadas

- **Origen del código.** Todo se escribió a partir de la formulación de libros (McGuire, Gallagher y Ziemian, *Matrix Structural Analysis*, 2.ª ed., caps. 4 y 5; Przemieniecki, *Theory of Matrix Structural Analysis*, caps. 5 y 6; Timoshenko y Goodier para la torsión de la sección rectangular), citada en los comentarios. No se copió ni se portó código de otros programas, ni siquiera de proyectos con licencia compatible, para no tener que arrastrar avisos de copyright ni dudas de licencia.
- **Módulo aparte y no generalizar el plano.** El pórtico plano ya está verificado, tiene GUI, formato `.nrv` y contrato estable; un módulo nuevo no lo arriesga. Lo que sí se comparte (flexión de la barra, solución, mecanismos) se extrajo en funciones comunes, y las 47 verificaciones del plano siguen en verde.
- **Z vertical** en 3D, como en los programas de edificios, aunque el plano use Y vertical. Con la regla por defecto, las vigas tienen `y` hacia arriba y la flexión gravitatoria usa `Iz`, igual que `I` en el plano. En barras verticales `z = -Y`: así un pórtico plano dibujado en XZ tiene los mismos ejes locales que en el motor plano.
- **Signos de los esfuerzos 3D**: componentes de la acción sobre la cara positiva (`N`, `T`, `My`, `Mz`), salvo los cortantes, que se definen como `dM/dx` para que `Mz` y `Vy` sean exactamente `M` y `V` del plano.
- **Contrato 3D con su propia versión** (`VERSION_CONTRATO_3D`), en lugar de subir `VERSION_CONTRATO`: agregar una función nueva no rompe nada del contrato plano.

## Pendiente y problemas conocidos

- En 3D faltan: momentos concentrados en el tramo, cargas térmicas, torsores distribuidos, combinaciones resueltas junto con el modelo (hoy `combinar` interpola si las estaciones difieren), brazos rígidos (#13) y diafragma rígido (#14).
- No hay módulo `.nrv` para modelos 3D ni visor 3D en la interfaz (#30).
- Verificación contra ejemplos 3D **publicados** (#15): los casos de esta entrada son soluciones cerradas y estática, no ejemplos transcriptos de un libro.
- Torsión de Saint-Venant sin alabeo: para perfiles abiertos de pared delgada (I, U) la rigidez torsional real es mayor; queda para la Fase 2.
- Firma DCO: pendiente. Este trabajo no tiene autorización escrita del usuario para que el agente firme; la firma la agrega el usuario con `git rebase --signoff origin/main` (o autoriza por escrito).

## Para quien siga

- Leé `docs/convenciones.md` §Pórtico espacial antes de tocar `crates/nervi-core/src/espacial/`.
- Lo que más destraba ahora es #15 (ejemplos 3D publicados) y las matrices de masa (#16) para el análisis modal (#17): la rigidez 12×12 y el ensamblaje ya están.
- Para sumar un tipo de carga 3D, agregalo a `TipoCargaBarra3d` y llevalo a los dos planos en `carga_a_local_3d`; las funciones de la barra plana hacen el resto.
