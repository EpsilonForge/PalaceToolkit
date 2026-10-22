# Deploying Docs

The PalaceToolkit documentation is built and published entirely from a local
checkout. There is no CI workflow that executes the notebooks or deploys the
site.

Deployment means one command:

```bash
just deploy-docs
# or directly:
./scripts/deploy-docs.sh
```

The published site lives on the `gh-pages` branch of the repository and is
served by GitHub Pages.

## What the script does

`scripts/deploy-docs.sh` performs these steps:

1. Checks the Python environment (`sphinx`, `papermill`, `ipykernel`, and
   `palacetoolkit` must be importable).
2. Copies `docs/` into a temporary directory. The source tree, including the
   notebooks in `docs/examples/`, is never modified.
3. Registers the `palacetoolkit` Jupyter kernel and checks the Palace runtime.
   If no runtime is available, the prebuilt Palace CPU runtime is installed.
4. Executes **every** notebook in `docs/examples/` with papermill, with
   `DOCS_BUILD=1`, a non-interactive matplotlib backend, and off-screen
   PyVista rendering. This is the simulation step: the built pages contain the
   outputs from the run that just finished. A failing Palace run is a hard
   error rather than a fallback to previously committed postprocessing data.
5. Builds the static site with Sphinx in strict mode.
6. Adds `.nojekyll` so GitHub Pages serves Sphinx's `_static` and `_sources`
   directories.
7. Replaces the contents of `gh-pages` with the new site and pushes it to
   `origin`. The first deploy creates the branch as an orphan; later deploys
   replace its contents.

If any notebook fails, the script stops and nothing is published.

## Prerequisites

Install the docs dependencies in your virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[docs]"
```

The script uses `.venv/bin/python` when it exists. Set `PYTHON=/path/to/python`
to use a different interpreter.

The notebooks execute Palace simulations locally, so the machine must be able
to run Palace. On Linux x86_64 the script installs the prebuilt CPU runtime on
first use when none is configured. See the main README for the WSL system
packages needed by Gmsh, MPI, and headless rendering.

## One-time GitHub Pages setup

In the GitHub repository:

1. Open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Choose branch **`gh-pages`** and folder **`/ (root)`**.
4. Save.

The site is served at:

```text
https://<owner>.github.io/<repository>/
```

For this repository that is `https://epsilonforge.github.io/PalaceToolkit/`.

Do not use the "GitHub Actions" Pages source: this repository intentionally has
no docs deploy workflow.

## Usage

```bash
# Execute all simulations, build, and publish to origin/gh-pages
just deploy-docs

# Publish using the notebook outputs already stored in docs/examples/*.ipynb
# (useful for the first deploy or documentation-only changes)
SKIP_SIMULATIONS=1 just deploy-docs
./scripts/deploy-docs.sh --skip-simulations

# Directly, with optional overrides
PYTHON=.venv/bin/python ./scripts/deploy-docs.sh
GIT_REMOTE=upstream GH_PAGES_BRANCH=gh-pages ./scripts/deploy-docs.sh
```

With `--skip-simulations` (or `SKIP_SIMULATIONS=1`), the script neither
registers the Jupyter kernel nor checks the Palace runtime; it builds the site
from the outputs already present in the committed notebooks.

The deploy script publishes the current checkout. Commit or stash source
changes first if you want the published `gh-pages` history to point at a clean
source revision; the script records the current branch and commit in its commit
message.

If the generated site is identical to the previous deployment, the script
reports that there are no changes and does not create an empty commit.

## Local preview

To inspect the staged site without publishing, run the normal docs build and
serve it:

```bash
just docs-full   # execute notebooks in-place, then build site/
just serve       # http://localhost:8080
```

Note that `just docs-full` executes notebooks in your working tree, whereas
`just deploy-docs` works from a temporary copy.

## Troubleshooting

- **A notebook fails:** the script exits before building or pushing. Fix the
  notebook or the local Palace runtime and run the script again.
- **`missing Python dependencies`:** install them with
  `pip install -e ".[docs]"`.
- **Palace runtime cannot start:** run `palace-toolkit-check` and, if needed,
  `palace-toolkit-install-binary --force`.
- **Pages shows a 404:** confirm the Pages source is the `gh-pages` branch and
  `/ (root)` folder, and that the branch was pushed successfully.
- **Assets are missing or unstyled:** make sure `.nojekyll` is present at the
  root of `gh-pages`; the deploy script adds it automatically.
- **Push rejected:** someone else updated `gh-pages` after your fetch. Re-run
  the deploy so it starts from the latest remote branch.
