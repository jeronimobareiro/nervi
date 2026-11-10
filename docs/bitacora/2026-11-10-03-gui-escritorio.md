# 2026-11-10-03 · Interfaz de escritorio, formato .nrv e instaladores

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-isqnl8`
- **Fase de la hoja de ruta:** vía paralela de interfaz (adelanta parte de la Fase 5) y formato `.nrv`

## Qué se pidió

Sacar ya instaladores simples para Windows (`.exe`) y Linux con una interfaz que crezca en paralelo al motor, usando PySide6 y PyInstaller, siguiendo el diseño de interfaz aprobado (claro, plano, todo en una sola ventana). OpenCADStudio se usa solo como referencia, no como fork.

## Qué se hizo

- `python/nervi/formato/`: lectura y escritura de proyectos `.nrv` según `docs/formato-nrv.md` (contenedor ZIP con firma `mimetype`, manifiesto, `modelo.json` con `id` estables, validación con ruta JSON del error, escritura segura con `.tmp` + `fsync` + `os.replace`, migraciones en cadena, conservación de miembros desconocidos).
- Integración con las cargas trapezoidales de la entrada 2026-11-10-02 (contrato v2): `nervi.formato` lee y escribe el tipo `trapezoidal` (`a`, `b`, `qx1`, `qy1`, `qx2`, `qy2`; `b` ausente = hasta el nudo j) y la tabla de cargas en barras de la GUI lo edita, con columnas que se habilitan según el tipo.
- `python/nervi/gui/`: aplicación PySide6 (`nervi-gui` o `python -m nervi.gui`).
  - `ventana.py`: una sola ventana con flujo de trabajo (Geometría › Cargas › Análisis › Resultados; Diseño y Memoria deshabilitados), barra contextual (diagrama, combinación, valores), explorador del proyecto, propiedades de la selección y barra de estado con el aviso "Versión preliminar · no apta para proyecto".
  - `vista2d.py`: pórtico con diagramas N, V, M y deformada, valores extremos, lectura de M, V y N al pasar el cursor, selección con clic.
  - `tablas.py`: tablas editables de nudos, barras, apoyos, casos, cargas y combinaciones (modelo/vista de Qt) y tablas de reacciones, fuerzas de extremo y desplazamientos.
  - `sesion.py`: estado del documento; toda edición pasa por `modelo.json`, y el cálculo por `nervi.formato.construir_modelo` + `Modelo.resolver`. Revisión del modelo (apoyos, nudos sueltos, barras superpuestas, casos fuera de combinaciones).
  - `paleta.py` (Ctrl+K, comandos y elementos, búsqueda sin tildes) y `consola.py` (Python con `nervi`, `doc`, `res` y `r`).
- `packaging/`: entrada de PyInstaller, generación de íconos desde el isotipo, instalador Inno Setup con la asociación de `.nrv` de `docs/formato-nrv.md` §7.1, y AppImage con `.desktop` y tipo MIME de §7.2.
- `.github/workflows/publicacion.yml`: con una etiqueta `v*` compila en Windows y Linux (Ubuntu 22.04), prueba que el ejecutable arranque, arma el `.exe` y el AppImage y crea una versión **preliminar** en Releases. A mano (workflow_dispatch) solo deja los instaladores como artefactos.
- CI: el job de Python instala PySide6 y pytest-qt y corre las pruebas de la interfaz sin pantalla (`QT_QPA_PLATFORM=offscreen`).
- `pyproject.toml`: extra `gui` (`PySide6-Essentials`), `pytest-qt` en `dev`, script `nervi-gui`. README, `formato-nrv.md` §8 y `hoja-de-ruta.md` (Fase 5 como vía paralela) actualizados.

## Cómo se verificó

- `pytest`: 64 pruebas en verde (25 de formato y 11 de la interfaz con pytest-qt, nuevas), rebasado sobre `main` con las trapezoidales. La ida y vuelta bit a bit incluye cargas trapezoidales con y sin `b`.
- `ruff check` y `ruff format --check` en verde.
- Se generó el ejecutable de Linux con PyInstaller (unos 220 MB sin comprimir) y arrancó sin errores con `QT_QPA_PLATFORM=offscreen`.
- Captura de la ventana con el ejemplo calculado: valores iguales a `examples/portico_simple.py` (M+ de la viga 119.08 kN·m en 1.2D+1.6L; lectura a x = 4.20 m: M = 90.28, V = −48.00, N = −30.41).
- **No verificado localmente:** el instalador de Windows (Inno Setup) y el armado del AppImage (`appimagetool`), que solo corren en el CI de publicación. Hay que lanzarlo una vez a mano desde Actions antes de la primera etiqueta.

## Decisiones tomadas

- PySide6 (LGPL-3.0, compatible con GPL-3.0) en lugar de PyQt6 o de una interfaz en Rust: madurez de tablas, paneles y accesibilidad; la escalabilidad depende del motor en Rust, de datos en arreglos y del dibujo en GPU, no de la biblioteca de ventanas. La interfaz solo habla con `nervi` y `nervi.formato`, así que se puede reemplazar sin tocar el motor.
- Las cargas trapezoidales entran al esquema 1 del `.nrv` en lugar de abrir un esquema 2: el esquema todavía no se congeló (se congela con `v0.1.0`) y el cambio solo agrega un valor de `tipo`, así que todo archivo anterior sigue siendo válido.
- `nervi.formato.abrir` devuelve un `Documento` y no un `Modelo` (ver `formato-nrv.md` §8).
- Validación escrita a mano en lugar de `jsonschema`, para no sumar dependencias obligatorias.
- OpenCADStudio (GPL-3.0, Rust/iced) queda como referencia: no se copió código ni aspecto. El diseño de la interfaz es propio, a partir de la organización funcional de programas de cálculo y CAD (sala limpia), sin copiar íconos, colores ni pantallas.
- Instaladores sin firma de código por ahora; las versiones se publican como *prerelease*.
- PyInstaller en modo carpeta (no un solo archivo): arranca más rápido y no se descomprime en cada inicio.

## Pendiente y problemas conocidos

- Probar el workflow de publicación (Actions → Publicación → Run workflow) y abrir el `.exe` en un Windows real.
- Firma de código (SignPath Foundation para proyectos libres, o un certificado) y paquetes `.deb`, Flatpak o AUR.
- La interfaz no dibuja todavía las cargas ni permite dibujar barras con el mouse; la vista 3D del diseño llega con la Fase 2a.
- El formato `.nrv` se congela con la primera versión publicada: antes de etiquetar `v0.1.0`, confirmar que el esquema 1 está bien.
- Licencias de dependencias Python (PySide6 LGPL-3.0, PyInstaller GPL-2.0 con excepción para el cargador): no hay un control automático equivalente a `cargo-deny`; se revisaron a mano.

## Para quien siga

- La ventana está en `python/nervi/gui/ventana.py`; el estado y el cálculo en `sesion.py`. Para una nueva tabla editable alcanza con agregar la lista y sus columnas en `tablas.LISTAS`.
- El diseño de referencia de la interfaz es el artefacto "Nervi Escritorio" del proyecto.
