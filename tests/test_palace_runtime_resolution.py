"""Unit tests for Palace runtime resolution.

These use real executable stand-ins rather than a patched ``subprocess`` so the
tests exercise the same launch path that failed in production: a runtime that is
present and executable but aborts on startup, which happens when the packaged
Open MPI runtime is incomplete.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from palacetoolkit import palace_runtime


def _write_script(path: Path, body: str, *, executable: bool = True) -> Path:
    path.write_text(body)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _working_palace(path: Path) -> Path:
    return _write_script(
        path,
        "#!/bin/sh\necho 'Palace version: v0.17.0-272-gb22f654ab'\nexit 0\n",
    )


def _broken_palace(path: Path) -> Path:
    """A launcher that aborts the way an incomplete MPI runtime does."""
    return _write_script(
        path,
        "#!/bin/sh\necho 'opal_shmem_base_select failed' >&2\nexit 1\n",
    )


def test_binary_is_runnable_accepts_working_binary(tmp_path: Path) -> None:
    binary = _working_palace(tmp_path / "palace")
    assert palace_runtime._binary_is_runnable(binary, None) is True


def test_binary_is_runnable_rejects_binary_that_aborts_on_startup(tmp_path: Path) -> None:
    binary = _broken_palace(tmp_path / "palace")
    assert palace_runtime._binary_is_runnable(binary, None) is False


def test_binary_is_runnable_rejects_non_executable_file(tmp_path: Path) -> None:
    binary = _write_script(tmp_path / "palace", "#!/bin/sh\nexit 0\n", executable=False)
    assert palace_runtime._binary_is_runnable(binary, None) is False


def test_binary_is_runnable_rejects_missing_file(tmp_path: Path) -> None:
    assert palace_runtime._binary_is_runnable(tmp_path / "absent", None) is False


def test_binary_is_runnable_caches_per_binary(tmp_path: Path) -> None:
    counter = tmp_path / "launches"
    binary = _write_script(
        tmp_path / "palace",
        f"#!/bin/sh\nprintf x >> {counter}\nexit 0\n",
    )

    assert palace_runtime._binary_is_runnable(binary, None) is True
    assert palace_runtime._binary_is_runnable(binary, None) is True

    assert counter.read_text() == "x", "binary should be launched only once"


def test_resolve_palace_binary_rejects_broken_palace_bin(tmp_path, monkeypatch) -> None:
    """A PALACE_BIN that cannot start must not be handed back as usable."""
    binary = _broken_palace(tmp_path / "palace")

    monkeypatch.setenv("PALACE_BIN", str(binary))
    monkeypatch.setattr(palace_runtime, "_cached_binary", lambda: None)
    monkeypatch.setattr(palace_runtime, "_auto_download_enabled", lambda: False)

    def _no_packaged_runtime(*args, **kwargs):
        raise FileNotFoundError("palacetoolkit_palace_cpu is not installed")

    monkeypatch.setattr(palace_runtime.resources, "path", _no_packaged_runtime)

    assert palace_runtime.resolve_palace_binary() is None


def test_resolve_palace_binary_accepts_working_palace_bin(tmp_path, monkeypatch) -> None:
    binary = _working_palace(tmp_path / "palace")

    monkeypatch.setenv("PALACE_BIN", str(binary))
    monkeypatch.setattr(palace_runtime, "_auto_download_enabled", lambda: False)

    assert palace_runtime.resolve_palace_binary() == binary.resolve()


def test_failed_launch_output_is_reported(tmp_path: Path) -> None:
    """The cause must survive resolution, which otherwise skips the binary silently."""
    binary = _broken_palace(tmp_path / "palace")

    assert palace_runtime._binary_is_runnable(binary, None) is False

    failure = palace_runtime.last_runtime_failure()
    assert failure is not None
    assert str(binary) in failure
    assert "opal_shmem_base_select failed" in failure


def test_no_executable_message_includes_the_launch_failure(tmp_path: Path) -> None:
    from palacetoolkit import simulation

    binary = _broken_palace(tmp_path / "palace")
    palace_runtime._binary_is_runnable(binary, None)

    message = simulation._no_executable_message("Set PALACE_BIN.")
    assert "No Palace executable found." in message
    assert "did not start" in message
    assert "opal_shmem_base_select failed" in message


def _fake_cached_runtime(root: Path, script_body: str) -> Path:
    """Lay out a cached runtime prefix the way install_palace_runtime expects."""
    prefix = root / "palace-cpu-v0.17.0"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "lib").mkdir()
    return _write_script(prefix / "bin" / "palace", script_body)


def test_install_reports_failure_when_cached_runtime_cannot_start(tmp_path, monkeypatch) -> None:
    """Unpacking the files is not proof the runtime works."""
    monkeypatch.setenv("PALACETOOLKIT_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("PALACETOOLKIT_PALACE_CPU_TAG", "0.17.0")
    _fake_cached_runtime(
        tmp_path, "#!/bin/sh\necho 'opal_shmem_base_select failed' >&2\nexit 1\n"
    )

    with pytest.raises(RuntimeError) as excinfo:
        palace_runtime.install_palace_runtime()

    assert "not usable" in str(excinfo.value)
    assert "opal_shmem_base_select failed" in str(excinfo.value)


def test_install_returns_cached_runtime_that_starts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PALACETOOLKIT_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("PALACETOOLKIT_PALACE_CPU_TAG", "0.17.0")
    binary = _fake_cached_runtime(
        tmp_path, "#!/bin/sh\necho 'Palace version: v0.17.0'\nexit 0\n"
    )

    assert palace_runtime.install_palace_runtime() == binary


def test_install_skip_verify_accepts_a_broken_runtime(tmp_path, monkeypatch) -> None:
    """The escape hatch still exists for installing on a machine that will not run it."""
    monkeypatch.setenv("PALACETOOLKIT_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("PALACETOOLKIT_PALACE_CPU_TAG", "0.17.0")
    binary = _fake_cached_runtime(tmp_path, "#!/bin/sh\nexit 1\n")

    assert palace_runtime.install_palace_runtime(verify=False) == binary
