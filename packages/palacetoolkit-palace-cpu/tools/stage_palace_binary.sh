#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 /path/to/palace-binary /path/to/palace-lib-dir"
  exit 2
fi

src_bin="$1"
src_lib_dir="$2"
if [[ ! -f "$src_bin" ]]; then
  echo "Binary not found: $src_bin"
  exit 1
fi
if [[ ! -d "$src_lib_dir" ]]; then
  echo "Library directory not found: $src_lib_dir"
  exit 1
fi

pkg_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dst_bin="$pkg_dir/src/palacetoolkit_palace_cpu/bin/palace"
dst_lib_dir="$pkg_dir/src/palacetoolkit_palace_cpu/lib"

cp "$src_bin" "$dst_bin"
chmod +x "$dst_bin"
rm -rf "$dst_lib_dir"
mkdir -p "$dst_lib_dir"
cp -a "$src_lib_dir"/. "$dst_lib_dir"/
echo "Staged $dst_bin and libraries in $dst_lib_dir"
