from __future__ import annotations

import os
import platform
import shutil
import stat
import tempfile
import json
import subprocess
from contextlib import suppress
from importlib import resources
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile


_DEFAULT_BINARY_TAG = "0.18.0"
_AUTO_DOWNLOAD_ENV = "PALACETOOLKIT_AUTO_DOWNLOAD_BINARY"
_TAG_ENV = "PALACETOOLKIT_PALACE_CPU_TAG"
_CACHE_ENV = "PALACETOOLKIT_RUNTIME_DIR"


def _is_linux_x86_64() -> bool:
    return platform.system() == "Linux" and platform.machine() == "x86_64"


def _runtime_cache_dir() -> Path:
    root = os.environ.get(_CACHE_ENV, "").strip()
    if root:
        return Path(root).expanduser().resolve()
    return (Path.home() / ".cache" / "palacetoolkit" / "runtime").resolve()


def _binary_tag() -> str:
    return os.environ.get(_TAG_ENV, _DEFAULT_BINARY_TAG).strip() or _DEFAULT_BINARY_TAG


def _binary_wheel_url(tag: str) -> str:
    return (
        "https://github.com/EpsilonForge/PalaceToolkit/releases/download/"
        f"palace-cpu-v{tag}/"
        f"palacetoolkit_palace_cpu-{tag}-py3-none-linux_x86_64.whl"
    )


def _binary_wheel_url_from_release(tag: str, timeout: float) -> str | None:
    api_url = (
        "https://api.github.com/repos/EpsilonForge/PalaceToolkit/releases/tags/"
        f"palace-cpu-v{tag}"
    )
    request = Request(api_url, headers={"Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    assets = payload.get("assets", [])
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.endswith("linux_x86_64.whl") and "palacetoolkit_palace_cpu-" in name:
            url = str(asset.get("browser_download_url", ""))
            if url:
                return url
    return None


def _cached_runtime_prefix(tag: str | None = None) -> Path:
    resolved_tag = tag or _binary_tag()
    return _runtime_cache_dir() / f"palace-cpu-v{resolved_tag}"


def _set_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_palace_runtime(
    force: bool = False,
    timeout: float = 180.0,
    verify: bool = True,
) -> Path:
    """Download and cache the prebuilt Palace CPU runtime.

    Args:
        force: Re-download and overwrite an existing cached runtime.
        timeout: Network timeout for the wheel download, in seconds.
        verify: Launch the installed runtime before reporting success.  A
            runtime whose bundled MPI is incomplete unpacks perfectly and then
            fails at the user's first simulation, so "the files are in place" is
            not the same thing as "the install worked".

    Returns:
        Path to the cached ``palace`` launcher executable.

    Raises:
        RuntimeError: If the runtime cannot be installed, or if ``verify`` is set
            and the installed runtime does not start.
    """
    if not _is_linux_x86_64():
        raise RuntimeError("Prebuilt runtime download is only supported on Linux x86_64")

    tag = _binary_tag()
    prefix = _cached_runtime_prefix(tag)
    bin_palace = prefix / "bin" / "palace"
    lib_dir = prefix / "lib"
    if not force and bin_palace.is_file() and lib_dir.is_dir():
        if verify:
            _verify_runtime(bin_palace, lib_dir)
        return bin_palace

    prefix.mkdir(parents=True, exist_ok=True)
    downloads = _runtime_cache_dir() / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    wheel_name = f"palacetoolkit_palace_cpu-{tag}-py3-none-linux_x86_64.whl"
    wheel_path = downloads / wheel_name

    if force or not wheel_path.is_file():
        url = _binary_wheel_url(tag)
        with suppress(Exception):
            discovered = _binary_wheel_url_from_release(tag, timeout=timeout)
            if discovered:
                url = discovered
        with urlopen(url, timeout=timeout) as response:
            wheel_path.write_bytes(response.read())

    with tempfile.TemporaryDirectory(prefix="palace-runtime-", dir=_runtime_cache_dir()) as tmp:
        tmp_path = Path(tmp)
        with ZipFile(wheel_path, "r") as wheel_zip:
            wheel_zip.extractall(tmp_path)

        payload_root = tmp_path / "palacetoolkit_palace_cpu"
        if not payload_root.is_dir():
            raise RuntimeError("Downloaded wheel does not contain palacetoolkit_palace_cpu payload")

        bin_src = payload_root / "bin"
        lib_src = payload_root / "lib"
        if not bin_src.is_dir() or not lib_src.is_dir():
            raise RuntimeError("Downloaded wheel is missing expected bin/lib runtime directories")

        if prefix.exists():
            shutil.rmtree(prefix)
        prefix.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bin_src, prefix / "bin")
        shutil.copytree(lib_src, prefix / "lib")

        # Open MPI help text, when the wheel bundles its own MPI runtime.
        share_src = payload_root / "share"
        if share_src.is_dir():
            shutil.copytree(share_src, prefix / "share")

    if not bin_palace.is_file():
        raise RuntimeError("Cached runtime install did not produce bin/palace")
    # Zip extraction drops the executable bit, so restore it for everything in
    # bin/: the launcher, the Palace binary, and the bundled MPI runtime
    # (orted/orterun) that Open MPI execs to start even a single rank.
    for entry in sorted((prefix / "bin").iterdir()):
        if entry.is_file():
            _set_executable(entry)
    if verify:
        _verify_runtime(bin_palace, prefix / "lib")
    return bin_palace


def _verify_runtime(binary: Path, lib_dir: Path | None) -> None:
    """Raise unless ``binary`` actually starts, quoting why it did not."""
    if _binary_is_runnable(binary, lib_dir):
        return
    detail = last_runtime_failure() or f"{binary} did not start"
    raise RuntimeError(f"Installed Palace runtime is not usable: {detail}")


def _cached_binary() -> Path | None:
    candidate = _cached_runtime_prefix() / "bin" / "palace"
    if candidate.is_file():
        return candidate
    return None


def _cached_library_dir() -> Path | None:
    candidate = _cached_runtime_prefix() / "lib"
    if candidate.is_dir():
        return candidate
    return None


_RUNNABLE_CACHE: dict[tuple[str, int, int], bool] = {}
_LAST_RUNTIME_FAILURE: str | None = None


def _binary_is_runnable(binary: Path, lib_dir: Path | None, timeout: float = 15.0) -> bool:
    """Return True when ``binary`` actually starts, not merely when it exists.

    A Palace runtime can be present and executable yet unable to run at all --
    most often because its bundled MPI runtime is incomplete, which aborts the
    process during MPI_Init long before Palace itself is reached.  Checking only
    the file mode reports such a runtime as usable, so resolution hands back a
    binary that fails at the user's first simulation instead of falling through
    to the next candidate.  Run ``--version`` and require a clean exit.

    The result is cached per binary (keyed by path, mtime and size) so repeated
    resolution within a process does not pay for the launch each time.
    """
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return False

    try:
        stamp = binary.stat()
    except OSError:
        return False
    key = (str(binary), stamp.st_mtime_ns, stamp.st_size)
    cached = _RUNNABLE_CACHE.get(key)
    if cached is not None:
        return cached

    run_env = os.environ.copy()
    if lib_dir is not None and lib_dir.is_dir():
        prior = run_env.get("LD_LIBRARY_PATH", "")
        run_env["LD_LIBRARY_PATH"] = f"{lib_dir}:{prior}" if prior else str(lib_dir)

    global _LAST_RUNTIME_FAILURE
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
            # The launcher writes a node file into the working directory under a
            # batch scheduler; keep that out of the caller's directory.
            cwd=tempfile.gettempdir(),
        )
        runnable = result.returncode == 0
        if not runnable:
            _LAST_RUNTIME_FAILURE = _summarise_failure(
                binary, result.returncode, result.stderr or result.stdout or ""
            )
    except (OSError, subprocess.SubprocessError) as exc:
        runnable = False
        _LAST_RUNTIME_FAILURE = f"{binary} could not be launched: {exc}"

    _RUNNABLE_CACHE[key] = runnable
    return runnable


