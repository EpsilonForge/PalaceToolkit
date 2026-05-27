from __future__ import annotations

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


if __name__ == "__main__":
    raise SystemExit(palace_toolkit_check())
