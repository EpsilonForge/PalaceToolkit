# Getting Started

This project currently focuses on a local clone workflow.

## 1. Clone and create a Python environment

```bash
git clone https://github.com/EpsilonForge/PalaceToolkit.git
cd PalaceToolkit
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install locally (binary-first runtime)

```bash
./tools/install_local_editable.sh
```

This installs:

- `palacetoolkit-palace-cpu` from `packages/palacetoolkit-palace-cpu`
- `PalaceToolkit` in editable mode

Equivalent manual commands:

```bash
pip install -e packages/palacetoolkit-palace-cpu
pip install -e ".[plot,docs]"
```

## 3. Verify your setup

```bash
python -c "from palacetoolkit.mesh import Entity; print('Ready!')"
```

## 4. Optional power-user source builds

Use this only for nightly/custom Palace builds (CUDA/HIP/MAGMA options):

```bash
PALACETOOLKIT_BUILD_PALACE=1 PALACETOOLKIT_CLONE_NIGHTLY=1 pip install -e .
```

See the dedicated Ubuntu guide and compatibility policy for details.

