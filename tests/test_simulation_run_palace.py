"""Unit tests for Palace runtime launch behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from palacetoolkit import simulation


def test_run_palace_uses_resolved_executable(monkeypatch, tmp_path: Path) -> None:
    """run_palace should invoke the resolved executable when available."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")

    fake_exec = tmp_path / "palace"
    calls: list[dict] = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(simulation, "_PALACE_EXEC_OVERRIDE", None)
    monkeypatch.setattr(simulation, "_PALACE_SIF_OVERRIDE", None)
    monkeypatch.setattr(simulation, "resolve_palace_binary", lambda: fake_exec)
    monkeypatch.setattr(simulation, "resolve_palace_library_dir", lambda: None)
    monkeypatch.setattr(simulation.subprocess, "run", fake_run)

    simulation.run_palace(config_file=config_file, num_procs=1)

    assert len(calls) == 1
    launched = calls[0]["cmd"]
    assert launched[0] == str(fake_exec)
    assert launched[1] == str(config_file.resolve())


def test_get_palace_executable_returns_resolved(monkeypatch, tmp_path: Path) -> None:
    """get_palace_executable should return an already resolved runtime."""
    fake_exec = tmp_path / "palace"
    monkeypatch.setattr(simulation, "_PALACE_EXEC_OVERRIDE", None)
    monkeypatch.setattr(simulation, "resolve_palace_binary", lambda: fake_exec)

    called = {"install": False}

    def fake_install(force=False):
        called["install"] = True
        return fake_exec

    monkeypatch.setattr(simulation, "install_palace_runtime", fake_install)

    result = simulation.get_palace_executable()

    assert result == fake_exec
    assert called["install"] is False


def test_get_palace_executable_installs_when_missing(monkeypatch, tmp_path: Path) -> None:
    """get_palace_executable should install runtime when none is resolved."""
    installed_exec = tmp_path / "palace-installed"
    monkeypatch.setattr(simulation, "_PALACE_EXEC_OVERRIDE", None)
    monkeypatch.setattr(simulation, "resolve_palace_binary", lambda: None)

    calls = []

    def fake_install(force=False):
        calls.append(force)
        return installed_exec

    monkeypatch.setattr(simulation, "install_palace_runtime", fake_install)

    result = simulation.get_palace_executable(install_if_missing=True, force_install=True)

    assert result == installed_exec
    assert calls == [True]


def test_get_palace_runtime_env_includes_inferred_lib_dir(monkeypatch, tmp_path: Path) -> None:
    """Runtime env helper should inject sibling lib dir for bundled runtime."""
    runtime_bin = tmp_path / "runtime" / "bin"
    runtime_lib = tmp_path / "runtime" / "lib"
    runtime_bin.mkdir(parents=True)
    runtime_lib.mkdir(parents=True)
    fake_exec = runtime_bin / "palace"
    fake_exec.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/lib")
    env = simulation.get_palace_runtime_env(palace_executable=fake_exec)

    assert env["LD_LIBRARY_PATH"].startswith(str(runtime_lib))
    assert env["LD_LIBRARY_PATH"].endswith(":/usr/lib")


def test_get_palace_runtime_returns_path_and_env(monkeypatch, tmp_path: Path) -> None:
    """Combined helper should return both executable path and run environment."""
    fake_exec = tmp_path / "palace"
    fake_env = {"LD_LIBRARY_PATH": "/tmp/lib"}

    monkeypatch.setattr(simulation, "get_palace_executable", lambda **_: fake_exec)
    monkeypatch.setattr(simulation, "get_palace_runtime_env", lambda **_: fake_env)

    result_exec, result_env = simulation.get_palace_runtime()

    assert result_exec == fake_exec
    assert result_env == fake_env
