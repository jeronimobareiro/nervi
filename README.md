<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/marca/nervi-logotipo-oscuro.svg">
    <img alt="Nervi" src="docs/marca/nervi-logotipo-claro.svg" width="320">
  </picture>
</p>

# Nervi

_Antes llamado Apex BIM._

Software libre de análisis y dimensionamiento estructural, con un núcleo numérico en Rust y una capa de aplicación en Python.

Documentación: **[jeronimobareiro.github.io/nervi](https://jeronimobareiro.github.io/nervi/)**.

> **Estado: Fase 1 (pórtico plano lineal elástico).** Todavía no hay diseño según normas, interfaz gráfica ni IFC. Ver la hoja de ruta en [`docs/especificacion-tecnica.md`](docs/especificacion-tecnica.md).
>
> Este software asiste al ingeniero; no reemplaza su criterio ni su responsabilidad profesional. Verificá siempre los resultados.

## Qué hace hoy

- Pórticos planos con barras Euler-Bernoulli (3 GDL por nudo).
- Cargas nodales, uniformes y puntuales en barras, en ejes locales o globales.
- Articulaciones y liberaciones de extremo; cerchas.
- Apoyos rígidos, apoyos elásticos y asentamientos impuestos.
- Varios casos de carga con una sola factorización, y combinaciones lineales.
- Reacciones, fuerzas de extremo, diagramas `N`, `V`, `M` y deformada, incluyendo los puntos de momento máximo.
- Detección de mecanismos y validación de datos con mensajes claros.

Apoyos por partición de grados de libertad (sin penalización) y Cholesky disperso con [`faer`](https://github.com/sarah-quinones/faer-rs). Un pórtico de 8 100 barras se resuelve en unos 45 ms (release).

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

Más ejemplos en [`examples/`](examples/). Convenciones de signos en [`docs/convenciones.md`](docs/convenciones.md).

### Interfaz de escritorio (preliminar)

```
pip install "nervi[gui]"       # o, desde el código fuente: pip install PySide6-Essentials
nervi-gui                      # o: python -m nervi.gui proyecto.nrv
```

Todo el trabajo pasa en una sola ventana: tablas de nudos, barras, apoyos, cargas y combinaciones, cálculo con F5, diagramas N, V, M y deformada con lectura de esfuerzos al pasar el cursor, propiedades de la selección, revisión del modelo, consola Python y buscador de comandos (Ctrl+K). Los proyectos se guardan en formato [`.nrv`](docs/formato-nrv.md). Los instaladores para Windows (`.exe`) y Linux (AppImage) se generan en [Releases](https://github.com/jeronimobareiro/nervi/releases) al publicar una etiqueta `v*`; no están firmados.

> **Versión preliminar, no apta para proyecto.** El análisis lineal elástico está verificado contra soluciones analíticas; el diseño según norma todavía no existe.

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
crates/nervi-core/   núcleo MEF en Rust puro (sin Python)
  src/elemento.rs     rigidez, transformación, cargas equivalentes, liberaciones
  src/analisis.rs     ensamblaje, solución, reacciones, diagramas
  tests/verificacion.rs  casos contra soluciones analíticas
crates/nervi-py/     puente PyO3 (contrato en docs/contrato-datos.md)
python/nervi/        paquete Python
tests/              pruebas de la API Python
docs/               especificación, convenciones, contrato de datos
sitio/              portada y estilo del sitio web (mkdocs.yml, scripts/preparar_sitio.py)
```

## Verificación

Cada caso de `crates/nervi-core/tests/verificacion.rs` compara contra una fórmula cerrada con tolerancia relativa de 1e-9: voladizos, vigas biapoyadas, biempotradas y continuas, carga puntual excéntrica, pórtico con carga lateral, cercha, barras inclinadas, asentamientos, apoyos elásticos, viga Gerber con articulación, equilibrio global de un pórtico de varios pisos y detección de mecanismos.

**Regla para contribuir:** toda funcionalidad nueva llega con sus casos de verificación y la fuente de cada fórmula (ver [`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Pendiente de la Fase 1

- Cargas trapezoidales y parciales en el tramo, y momentos puntuales en el tramo.
- Cargas térmicas.

## Contribuir

Nervi está abierto a estudiantes, docentes, investigadores e ingenieros. Empezá por [`CONTRIBUTING.md`](CONTRIBUTING.md); las reglas de convivencia están en el [Código de conducta](CODE_OF_CONDUCT.md) y las de decisión en [`GOVERNANCE.md`](GOVERNANCE.md). Si encontrás un resultado incorrecto que pueda afectar una estructura real, seguí [`SECURITY.md`](SECURITY.md).

Para citar Nervi en un trabajo académico, usá los datos de [`CITATION.cff`](CITATION.cff).

## Licencia

Copyright (C) 2026 Jerónimo Bareiro y colaboradores de Nervi ([`AUTHORS.md`](AUTHORS.md)).

GPL-3.0 o posterior. Ver [`LICENSE`](LICENSE). Nervi se distribuye sin ninguna garantía; todo cálculo usado en un proyecto real debe ser verificado y firmado por un profesional habilitado.

Nervi implementa métodos descritos en normas técnicas (ACI, AISC, Eurocódigos y otras) citando sus artículos; no reproduce sus textos y no está certificado ni avalado por esos organismos. El nombre y el logo de Nervi identifican al proyecto (ver [`GOVERNANCE.md`](GOVERNANCE.md#marca)).
