<div style="text-align: center; margin-bottom: 1em;">
  <img src="_static/PalaceToolkit.png" alt="PalaceToolkit" style="max-width: 320px;">
</div>

# PalaceToolkit

PalaceToolkit is a lightweight Python package that integrates
[Palace](https://awslabs.github.io/palace/) and
[Gmsh](https://gmsh.info/) into a unified open-source electromagnetic FEM simulation workflow.

---

## What is PalaceToolkit?

PalaceToolkit bridges the gap between mesh generation and full-wave
electromagnetic solving.  In a single Python script you can:

- **Define geometry** with the `Entity` abstraction and Gmsh's OpenCASCADE kernel.
- **Generate meshes** via an automatic boolean pipeline that handles
  material priorities, interface labelling, and physical-group assignment.
- **Configure & run Palace** — build JSON configs from entity definitions
  and launch solves with the downloaded executable by default, or an
  Apptainer/SIF image when needed.
- **Post-process results** — extract S-parameters, impedance, effective
  index, and render interactive 3D mesh viewers.

## Quick links

| | |
|:--|:--|
| [Getting Started](getting-started/index.md) | Installation, meshing, simulation setup, post-processing |
| [Examples](examples/index.md) | Waveguides, antennas, and planar microwave circuits |
| [Full Course](full-course.md) | Structured video lectures |
| [Palace docs](https://awslabs.github.io/palace/) | Upstream Palace reference |
| [Gmsh docs](https://gmsh.info/doc/texinfo/gmsh.html) | Upstream Gmsh reference |

```{toctree}
:maxdepth: 2
:hidden:

getting-started/index
examples/index
full-course
```
