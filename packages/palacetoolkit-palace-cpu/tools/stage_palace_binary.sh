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

pkg_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dst_bin_dir="$pkg_dir/src/palacetoolkit_palace_cpu/bin"
dst_lib_dir="$pkg_dir/src/palacetoolkit_palace_cpu/lib"

mkdir -p "$dst_bin_dir"
cp "$src_launcher" "$dst_bin_dir/palace"
cp "$src_engine" "$dst_bin_dir/palace-x86_64.bin"
chmod +x "$dst_bin_dir/palace" "$dst_bin_dir/palace-x86_64.bin"

rm -rf "$dst_lib_dir"/*
mkdir -p "$dst_lib_dir"

declare -a valid_lib_dirs=()
for src_lib_dir in "$@"; do
  if [[ -d "$src_lib_dir" ]]; then
    valid_lib_dirs+=("$src_lib_dir")
  fi
done

if [[ ${#valid_lib_dirs[@]} -eq 0 ]]; then
  echo "No valid library directory found in arguments: $*"
  exit 1
fi

is_runtime_lib() {
  local dep="$1"
  for root in "${valid_lib_dirs[@]}"; do
    case "$dep" in
      "$root"/*) return 0 ;;
    esac
  done
  return 1
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
    if ! is_runtime_lib "$dep"; then
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
  echo "No runtime libraries were discovered from provided library directories."
  exit 1
fi

if command -v strip >/dev/null 2>&1; then
  strip --strip-unneeded "$dst_bin_dir/palace-x86_64.bin" || true
  find "$dst_lib_dir" -type f -name '*.so*' -exec strip --strip-unneeded {} + || true
fi

echo "Staged binaries in $dst_bin_dir and ${#queued[@]} runtime libraries in $dst_lib_dir"
du -sh "$dst_bin_dir" "$dst_lib_dir"
