#!/usr/bin/env bash
set -eo pipefail
echo "=== Starting Palace build ==="

BUILD_ROOT="${BUILD_ROOT:-C:/build}"
PALACE_SRC="$BUILD_ROOT/palace-src"
PALACE_BUILD="$BUILD_ROOT/palace-build"
PALACE_INSTALL="$BUILD_ROOT/palace-install"

echo "=== Cloning Palace ==="
git clone https://github.com/awslabs/palace.git "$PALACE_SRC" 2>&1
cd "$PALACE_SRC" && git fetch --all --tags && git checkout "${PALACE_REF:-main}" 2>&1

echo "=== Creating FindMPI stub ==="
mkdir -p "$PALACE_SRC/cmake"
for var in "MPI_C_FOUND TRUE" "MPI_CXX_FOUND TRUE" "MPI_Fortran_FOUND TRUE" "MPI_FOUND TRUE" 'MPI_C_COMPILER "gcc"' 'MPI_CXX_COMPILER "g++"' 'MPI_Fortran_COMPILER "gfortran"' 'MPI_C_INCLUDE_DIRS "C:/msys64/mingw64/include"' 'MPI_CXX_INCLUDE_DIRS "C:/msys64/mingw64/include"' 'MPI_Fortran_INCLUDE_DIRS "C:/msys64/mingw64/include"' 'MPI_C_LIBRARIES "C:/msys64/mingw64/lib/libmsmpi.dll.a"' 'MPI_CXX_LIBRARIES "C:/msys64/mingw64/lib/libmsmpi.dll.a"' 'MPI_Fortran_LIBRARIES "C:/msys64/mingw64/lib/libmsmpi.dll.a"' 'MPIEXEC_EXECUTABLE "C:/msys64/mingw64/bin/mpiexec.exe"'; do echo "set($var)" >> "$PALACE_SRC/cmake/FindMPI.cmake"; done

echo "=== Fixing patch files ==="
find "$PALACE_SRC/extern/patch" -name "*.diff" -exec sed -i 's/\r$//' {} \;

echo "=== Patching external projects ==="
sed -i 's/\${CMAKE_MAKE_PROGRAM}/mingw32-make/g' "$PALACE_SRC/cmake/ExternalGSLIB.cmake"
sed -i 's/\${CMAKE_MAKE_PROGRAM}/mingw32-make/g' "$PALACE_SRC/cmake/ExternalLIBXSMM.cmake"
sed -i '/STATIC=0/s/$/ WERROR=0/' "$PALACE_SRC/cmake/ExternalLIBXSMM.cmake"

echo "=== Configuring CMake ==="
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
  -DCMAKE_C_FLAGS="-Dffs=__builtin_ffs" 2>&1

echo "=== Building ==="
set +e
cmake --build "$PALACE_BUILD" 2>&1; rc=$?
set -e

if [ $rc -ne 0 ]; then
  echo "=== First build failed, patching and retrying ==="
  XSMM_MK="$PALACE_BUILD/extern/libxsmm/Makefile"
  [ -f "$XSMM_MK" ] && sed -i 's/-Werror//g' "$XSMM_MK" && echo "Patched libxsmm -Werror"
  GSLIB_MK="$PALACE_BUILD/extern/gslib/Makefile"
  [ -f "$GSLIB_MK" ] && sed -i 's/\.so/.dll/g' "$GSLIB_MK" && echo "Patched gslib .so to .dll"
  HYPRE_HDR=$(find "$PALACE_BUILD/extern/hypre" -name "_hypre_utilities.h" -print -quit 2>/dev/null)
  if [ -n "$HYPRE_HDR" ]; then
    sed -i 's/ffs(/__builtin_ffs(/g' "$HYPRE_HDR" && echo "Patched HYPRE ffs"
    sed -i '/#include <malloc.h>/d' "$HYPRE_HDR" && echo "Patched HYPRE malloc.h"
    find "$PALACE_BUILD/extern/hypre" -name "*.c" -o -name "*.h" 2>/dev/null | xargs touch 2>/dev/null
  fi
  set +e
  cmake --build "$PALACE_BUILD" 2>&1
  set -e
fi

echo "=== Build finished with exit code: $rc ==="
