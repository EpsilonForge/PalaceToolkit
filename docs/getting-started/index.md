# Installation

### Palace (via Apptainer)

Palace is distributed as an [Apptainer](https://apptainer.org/) container:

```bash
apptainer pull palace.sif oras://ghcr.io/awslabs/palace:latest-ubuntu22.04
export PALACE_SIF=$PWD/palace.sif
```

### PalaceToolkit (Python package)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[docs]"
```

### Verify your setup

```bash
python -c "from palace.mesh import Entity; print('Ready!')"
```

