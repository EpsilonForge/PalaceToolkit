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
dst_bin_dir="$pkg_dir/src/palacetoolkit_palace_cpu/bin"
dst_lib_dir="$pkg_dir/src/palacetoolkit_palace_cpu/lib"

mkdir -p "$dst_bin_dir"
cp "$src_launcher" "$dst_bin_dir/palace"
cp "$src_engine" "$dst_bin_dir/palace-x86_64.bin"
chmod +x "$dst_bin_dir/palace" "$dst_bin_dir/palace-x86_64.bin"

rm -rf "$dst_lib_dir"/*
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

declare -A queued
declare -a queue=("$dst_bin_dir/palace-x86_64.bin")

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
  echo "RPATH set on palace-x86_64.bin (and stripped from bundled libs)"
else
  echo "WARNING: patchelf not found — RPATH not set. The bundled libs will"
  echo "require LD_LIBRARY_PATH at runtime."
fi

# Strip debug symbols to shrink the package
if command -v strip >/dev/null 2>&1; then
  strip --strip-unneeded "$dst_bin_dir/palace-x86_64.bin" || true
  find "$dst_lib_dir" -type f -name '*.so*' -exec strip --strip-unneeded {} + || true
fi

echo "Staged binaries in $dst_bin_dir and ${#queued[@]} runtime libraries in $dst_lib_dir"
du -sh "$dst_bin_dir" "$dst_lib_dir"
