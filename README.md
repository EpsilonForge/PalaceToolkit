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
* [Gmsh](https://gmsh.info/) (the `gmsh` Python package is pulled automatically)

### Install the package

```bash
# Clone the repository
git clone https://github.com/EpsilonForge/PalaceToolkit.git
cd PalaceToolkit

# Create a virtual environment and install in editable mode
python -m venv .venv
source .venv/bin/activate

# Local clone install (recommended for now)
./tools/install_local_editable.sh

# Or equivalent manual commands:
pip install https://github.com/EpsilonForge/PalaceToolkit/releases/download/palace-cpu-vX.Y.Z/<wheel-file>.whl
pip install -e ".[plot,docs]"
```

Default runtime is binary-first when `palacetoolkit-palace-cpu` is installed.

By default, `./tools/install_local_editable.sh` fetches the latest
GA-built binary wheel from GitHub Releases.

To force local binary package mode from the checkout:

```bash
PALACETOOLKIT_BINARY_SOURCE=local ./tools/install_local_editable.sh
```

### Compatibility Policy

- Stable releases of `PalaceToolkit` are validated against a matching stable release of `palacetoolkit-palace-cpu`.
- The default local clone path (`./tools/install_local_editable.sh`) installs both packages from the same repository checkout and is the reference development workflow.
- Nightly Palace builds are supported for power users through opt-in source builds and are treated as best-effort (no stability guarantee across commits).
- If API/runtime behavior differs between stable and nightly Palace, `PalaceToolkit` stable behavior is defined by the stable `palacetoolkit-palace-cpu` line.

See `docs/getting-started/compatibility-policy.md` for the full policy and release cadence.

### Release Tags and CI Publishing

- `palace-cpu-vX.Y.Z` triggers binary build/publish workflow for `palacetoolkit-palace-cpu`.
- `vX.Y.Z` triggers main package build/publish workflow for `PalaceToolkit`.
- Both workflows also support manual dispatch from GitHub Actions.

### Optional: Power-user source build (nightly/custom)

Source builds are opt-in and disabled by default.
Use this only if you need custom flags (CUDA/HIP/MAGMA/etc.) or nightly Palace.

```bash
PALACETOOLKIT_BUILD_PALACE=1 \
PALACETOOLKIT_CLONE_NIGHTLY=1 \
PALACETOOLKIT_PALACE_WITH_CUDA=0 \
PALACETOOLKIT_PALACE_WITH_HIP=0 \
PALACETOOLKIT_PALACE_WITH_MAGMA=0 \
pip install -e .
```

Source builds are cached at:

`~/.cache/palacetoolkit/palace/<source-key>-<platform>-<options-hash>/build/bin/palace`

On subsequent installs, the cached build is reused automatically. Useful controls:

```bash
# Force rebuild even when cache exists
PALACETOOLKIT_FORCE_PALACE_REBUILD=1 pip install -e .

# Use a local Palace source tree instead of cloning nightly
PALACETOOLKIT_PALACE_SOURCE=/path/to/palace PALACETOOLKIT_BUILD_PALACE=1 pip install -e .

# Override parallel build jobs
PALACETOOLKIT_PALACE_JOBS=8 pip install -e .

# Extra custom CMake args
PALACETOOLKIT_PALACE_EXTRA_CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release" pip install -e .
```

The core install pulls `gmsh`, `numpy`, `meshio`, `pyvista`,
`enlighten`, and `pint`. The optional dependency groups are:

| Group | Extra packages |
|-------|---------------|
| `plot` | `pandas`, `matplotlib` |
| `docs` | `mkdocs`, `mkdocs-material`, `pyvista[jupyter]`, `nbconvert`, `ipykernel`, `papermill`, `nb-clean`, `pre-commit` |

## Quick start

Below is a minimal example that creates a coaxial geometry, meshes it, runs
Palace, and plots the S-parameters:

```python
import palacetoolkit as ptk
from ptk.mesh import Entity, run_meshing_pipeline
from ptk.simulation import run_palace
from ptk.s_plot import plot_s_params

# 1. Define entities with names, priorities and materials
inner  = Entity(name="inner_conductor", ...)
dielectric = Entity(name="dielectric", ...)
outer  = Entity(name="outer_conductor", ...)

# 2. Run the boolean pipeline — cuts, fragments, and meshes
run_meshing_pipeline([inner, dielectric, outer], output="coax.msh")

# 3. Run Palace with a JSON config
run_palace("coax.json", np=4)

# 4. Plot results
plot_s_params("postpro/coax")
```

See `docs/examples/` notebooks for worked examples covering waveguides,
dipole antennas, horn antennas, and planar microwave circuits.

## Building the docs

The documentation site is built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).
A [justfile](https://github.com/casey/just) automates the full pipeline.

```bash
# Install docs dependencies (if not already)
pip install -e ".[docs]"

# Register the virtualenv as a Jupyter kernel
just ipykernel

# Full build: execute notebooks → build site
just docs-full

# Run documentation doctests (executes notebooks and fails on errors)
just doctest

# Or run each step individually:
just nbrun      # execute docs example notebooks with papermill
just nbdocs     # no-op (MkDocs renders .ipynb directly)
just docs       # build the MkDocs static site

# Serve locally for development
just serve      # starts a dev server on http://localhost:8080
```

### Other useful recipes

| Recipe | Description |
|--------|-------------|
| `just nbclean` | Strip cell outputs from docs example notebooks for clean commits. |