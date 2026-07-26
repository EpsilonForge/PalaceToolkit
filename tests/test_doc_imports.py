"""Verify that all documented Python imports are valid and exist in the package."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC_GLOBS = [
    "README.md",
    "docs/**/*.md",
    "docs/**/*.ipynb",
    "src/palacetoolkit/**/*.py",
]

# Matches a single-line `from palacetoolkit(.module) import name1, name2`
RE_IMPORT = re.compile(
    r"from\s+palacetoolkit(?:\.(\w+))?\s+import\s+([a-zA-Z_][\w,\s]*(?:\s+as\s+\w+)?)"
)

# Matches bare `palace.` prefix when it looks like a Python module reference
# Excludes quoted strings like "palace.conf" or "palace.mesh" (filenames)
RE_MODULE_REF = re.compile(
    r"""(?<!["'\w])palace\.\w+"""
)

RE_INIT_IMPORT = re.compile(r"from\s+palacetoolkit\.(\w+)\s+import")


def _iter_doc_files() -> Iterator[Path]:
    for pat in DOC_GLOBS:
        yield from sorted(ROOT.glob(pat))


def _extract_imports_from(text: str) -> list[tuple[str, str, str]]:
    """Extract (module_name, names_str, full_match) from import lines."""
    results = []
    for line in text.splitlines():
        m = RE_IMPORT.search(line)
        if m:
            results.append((m.group(1) or "", m.group(2), m.group(0)))
    return results


@pytest.fixture(scope="session")
def palacetoolkit_module():
    return importlib.import_module("palacetoolkit")


def test_all_documented_imports_resolve():
    errors: list[str] = []
    for path in _iter_doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for mod_name, names_part, full_match in _extract_imports_from(text):
            for name in names_part.split(","):
                name = name.strip().split(" as ")[0].strip()
                if not name:
                    continue
                fqname = f"palacetoolkit.{mod_name}.{name}" if mod_name else f"palacetoolkit.{name}"
                try:
                    if mod_name:
                        mod = importlib.import_module(f"palacetoolkit.{mod_name}")
                    else:
                        mod = importlib.import_module("palacetoolkit")
                    if not hasattr(mod, name):
                        errors.append(
                            f"{path}: {full_match!r} -> {name!r} not found in {fqname}"
                        )
                except ImportError as exc:
                    errors.append(f"{path}: cannot import {fqname}: {exc}")
    if errors:
        pytest.fail("\n".join(errors))


def test_no_bare_palace_prefix_in_docs():
    errors: list[str] = []
    for path in _iter_doc_files():
        if path.suffix not in (".md", ".py", ".ipynb"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in RE_MODULE_REF.finditer(text):
            errors.append(f"{path}:{_line_of(text, match.start())}: {match.group()!r} (use palacetoolkit. prefix)")
    if errors:
        pytest.fail("\n".join(errors))


def test_init_py_submodules_exist_on_disk(palacetoolkit_module):
    src_dir = ROOT / "src" / "palacetoolkit"
    errors: list[str] = []
    for match in RE_INIT_IMPORT.finditer((ROOT / "src" / "palacetoolkit" / "__init__.py").read_text()):
        mod_name = match.group(1)
        mod_file = src_dir / f"{mod_name}.py"
        if not mod_file.is_file() and not (src_dir / mod_name / "__init__.py").is_file():
            errors.append(f"__init__.py imports palacetoolkit.{mod_name} but no {mod_file} exists")
    if errors:
        pytest.fail("\n".join(errors))


def test_no_s_plot_anywhere():
    errors: list[str] = []
    for path in _iter_doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if "s_plot" in text:
            errors.append(f"{path}: references non-existent s_plot module")
    if errors:
        pytest.fail("\n".join(errors))


def test_no_analyse_mesh_anywhere():
    errors: list[str] = []
    for path in _iter_doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if "analyse_mesh" in text:
            errors.append(f"{path}: references non-existent analyse_mesh function")
    if errors:
        pytest.fail("\n".join(errors))


def _line_of(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1