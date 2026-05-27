from __future__ import annotations

import argparse

from palacetoolkit.palace_runtime import install_palace_runtime
from palacetoolkit.simulation import check_palace_runtime


def palace_toolkit_check() -> int:
    """CLI entrypoint to verify Palace runtime availability."""
    try:
        info = check_palace_runtime()
    except Exception as exc:
        print(f"Palace runtime check: FAIL - {exc}")
        return 1

    print("Palace runtime check: OK")
    print(f"Mode: {info['mode']}")
    print(f"Path: {info['path']}")
    print(f"Version: {info['version']}")
    return 0


def palace_toolkit_install_binary() -> int:
    """CLI entrypoint to download/cache the Palace runtime binary."""
    parser = argparse.ArgumentParser(prog="palace-toolkit-install-binary")
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite cached runtime")
    args = parser.parse_args()

    try:
        binary_path = install_palace_runtime(force=args.force)
    except Exception as exc:
        print(f"Palace runtime install: FAIL - {exc}")
        return 1

    print("Palace runtime install: OK")
    print(f"Binary: {binary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(palace_toolkit_check())
