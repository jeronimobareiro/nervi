<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/marca/nervi-logotipo-oscuro.svg">
    <img alt="Nervi" src="docs/marca/nervi-logotipo-claro.svg" width="320">
  </picture>
</p>

# Nervi

[Español](README.md) · **English** · [Português](README.pt.md) · [Русский](README.ru.md)

Free, collaborative structural design and analysis software, with a numerical core in Rust and an application layer in Python. The goal: engineers size, analyze and design reinforced concrete, steel and composite structures starting from the architectural drawing, and deliver the calculation report, quantity takeoffs, rebar schedules and detail drawings. Today it covers frame analysis and the design of concrete beams and columns; the rest is in the [roadmap](docs/hoja-de-ruta.md) (Spanish).

Website: **[jeronimobareiro.github.io/nervi](https://jeronimobareiro.github.io/nervi/)**.

> **Status: preliminary version under development.** Linear elastic plane frames (Phase 1) are nearly complete and have a desktop interface. Space frames and dynamics (Phase 2) and reinforced concrete design per ACI 318-19 (Phase 3) have started and are preliminary or experimental. There is no regional design code or IFC support yet. Details in [`docs/ESTADO.md`](docs/ESTADO.md) and the plan in the [roadmap](docs/hoja-de-ruta.md) (both in Spanish).
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

### Analysis

- **Plane frames** with Euler-Bernoulli members (3 DOF per node): nodal loads; uniform, point, trapezoidal or partial and thermal member loads, in local or global axes; concentrated moments within a member; hinges, end releases and trusses; rigid and elastic supports and prescribed settlements.
- Several load cases with a single factorization and linear combinations. Reactions, member end forces, `N`, `V`, `M` diagrams and deflected shape, with the points of maximum moment.
- Mechanism detection (it tells which node and degree of freedom move without stiffness) and input validation with clear messages.
- **Space frames** from Python (`nervi.Modelo3D`, preliminary): 12-DOF members with biaxial bending, axial force and torsion, local axes set by a reference vector, space-truss bars and common sections in `nervi.secciones`. **Rigid floor diaphragms** (`Modelo3D.diafragma`, master-slave constraint by transformation, with center of mass and story drifts) and **rigid end offsets** (`brazo_i`, `brazo_j`), with member forces at the joint face. No interface or `.nrv` support yet.
- **Dynamics** (preliminary): nodal masses, member masses (lumped or consistent) and masses from load cases; modal analysis with periods, mode shapes and participating mass per direction; response spectrum analysis with SRSS or CQC (`Modelo3D.modal`). The code spectrum is supplied by the designer. For plane frames, also from the desktop interface (`nervi.dinamica_plana`).
- **Physical building model** (`nervi.fisico.ModeloFisico`, preliminary): stories with their elevation, grid lines, materials and sections, and columns, beams, solid slabs and walls as objects, saved in the `.nrv` file. In the interface, a project with a building shows the plan of each story (▲▼ to move up and down), the tree, editable tables and properties, and a floor manager. **Floor loads** (superimposed dead and live load in kN/m², plus each slab's self-weight) are distributed to beams and walls by tributary areas with exact equilibrium, and the *Cargas* (loads) button shows the areas and what each beam receives. The **analysis model** is generated from the building automatically (a 3D frame with rigid end offsets, one diaphragm per story, fixed bases and the slab loads; `ModeloFisico.modelo_calculo()` from Python): *Calcular* (F5) solves it for 1.4D and 1.2D+1.6L, the 3D view shows the building, the analysis model or both with their diagrams, and *Resultados › Por elemento* maps the internal forces back to each beam, column and wall. There is no *Edificio | Cálculo* switch: the stages (Geometry › Loads › Analysis › Results › Design) decide what is shown. The building is **drawn with the mouse**: grid lines, columns, beams, walls and slabs, with object snaps, Ortho (F8) and typed length and angle.

### Reinforced concrete design per ACI 318-19 (experimental)

- Load combinations and envelopes per section (`nervi.design`).
- Rectangular **beams**: singly or doubly reinforced flexural design, choice of commercial bars and shear stirrups; immediate and long-term deflections with effective moment of inertia, crack control, and development, hook and lap splice lengths (`aci318.servicio`, `aci318.detalle`). Flexural design and bar selection run in Rust.
- **Columns**: biaxial bending with axial load and interaction diagram, slenderness by moment magnification and choice of reinforcement, from plane or space frames. The computation runs in Rust.

It has not yet been reviewed by a structural engineer: do not use it for real projects.

### Desktop interface and documents

- **Interface** (`nervi-gui`, PySide6) in a single window, following the stages Geometry › Loads › Analysis › Results › Design: model tables, analysis with F5, diagrams with values under the cursor, a single viewer for the front and 3D views (right-drag orbits around the point under the cursor; 3D is optional), **Dinámica** tab (masses, animated modes and spectra), **Design** stage (every beam and column, each check with its code clause), model check, Python console, command palette (Ctrl+K), undo and redo (Ctrl+Z, Ctrl+Y) and an AI assistant panel to apply or discard what your AI proposes. Light theme by default and a dark theme in the brand colors. The interface is currently in Spanish.
- **Projects** in the [`.nrv`](docs/formato-nrv.md) format, with versioned modules (model, design, dynamics) and migrations so that old projects always open.
- **Calculation report in PDF**, in Spanish with an editable template: cover page, reference codes, model data, loads, combinations, results, diagrams, envelopes and, when applicable, the design and dynamic analysis chapters (`nervi.memoria`, or Ctrl+P in the interface).
- **Full-precision results** in JSON, without the rounding of the report: displacements, reactions, end forces and diagrams of every load case and combination, plus design and dynamics when up to date, with the fingerprint of the model they belong to ([`formato-resultados.md`](docs/formato-resultados.md)).
- **DXF import**: the lines of a drawing from AutoCAD or another program, by layer, become nodes and members, with a preview before applying (*Archivo › Importar DXF*). No AI needed.
- **AI agent connection** over MCP (`nervi-mcp`): the agent you already use (Claude, Gemini or another MCP client) queries the open project or a file and explains the results, with every number taken from the engine; it changes nothing, it only proposes changes that you apply or discard ([`agentes-ia.md`](docs/agentes-ia.md), in Spanish).

### Performance

Supports are handled by partitioning degrees of freedom (no penalty method), and the system is solved with sparse Cholesky from [`faer`](https://github.com/sarah-quinones/faer-rs): a frame with 8,100 members solves in about 45 ms (release build). With column and beam design in Rust, the Design stage of the 130-member reference frame went from 132 s to 2.4 s (`scripts/medir_diseno.py`).

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

More examples in [`examples/`](examples/) (plane frame, space frame, building with diaphragms, beam and column design). Sign conventions in [`docs/convenciones.md`](docs/convenciones.md).

### Desktop interface (preliminary)

```
pip install "nervi[gui]"       # or, from source: pip install PySide6-Essentials
pip install "nervi[visor3d]"   # optional: 3D viewer (PyVista and VTK)
nervi-gui                      # or: python -m nervi.gui project.nrv
```

Choose the light or dark theme and the font size in **Preferencias** (the bottom icon of the side bar); the report cover data, materials and design criteria go in **Configuración del proyecto** (Archivo menu). Windows (`.exe`) and Linux (AppImage) installers are built in [Releases](https://github.com/jeronimobareiro/nervi/releases) when a `v*` tag is published; they are not signed. A step-by-step guide is on the [website](https://jeronimobareiro.github.io/nervi/en/).

> **Preliminary version, not fit for real projects.** Linear elastic analysis is verified against analytical solutions; space frames and dynamics are preliminary, and ACI 318-19 design is experimental and has not yet been reviewed by a structural engineer.

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
crates/nervi-core/   numerical core in pure Rust (no Python)
  src/                plane frame: elements, analysis, mechanisms
  src/espacial/       space frame, diaphragms and rigid offsets, dynamics
  src/diseno/         heavy design computations (column biaxial bending)
  tests/              cases against analytical solutions
crates/nervi-py/     PyO3 bridge (contracts in docs/contrato-datos.md)
python/nervi/        Python package: API, .nrv format, PDF report
  design/             code-based design (ACI 318-19)
  gui/                desktop interface and its design system (estilo.py)
tests/               Python API and interface tests
verification/        verification cases in TOML, no Rust needed
examples/            usage examples
scripts/             timing benchmark, CI checks and website build
docs/                specification, conventions, contracts, status and log
sitio/               public website ("sitio" = site)
```

## Verification

Each case in `crates/nervi-core/tests/` and `verification/` is compared against a closed-form solution or a published example, with a relative tolerance of 1e-9 for analysis: cantilevers, simply supported, fixed-end and continuous beams, frames under lateral load, trusses, settlements, elastic supports, mechanisms, space frames, diaphragms, modes and spectra. Design is checked against hand calculations and other free libraries; comparison with published examples is pending.

## How we work

These rules apply to every contribution, from people or from AI agents. Details in [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md).

1. **Verification and sources.** Every new feature comes with its verification cases and the source of each formula.
2. **Performance first.** Every computation that loops over members, nodes, combinations or points (analysis, design, envelopes, interaction diagrams) goes in Rust and is exposed to Python with the same API. Python is for the interface, the PDF report, examples and prototypes. Every migration or optimization is timed before and after with the benchmark, passes the same tests and gives exactly the same results: tolerances and accuracy are never lowered to gain speed.
3. **One design system for the interface.** Every control takes its style from [`estilo.py`](python/nervi/gui/estilo.py), following the [interface design guidelines](docs/diseno-interfaz.md): light theme by default and the brand's dark theme. Design changes are agreed on with a visual sample before they are implemented.
4. **Documentation kept up to date.** Every contribution updates, in the same pull request, the informative files it affects: the README and its translations, `CONTRIBUTING.md`, `AGENTS.md`, `docs/ESTADO.md`, the roadmap, the website and related technical documents, plus its entry in the log. That way newcomers know where the project stands.

## What comes next

- Performance: add the timing benchmark to CI and speed up the column reinforcement search, which is now almost all of the design time.
- Close Phase 1: textbook examples in `verification/` ([#6](https://github.com/jeronimobareiro/nervi/issues/6)) and teaching material ([#10](https://github.com/jeronimobareiro/nervi/issues/10)).
- Space frames in the interface and the `.nrv` format, verification against published 3D examples ([#15](https://github.com/jeronimobareiro/nervi/issues/15)), P-Δ ([#19](https://github.com/jeronimobareiro/nervi/issues/19)) and the regional code spectrum ([#20](https://github.com/jeronimobareiro/nervi/issues/20)).
- Engineering review of reinforced concrete design and comparison with published examples.
- Expanded vision (phases 6 to 12): physical model from the architectural DXF, shells for slabs and walls, code loads and preliminary sizing, steel design to AISC 360-22, slabs, walls and foundations, composite structures and construction documents (rebar schedules, detail drawings, quantity takeoffs). Issues [#73](https://github.com/jeronimobareiro/nervi/issues/73) to [#98](https://github.com/jeronimobareiro/nervi/issues/98).

## Contributing

Nervi is open to students, teachers, researchers and engineers from anywhere in the world. Start with the [contributing guide](CONTRIBUTING.md#contributing-from-other-countries) and the [glossary](docs/glosario.md). Issues labelled `buen-primer-aporte` are good first issues; `proyecto-academico` and `tesis-posible` mark topics the size of a course project or a thesis. The rules of conduct are in the [Code of Conduct](CODE_OF_CONDUCT.md) and decision rules in [`GOVERNANCE.md`](GOVERNANCE.md). If you find a wrong result that could affect a real structure, follow [`SECURITY.md`](SECURITY.md).

To cite Nervi in academic work, use [`CITATION.cff`](CITATION.cff).

## License

Copyright (C) 2026 Jerónimo Bareiro and Nervi contributors ([`AUTHORS.md`](AUTHORS.md)).

GPL-3.0 or later. See [`LICENSE`](LICENSE). Nervi comes with no warranty; any calculation used in a real project must be checked and signed by a licensed professional.

Nervi implements methods described in technical standards (ACI, AISC, Eurocodes and others) by citing their clauses; it does not reproduce their text and is not certified or endorsed by those bodies. The Nervi name and logo identify the project (see [`GOVERNANCE.md`](GOVERNANCE.md#marca)).

*If this translation and the [Spanish README](README.md) differ, the Spanish version prevails.*
