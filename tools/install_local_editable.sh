#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_bin="${PYTHON_BIN:-python}"
main_extras="${PALACETOOLKIT_MAIN_EXTRAS:-[plot,docs]}"
binary_source="${PALACETOOLKIT_BINARY_SOURCE:-github-release}"
github_repo="${PALACETOOLKIT_GITHUB_REPO:-EpsilonForge/PalaceToolkit}"
tag_prefix="${PALACETOOLKIT_BINARY_TAG_PREFIX:-palace-cpu-v}"

install_release_wheel() {
	wheel_url="$($python_bin - <<'PY'
import json
import os
import platform
import sys
import urllib.request

repo = os.environ["PALACETOOLKIT_GITHUB_REPO"]
prefix = os.environ["PALACETOOLKIT_BINARY_TAG_PREFIX"]

machine = platform.machine().lower().replace("amd64", "x86_64")
os_name = platform.system().lower()
target = f"{os_name}_{machine}"

api_url = f"https://api.github.com/repos/{repo}/releases?per_page=30"
req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})

with urllib.request.urlopen(req, timeout=30) as resp:
		releases = json.load(resp)

for rel in releases:
		tag = rel.get("tag_name", "")
		if not tag.startswith(prefix):
				continue
		for asset in rel.get("assets", []):
				name = asset.get("name", "")
				if not name.endswith(".whl"):
						continue
				if "palacetoolkit_palace_cpu" not in name:
						continue
				if target in name:
						print(asset["browser_download_url"])
						sys.exit(0)

sys.exit(1)
PY
	)"

	"$python_bin" -m pip install "$wheel_url"
}

export PALACETOOLKIT_GITHUB_REPO="$github_repo"
export PALACETOOLKIT_BINARY_TAG_PREFIX="$tag_prefix"

if [[ "$binary_source" == "github-release" ]]; then
	echo "Installing latest GA-built Palace CPU wheel from GitHub Releases..."
	if ! install_release_wheel; then
		echo "Could not find/install a release wheel for this platform from $github_repo." >&2
		echo "Set PALACETOOLKIT_BINARY_SOURCE=local to use in-repo editable package." >&2
		exit 1
	fi
elif [[ "$binary_source" == "local" ]]; then
	echo "Installing local editable binary package from repository checkout..."
	"$python_bin" -m pip install -e "$repo_root/packages/palacetoolkit-palace-cpu"
else
	echo "Unsupported PALACETOOLKIT_BINARY_SOURCE='$binary_source' (use github-release or local)." >&2
	exit 1
fi

"$python_bin" -m pip install -e "$repo_root${main_extras}"

echo "Local editable install complete (binary package + PalaceToolkit)."
