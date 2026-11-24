---
hide:
  - navigation
  - toc
---

# Nervi { .nv-oculto }

<div class="nv-portada" markdown>

<img class="nv-logo nv-claro" src="marca/nervi-logotipo-claro.svg" alt="Nervi">
<img class="nv-logo nv-oscuro" src="marca/nervi-logotipo-oscuro.svg" alt="Nervi">

<p class="nv-lema">Free software for structural analysis.</p>

Nervi analyses frames with the finite element method and shows reactions, internal forces and deformations. It is free, open source, and every result is checked against a known solution.

[Download](descargar.md){ .md-button .md-button--primary }
[Getting started](primeros-pasos.md){ .md-button }

[Why is it called Nervi?](por-que-nervi.md){ .nv-porque }

</div>

![The Nervi window with the moment diagrams of a frame](img/interfaz-claro.png){ .nv-captura .nv-claro }
![The Nervi window with the moment diagrams of a frame](img/interfaz-oscuro.png){ .nv-captura .nv-oscuro }

!!! warning "Preliminary version, not suitable for design work"
    Nervi is under development. It analyses plane and space frames with linear elastic analysis; the space frame and dynamics are preliminary, and reinforced concrete design to ACI 318-19 is experimental until a structural engineer reviews it. It assists the engineer; it does not replace their judgment or their signature.

<div class="grid cards nv-tarjetas" markdown>

-   **Verifiable**

    Every type of calculation is compared with a known formula and cites its source. You can check how it reaches each number and see the [verified cases](casos-verificados.md).

-   **Free and open**

    GPL-3.0 license. You can use it, teach with it, study it and improve it, without paying for licenses.

-   **Built with universities**

    Students, teachers and engineers can contribute coursework, theses or reviews. See [how to take part](participar/index.md).

</div>

## What it does today

- **Plane frames** with members, hinges, trusses, fixed or elastic supports and support settlements.
- **Space (3D) frames**, preliminary: 12-degree-of-freedom members, rigid offsets and a rigid diaphragm per floor.
- **Loads** on nodes and members: uniform, point, trapezoidal or partial, concentrated moments and thermal loads.
- **Load cases and combinations**, for example 1.2D + 1.6L.
- **Results**: reactions, axial force, shear and moment diagrams and the deformed shape, in 2D and in a 3D viewer. Hovering over a member shows the values at that point. If the model is a mechanism, it tells you which node moves without stiffness.
- **Dynamic analysis**: vibration modes, mass participation and response spectrum (CQC and SRSS), preliminary.
- **Reinforced concrete design to ACI 318-19**, experimental: beams (flexure, shear, deflections and reinforcement detailing) and columns (biaxial bending with axial load, and slenderness), each check with its code article.
- **Calculation report in PDF** with geometry, loads, diagrams, design and dynamic analysis.
- **Desktop interface** in a single window, with a structure panel, tables to enter the model, light and night themes, and use from Python for those who program.
- **An AI assistant on your terms**: you connect the AI you already use (through the MCP standard) to query the model and the results. It can only propose changes that you apply or discard, and every number is computed by Nervi's engine, never by the AI.
- **Projects** saved as `.nrv` files and dozens of verification cases against known solutions.

## What is coming

The goal is for the engineer to receive the architectural drawing as a DXF and deliver the designed structure with complete documentation: calculation report, quantity takeoffs, rebar schedules and concrete and steel detail drawings. On the way come second-order effects (P-Δ), regional codes and spectra (CIRSOC, NBR, NCh, Eurocode), graphical model editing, slabs and walls, wind and seismic loads, preliminary sizing, steel (AISC 360) and composite structures, foundations, exchange with BIM programs (IFC), community plug-ins and a chat inside Nervi. The order and the tasks are in the [roadmap](hoja-de-ruta.md).

## Keep reading

- [Download and install](descargar.md)
- [Getting started](primeros-pasos.md): your first frame, with the interface or with Python
- [Technical documentation](tecnica/especificacion.md): how it calculates, sign conventions and file format
- [How to take part](participar/index.md)
