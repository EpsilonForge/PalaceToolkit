#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 /path/to/palace-bin-dir /path/to/palace-lib-dir [/path/to/extra-lib-dir ...]"
  exit 2
fi

src_bin_dir="$1"
shift
if [[ ! -d "$src_bin_dir" ]]; then
  echo "Binary directory not found: $src_bin_dir"
  exit 1
fi

src_launcher="$src_bin_dir/palace"
src_engine="$src_bin_dir/palace-x86_64.bin"

if [[ ! -f "$src_launcher" ]]; then
  echo "Binary not found: $src_launcher"
  exit 1
fi
if [[ ! -f "$src_engine" ]]; then
  echo "Binary not found: $src_engine"
  exit 1
fi

# Include build-output lib dirs in LD_LIBRARY_PATH so ldd can resolve them
for src_lib_dir in "$@"; do
  if [[ -d "$src_lib_dir" ]]; then
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$src_lib_dir"
  fi
done
export LD_LIBRARY_PATH

pkg_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dst_root="$pkg_dir/src/palacetoolkit_palace_cpu"
dst_bin_dir="$dst_root/bin"
dst_lib_dir="$dst_root/lib"
dst_share_dir="$dst_root/share"

# Bundling the Open MPI runtime is the default.  Set this to 1 only to build a
# wheel that deliberately relies on a matching Open MPI already installed on the
# host; such a wheel will not run on a machine without one.
skip_mpi_runtime="${PALACE_SKIP_MPI_RUNTIME:-0}"

mkdir -p "$dst_bin_dir"
rm -f "$dst_bin_dir/palace" "$dst_bin_dir/palace-launcher" "$dst_bin_dir/orted" \
      "$dst_bin_dir/orterun" "$dst_bin_dir/mpirun"
cp "$src_engine" "$dst_bin_dir/palace-x86_64.bin"
chmod +x "$dst_bin_dir/palace-x86_64.bin"

# The upstream `palace` script is an MPI launcher wrapper.  When we bundle our
# own Open MPI it is installed as `palace-launcher` and fronted by a wrapper
# that points Open MPI at the bundled runtime (see stage_mpi_runtime below).
cp "$src_launcher" "$dst_bin_dir/palace-launcher"
chmod +x "$dst_bin_dir/palace-launcher"

rm -rf "$dst_lib_dir" "$dst_share_dir"
mkdir -p "$dst_lib_dir"

# Libraries that are universally available on glibc-based Linux systems and
# should NOT be bundled.  Bundling them would risk ABI conflicts with the
# host system's versions.
is_system_lib() {
  local dep="$1"
  local name
  name="$(basename "$dep")"
  case "$name" in
    linux-vdso*|ld-linux-*|libc.so*|libm.so*|libdl.so*)
      return 0 ;;
    libpthread.so*|librt.so*|libutil.so*|libresolv.so*)
      return 0 ;;
    libnss_*|libBrokenLocale*|libanl.so*|libcidn.so*)
      return 0 ;;
    libcrypt.so*|libkeyutils.so*|libselinux.so*|libcap.so*)
      return 0 ;;
    libstdc++.so*|libgcc_s.so*)
      return 0 ;;
    libz.so*|libbz2.so*|liblzma.so*|libzstd.so*)
      return 0 ;;
    *)
      return 1 ;;
  esac
}

collect_deps() {
  local target="$1"
  ldd "$target" 2>/dev/null | awk '
    /=>/ && $3 ~ /^\// { print $3 }
    /^[[:space:]]*\// { print $1 }
  '
}

copy_lib_with_links() {
  local dep="$1"
  local real
  real="$(readlink -f "$dep")"
  local real_name
  real_name="$(basename "$real")"

  if [[ -e "$dst_lib_dir/$real_name" ]]; then
    return  # already copied
  fi

  cp -a "$real" "$dst_lib_dir/$real_name"

  local dep_name
  dep_name="$(basename "$dep")"
  if [[ "$dep_name" != "$real_name" ]]; then
    ln -sf "$real_name" "$dst_lib_dir/$dep_name"
  fi
}

