# Installation

## Installing Palace

Details for Linux (Debian/Ubuntu), using an Apptainer container (previously
known as Singularity).

For Windows, Palace has to be installed through WSL. Additional information
is included below.

#### 1. Install apptainer

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:apptainer/ppa
sudo apt update
sudo apt install -y apptainer-suid
```

#### 2. Build using the singularity.def file from the Palace repo

Download the contents of the [Palace repo](https://github.com/awslabs/palace)
and from its root directory run:

```bash
sudo apptainer build Palace.sif singularity/singularity.def
```

(this will take a while)

#### 3. Run Palace

Once installed, from the Palace root directory:

```bash
apptainer run Palace.sif <palace arguments>
```

## Python Environment Setup

To run Palace Server, set up a virtual environment and install dependencies:

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies as specified in `pyproject.toml`:

   ```bash
   pip install -e .[dev]
   ```

Your Python environment is now ready for Palace simulations.

#### Notes for WSL users

It may be necessary to manually install the following libraries: `libGLU`,
`libgomp`, and `libXft` (WSL has no GUI stack).

```bash
sudo apt install libglu1-mesa-dev
sudo apt install libgomp1
sudo apt install libxft2
```

Matplotlib will use a non-interactive backend (`FigureCanvasAgg`). To display
windows, install an interactive backend (TkAgg or Qt5Agg):

```bash
sudo apt install python3-tk
```

Then set the backend. One way is to edit `~/.config/matplotlib/matplotlibrc`
and add:

```text
backend: TkAgg
```

### Verify your setup

```bash
python -c "from palacetoolkit.mesh import Entity; print('Ready!')"
```

