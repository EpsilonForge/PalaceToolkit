"""Prebuilt Palace CPU binary package."""

import sys
from pathlib import Path


def palace_binary_path() -> Path:
    """Return the packaged Palace executable path."""
    if sys.platform == "win32":
        name = "palace-x86_64.exe"
    else:
        name = "palace"
    return Path(__file__).resolve().parent / "bin" / name


def palace_library_path() -> Path:
    """Return the packaged Palace shared library directory path."""
    return Path(__file__).resolve().parent / "lib"
