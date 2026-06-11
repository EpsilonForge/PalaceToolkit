"""Doctest-style smoke test for documentation build integrity."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.docs
def test_docs_build_has_no_errors() -> None:
    """Build docs in strict mode and fail with captured logs on error."""
    env = os.environ.copy()
    env["DOCS_BUILD"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "--keep-going",
            "-b",
            "html",
            "docs",
            "site",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = "\n".join([result.stdout.strip(), result.stderr.strip()]).strip()
        pytest.fail(
            "sphinx-build failed in strict mode.\n"
            f"exit_code={result.returncode}\n"
            f"{output}"
        )