_FAILURE_OUTPUT_LIMIT = 1500


def _summarise_failure(binary: Path, returncode: int, output: str) -> str:
    """Record a failed launch, keeping the output that names the cause.

    Open MPI wraps its diagnostics in banners of generic prose with the decisive
    line ("opal_shmem_base_select failed") buried among them, and no cheap
    heuristic reliably picks it out -- so keep the whole thing, minus the rules,
    and truncate only if it is unreasonably long.
    """
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    lines = [line for line in lines if set(line.strip()) != {"-"}]
    detail = "\n".join(lines) if lines else "(no output)"
    if len(detail) > _FAILURE_OUTPUT_LIMIT:
        detail = detail[:_FAILURE_OUTPUT_LIMIT] + "\n... (output truncated)"
    return f"{binary} exited with code {returncode}:\n{detail}"


def last_runtime_failure() -> str | None:
    """Return why the most recent runtime candidate was rejected, if any.

    Resolution silently skips a Palace binary that cannot start, so callers that
    end up with no runtime at all use this to report the underlying cause rather
    than a bare "no executable found".
    """
    return _LAST_RUNTIME_FAILURE


def _auto_download_enabled() -> bool:
    raw = os.environ.get(_AUTO_DOWNLOAD_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def resolve_palace_binary() -> Path | None:
    """Return a local Palace executable path when available.

    Resolution order:
    1. PALACE_BIN environment variable
    2. Prebuilt CPU package data (palacetoolkit_palace_cpu/bin/palace)
    3. Cached runtime downloaded from GitHub Releases (Linux x86_64)
    """
    env_bin = os.environ.get("PALACE_BIN", "").strip()
    if env_bin:
        candidate = Path(env_bin).expanduser().resolve()
        if candidate.is_file() and _binary_is_runnable(candidate, None):
            return candidate

    with suppress(ModuleNotFoundError, FileNotFoundError):
        with resources.path("palacetoolkit_palace_cpu", "__init__.py") as init_py:
            candidate = init_py.parent / "bin" / "palace"
            lib_dir = init_py.parent / "lib"
            if candidate.is_file() and _binary_is_runnable(candidate, lib_dir):
                return candidate

    cached = _cached_binary()
    if cached is not None and _binary_is_runnable(cached, _cached_library_dir()):
        return cached

    if _is_linux_x86_64() and _auto_download_enabled():
        with suppress(Exception):
            downloaded = install_palace_runtime(force=False)
            if _binary_is_runnable(downloaded, _cached_library_dir()):
                return downloaded
    return None


def resolve_palace_library_dir() -> Path | None:
    """Return packaged Palace library directory when available."""
    with suppress(ModuleNotFoundError, FileNotFoundError):
        with resources.path("palacetoolkit_palace_cpu", "__init__.py") as init_py:
            candidate = init_py.parent / "lib"
            if candidate.is_dir():
                return candidate

    cached = _cached_library_dir()
    if cached is not None:
        return cached
    return None
