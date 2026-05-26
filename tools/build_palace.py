from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class PalaceBuildError(RuntimeError):
    """Raised when Palace cannot be built or validated."""


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _run_capture(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise PalaceBuildError(
            f"Required build tool '{name}' not found in PATH. "
            "Install build dependencies from docs/getting-started/compile_instructions_ubuntu.md."
        )


def _truthy_env(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PalaceCachePaths:
    source_dir: Path
    source_key: str
    install_dir: Path
    build_dir: Path
    marker_file: Path
    palace_bin: Path


def _resolve_source_dir(cache_root: Path) -> tuple[Path, str]:
    explicit = os.environ.get("PALACETOOLKIT_PALACE_SOURCE", "").strip()
    if explicit:
        source_dir = Path(explicit).expanduser().resolve()
        if not (source_dir / "CMakeLists.txt").is_file():
            raise PalaceBuildError(
                f"PALACETOOLKIT_PALACE_SOURCE does not look like a Palace checkout: {source_dir}"
            )
        commit = _submodule_commit(source_dir)[:12]
        return source_dir, f"custom-{commit}"

    if not _truthy_env("PALACETOOLKIT_CLONE_NIGHTLY", "0"):
        raise PalaceBuildError(
            "No Palace source directory configured. Set PALACETOOLKIT_PALACE_SOURCE to an existing "
            "checkout or set PALACETOOLKIT_CLONE_NIGHTLY=1 for an on-demand clone."
        )

    nightly_dir = cache_root / "_sources" / "palace-nightly"
    nightly_dir.parent.mkdir(parents=True, exist_ok=True)
    if not nightly_dir.exists():
        _run(["git", "clone", "--depth", "1", "https://github.com/awslabs/palace.git", str(nightly_dir)])
    else:
        _run(["git", "fetch", "--depth", "1", "origin", "HEAD"], cwd=nightly_dir)
        _run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=nightly_dir)

    commit = _submodule_commit(nightly_dir)[:12]
    return nightly_dir, f"nightly-{commit}"


def _submodule_commit(source_dir: Path) -> str:
    try:
        return _run_capture(["git", "rev-parse", "HEAD"], cwd=source_dir)
    except Exception as exc:
        raise PalaceBuildError("Unable to resolve Palace submodule commit") from exc


def _cache_paths() -> PalaceCachePaths:
    cache_root = Path(
        os.environ.get("PALACETOOLKIT_PALACE_CACHE", str(Path.home() / ".cache" / "palacetoolkit" / "palace"))
    ).expanduser()
    source_dir, source_key = _resolve_source_dir(cache_root)

    flags_fingerprint = _options_fingerprint()
    platform_key = f"{platform.system().lower()}-{platform.machine().lower()}"
    key = f"{source_key}-{platform_key}-{flags_fingerprint}"

    install_dir = cache_root / key
    build_dir = install_dir / "build"
    marker_file = install_dir / ".build-meta.json"
    palace_bin = build_dir / "bin" / "palace"
    return PalaceCachePaths(
        source_dir=source_dir,
        source_key=source_key,
        install_dir=install_dir,
        build_dir=build_dir,
        marker_file=marker_file,
        palace_bin=palace_bin,
    )


def _env_bool_cmake(name: str, default: str) -> str:
    return "ON" if _truthy_env(name, default) else "OFF"


def _cmake_options() -> list[str]:
    return [
        "-DBUILD_SHARED_LIBS:BOOL=ON",
        "-DPALACE_WITH_64BIT_INT:BOOL=OFF",
        f"-DPALACE_WITH_OPENMP:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_OPENMP', '1')}",
        f"-DPALACE_WITH_CUDA:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_CUDA', '0')}",
        f"-DPALACE_WITH_HIP:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_HIP', '0')}",
        f"-DPALACE_WITH_SUPERLU:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_SUPERLU', '1')}",
        f"-DPALACE_WITH_STRUMPACK:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_STRUMPACK', '1')}",
        f"-DPALACE_WITH_MUMPS:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_MUMPS', '1')}",
        f"-DPALACE_WITH_SLEPC:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_SLEPC', '1')}",
        f"-DPALACE_WITH_ARPACK:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_ARPACK', '1')}",
        f"-DPALACE_WITH_LIBXSMM:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_LIBXSMM', '1')}",
        f"-DPALACE_WITH_MAGMA:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_MAGMA', '0')}",
        f"-DPALACE_WITH_GSLIB:BOOL={_env_bool_cmake('PALACETOOLKIT_PALACE_WITH_GSLIB', '1')}",
    ]


def _options_fingerprint() -> str:
    options = _cmake_options()
    extra = os.environ.get("PALACETOOLKIT_PALACE_EXTRA_CMAKE_ARGS", "").strip()
    payload = "\n".join(options + [extra])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def _cmake_configure(paths: PalaceCachePaths) -> None:
    paths.build_dir.mkdir(parents=True, exist_ok=True)

    cxx_flags = "-O3 -ffp-contract=fast -funroll-loops -march=native"
    c_flags = "-O3 -ffp-contract=fast -funroll-loops -march=native"
    fortran_flags = "-O3 -ffp-contract=fast -funroll-loops -march=native"

    cmd = [
        "cmake",
        str(paths.source_dir),
        f"-DCMAKE_INSTALL_PREFIX={paths.install_dir}",
        "-DCMAKE_CXX_COMPILER=g++",
        f"-DCMAKE_CXX_FLAGS={cxx_flags}",
        "-DCMAKE_C_COMPILER=gcc",
        f"-DCMAKE_C_FLAGS={c_flags}",
        "-DCMAKE_Fortran_COMPILER=gfortran",
        f"-DCMAKE_Fortran_FLAGS={fortran_flags}",
    ]
    cmd.extend(_cmake_options())

    extra_args = os.environ.get("PALACETOOLKIT_PALACE_EXTRA_CMAKE_ARGS", "").strip()
    if extra_args:
        cmd.extend(extra_args.split())
    _run(cmd, cwd=paths.build_dir)


def _cmake_build(paths: PalaceCachePaths) -> None:
    jobs = os.environ.get("PALACETOOLKIT_PALACE_JOBS")
    if jobs and jobs.isdigit() and int(jobs) > 0:
        build_jobs = int(jobs)
    else:
        build_jobs = max((os.cpu_count() or 2) // 2, 1)
    _run(["cmake", "--build", ".", "--parallel", str(build_jobs)], cwd=paths.build_dir)


def _is_cached(paths: PalaceCachePaths) -> bool:
    if not paths.palace_bin.is_file() or not paths.marker_file.is_file():
        return False
    try:
        with paths.marker_file.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return False
    return bool(meta.get("ok", False))


def _write_marker(paths: PalaceCachePaths) -> None:
    payload = {
        "ok": True,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_key": paths.source_key,
        "options_fingerprint": _options_fingerprint(),
        "palace_binary": str(paths.palace_bin),
    }
    paths.install_dir.mkdir(parents=True, exist_ok=True)
    with paths.marker_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def ensure_palace_cached_build() -> None:
    for tool in ("git", "cmake", "make", "gcc", "g++", "gfortran"):
        _require_tool(tool)

    paths = _cache_paths()
    force = _truthy_env("PALACETOOLKIT_FORCE_PALACE_REBUILD", "0")

    lock_file = paths.install_dir / ".build.lock"
    paths.install_dir.mkdir(parents=True, exist_ok=True)

    with lock_file.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

        if force and paths.build_dir.exists():
            shutil.rmtree(paths.build_dir, ignore_errors=True)
            if paths.marker_file.exists():
                paths.marker_file.unlink()

        if _is_cached(paths):
            print(f"PalaceToolkit: reusing cached Palace build at {paths.palace_bin}")
            return

        print(
            f"PalaceToolkit: compiling Palace from {paths.source_dir} into cache directory {paths.install_dir}"
        )
        _cmake_configure(paths)
        _cmake_build(paths)

        if not paths.palace_bin.is_file():
            raise PalaceBuildError(
                f"Palace build completed but expected binary was not found at {paths.palace_bin}"
            )
        _write_marker(paths)
        print(f"PalaceToolkit: Palace build cached at {paths.palace_bin}")


if __name__ == "__main__":
    ensure_palace_cached_build()
