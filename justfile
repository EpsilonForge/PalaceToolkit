venv    := ".venv/bin/"
python  := venv + "python"
gallery := "docs/gallery"
nbsdir  := gallery + "/nbs"

# Register ipykernel (one-time setup)
ipykernel:
    {{python}} -m ipykernel install --user --name palace-course --display-name "PalaceToolkit"

# Step 1: Execute notebooks in-place with papermill
nbrun: ipykernel
    mkdir -p {{gallery}}/img
    export DOCS_BUILD=1 && find {{gallery}} -maxdepth 1 -name "*.ipynb" \
        -not -path "*/.ipynb_checkpoints/*" | sort | while read nb; do \
        echo "Running: $nb"; \
        {{python}} -m papermill "$nb" "$nb" -k palace-course --cwd {{gallery}}; \
    done

# Step 2: Convert executed notebooks → Markdown (strip remove_cell tags)
nbdocs:
    mkdir -p {{nbsdir}}
    find {{gallery}} -maxdepth 1 -name "*.ipynb" \
        -not -path "*/.ipynb_checkpoints/*" \
        -exec {{python}} -m jupyter nbconvert --to markdown --embed-images \
            {} --output-dir {{nbsdir}} \
            --TagRemovePreprocessor.enabled=True \
            --TagRemovePreprocessor.remove_cell_tags='["remove_cell"]' \;

# Step 3: Build MkDocs site
docs:
    {{python}} -m mkdocs build

# All three steps in sequence
docs-full: nbrun nbdocs docs

# Dev server (assumes nbdocs already ran)
serve:
    {{python}} -m mkdocs serve -a localhost:8080

# Strip outputs from notebooks before committing
nbclean:
    find {{gallery}} -maxdepth 1 -name "*.ipynb" \
        -not -path "*/.ipynb_checkpoints/*" \
        -exec {{venv}}nb-clean clean --remove-empty-cells \
            --preserve-cell-metadata tags -- {} \;
