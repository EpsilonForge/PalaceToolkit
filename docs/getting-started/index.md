# Getting Started

The default install path is one command from PyPI.

## 1. Create a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install PalaceToolkit

```bash
pip install palace-toolkit
```

On Linux x86_64, this also fetches the matching prebuilt Palace CPU runtime
wheel from GitHub Releases.

## 3. Verify Palace runtime

```bash
palace-toolkit-check
```

Expected output includes `Palace runtime check: OK`, the selected runtime path,
and a Palace version line.

## 3b. WSL users (optional GUI + runtime libraries)

Some WSL environments need additional runtime libraries:

```bash
sudo apt update
sudo apt install -y libglu1-mesa-dev libgomp1 libxft2
```

For interactive matplotlib windows in WSL:

```bash
sudo apt install -y python3-tk
```

Then set the backend in `~/.config/matplotlib/matplotlibrc`:

```text
backend: TkAgg
```

## 4. Optional power-user source builds (latest/custom Palace)

Use this only when you explicitly want a source-built Palace (nightly/custom
flags such as CUDA/HIP/MAGMA):

```bash
git clone https://github.com/EpsilonForge/PalaceToolkit.git
cd PalaceToolkit
python3 -m venv .venv
source .venv/bin/activate
PALACETOOLKIT_BUILD_PALACE=1 PALACETOOLKIT_CLONE_NIGHTLY=1 pip install -e .
```

You can then point PalaceToolkit at your custom runtime via Python:

```bash
python -c "from palacetoolkit.simulation import set_palace_path; set_palace_path('/path/to/palace-or-Palace.sif')"
```

See the dedicated Ubuntu build guide and compatibility policy for details.

