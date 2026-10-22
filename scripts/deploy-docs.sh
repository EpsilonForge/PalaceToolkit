#!/usr/bin/env bash
#
# Execute every documentation notebook (including the Palace simulations),
# build the Sphinx site, and publish the resulting static site to the
# ``gh-pages`` branch.  Everything runs locally; there is no CI involved.
#
# Usage:
#   ./scripts/deploy-docs.sh
#   ./scripts/deploy-docs.sh --skip-simulations
#   just deploy-docs
#   SKIP_SIMULATIONS=1 just deploy-docs
#
# Environment overrides:
#   PYTHON             Python interpreter to use (default: .venv/bin/python)
#   GIT_REMOTE         Git remote to push to (default: origin)
#   GH_PAGES_BRANCH    Branch that GitHub Pages serves (default: gh-pages)
#   SKIP_SIMULATIONS   Set to 1 to build from existing notebook outputs

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REMOTE="${GIT_REMOTE:-origin}"
BRANCH="${GH_PAGES_BRANCH:-gh-pages}"
SKIP_SIMULATIONS="${SKIP_SIMULATIONS:-0}"

for arg in "$@"; do
    case "$arg" in
        --skip-simulations)
            SKIP_SIMULATIONS=1
            ;;
        -h|--help)
            sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "error: unknown argument '$arg'" >&2
            echo "       Usage: $0 [--skip-simulations]" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Locate the Python interpreter
# ---------------------------------------------------------------------------
if [[ -n "${PYTHON:-}" ]]; then
    PY="$PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
else
    PY="$(command -v python3 || true)"
fi

if [[ -z "${PY:-}" ]]; then
    echo "error: no Python interpreter found; set PYTHON=/path/to/python" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
for cmd in git find; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "error: required command '$cmd' not found" >&2
        exit 1
    fi
done

if ! SKIP_SIMULATIONS="$SKIP_SIMULATIONS" "$PY" - <<'PY'
import importlib
import os

modules = ["sphinx", "palacetoolkit"]
if os.environ.get("SKIP_SIMULATIONS") != "1":
    modules += ["papermill", "ipykernel"]

for module in modules:
    importlib.import_module(module)
PY
then
    echo "error: missing Python dependencies." >&2
    echo "       Install them with: pip install -e '.[docs]'" >&2
    exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "error: $ROOT is not a Git repository" >&2
    exit 1
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
    echo "error: Git remote '$REMOTE' does not exist" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Temporary workspace
# ---------------------------------------------------------------------------
# The docs are executed from a copy so the working tree (in particular the
# notebooks in docs/examples) is never modified by a deploy.
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/palacetoolkit-docs.XXXXXX")"
DOCS_DIR="$TMP_ROOT/docs"
SITE_DIR="$TMP_ROOT/site"
DEPLOY_DIR="$TMP_ROOT/gh-pages"
WORKTREE_ADDED=0

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$WORKTREE_ADDED" -eq 1 ]]; then
        git worktree remove --force "$DEPLOY_DIR" >/dev/null 2>&1 || true
    fi
    rm -rf "$TMP_ROOT"
    exit "$status"
}
trap cleanup EXIT

echo "==> Copying docs to $DOCS_DIR"
mkdir -p "$DOCS_DIR"
cp -a "$ROOT/docs/." "$DOCS_DIR/"
find "$DOCS_DIR" -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +

# ---------------------------------------------------------------------------
# Runtime requirements and notebook execution
# ---------------------------------------------------------------------------
if [[ "$SKIP_SIMULATIONS" == "1" ]]; then
    echo "==> Skipping simulations; using the outputs already stored in docs/examples/*.ipynb"
