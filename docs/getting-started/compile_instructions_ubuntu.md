# Palace Build Instructions for Ubuntu 24.04

This guide is focused on the current recommended workflow:

1. Install `palace-toolkit` from PyPI
2. Verify Palace runtime
3. Use optional source build only for power-user/nightly scenarios

## Quick Start (Recommended)

Examples:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package
pip install palace-toolkit

# Optional: install prebuilt Palace CPU runtime (Linux x86_64)
pip install "palacetoolkit-palace-cpu @ https://github.com/EpsilonForge/PalaceToolkit/releases/download/palace-cpu-v0.1.2/palacetoolkit_palace_cpu-0.1.2-py3-none-linux_x86_64.whl"

# Verify Palace runtime
palace-toolkit-check
```

For versioning/support guarantees, see `docs/getting-started/compatibility-policy.md`.

## WSL troubleshooting notes

On WSL, install these libraries if runtime/plotting issues appear:

```bash
sudo apt update
sudo apt install -y libglu1-mesa-dev libgomp1 libxft2
```

Matplotlib in WSL is often non-interactive by default (`FigureCanvasAgg`).
For interactive windows:

```bash
sudo apt install -y python3-tk
```

Then set:

```text
backend: TkAgg
```

## Optional: Source Build (Nightly/Custom)

Only use this mode if you need non-default Palace options (CUDA/HIP/MAGMA, etc.)
or nightly source.

```bash
PALACETOOLKIT_BUILD_PALACE=1 PALACETOOLKIT_CLONE_NIGHTLY=1 pip install -e .

# force rebuild if cache exists
PALACETOOLKIT_FORCE_PALACE_REBUILD=1 pip install -e .

# verify custom runtime
palace-toolkit-check
```

## System Information

- **OS:** Ubuntu 24.04 (Linux)
- **Architecture:** x86_64
- **CPU Cores:** 32

## Prerequisites Check

First, we verified which dependencies were already installed and which needed to be added:

```bash
# Check CMake (not installed initially)
cmake --version

# Check compilers (already installed)
g++ --version
gcc --version

# Check Fortran (not installed initially)
gfortran --version

# Check MPI (not installed initially)
mpirun --version
mpiexec --version
mpic++ --version
mpicc --version

# Check Python (already installed)
python3 --version

# Check pkg-config (not installed initially)
pkg-config --version

# Check for BLAS/LAPACK libraries (not installed initially)
ldconfig -p | grep openblas

# Check for optional libraries
ldconfig -p | grep libunwind
ldconfig -p | grep libz

# Check available CPU cores
nproc
```

## Step 1: Update Package Lists

```bash
sudo apt update
```

## Step 2: Install Required Dependencies

```bash
sudo apt install -y cmake gfortran openmpi-bin libopenmpi-dev libopenblas-dev pkg-config git make
```

This single command installs:
- **cmake**: Build system (version 3.28.3)
- **gfortran**: Fortran compiler (version 13.3.0)
- **openmpi-bin**: OpenMPI runtime and binaries (version 4.1.6)
- **libopenmpi-dev**: OpenMPI development headers
- **libopenblas-dev**: OpenBLAS linear algebra library (BLAS/LAPACK)
- **pkg-config**: Package configuration tool
- **git**: Version control (likely already installed)
- **make**: Build automation tool (likely already installed)

## Step 3: Verify Installations

```bash
cmake --version
gfortran --version
mpirun --version
pkg-config --version
```

Expected output:
- CMake: version 3.28.3 or later
- GFortran: version 13.3.0
- MPI: OpenMPI 4.1.6
- pkg-config: version 1.8.1

## Step 4: Clone Palace Repository (power-user source build only)

```bash
git clone https://github.com/awslabs/palace.git
cd palace
```

## Step 5: Configure the Build

Create a build directory and configure with CMake using optimized settings:

```bash
mkdir -p build
cd build

