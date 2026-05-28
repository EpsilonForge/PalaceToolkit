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