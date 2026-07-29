#!/usr/bin/env bash
# =============================================================================
# build_windows.sh — Build Palace from source on Windows (MSYS2 MinGW64)
#
# Called from .github/workflows/palace-cpu-wheel.yml.  All build logic lives
# here so the YAML stays thin and this script can be tested locally.
#
# Environment variables:
#   PALACE_REF     Git ref of awslabs/palace to build (default: main)
#   RUNNER_TEMP    Temp directory (set by GitHub Actions)
# =============================================================================
set -euo pipefail

# ── PATH setup ────────────────────────────────────────────────────────────
export PATH="/c/ninja-1111:/mingw64/bin:/usr/bin:/c/Program Files/Git/bin:/c/Program Files/Git/cmd:$PATH"

BUILD_ROOT="$(echo "${RUNNER_TEMP:-/tmp}" | sed 's|\\|/|g')"
PALACE_SRC="$BUILD_ROOT/palace-src"
PALACE_BUILD="$BUILD_ROOT/palace-build"
PALACE_INSTALL="$BUILD_ROOT/palace-install"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Palace Windows Build ==="
echo "  Source:    $PALACE_SRC"
echo "  Build:     $PALACE_BUILD"
echo "  Install:   $PALACE_INSTALL"

# ── Clone Palace ──────────────────────────────────────────────────────────
git clone --branch "${PALACE_REF:-main}" --depth 1 \
  https://github.com/awslabs/palace.git "$PALACE_SRC"

# ── Stub FindMPI.cmake ────────────────────────────────────────────────────
# CMake's stock FindMPI doesn't recognise the MSYS2 msmpi layout, so we
# provide explicit values via a local module override.
mkdir -p "$PALACE_SRC/cmake"
cat > "$PALACE_SRC/cmake/FindMPI.cmake" << 'EOF'
set(MPI_C_FOUND TRUE)
set(MPI_CXX_FOUND TRUE)
set(MPI_Fortran_FOUND TRUE)
set(MPI_FOUND TRUE)
set(MPI_C_COMPILER "gcc")
set(MPI_CXX_COMPILER "g++")
set(MPI_Fortran_COMPILER "gfortran")
set(MPI_C_INCLUDE_DIRS "C:/msys64/mingw64/include")
set(MPI_CXX_INCLUDE_DIRS "C:/msys64/mingw64/include")
set(MPI_Fortran_INCLUDE_DIRS "C:/msys64/mingw64/include")
set(MPI_C_LIBRARIES "C:/msys64/mingw64/lib/libmsmpi.dll.a")
set(MPI_CXX_LIBRARIES "C:/msys64/mingw64/lib/libmsmpi.dll.a")
set(MPI_Fortran_LIBRARIES "C:/msys64/mingw64/lib/libmsmpi.dll.a")
set(MPIEXEC_EXECUTABLE "C:/msys64/mingw64/bin/mpiexec.exe")
EOF

# ── Fix patch file line endings ────────────────────────────────────────────
find "$PALACE_SRC/extern/patch" -name "*.diff" -exec sed -i 's/\r$//' {} \;

# ── Patch External*.cmake files for MinGW compatibility ──────────────────

# gslib & libxsmm: use mingw32-make instead of ninja
sed -i 's/\${CMAKE_MAKE_PROGRAM}/mingw32-make/g' "$PALACE_SRC/cmake/ExternalGSLIB.cmake"
sed -i 's/\${CMAKE_MAKE_PROGRAM}/mingw32-make/g' "$PALACE_SRC/cmake/ExternalLIBXSMM.cmake"

# libxsmm: disable warnings-as-errors
sed -i '/STATIC=0/s/$/ WERROR=0 WCHECK=0/' "$PALACE_SRC/cmake/ExternalLIBXSMM.cmake"

# Disable libCEED (not needed for CPU-only, avoids build issues)
sed -i 's/INSTALL_COMMAND.*/INSTALL_COMMAND ""\n  BUILD_COMMAND     ""\n  CONFIGURE_COMMAND ""/' \
  "$PALACE_SRC/cmake/ExternalLibCEED.cmake"

# Ensure MFEM waits for SUNDIALS
sed -i 's/set(MFEM_DEPENDENCIES hypre metis)/set(MFEM_DEPENDENCIES hypre metis sundials)/' \
  "$PALACE_SRC/cmake/ExternalMFEM.cmake"

# Install fix_mfem.py and wire it into MFEM's PATCH_COMMAND
cp "$SCRIPT_DIR/fix_mfem.py" "$PALACE_SRC/cmake/fix_mfem.py"
sed -i \
  's|git apply "${MFEM_PATCH_FILES}"|git apply "${MFEM_PATCH_FILES}" \&\& python "${CMAKE_SOURCE_DIR}/cmake/fix_mfem.py"|' \
  "$PALACE_SRC/cmake/ExternalMFEM.cmake"

