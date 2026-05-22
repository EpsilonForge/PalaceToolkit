"""Documentation doctests for notebook examples.

These tests execute notebooks under docs/examples with papermill to verify
that user-facing documentation runs without execution errors.
"""

from __future__ import annotations

import os
from pathlib import Path

import papermill as pm
import pytest
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "docs" / "examples"


def _discover_notebooks() -> list[Path]:
    notebook_glob = os.environ.get("PALACETOOLKIT_NOTEBOOK_GLOB", "*.ipynb")
    notebooks = sorted(EXAMPLES_DIR.glob(notebook_glob))
    limit = os.environ.get("PALACETOOLKIT_NOTEBOOK_LIMIT")
    if limit:
        notebooks = notebooks[: int(limit)]
    return notebooks


NOTEBOOKS = _discover_notebooks()


@pytest.fixture(scope="session")
def docs_kernel_name() -> str:
    return os.environ.get("PALACETOOLKIT_TEST_KERNEL", "palacetoolkit")


@pytest.fixture(scope="session", autouse=True)
def ensure_docs_kernel(docs_kernel_name: str) -> None:
    available = set(KernelSpecManager().find_kernel_specs().keys())
    assert docs_kernel_name in available, (
        f"Kernel '{docs_kernel_name}' is not installed. "
        "Run `just ipykernel` first."
    )


@pytest.mark.docs
@pytest.mark.parametrize("notebook_path", NOTEBOOKS, ids=lambda p: p.stem)
def test_docs_notebook_executes(
    notebook_path: Path,
    tmp_path: Path,
    docs_kernel_name: str,
) -> None:
    output_path = tmp_path / notebook_path.name

    old_docs_build = os.environ.get("DOCS_BUILD")
    os.environ["DOCS_BUILD"] = "1"
    try:
        pm.execute_notebook(
            str(notebook_path),
            str(output_path),
            kernel_name=docs_kernel_name,
            cwd=str(EXAMPLES_DIR),
            progress_bar=False,
            log_output=False,
            report_mode=True,
            request_save_on_cell_execute=False,
        )
    finally:
        if old_docs_build is None:
            os.environ.pop("DOCS_BUILD", None)
        else:
            os.environ["DOCS_BUILD"] = old_docs_build
