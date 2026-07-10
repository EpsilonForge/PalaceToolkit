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
| `palace.simulation` | Run Palace via downloaded runtime or optional Apptainer/SIF and extract S-parameters and impedance. |
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

- `palace-cpu-vX.Y.Z` triggers binary build/publish workflow for `palacetoolkit-palace-cpu`.
- `vX.Y.Z` triggers main package build/publish workflow for `palace-toolkit`.
- Both workflows also support manual dispatch from GitHub Actions.

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
```

## Deploying docs to epsilonforge.com/palace-toolkit

This repository can deploy its docs independently and attach them to the shared
Router managed by the private website infrastructure.

### One-time setup

1. Install deploy dependencies:

```bash
npm install
python -m pip install sphinx pydata-sphinx-theme myst-parser myst-nb sphinx-copybutton sphinx-design linkify-it-py
```

2. Set environment variables:

```bash
export EPSILON_FORGE_ROUTER_DISTRIBUTION_ID="<router-distribution-id>"
export AWS_REGION="us-east-2"
```

The `EPSILON_FORGE_ROUTER_DISTRIBUTION_ID` value comes from the private repo
stack output `routerDistributionId`.

### Deploy

```bash
npx sst deploy --stage production
```

### GitHub Actions assumptions

The workflow assumes a deterministic IAM role name and reads the shared Router
distribution ID from AWS SSM Parameter Store.

- Role name pattern: `epsilon-forge-palace-toolkit-docs-deploy-<stage>`
- SSM parameter pattern: `/epsilon-forge/<stage>/router-distribution-id`
- AWS account has an IAM OIDC provider for `https://token.actions.githubusercontent.com`

For account `527097962874`, the provider ARN is expected to be:

```text
arn:aws:iam::527097962874:oidc-provider/token.actions.githubusercontent.com
```

The deploy role trust policy must allow `sts:AssumeRoleWithWebIdentity` for this
repository. For pushes to `main`, the subject should match:

```text
repo:EpsilonForge/PalaceToolkit:ref:refs/heads/main
```

Both are created by the private infrastructure repo stack outputs.
### Other useful recipes

| Recipe | Description |
|--------|-------------|
| `just nbclean` | Strip cell outputs from docs example notebooks for clean commits. |