# ── CMake configure ──────────────────────────────────────────────────────
cmake -S "$PALACE_SRC" -B "$PALACE_BUILD" \
  -G "Ninja" \
  -DCMAKE_INSTALL_PREFIX="$PALACE_INSTALL" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_Fortran_COMPILER=gfortran \
  -DBLA_VENDOR=OpenBLAS \
  -DBLAS_LIBRARIES="C:/msys64/mingw64/lib/libopenblas.dll.a" \
  -DLAPACK_LIBRARIES="C:/msys64/mingw64/lib/libopenblas.dll.a" \
  -DOpenMP_C_FLAGS="-fopenmp" \
  -DOpenMP_C_LIB_NAMES="gomp" \
  -DOpenMP_gomp_LIBRARY="C:/msys64/mingw64/lib/libgomp.dll.a" \
  -DOpenMP_CXX_FLAGS="-fopenmp" \
  -DOpenMP_CXX_LIB_NAMES="gomp" \
  -DOpenMP_Fortran_FLAGS="-fopenmp" \
  -DOpenMP_Fortran_LIB_NAMES="gomp" \
  -DBUILD_SHARED_LIBS=ON \
  -DPALACE_WITH_64BIT_INT=OFF \
  -DPALACE_WITH_OPENMP=ON \
  -DPALACE_WITH_CUDA=OFF \
  -DPALACE_WITH_HIP=OFF \
  -DPALACE_WITH_SUPERLU=OFF \
  -DPALACE_WITH_STRUMPACK=OFF \
  -DPALACE_WITH_MUMPS=OFF \
  -DPALACE_WITH_SLEPC=OFF \
  -DPALACE_WITH_ARPACK=ON \
  -DPALACE_WITH_LIBXSMM=ON \
  -DPALACE_WITH_MAGMA=OFF \
  -DPALACE_WITH_GSLIB=OFF \
  -DCMAKE_C_FLAGS="-Dffs=__builtin_ffs" \
  -DCMAKE_CXX_FLAGS="-Dffs=__builtin_ffs"

# ── CMake build (with retry for known MinGW issues) ──────────────────────
# The first build may fail because:
#   - libxsmm generates Makefile.inc with WERROR enabled at build time
#   - HYPRE source files (downloaded during build) use ffs() and malloc.h
# Both are patched after the first attempt and the build is retried.
set +e
cmake --build "$PALACE_BUILD" 2>&1
BUILD_RC=$?
set -e

if [ "$BUILD_RC" -ne 0 ]; then
  echo "=== First build attempt failed (rc=$BUILD_RC), applying post-build patches ==="

  # Patch libxsmm Makefile.inc WERROR (generated during first build)
  XSMM_INC="$PALACE_BUILD/extern/libxsmm/Makefile.inc"
  if [ -f "$XSMM_INC" ]; then
    sed -i 's/WERROR_CFLAG.*:=.*/WERROR_CFLAG :=/' "$XSMM_INC"
    echo "  Patched libxsmm WERROR in Makefile.inc"
  fi
  rm -f "$PALACE_BUILD/extern/libxsmm-cmake/src/libxsmm-stamp/libxsmm-build"
  rm -f "$PALACE_BUILD/extern/libxsmm/obj/intel64/generator_rv64_instructions.o"

  # Patch HYPRE: fix ffs macro and remove malloc.h include
  HYPRE_HDR=$(find "$PALACE_BUILD/extern/hypre" -name "_hypre_utilities.h" -print -quit 2>/dev/null)
  if [ -n "$HYPRE_HDR" ]; then
    sed -i 's/#define hypre_ffs(x) ffs(x)/#define hypre_ffs(x) __builtin_ffs(x)/' "$HYPRE_HDR"
    sed -i '/#include <malloc.h>/d' "$HYPRE_HDR"
    find "$PALACE_BUILD/extern/hypre" -name "*.c" -o -name "*.h" 2>/dev/null | xargs touch 2>/dev/null
    echo "  Patched HYPRE ffs + malloc.h"
  fi

  echo "=== Retrying build ==="
  cmake --build "$PALACE_BUILD" 2>&1
fi

# ── Install ──────────────────────────────────────────────────────────────
cmake --install "$PALACE_BUILD" 2>&1

echo "=== Palace build + install complete ==="
echo "=== Install tree bin/ contents: ==="
ls -la "$PALACE_INSTALL/bin/" 2>&1 || echo "No bin dir found"
