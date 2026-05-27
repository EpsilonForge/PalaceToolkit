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

### Install the package (recommended)

```bash
python -m venv .venv
source .venv/bin/activate
pip install palace-toolkit
```

This installs `palace-toolkit` and, on Linux x86_64, fetches the matching
prebuilt Palace CPU runtime on first use.

Optional (Linux x86_64) prebuilt runtime install:

```bash
palace-toolkit-install-binary
```

### Verify Palace runtime after install

```bash
palace-toolkit-check
```

Expected output includes:

- `Palace runtime check: OK`
- resolved runtime mode/path
- Palace version line from `--version`

### WSL notes (Ubuntu on Windows)

If you run inside WSL, you may need extra system libraries for runtime and plotting:

```bash
sudo apt update
sudo apt install -y libglu1-mesa-dev libgomp1 libxft2
```

Matplotlib may default to a non-interactive backend (`FigureCanvasAgg`).
If you want interactive plot windows:

```bash
sudo apt install -y python3-tk
```

Then set a GUI backend in `~/.config/matplotlib/matplotlibrc`:

```text
backend: TkAgg
```

### Compatibility Policy

- Stable releases of `palace-toolkit` are validated against a matching stable release of `palacetoolkit-palace-cpu`.
- The default user install path is `pip install palace-toolkit`.
- A local clone/editable workflow is still supported for contributors.
- Nightly Palace builds are supported for power users through opt-in source builds and are treated as best-effort (no stability guarantee across commits).
- If API/runtime behavior differs between stable and nightly Palace, `palace-toolkit` stable behavior is defined by the stable `palacetoolkit-palace-cpu` line.

See `docs/getting-started/compatibility-policy.md` for the full policy and release cadence.

### Release Tags and CI Publishing

- `palace-cpu-vX.Y.Z` triggers binary build/publish workflow for `palacetoolkit-palace-cpu`.
- `vX.Y.Z` triggers main package build/publish workflow for `palace-toolkit`.
- Both workflows also support manual dispatch from GitHub Actions.

### Optional: Power-user source build (nightly/custom)

Source builds are opt-in and disabled by default.
Use this only if you need custom flags (CUDA/HIP/MAGMA/etc.) or nightly Palace.

```bash
git clone https://github.com/EpsilonForge/PalaceToolkit.git
cd PalaceToolkit
python -m venv .venv
source .venv/bin/activate

PALACETOOLKIT_BUILD_PALACE=1 \
PALACETOOLKIT_CLONE_NIGHTLY=1 \
PALACETOOLKIT_PALACE_WITH_CUDA=0 \
PALACETOOLKIT_PALACE_WITH_HIP=0 \
PALACETOOLKIT_PALACE_WITH_MAGMA=0 \
pip install -e .

# Optional: point runtime to your just-built Palace binary or SIF
# python -c "from palacetoolkit.simulation import set_palace_path; set_palace_path('/path/to/palace')"
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