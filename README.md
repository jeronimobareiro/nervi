<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/marca/nervi-logotipo-oscuro.svg">
    <img alt="Nervi" src="docs/marca/nervi-logotipo-claro.svg" width="320">
  </picture>
</p>

# Nervi

**Español** · [English](README.en.md) · [Português](README.pt.md) · [Русский](README.ru.md)

Software libre y colaborativo de diseño y cálculo de estructuras, con un núcleo numérico en Rust y una capa de aplicación en Python. La meta: que los ingenieros predimensionen, calculen y dimensionen estructuras de hormigón armado, acero y mixtas a partir del plano de arquitectura, y entreguen la memoria, los cómputos, las planillas de armaduras y los planos de detalle. Hoy cubre el análisis de pórticos y el diseño de vigas y columnas de hormigón; el resto está en la [hoja de ruta](docs/hoja-de-ruta.md).

Documentación: **[jeronimobareiro.github.io/nervi](https://jeronimobareiro.github.io/nervi/)**.

> **Estado: versión preliminar en desarrollo.** El pórtico plano lineal elástico (Fase 1) está casi completo y tiene interfaz de escritorio. El pórtico espacial y la dinámica (Fase 2) y el diseño de hormigón armado según ACI 318-19 (Fase 3) ya empezaron y son preliminares o experimentales. Todavía no hay norma regional ni IFC. Detalle en [`docs/ESTADO.md`](docs/ESTADO.md) y plan en la [hoja de ruta](docs/hoja-de-ruta.md).
>
> Este software asiste al ingeniero; no reemplaza su criterio ni su responsabilidad profesional. Verificá siempre los resultados.

## Qué hace hoy

### Análisis

- **Pórtico plano** con barras Euler-Bernoulli (3 GDL por nudo): cargas nodales, uniformes, puntuales, trapezoidales o parciales y térmicas en barras, en ejes locales o globales, y momentos concentrados en el tramo; articulaciones, liberaciones de extremo y cerchas; apoyos rígidos, elásticos y asentamientos impuestos.
- Varios casos de carga con una sola factorización y combinaciones lineales. Reacciones, fuerzas de extremo, diagramas `N`, `V`, `M` y deformada, con los puntos de momento máximo.
- Detección de mecanismos (dice qué nudo y qué grado de libertad se mueven sin rigidez) y validación de datos con mensajes claros.
- **Pórtico espacial** desde Python (`nervi.Modelo3D`, preliminar): barras de 12 GDL con flexión en dos planos, axil y torsión, ejes locales con vector de referencia, bielas de cercha espacial y secciones habituales en `nervi.secciones`. **Diafragma rígido por piso** (`Modelo3D.diafragma`, maestro-esclavo por transformación, con centro de masa y derivas de piso) y **brazos rígidos** en los extremos de las barras (`brazo_i`, `brazo_j`), con esfuerzos en la cara de la unión. Todavía sin interfaz ni `.nrv`.
- **Dinámica** (preliminar): masas nodales, de las barras (concentradas o consistentes) y desde los casos de carga; análisis modal con periodos, formas y masa participante por dirección; espectro de respuesta con SRSS o CQC (`Modelo3D.modal`). El espectro de la norma lo da quien diseña. En el pórtico plano también desde la interfaz (`nervi.dinamica_plana`).
- **Modelo físico** del edificio (`nervi.fisico.ModeloFisico`, preliminar): pisos con su nivel, ejes, materiales y secciones, y columnas, vigas, losas macizas y muros como objetos, guardados en el `.nrv`. En la interfaz, el modo *Edificio* muestra la planta de cada piso (con ▲▼ para subir y bajar), el árbol, tablas y propiedades editables y un gestor de plantas. Las **cargas por planta** (permanente y sobrecarga en kN/m², más el peso propio de cada losa) se reparten a vigas y muros por áreas tributarias, con equilibrio exacto, y el botón *Cargas* muestra las zonas y lo que recibe cada viga. Se **dibuja con el mouse**: ejes, columnas (una o una en cada cruce de ejes de una ventana), vigas y muros encadenados y losas con un clic dentro del paño, con enganche a extremos, medios, cruces, ejes y grilla, Orto (F8) y largo y ángulo escritos. Desde Python, `ModeloFisico.modelo_calculo()` genera el **modelo de cálculo** (pórtico espacial con brazos rígidos, un diafragma por piso, empotramientos y las cargas de las losas) y devuelve los esfuerzos a cada viga y columna; la interfaz todavía no lo usa.

### Diseño de hormigón armado según ACI 318-19 (experimental)

- Combinaciones de carga y envolventes por sección (`nervi.design`).
- **Vigas** rectangulares: armadura a flexión simple o doble, elección de barras comerciales y estribos a cortante; flechas inmediatas y diferidas con inercia efectiva, fisuración y longitudes de anclaje, ganchos y empalmes (`aci318.servicio`, `aci318.detalle`). La flexión y la elección de barras corren en Rust.
- **Columnas**: flexocompresión biaxial con curva de interacción, esbeltez por magnificación de momentos y elección de la armadura, desde el pórtico plano o el espacial. El cálculo corre en Rust.

Todavía no lo revisó un ingeniero estructural: no usar para proyecto.

### Interfaz de escritorio y documentos

- **Interfaz** (`nervi-gui`, PySide6) en una sola ventana, con el recorrido Geometría › Cargas › Análisis › Resultados › Diseño: tablas del modelo, cálculo con F5, diagramas con lectura de esfuerzos bajo el cursor, un solo visor para la vista de frente y la 3D (que gira alrededor del punto bajo el cursor con el botón derecho; la 3D es opcional), pestaña **Dinámica** (masas, modos animados y espectros), etapa **Diseño** (todas las vigas y columnas, cada verificación con su artículo), revisión del modelo, consola Python, buscador de comandos (Ctrl+K), deshacer y rehacer (Ctrl+Z, Ctrl+Y) y panel del asistente de IA para aplicar o descartar lo que propone tu IA. Tema claro por defecto y tema oscuro con los colores de la marca.
- **Proyectos** en formato [`.nrv`](docs/formato-nrv.md), con módulos versionados (modelo, diseño, dinámica) y migraciones para que los proyectos viejos se sigan abriendo.
- **Memoria de cálculo en PDF**, en español y con plantilla editable: carátula, normativa de referencia, datos del modelo, cargas, combinaciones, resultados, diagramas, envolventes y, si corresponde, los capítulos de diseño y de análisis dinámico (`nervi.memoria`, o Ctrl+P en la interfaz).
- **Resultados a precisión completa** en JSON, sin el redondeo de la memoria: desplazamientos, reacciones, fuerzas de extremo y diagramas de cada caso y combinación, y el diseño y la dinámica si están al día, con la huella del modelo al que corresponden ([`formato-resultados.md`](docs/formato-resultados.md)).
- **Importar DXF**: las líneas de un dibujo de AutoCAD u otro programa, por capa, se vuelven nudos y barras, con vista previa antes de aplicar (*Archivo › Importar DXF*). No necesita IA.
- **Conexión con agentes de IA** por MCP (`nervi-mcp`): el agente que ya usás (Claude, Gemini u otro cliente MCP) consulta el proyecto abierto o un archivo y explica los resultados, con cada número sacado del motor; no cambia nada, solo propone cambios que vos aplicás o descartás ([`agentes-ia.md`](docs/agentes-ia.md)).

### Rendimiento

Apoyos por partición de grados de libertad (sin penalización) y Cholesky disperso con [`faer`](https://github.com/sarah-quinones/faer-rs): un pórtico de 8 100 barras se resuelve en unos 45 ms (release). Con el diseño de columnas y de vigas en Rust, la etapa Diseño del pórtico de referencia de 130 barras bajó de 132 s a 2,4 s (`scripts/medir_diseno.py`).

## Uso

```python
import nervi

m = nervi.Modelo()
a = m.agregar_nudo(0, 0)
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)   # kN, m
m.apoyar(a, ux=True, uy=True, rz=False)                    # articulado fijo
m.apoyar(b, ux=False, uy=True, rz=False)                   # carrito
m.carga_uniforme("D", viga, qy=-20)                        # kN/m hacia abajo
m.carga_uniforme("L", viga, qy=-10)

res = m.resolver()
combo = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
print(combo.reacciones[a])                 # [Rx, Ry, Mz]
print(combo.diagrama(viga)["M"].max())     # 0.125 · 40 · 6² = 180 kN·m
```

Más ejemplos en [`examples/`](examples/) (pórtico plano, pórtico espacial, edificio con diafragma, diseño de vigas y columnas). Convenciones de signos en [`docs/convenciones.md`](docs/convenciones.md).

### Interfaz de escritorio (preliminar)

```
pip install "nervi[gui]"       # o, desde el código fuente: pip install PySide6-Essentials
pip install "nervi[visor3d]"   # opcional: visor 3D (PyVista y VTK)
nervi-gui                      # o: python -m nervi.gui proyecto.nrv
```

El modelo de cálculo se carga en tablas o se **dibuja con el mouse** en la vista de frente: nudos, barras (que unen y parten lo que tocan), apoyos y cargas puntuales y repartidas, con el mismo enganche, Orto (F8) y largo escrito que la planta del edificio. La rueda acerca y aleja, el botón del medio desplaza y F encuadra. Los paneles (Estructura, Propiedades, Tablas y resultados, Asistente) se acoplan a cualquier borde, se apilan, se desacoplan a otra ventana o a otro monitor y se cierran; *Ver › Paneles* guarda distribuciones con nombre, y Nervi recuerda la última al volver a abrir.

El tema claro u oscuro y el tamaño de letra se eligen en **Preferencias** (el ícono de abajo en la barra lateral); los datos de la carátula, los materiales y los criterios de diseño, en **Configuración del proyecto** (menú Archivo). Los instaladores para Windows (`.exe`) y Linux (AppImage) se generan en [Releases](https://github.com/jeronimobareiro/nervi/releases) al publicar una etiqueta `v*`; no están firmados. Una guía paso a paso está en [Primeros pasos](https://jeronimobareiro.github.io/nervi/primeros-pasos/).

> **Versión preliminar, no apta para proyecto.** El análisis lineal elástico está verificado contra soluciones analíticas; el pórtico espacial y la dinámica son preliminares, y el diseño según ACI 318-19 es experimental y todavía no lo revisó un ingeniero estructural.

## Compilar desde el código fuente

Requisitos: Rust estable y Python ≥ 3.10.

```bash
python -m venv .venv && source .venv/bin/activate
pip install maturin pytest
maturin develop --release
pytest
cargo test -p nervi-core
```

## Estructura

```
crates/nervi-core/   núcleo numérico en Rust puro (sin Python)
  src/                pórtico plano: elementos, análisis, mecanismos
  src/espacial/       pórtico espacial, diafragmas y brazos rígidos, dinámica
  src/diseno/         cálculo pesado del diseño (flexocompresión de columnas)
  tests/              casos contra soluciones analíticas
crates/nervi-py/     puente PyO3 (contratos en docs/contrato-datos.md)
python/nervi/        paquete Python: API, formato .nrv, memoria PDF
  design/             diseño según norma (ACI 318-19)
  gui/                interfaz de escritorio y su sistema de diseño (estilo.py)
tests/               pruebas de la API Python y de la interfaz
verification/        casos de verificación en TOML, sin Rust
examples/            ejemplos de uso
scripts/             banco de tiempos, controles del CI y armado del sitio
docs/                especificación, convenciones, contratos, estado y bitácora
sitio/               sitio web público (mkdocs.yml)
```

## Verificación

Cada caso de `crates/nervi-core/tests/` y de `verification/` compara contra una fórmula cerrada o un ejemplo publicado, con tolerancia relativa de 1e-9 en el análisis: voladizos, vigas biapoyadas, biempotradas y continuas, pórticos con carga lateral, cerchas, asentamientos, apoyos elásticos, mecanismos, pórticos espaciales, diafragmas, modos y espectros. El diseño se verifica con cálculos a mano y contra otras bibliotecas libres; falta compararlo con ejemplos publicados.

## Cómo trabajamos

Estas reglas valen para todo aporte, de personas o de agentes de IA. El detalle está en [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`AGENTS.md`](AGENTS.md).

1. **Verificación y fuentes.** Toda funcionalidad nueva llega con sus casos de verificación y la fuente de cada fórmula.
2. **Rendimiento primero.** Todo cálculo que recorra barras, nudos, combinaciones o puntos (análisis, diseño, envolventes, diagramas de interacción) va en Rust y se expone a Python con la misma API. Python queda para la interfaz, la memoria PDF, los ejemplos y los prototipos. Cada migración u optimización se mide antes y después con el banco de tiempos, pasa las mismas pruebas y da exactamente los mismos resultados: nunca se bajan tolerancias ni exactitud para ganar tiempo.
3. **Un único sistema de diseño en la interfaz.** Todo control toma su estilo de [`estilo.py`](python/nervi/gui/estilo.py) siguiendo la [línea de diseño](docs/diseno-interfaz.md): tema claro por defecto y tema oscuro de la marca. Los cambios de diseño se acuerdan con una muestra visual antes de implementarlos.
4. **Documentación al día.** Cada aporte actualiza en el mismo PR los archivos informativos que correspondan: este README y sus traducciones, `CONTRIBUTING.md`, `AGENTS.md`, `docs/ESTADO.md`, la hoja de ruta, el sitio y la documentación técnica relacionada, además de su entrada en la bitácora. Así quien llega sabe dónde está el proyecto.

## Qué sigue

- Rendimiento: sumar el banco de tiempos al CI y acelerar la búsqueda de la armadura de columnas, que hoy es casi todo el tiempo del diseño.
- Cerrar la Fase 1: ejemplos resueltos de libros en `verification/` ([#6](https://github.com/jeronimobareiro/nervi/issues/6)) y material didáctico ([#10](https://github.com/jeronimobareiro/nervi/issues/10)).
- Pórtico espacial en la interfaz y en el `.nrv`, verificación contra ejemplos 3D publicados ([#15](https://github.com/jeronimobareiro/nervi/issues/15)), P-Δ ([#19](https://github.com/jeronimobareiro/nervi/issues/19)) y espectro de la norma regional ([#20](https://github.com/jeronimobareiro/nervi/issues/20)).
- Revisión de ingeniería del diseño de hormigón armado y comparación con ejemplos publicados.
- Visión ampliada (fases 6 a 12): modelo físico desde el DXF de arquitectura, láminas para losas y muros, cargas según norma y predimensionado, acero según AISC 360-22, losas, muros y fundaciones, estructuras mixtas y documentación de obra (planillas, planos de detalle, cómputos). Issues [#73](https://github.com/jeronimobareiro/nervi/issues/73) a [#98](https://github.com/jeronimobareiro/nervi/issues/98).

## Contribuir

Nervi está abierto a estudiantes, docentes, investigadores e ingenieros. Empezá por [`CONTRIBUTING.md`](CONTRIBUTING.md); las reglas de convivencia están en el [Código de conducta](CODE_OF_CONDUCT.md) y las de decisión en [`GOVERNANCE.md`](GOVERNANCE.md). Si encontrás un resultado incorrecto que pueda afectar una estructura real, seguí [`SECURITY.md`](SECURITY.md).

Nervi recibe aportes de todo el mundo: issues y PR se pueden escribir en español, inglés, portugués o ruso, y el [glosario](docs/glosario.md) traduce los términos del código.

Para citar Nervi en un trabajo académico, usá los datos de [`CITATION.cff`](CITATION.cff).

## Licencia

Copyright (C) 2026 Jerónimo Bareiro y colaboradores de Nervi ([`AUTHORS.md`](AUTHORS.md)).

GPL-3.0 o posterior. Ver [`LICENSE`](LICENSE). Nervi se distribuye sin ninguna garantía; todo cálculo usado en un proyecto real debe ser verificado y firmado por un profesional habilitado.

Nervi implementa métodos descritos en normas técnicas (ACI, AISC, Eurocódigos y otras) citando sus artículos; no reproduce sus textos y no está certificado ni avalado por esos organismos. El nombre y el logo de Nervi identifican al proyecto (ver [`GOVERNANCE.md`](GOVERNANCE.md#marca)).
