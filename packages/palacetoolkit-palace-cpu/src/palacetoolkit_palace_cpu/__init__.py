"""Prebuilt Palace CPU binary package."""

from pathlib import Path


def palace_binary_path() -> Path:
    """Return the packaged Palace executable path."""
    return Path(__file__).resolve().parent / "bin" / "palace"


def palace_library_path() -> Path:
    """Return the packaged Palace shared library directory path."""
    return Path(__file__).resolve().parent / "lib"
