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

![The Nervi window with the moment diagrams of a frame](img/interfaz.png){ .nv-captura }

!!! warning "Preliminary version, not suitable for design work"
    Nervi is under development. Today it analyses plane frames with linear elastic analysis; it does not yet design to codes. It assists the engineer; it does not replace their judgment or their signature.

<div class="grid cards nv-tarjetas" markdown>

-   **Verifiable**

    Every type of calculation is compared with a known formula and cites its source. You can check how it reaches each number.

-   **Free and open**

    GPL-3.0 license. You can use it, teach with it, study it and improve it, without paying for licenses.

-   **Built with universities**

    Students, teachers and engineers can contribute coursework, theses or reviews. See [how to take part](participar/index.md).

</div>

## What it does today

- **Plane frames** with members, hinges, trusses, fixed or elastic supports and support settlements.
- **Loads** on nodes and members: uniform, point, and trapezoidal or partial.
- **Load cases and combinations**, for example 1.2D + 1.6L.
- **Results**: reactions, axial force, shear and moment diagrams, and the deformed shape. Hovering over a member shows the values at that point.
- **Desktop interface** in a single window, with tables to enter the model, or use from Python for those who program.
- **Projects** saved as `.nrv` files.

## What is coming

3D frames, seismic analysis, reinforced concrete design to code, exchange with BIM programs (IFC) and calculation reports. The order and the tasks are in the [roadmap](hoja-de-ruta.md).

## Keep reading

- [Download and install](descargar.md)
- [Getting started](primeros-pasos.md): your first frame, with the interface or with Python
- [Technical documentation](tecnica/especificacion.md): how it calculates, sign conventions and file format
- [How to take part](participar/index.md)