stage_components() {
  # Copy a directory of dlopened MCA components into lib/<name>/.
  local src="$1" name="$2"
  shopt -s nullglob
  local comps=("$src"/*.so)
  shopt -u nullglob
  if [[ ${#comps[@]} -eq 0 ]]; then
    return 1
  fi
  mkdir -p "$dst_lib_dir/$name"
  cp -a "${comps[@]}" "$dst_lib_dir/$name/"
  echo "  staged ${#comps[@]} $name components from $src"
  return 0
}

stage_data() {
  # Copy a runtime's help text into share/<name>/.  Without it, failures are
  # reported as "couldn't open the help file" instead of the actual cause.
  local src="$1" name="$2"
  if [[ -d "$src" ]]; then
    mkdir -p "$dst_share_dir/$name"
    cp -a "$src"/. "$dst_share_dir/$name/"
  else
    echo "WARNING: $src not found — $name runtime errors will be terse"
  fi
}

# ---------------------------------------------------------------------------
# Open MPI runtime
#
# Palace links libmpi, so ldd finds the Open MPI shared libraries.  It does NOT
# find the two other halves of an Open MPI installation:
#
#   * the MCA components (lib/openmpi/mca_*.so), which Open MPI dlopens -- with
#     none present, opal_shmem_base_select fails and the process aborts before
#     MPI_Init, even for a single serial rank;
#   * orted, which Open MPI execs to bootstrap a rank (including a singleton).
#
# A wheel staged from ldd output alone therefore ships a Palace binary that
# cannot start on any machine that lacks a matching host Open MPI.  Stage both
# explicitly, plus the help text under share/openmpi so runtime errors are
# readable rather than "couldn't open the help file".
# ---------------------------------------------------------------------------
ompi_path() {
  ompi_info --path "$1" 2>/dev/null | head -1 | awk -F': *' '{print $2}'
}

stage_mpi_runtime() {
  if ! command -v ompi_info >/dev/null 2>&1; then
    echo "Error: ompi_info not found, so the Open MPI runtime cannot be located."
    echo "Install the Open MPI development tools, or set PALACE_SKIP_MPI_RUNTIME=1"
    echo "to build a wheel that requires a matching host Open MPI."
    exit 1
  fi

  local version major
  version="$(ompi_info --version 2>/dev/null | head -1 | awk '{print $NF}' | tr -d 'v')"
  major="${version%%.*}"
  if [[ "$major" != "4" ]]; then
    echo "Error: found Open MPI $version; only 4.x runtime bundling is implemented."
    echo "Open MPI 5.x replaces orted/orterun with PRRTE and needs different staging."
    exit 1
  fi

  local prefix libdir pkglibdir pkgdatadir bindir
  prefix="$(ompi_path prefix)"
  libdir="$(ompi_path libdir)"
  pkglibdir="$(ompi_path pkglibdir)"
  pkgdatadir="$(ompi_path pkgdatadir)"
  bindir="$(ompi_path bindir)"

  if [[ ! -d "$pkglibdir" || ! -d "$bindir" ]]; then
    echo "Error: ompi_info reported unusable paths (pkglibdir=$pkglibdir bindir=$bindir)"
    exit 1
  fi

  # Guard against staging one Open MPI's components next to another's
  # libraries.  Same version number is not enough: builds differ in whether
  # hwloc is embedded, and mismatched components fail to load with an
  # undefined-symbol error at MPI_Init.
  local linked_libmpi linked_real
  linked_libmpi="$(collect_deps "$dst_bin_dir/palace-x86_64.bin" | grep -m1 '/libmpi\.so' || true)"
  if [[ -n "$linked_libmpi" ]]; then
    linked_real="$(readlink -f "$linked_libmpi")"
    if [[ "$linked_real" != "$prefix"/* ]]; then
      echo "Error: Palace links $linked_real but ompi_info reports prefix $prefix."
      echo "The staged MCA components would not match the staged libmpi."
      echo "Put the Open MPI that Palace was built against first on PATH."
      exit 1
    fi
  fi

  # orted/orterun are copied first: PMIx discovery below reads orted's own
  # dependency list.
  local exe
  for exe in orted orterun; do
    if [[ ! -f "$bindir/$exe" ]]; then
      echo "Error: $bindir/$exe not found; cannot bundle a usable Open MPI runtime"
      exit 1
    fi
    cp "$bindir/$exe" "$dst_bin_dir/$exe"
    chmod +x "$dst_bin_dir/$exe"
  done
  ln -sf orterun "$dst_bin_dir/mpirun"

  if ! stage_components "$pkglibdir" openmpi; then
    echo "Error: no MCA components found in $pkglibdir"
    exit 1
  fi
  stage_data "$pkgdatadir" openmpi

  # PMIx ships its own dlopened components and help text, and Open MPI aborts in
  # pmix_init without them.  Open MPI 4.1 may use an internal PMIx under
  # $libdir/pmix or an external one installed under its own prefix (Debian puts
  # it in .../pmix2/lib), so locate it from the library orted actually links.
  # Distributions disagree on where PMIx lives: Open MPI 4.1 with internal PMIx
  # puts the components in $libdir/pmix, while a build against an external
  # openpmix keeps them under that package's own prefix.  Try the known layouts,
  # then fall back to a bounded search beside the linked libpmix.
  local pmix_lib pmix_libdir pmix_root candidate
  pmix_lib="$(collect_deps "$dst_bin_dir/orted" | grep -m1 '/libpmix\.so' || true)"
  pmix_libdir=""
  if [[ -n "$pmix_lib" ]]; then
    pmix_libdir="$(dirname "$(readlink -f "$pmix_lib")")"
  fi

  pmix_root=""
  for candidate in "$libdir/pmix" "$pmix_libdir/pmix" "$prefix/lib/pmix"; do
    [[ -n "$candidate" ]] || continue
    if compgen -G "$candidate/*.so" >/dev/null 2>&1; then
      pmix_root="$candidate"
      break
    fi
  done
  if [[ -z "$pmix_root" && -n "$pmix_libdir" ]]; then
    while IFS= read -r candidate; do
      if compgen -G "$candidate/*.so" >/dev/null 2>&1; then
        pmix_root="$candidate"
        break
      fi
    done < <(find "$(dirname "$pmix_libdir")" -maxdepth 4 -type d -name pmix 2>/dev/null)
  fi

  if [[ -n "$pmix_root" ]]; then
    stage_components "$pmix_root" pmix || true
    stage_data "$(dirname "$(dirname "$pmix_root")")/share/pmix" pmix
  else
    # Not fatal: some builds link PMIx statically into libopen-pal.  The wheel
    # smoke test is what actually proves the bundled runtime starts.
    echo "WARNING: no PMIx component directory found; if the wheel smoke test"
    echo "         fails in pmix_init, stage PMIx explicitly."
  fi

  # Wrapper: OPAL_PREFIX alone is not reliable, because distributions configure
  # libdir outside $prefix (Debian) and the relocation arithmetic then points
  # Open MPI at the wrong directory.  Set the component path explicitly, and
  # put the bundled bin dir first on PATH so the upstream launcher's default
  # `mpirun` resolves to the bundled orterun rather than to whatever MPI the
  # host happens to have -- which may be a different implementation entirely.
  cat > "$dst_bin_dir/palace" <<'WRAPPER'
#!/bin/bash
# Point Open MPI at the runtime bundled inside this package before handing off
# to the upstream Palace launcher.
PKG_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
export OPAL_PREFIX="$PKG_DIR"
export OMPI_MCA_mca_base_component_path="$PKG_DIR/lib/openmpi"
export OMPI_MCA_orte_launch_agent="$PKG_DIR/bin/orted"
export PMIX_INSTALL_PREFIX="$PKG_DIR"
export PMIX_MCA_mca_base_component_path="$PKG_DIR/lib/pmix"
export PATH="$PKG_DIR/bin:$PATH"
exec "$PKG_DIR/bin/palace-launcher" "$@"
WRAPPER
  chmod +x "$dst_bin_dir/palace"

  echo "Staged Open MPI $version runtime: components, orted and orterun"
}

if [[ "$skip_mpi_runtime" == "1" ]]; then
  echo "WARNING: PALACE_SKIP_MPI_RUNTIME=1 — the wheel will require a matching"
  echo "         Open MPI on the host and will not run without one."
  rm -f "$dst_bin_dir/palace-launcher"
  cp "$src_launcher" "$dst_bin_dir/palace"
  chmod +x "$dst_bin_dir/palace"
else
  stage_mpi_runtime
fi

declare -A queued
declare -a queue=("$dst_bin_dir/palace-x86_64.bin")

# The MCA components and the MPI runtime executables have their own dependency
# trees; walk them too, or the components load and then fail on a missing lib.
shopt -s nullglob
for staged in "$dst_lib_dir"/openmpi/*.so "$dst_lib_dir"/pmix/*.so \
              "$dst_bin_dir"/orted "$dst_bin_dir"/orterun; do
  queue+=("$staged")
done
shopt -u nullglob

while [[ ${#queue[@]} -gt 0 ]]; do
  target="${queue[0]}"
  queue=("${queue[@]:1}")
  while IFS= read -r dep; do
    [[ -n "$dep" ]] || continue
    [[ -e "$dep" ]] || continue
    if is_system_lib "$dep"; then
      continue
    fi

    real_dep="$(readlink -f "$dep")"
    if [[ -n "${queued[$real_dep]:-}" ]]; then
      continue
    fi
    queued[$real_dep]=1

    copy_lib_with_links "$dep"
    queue+=("$dst_lib_dir/$(basename "$real_dep")")
  done < <(collect_deps "$target")
done

if [[ ${#queued[@]} -eq 0 ]]; then
  echo "No runtime libraries were discovered."
  exit 1
fi

# Set RPATH on the actual ELF binary so the dynamic linker finds bundled
# libs automatically without needing LD_LIBRARY_PATH.  (The `palace`
# launcher is a bash script so we skip it.)
if command -v patchelf >/dev/null 2>&1; then
  # Strip embedded RUNPATH/RPATH from all bundled .so files so they
  # don't block the main binary's RPATH propagation.
  for so in "$dst_lib_dir"/*.so*; do
    [[ -f "$so" ]] || continue
    patchelf --remove-rpath "$so" 2>/dev/null || true
  done

  # Use --force-rpath to set the legacy RPATH (not RUNPATH) on the
  # main binary so it propagates to transitive dependencies.
  # RUNPATH does not propagate, so libs loaded by bundled .so files
  # (e.g. libarpack -> libopenblas) would not find them.
  patchelf --force-rpath --set-rpath '$ORIGIN/../lib' "$dst_bin_dir/palace-x86_64.bin"

  # MCA components are dlopened, so they inherit nothing from the main
  # binary's RPATH and need their own path back up to lib/.
  shopt -s nullglob
  for so in "$dst_lib_dir"/openmpi/*.so "$dst_lib_dir"/pmix/*.so; do
    patchelf --force-rpath --set-rpath '$ORIGIN/..' "$so" 2>/dev/null || true
  done
  for exe in "$dst_bin_dir"/orted "$dst_bin_dir"/orterun; do
    patchelf --force-rpath --set-rpath '$ORIGIN/../lib' "$exe" 2>/dev/null || true
  done
  shopt -u nullglob
  echo "RPATH set on palace-x86_64.bin, MPI runtime and MCA components"
else
  echo "WARNING: patchelf not found — RPATH not set. The bundled libs will"
  echo "require LD_LIBRARY_PATH at runtime."
fi

# Strip debug symbols to shrink the package
if command -v strip >/dev/null 2>&1; then
  strip --strip-unneeded "$dst_bin_dir/palace-x86_64.bin" || true
  find "$dst_lib_dir" -type f -name '*.so*' -exec strip --strip-unneeded {} + || true
  shopt -s nullglob
  for exe in "$dst_bin_dir"/orted "$dst_bin_dir"/orterun; do
    strip --strip-unneeded "$exe" || true
  done
  shopt -u nullglob
fi

echo "Staged binaries in $dst_bin_dir and ${#queued[@]} runtime libraries in $dst_lib_dir"
du -sh "$dst_bin_dir" "$dst_lib_dir"
[[ -d "$dst_share_dir" ]] && du -sh "$dst_share_dir"
