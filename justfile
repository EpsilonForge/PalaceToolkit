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

# Step 2: Build MkDocs site (renders notebooks directly via mkdocs-jupyter)
nbdocs:
    @echo "Notebook conversion is not required; MkDocs renders .ipynb directly."

# Step 3: Build MkDocs site
docs:
    {{python}} -m mkdocs build

# All three steps in sequence
docs-full: nbrun nbdocs docs

# Run documentation doctests (executes notebooks via papermill)
doctest: ipykernel
    {{python}} -m pytest -m docs tests/test_docs_notebooks.py

# Dev server
serve:
    {{python}} -m mkdocs serve -a localhost:8080

# Strip outputs from notebooks before committing
nbclean:
    find {{examples}} -maxdepth 1 -name "*.ipynb" \
        -not -path "*/.ipynb_checkpoints/*" \
        -exec {{venv}}nb-clean clean --remove-empty-cells \
            --preserve-cell-metadata tags -- {} \;
