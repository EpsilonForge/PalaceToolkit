# PalaceToolkit

A Python toolkit for open-source electromagnetic simulation with
[Palace](https://awslabs.github.io/palace/) and [Gmsh](https://gmsh.info/).
PalaceToolkit provides a declarative pipeline that takes you from geometry
definition to post-processed S-parameters and far-field plots — no commercial
licence required.

## Features

| Module | Description |
|--------|-------------|
| `palacetoolkit.mesh` | Priority-based boolean pipeline for multi-material Gmsh models with automatic size-field grading. |
| `palacetoolkit.simulation` | Run Palace via downloaded runtime or optional Apptainer/SIF and extract S-parameters and impedance. |
| `palacetoolkit.verify_topology` | Validate that a 3D tetrahedral mesh is topologically consistent for Palace/MFEM. |
| `palacetoolkit.analytic` | Closed-form transmission-line formulas (CPW impedance, effective index, …). |
| `palacetoolkit.postpro` | Quick matplotlib plots of Palace S-parameter CSV files. |
| `palacetoolkit.viz` | Interactive PyVista mesh viewer with per-group colouring. |
| `palacetoolkit.utils` | Headless-safe visualisation helpers that export standalone HTML for docs and notebooks. |

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
sudo apt install -y libglu1-mesa-dev libgomp1 libxft2 openmpi-bin libopenmpi-dev libopenblas0

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

- `palace-cpu-vX.Y.Z` triggers the binary build/release workflow for `palacetoolkit-palace-cpu`.
- The workflow also supports manual dispatch from GitHub Actions.

## Quick start

See `docs/examples/` notebooks for worked examples covering waveguides,
dipole antennas, horn antennas, and planar microwave circuits.

## Building the docs

The documentation site is built with
[PyData Sphinx Theme](https://pydata-sphinx-theme.readthedocs.io/en/stable/index.html).
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
just nbdocs     # no-op (Sphinx renders .ipynb directly)
just docs       # build the Sphinx static site (strict mode)

# Serve locally for development
just serve      # starts a dev server on http://localhost:8080

# Execute all simulations and publish the site to the gh-pages branch
just deploy-docs
```

## Deploying docs

The documentation site is executed, built, and published locally. There is no
CI workflow that runs the simulations or deploys the site.

```bash
pip install -e ".[docs]"
just deploy-docs
# or: ./scripts/deploy-docs.sh
```

The deploy script:

1. copies `docs/` to a temporary directory (the working tree is left untouched),
2. executes every notebook in `docs/examples/` with papermill, including the
   Palace simulations,
3. builds the static site with Sphinx in strict mode,
4. replaces the contents of the `gh-pages` branch with the new site and pushes
   it to `origin`.

Every deploy therefore re-runs all simulations and publishes their latest
outputs. The first deploy creates `gh-pages` as an orphan branch; later deploys
update it.

To publish using the notebook outputs already stored in the committed
`.ipynb` files instead (for example for the very first deploy), run:

```bash
SKIP_SIMULATIONS=1 just deploy-docs
# or: ./scripts/deploy-docs.sh --skip-simulations
```

### One-time GitHub Pages setup

In the repository settings, open **Settings → Pages → Build and deployment**
and select:

- **Source:** Deploy from a branch
- **Branch:** `gh-pages`, folder `/ (root)`

The site is then served at `https://<owner>.github.io/<repository>/`.

See `DEPLOYING-DOCS.md` for the full deploy workflow and troubleshooting notes.

### Other useful recipes

| Recipe | Description |
|--------|-------------|
| `just deploy-docs` | Execute all simulations, build the site, and publish it to `gh-pages`. |
| `just nbclean` | Strip cell outputs from docs example notebooks for clean commits. |

## Roadmap

- **Interactive 3D viewer for docs** — Currently, mesh visualisations in the
  documentation are static PNG screenshots. A future enhancement will embed an
  interactive VTK.js viewer powered by
  [trame](https://kitware.github.io/trame/) or PyVista's `export_html`, giving
  readers the ability to rotate, pan, and inspect 3D meshes directly in the
  browser without leaving the documentation page.