#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_bin="${PYTHON_BIN:-python}"
main_extras="${PALACETOOLKIT_MAIN_EXTRAS:-[plot,docs]}"

"$python_bin" -m pip install -e "$repo_root/packages/palacetoolkit-palace-cpu"
"$python_bin" -m pip install -e "$repo_root${main_extras}"

echo "Local editable install complete (binary package + PalaceToolkit)."