else
    echo "==> Registering the 'palacetoolkit' Jupyter kernel"
    "$PY" -m ipykernel install --user --name palacetoolkit \
        --display-name "PalaceToolkit" >/dev/null

    echo "==> Checking the Palace runtime"
    if ! "$PY" -c 'from palacetoolkit.simulation import check_palace_runtime; check_palace_runtime()' >/dev/null 2>&1; then
        echo "    Palace runtime not found; installing the prebuilt CPU runtime"
        "$PY" -c 'import sys; from palacetoolkit.cli import palace_toolkit_install_binary; sys.exit(palace_toolkit_install_binary())'
    fi

    export DOCS_BUILD=1
    # Deploys must publish the results of the run that just finished, so a
    # failing Palace run is a hard error instead of falling back to committed data.
    export DOCS_FAIL_ON_SIMULATION_ERROR=1
    export MPLBACKEND=Agg
    export PYVISTA_OFF_SCREEN=true
    export PYTHONUNBUFFERED=1

    mapfile -t notebooks < <(
        find "$DOCS_DIR/examples" -maxdepth 1 -name '*.ipynb' \
            -not -path '*/.ipynb_checkpoints/*' | sort
    )

    if [[ "${#notebooks[@]}" -eq 0 ]]; then
        echo "error: no notebooks found in docs/examples" >&2
        exit 1
    fi

    echo "==> Executing ${#notebooks[@]} documentation notebooks"
    index=0
    for notebook in "${notebooks[@]}"; do
        index=$((index + 1))
        name="$(basename "$notebook")"
        echo "    [$index/${#notebooks[@]}] $name"

        if ! "$PY" -m papermill "$notebook" "$notebook" \
            --kernel palacetoolkit \
            --cwd "$DOCS_DIR/examples" \
            --no-progress-bar
        then
            echo "error: $name failed; nothing was deployed." >&2
            exit 1
        fi
    done
fi

# ---------------------------------------------------------------------------
# Build the static site
# ---------------------------------------------------------------------------
echo "==> Building the Sphinx site"
rm -rf "$SITE_DIR" "$TMP_ROOT/doctrees"
"$PY" -m sphinx -W --keep-going -b html \
    -d "$TMP_ROOT/doctrees" \
    "$DOCS_DIR" "$SITE_DIR"

# GitHub Pages otherwise runs Jekyll, which ignores directories whose names
# start with an underscore (Sphinx's _static, _sources, ...).
touch "$SITE_DIR/.nojekyll"

# ---------------------------------------------------------------------------
# Publish to the gh-pages branch
# ---------------------------------------------------------------------------
echo "==> Publishing $SITE_DIR to $REMOTE/$BRANCH"

git worktree prune

if ! remote_heads="$(git ls-remote --heads "$REMOTE" "refs/heads/$BRANCH")"; then
    echo "error: could not query remote '$REMOTE'" >&2
    exit 1
fi

if [[ -n "$remote_heads" ]]; then
    git fetch --quiet "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH"
    git worktree add --quiet --detach "$DEPLOY_DIR" "refs/remotes/$REMOTE/$BRANCH"
elif git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add --quiet --detach "$DEPLOY_DIR" "refs/heads/$BRANCH"
else
    # First deployment: start an orphan branch so gh-pages contains only the
    # built site and not the history of the source branch.
    git worktree add --quiet --detach "$DEPLOY_DIR" HEAD
    git -C "$DEPLOY_DIR" checkout --quiet --orphan "$BRANCH"
fi
WORKTREE_ADDED=1

# Replace the previous site contents completely.
git -C "$DEPLOY_DIR" rm -rf --ignore-unmatch . >/dev/null
cp -a "$SITE_DIR/." "$DEPLOY_DIR/"
git -C "$DEPLOY_DIR" add -A

if git -C "$DEPLOY_DIR" diff --cached --quiet; then
    echo "==> No site changes to publish"
    published=0
else
    source_branch="$(git symbolic-ref --short -q HEAD || echo detached)"
    source_sha="$(git rev-parse --short HEAD)"
    timestamp="$(date -u '+%Y-%m-%d %H:%M UTC')"

    git -C "$DEPLOY_DIR" commit --quiet \
        -m "docs: publish site from ${source_branch}@${source_sha}" \
        -m "Simulation notebooks executed locally on ${timestamp}."

    git -C "$DEPLOY_DIR" push --quiet "$REMOTE" "HEAD:$BRANCH"
    published=1
fi

echo
if [[ "$published" -eq 1 ]]; then
    echo "==> Done. The site was published to $REMOTE/$BRANCH."
else
    echo "==> Done. $REMOTE/$BRANCH is already up to date."
fi
echo "    GitHub Pages must be configured to serve that branch:"
echo "    Settings -> Pages -> Build and deployment ->"
echo "    Source: Deploy from a branch -> Branch: $BRANCH, folder: / (root)"
