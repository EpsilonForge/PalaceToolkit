from __future__ import annotations

import os
from contextlib import suppress
from importlib import resources
from pathlib import Path


def resolve_palace_binary() -> Path | None:
    """Return a local Palace executable path when available.

    Resolution order:
    1. PALACE_BIN environment variable
    2. Prebuilt CPU package data (palacetoolkit_palace_cpu/bin/palace)
    """
    env_bin = os.environ.get("PALACE_BIN", "").strip()
    if env_bin:
        candidate = Path(env_bin).expanduser().resolve()
        if candidate.is_file():
            return candidate

    with suppress(ModuleNotFoundError, FileNotFoundError):
        with resources.path("palacetoolkit_palace_cpu", "__init__.py") as init_py:
            candidate = init_py.parent / "bin" / "palace"
            if candidate.is_file():
                return candidate
    return None


def resolve_palace_library_dir() -> Path | None:
    """Return packaged Palace library directory when available."""
    with suppress(ModuleNotFoundError, FileNotFoundError):
        with resources.path("palacetoolkit_palace_cpu", "__init__.py") as init_py:
            candidate = init_py.parent / "lib"
            if candidate.is_dir():
                return candidate
    return None
