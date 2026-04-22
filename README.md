# PalaceToolkit

A Python toolkit for open-source electromagnetic simulation with
[Palace](https://awslabs.github.io/palace/) and [Gmsh](https://gmsh.info/).
PalaceToolkit provides a declarative pipeline that takes you from geometry
definition to post-processed S-parameters and far-field plots — no commercial
licence required.

## Features

| Module | Description |
|--------|-------------|
| `palace.mesh` | Priority-based boolean pipeline for multi-material Gmsh models with automatic size-field grading. |
| `palace.simulation` | Run Palace via Apptainer/MPI and extract S-parameters and impedance. |
| `palace.verify_topology` | Validate that a 3D tetrahedral mesh is topologically consistent for Palace/MFEM. |
| `palace.analytic` | Closed-form transmission-line formulas (CPW impedance, effective index, …). |
| `palace.s_plot` | Quick matplotlib plots of Palace S-parameter CSV files. |
| `palace.view_mesh` | Interactive PyVista viewer with per-group colouring. |
| `palace.viz` | Headless-safe visualisation helpers that export standalone HTML for docs and notebooks. |

## Installation

### Prerequisites

* Python ≥ 3.8
* [Palace](https://awslabs.github.io/palace/) (installed or available via Apptainer/Docker)
* [Gmsh](https://gmsh.info/) (the `gmsh` Python package is pulled automatically)

### Install the package

```bash
# Clone the repository
git clone https://github.com/<your-org>/palace-course.git
cd palace-course

# Create a virtual environment and install in editable mode
python -m venv .venv
source .venv/bin/activate
pip install -e ".[plot,docs]"
```

The core install pulls `gmsh`, `numpy`, `meshio`, `pyvista`, `femwell`,
`enlighten`, and `pint`. The optional dependency groups are:

| Group | Extra packages |
|-------|---------------|
| `plot` | `pandas`, `matplotlib` |
| `docs` | `mkdocs`, `mkdocs-material`, `pyvista[jupyter]`, `nbconvert`, `ipykernel`, `papermill`, `nb-clean`, `pre-commit` |

## Quick start

Below is a minimal example that creates a coaxial geometry, meshes it, runs
Palace, and plots the S-parameters:

```python
from palace.mesh import Entity, run_boolean_pipeline
from palace.simulation import run_palace
from palace.s_plot import plot_s_params

# 1. Define entities with names, priorities and materials
inner  = Entity(name="inner_conductor", ...)
dielectric = Entity(name="dielectric", ...)
outer  = Entity(name="outer_conductor", ...)

# 2. Run the boolean pipeline — cuts, fragments, and meshes
run_boolean_pipeline([inner, dielectric, outer], output="coax.msh")

# 3. Run Palace with a JSON config
run_palace("coax.json", np=4)

# 4. Plot results
plot_s_params("postpro/coax")
```

See the `lecture_*` directories and `docs/gallery/` notebooks for complete
worked examples covering waveguides, dipole antennas, horn antennas, and
planar microwave circuits.

## Building the docs

The documentation site is built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).
A [justfile](https://github.com/casey/just) automates the full pipeline.

```bash
# Install docs dependencies (if not already)
pip install -e ".[docs]"

# Register the virtualenv as a Jupyter kernel
just ipykernel

# Full build: execute notebooks → convert to Markdown → build site
just docs-full

# Or run each step individually:
just nbrun      # execute all gallery notebooks with papermill
just nbdocs     # convert notebooks to Markdown with embedded images
just docs       # build the MkDocs static site

# Serve locally for development
just serve      # starts a dev server on http://localhost:8080
```

### Other useful recipes

| Recipe | Description |
|--------|-------------|
| `just nbclean` | Strip cell outputs from notebooks for clean commits. |