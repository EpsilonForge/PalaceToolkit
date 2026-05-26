from __future__ import annotations

import os
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


def _wants_palace_build() -> bool:
    raw = os.environ.get("PALACETOOLKIT_BUILD_PALACE", "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _run_palace_build() -> None:
    tools_dir = Path(__file__).parent / "tools"
    script = tools_dir / "build_palace.py"
    ns: dict[str, object] = {}
    with script.open("r", encoding="utf-8") as f:
        code = compile(f.read(), str(script), "exec")
    exec(code, ns)
    ns["ensure_palace_cached_build"]()


class build_py(_build_py):
    def run(self) -> None:
        if _wants_palace_build():
            self.announce("PalaceToolkit: opt-in Palace source build requested", level=3)
            _run_palace_build()
        else:
            self.announce("PalaceToolkit: skipping Palace source build (default)", level=3)
        super().run()


cmdclass: dict[str, type] = {"build_py": build_py}

try:
    from setuptools.command.editable_wheel import editable_wheel as _editable_wheel

    class editable_wheel(_editable_wheel):
        def run(self) -> None:
            if _wants_palace_build():
                self.announce("PalaceToolkit: opt-in Palace source build requested", level=3)
                _run_palace_build()
            else:
                self.announce("PalaceToolkit: skipping Palace source build (default)", level=3)
            super().run()

    cmdclass["editable_wheel"] = editable_wheel
except Exception:
    # Older setuptools versions may not expose editable_wheel.
    pass

setup(cmdclass=cmdclass)