cmake .. \
  -DCMAKE_INSTALL_PREFIX=/home/martin/Desktop/palace/build \
  -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_CXX_FLAGS="-O3 -ffp-contract=fast -funroll-loops -march=native" \
  -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_C_FLAGS="-O3 -ffp-contract=fast -funroll-loops -march=native" \
  -DCMAKE_Fortran_COMPILER=gfortran \
  -DCMAKE_Fortran_FLAGS="-O3 -ffp-contract=fast -funroll-loops -march=native" \
  -DBUILD_SHARED_LIBS:BOOL=ON \
  -DPALACE_WITH_64BIT_INT:BOOL=OFF \
  -DPALACE_WITH_OPENMP:BOOL=ON \
  -DPALACE_WITH_CUDA:BOOL=OFF \
  -DPALACE_WITH_HIP:BOOL=OFF \
  -DPALACE_WITH_SUPERLU:BOOL=ON \
  -DPALACE_WITH_STRUMPACK:BOOL=ON \
  -DPALACE_WITH_MUMPS:BOOL=ON \
  -DPALACE_WITH_SLEPC:BOOL=ON \
  -DPALACE_WITH_ARPACK:BOOL=ON \
  -DPALACE_WITH_LIBXSMM:BOOL=ON \
  -DPALACE_WITH_MAGMA:BOOL=OFF \
  -DPALACE_WITH_GSLIB:BOOL=ON
```

### Configuration Options Explained:

- **CMAKE_INSTALL_PREFIX**: Installation directory (default: build directory)
- **Compiler flags**: Aggressive optimization with `-O3`, fast math, loop unrolling, and native CPU optimization
- **BUILD_SHARED_LIBS=ON**: Build shared libraries instead of static
- **PALACE_WITH_OPENMP=ON**: Enable OpenMP for shared-memory parallelism
- **PALACE_WITH_SUPERLU=ON**: Include SuperLU_DIST sparse direct solver
- **PALACE_WITH_STRUMPACK=ON**: Include STRUMPACK sparse direct solver
- **PALACE_WITH_MUMPS=ON**: Include MUMPS sparse direct solver
- **PALACE_WITH_SLEPC=ON**: Include SLEPc eigenvalue solver
- **PALACE_WITH_ARPACK=ON**: Include ARPACK eigenvalue solver
- **PALACE_WITH_LIBXSMM=ON**: Include LIBXSMM backend for libCEED
- **PALACE_WITH_GSLIB=ON**: Include GSLIB for high-order field interpolation
- **PALACE_WITH_MAGMA=OFF**: Disabled (requires CUDA or HIP)

## Step 6: Build Palace

Build using all available CPU cores (32 in this case):

```bash
make -j16
```

**Note:** Adjust the number after `-j` based on your available CPU cores. You can use `nproc` to find the number of cores.

The build process will:
1. Download and build third-party dependencies (METIS, ParMETIS, Hypre, SuperLU_DIST, STRUMPACK, MUMPS, PETSc, SLEPc, ARPACK-NG, LIBXSMM, SUNDIALS, nlohmann/json, fmt, Eigen, GSLIB, libCEED)
2. Build MFEM (finite element discretization library)
3. Build Palace itself

Build time: Approximately 10-20 minutes depending on your system.

## Step 7: Verify Installation

Check that Palace was built successfully:

```bash
./bin/palace --version
``` 

Expected output:
```
Palace version: v0.15.0-9-gdcb3b0ba
```

View available options:
```bash
./bin/palace --help
```

## Step 8: Run Examples (Optional)

Test Palace with an example:

```bash
cd /home/martin/Desktop/palace/examples/cpw
../../build/bin/palace cpw.json
```

## File Locations

After successful build:
- **Palace binary**: `build/bin/palace`
- **Palace executable**: `build/bin/palace-x86_64.bin`
- **Validation tool**: `build/bin/validate-config`
- **Shared libraries**: `build/lib/`
- **Header files**: `build/include/`

## Using Palace

To run Palace simulations with MPI:

```bash
# Single process
./build/bin/palace config.json

# Multiple MPI processes (e.g., 4 processes)
./build/bin/palace -np 4 config.json

# With OpenMP threads (e.g., 8 threads)
./build/bin/palace -nt 8 config.json

# Combined MPI + OpenMP
./build/bin/palace -np 4 -nt 8 config.json
```

## Troubleshooting

### If build fails due to memory issues:
Reduce the number of parallel jobs:
```bash
make -j4  # Use only 4 cores
```

### To rebuild from scratch:
```bash
cd /home/martin/Desktop/palace/build
rm -rf *
cmake .. [OPTIONS]
make -j32
```

### To update and rebuild:
```bash
cd /home/martin/Desktop/palace
git pull
cd build
make -j32
```

## Additional Notes

- These options are useful for custom source builds when prebuilt CPU wheels are not sufficient
- The build uses serial BLAS/LAPACK (OpenBLAS) as recommended for pure MPI parallelism
- All third-party dependencies are automatically downloaded and built during the configuration/build process
- No manual dependency installation is required beyond the system packages listed in Step 2
