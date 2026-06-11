venv    := ".venv/bin/"
python  := venv + "python"
examples := "docs/examples"

# Register ipykernel (one-time setup)
ipykernel:
    {{python}} -m ipykernel install --user --name palacetoolkit --display-name "PalaceToolkit"

# Step 1: Execute docs examples notebooks in-place with papermill
nbrun: ipykernel
    export DOCS_BUILD=1 && find {{examples}} -maxdepth 1 -name "*.ipynb" \
        -not -path "*/.ipynb_checkpoints/*" | sort | while read nb; do \
        echo "Running: $nb"; \
        {{python}} -m papermill "$nb" "$nb" -k palacetoolkit --cwd {{examples}}; \
    done

# Step 2: Build Sphinx site (renders notebooks via myst-nb)
nbdocs:
    @echo "Notebook conversion is not required; Sphinx renders .ipynb directly."

# Step 3: Build Sphinx site
docs:
    rm -rf site
    {{python}} -m sphinx -W --keep-going -b html docs site

# Alias used by contributors coming from MkDocs-style workflows
build: docs

# Explicit docs build alias for CI/local parity
docs-build: docs

# All three steps in sequence
docs-full: nbrun nbdocs docs

# Run documentation doctests (executes notebooks via papermill)
doctest: ipykernel
    {{python}} -m pytest -m docs tests/test_docs_notebooks.py

# Local clone bootstrap: install in-repo CPU binary package and then PalaceToolkit.
install-local:
    {{python}} -m pip install -e packages/palacetoolkit-palace-cpu
    {{python}} -m pip install -e ".[plot,docs]"

# Dev server
serve:
    {{python}} -m sphinx_autobuild docs site --host localhost --port 8080 \
        --ignore "site/*" \
        --ignore "jupyter_execute/*" \
        --ignore ".jupyter_cache/*" \
        --re-ignore "docs/examples/postpro/.*" \
        --re-ignore "docs/examples/.*\\.(msh|json|config|conf)$"

# Explicit docs serve alias
docs-serve: serve

# Strip outputs from notebooks before committing
nbclean:
    find {{examples}} -maxdepth 1 -name "*.ipynb" \
        -not -path "*/.ipynb_checkpoints/*" \
        -exec {{venv}}nb-clean clean --remove-empty-cells \
            --preserve-cell-metadata tags -- {} \;
