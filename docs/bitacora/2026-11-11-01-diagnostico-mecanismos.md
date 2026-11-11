# 2026-11-11-01 · Indicar qué nudo hace inestable un modelo

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-a4wyl0`
- **Fase de la hoja de ruta:** Fase 1, cierre del pórtico plano · issue [#9](https://github.com/jeronimobareiro/nervi/issues/9)

## Qué se pidió

Último punto del plan de la semana: cuando el modelo es un mecanismo, decir **dónde** está el problema (nudo y GDL, y si se puede el modo de mecanismo) en lugar del error genérico "revisar apoyos y articulaciones" (issue #9).

## Qué se hizo

- **Motor**, módulo nuevo `crates/nervi-core/src/mecanismo.rs`: cuando falla Cholesky o se dispara el límite de flexibilidad, se buscan los vectores del núcleo de `K_ff` con iteración inversa por subespacios con desplazamiento sobre la matriz escalada por su diagonal (`S K S + εI`, Cholesky disperso), seguida de Rayleigh-Ritz con Jacobi cíclico. Fuentes en el encabezado del módulo (Saad 2011, Golub y Van Loan). Solo corre cuando ya hay un error, así que no cambia el tiempo de los modelos estables.
- **Error** (`error.rs`): `ErrorNervi::Mecanismo` pasa de `String` a `DiagnosticoMecanismo { detalle, ubicacion, modos }`, con `ComponenteModo { nudo, gdl, valor }` y `nudos()`. El mensaje dice, por ejemplo: "el nudo 1 se puede mover en uy sin que nada lo impida (nudos que se mueven: 0, 1, 2)".
- **Python** (`crates/nervi-py/src/lib.rs`): `MecanismoError` trae `nudo`, `gdl` y `modos`. La carga sobre un GDL sin rigidez también completa `nudo` y `gdl`. Documentado en `contrato-datos.md` como agregado compatible (sin subir `VERSION_CONTRATO`).

## Cómo se verificó

- `crates/nervi-core/tests/mecanismos.rs` (6 casos), con los modos esperados por cinemática de cuerpos rígidos: viga sobre dos carritos (traslación en X), viga de dos tramos con una rótula de más (el centro en `uy`, giros de apoyo ±1/3), pórtico sin arriostrar (traslación lateral y giros −1/4 de las columnas), cercha cuadrada sin diagonal, dos mecanismos independientes y un péndulo suelto sobre un pórtico estable de 10 × 10 (localiza el único nudo libre entre 122). Error menor a 1e-9 en las componentes.
- Prueba unitaria de Jacobi contra una matriz 2 × 2 conocida.
- `tests/test_mecanismos.py` (3 pruebas): atributos de la excepción y mensaje.
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test -p nervi-core`, `pytest` (100), `ruff`.

## Decisiones tomadas

- Iteración inversa por subespacios en lugar de una LU densa con pivoteo completo: reutiliza la factorización dispersa y escala a modelos grandes; una matriz densa de 12 000 GDL ocuparía más de 1 GB.
- El GDL informado es la **traslación** que más se mueve en el modo (es lo que el usuario ve); un giro solo si el modo no traslada nada. Ante un empate gana el nudo de menor número.
- Se buscan hasta 6 modos a la vez; si hay más, el mensaje dice "al menos 6".
- Si la matriz es casi singular pero ningún modo baja de la tolerancia (`1e-10` en la matriz escalada), se informa el modo más flexible como "ubicación probable".

## Pendiente y problemas conocidos

- La interfaz de escritorio muestra el mensaje nuevo, pero todavía no resalta el nudo en el dibujo; se puede hacer con `MecanismoError.nudo`.
- Firma DCO: firmado en nombre del usuario con la autorización escrita del 2026-11-10 ("firmalo todo por mi, te autorizo", 13:30 UTC, y "Mergeá todo, con mi firma autorizada", 22:37 UTC) para el plan de esta semana, del que este issue es el último punto, como `bareirojero <345933350+bareirojero@users.noreply.github.com>`.

## Para quien siga

- Resaltar en la GUI el nudo y animar el modo de mecanismo con `modos`.
- Con la Fase 2a (barra 3D, #11) el diagnóstico sirve igual: solo cambia `Gdl` a 6 por nudo.
