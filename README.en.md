<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/marca/nervi-logotipo-oscuro.svg">
    <img alt="Nervi" src="docs/marca/nervi-logotipo-claro.svg" width="320">
  </picture>
</p>

# Nervi

[Español](README.md) · **English** · [Português](README.pt.md) · [Русский](README.ru.md)

Free and open-source structural analysis and design software, with a numerical core in Rust and an application layer in Python.

Website: **[jeronimobareiro.github.io/nervi](https://jeronimobareiro.github.io/nervi/)**.

> **Status: Phase 1 (linear elastic plane frames), with a preliminary desktop interface.** There is no code-based design or IFC support yet. See the [roadmap](docs/hoja-de-ruta.md) (in Spanish).
>
> This software assists the engineer; it does not replace their judgment or professional responsibility. Always check the results.

## The code is in Spanish, and you are welcome anyway

Nervi was born in Latin America, so its code, comments and technical documentation are written in Spanish. That should not stop you from contributing:

- The **[glossary](docs/glosario.md)** translates every structural term and code name into English, Portuguese and Russian (`barra` = member, `nudo` = node, `apoyo` = support, `caso de carga` = load case, `momento flector` = bending moment…).
- **Issues, pull requests and discussions can be written in English, Portuguese or Russian.** Maintainers will answer in your language.
- In review we help you adapt new names to the Spanish vocabulary of the code, so do not let that hold you back.
- Formulas, design codes (ACI, AISC, Eurocodes…) and the mathematics are the same everywhere.

See the [contributing guide](CONTRIBUTING.md#contributing-from-other-countries).

## What it does today

- Plane frames with Euler-Bernoulli members (3 DOF per node).
- Nodal loads and uniform, point, trapezoidal or partial member loads, in local or global axes; thermal loads.
- Hinges and end releases; trusses.
- Rigid and elastic supports, and prescribed settlements.
- Several load cases with a single factorization, and linear combinations (ACI 318-19 combinations and envelopes, experimental).
- Reactions, member end forces, `N`, `V`, `M` diagrams and deflected shape, including the points of maximum moment.
- Mechanism detection and input validation with clear messages.

Supports are handled by partitioning degrees of freedom (no penalty method), and the system is solved with sparse Cholesky from [`faer`](https://github.com/sarah-quinones/faer-rs). A frame with 8,100 members solves in about 45 ms (release build).

## Usage

The API uses Spanish names; the comments show the English meaning.

```python
import nervi

m = nervi.Modelo()                                         # model
a = m.agregar_nudo(0, 0)                                   # add node
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)   # add member (beam), kN, m
m.apoyar(a, ux=True, uy=True, rz=False)                    # pinned support
m.apoyar(b, ux=False, uy=True, rz=False)                   # roller support
m.carga_uniforme("D", viga, qy=-20)                        # uniform load, kN/m downwards, dead load case
m.carga_uniforme("L", viga, qy=-10)                        # live load case

res = m.resolver()                                         # solve
combo = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})    # combine
print(combo.reacciones[a])                 # reactions [Rx, Ry, Mz]
print(combo.diagrama(viga)["M"].max())     # 0.125 · 40 · 6² = 180 kN·m
```

More examples in [`examples/`](examples/). Sign conventions in [`docs/convenciones.md`](docs/convenciones.md).

### Desktop interface (preliminary)

```
pip install "nervi[gui]"       # or, from source: pip install PySide6-Essentials
nervi-gui                      # or: python -m nervi.gui project.nrv
```

Everything happens in a single window: tables for nodes, members, supports, loads and combinations, analysis with F5, N, V, M and deflected-shape diagrams with values under the cursor, selection properties, model check, a Python console and a command palette (Ctrl+K). Projects are saved in the [`.nrv`](docs/formato-nrv.md) format. Windows (`.exe`) and Linux (AppImage) installers are built in [Releases](https://github.com/jeronimobareiro/nervi/releases) when a `v*` tag is published; they are not signed. The interface is currently in Spanish.

> **Preliminary version, not fit for real projects.** Linear elastic analysis is verified against analytical solutions; code-based design does not exist yet.

## Building from source

Requirements: stable Rust and Python ≥ 3.10.

```bash
python -m venv .venv && source .venv/bin/activate
pip install maturin pytest
maturin develop --release
pytest
cargo test -p nervi-core
```

## Layout

```
crates/nervi-core/   FEM core in pure Rust (no Python)
  src/elemento.rs     stiffness, transformation, equivalent loads, releases ("elemento" = element)
  src/analisis.rs     assembly, solution, reactions, diagrams ("análisis" = analysis)
  tests/verificacion.rs  cases against analytical solutions
crates/nervi-py/     PyO3 bridge (contract in docs/contrato-datos.md)
python/nervi/        Python package
tests/              Python API tests
verification/       verification cases in TOML, no Rust needed
docs/               specification, conventions, data contract, glossary
sitio/              website ("sitio" = site)
```

## Verification

Each case in `crates/nervi-core/tests/verificacion.rs` and `verification/` is compared against a closed-form solution or a published example: cantilevers, simply supported, fixed-end and continuous beams, eccentric point loads, a frame under lateral load, a truss, inclined members, settlements, elastic supports, a Gerber beam with a hinge, global equilibrium of a multi-storey frame and mechanism detection.

**Rule for contributors:** every new feature comes with its verification cases and the source of each formula (see [`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Contributing

Nervi is open to students, teachers, researchers and engineers from anywhere in the world. Start with the [contributing guide](CONTRIBUTING.md#contributing-from-other-countries) and the [glossary](docs/glosario.md). Issues labelled `buen-primer-aporte` are good first issues; `proyecto-academico` and `tesis-posible` mark topics the size of a course project or a thesis. The rules of conduct are in the [Code of Conduct](CODE_OF_CONDUCT.md) and decision rules in [`GOVERNANCE.md`](GOVERNANCE.md). If you find a wrong result that could affect a real structure, follow [`SECURITY.md`](SECURITY.md).

To cite Nervi in academic work, use [`CITATION.cff`](CITATION.cff).

## License

Copyright (C) 2026 Jerónimo Bareiro and Nervi contributors ([`AUTHORS.md`](AUTHORS.md)).

GPL-3.0 or later. See [`LICENSE`](LICENSE). Nervi comes with no warranty; any calculation used in a real project must be checked and signed by a licensed professional.

Nervi implements methods described in technical standards (ACI, AISC, Eurocodes and others) by citing their clauses; it does not reproduce their text and is not certified or endorsed by those bodies. The Nervi name and logo identify the project (see [`GOVERNANCE.md`](GOVERNANCE.md#marca)).

*If this translation and the [Spanish README](README.md) differ, the Spanish version prevails.*
