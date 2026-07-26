"""Unit tests for the postpro module."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import matplotlib
import matplotlib.figure
import matplotlib.pyplot as plt
import pytest

from palacetoolkit.postpro import s_params


@pytest.fixture(autouse=True)
def _noninteractive_backend() -> Generator[None, None, None]:
    backend = matplotlib.get_backend()
    matplotlib.use("Agg")
    yield
    plt.close("all")
    matplotlib.use(backend)


@pytest.fixture
def port_s_csv(tmp_path: Path) -> Path:
    content = (
        "        f (GHz),             |S[1][1]| (dB),        arg(S[1][1]) (deg.),"
        "             |S[2][1]| (dB),        arg(S[2][1]) (deg.)\n"
        " 1.00000000e+10,        -3.00000000e+01,        1.80000000e+02,"
        " -6.00000000e+01,        9.00000000e+01\n"
        " 1.10000000e+10,        -2.50000000e+01,        1.75000000e+02,"
        " -5.50000000e+01,        8.50000000e+01\n"
    )
    csv = tmp_path / "port-S.csv"
    csv.write_text(content)
    return csv


@pytest.fixture
def port_s_csv_single_port(tmp_path: Path) -> Path:
    content = (
        "        f (GHz),             |S[1][1]| (dB),        arg(S[1][1]) (deg.)\n"
        " 1.00000000e+10,        -3.00000000e+01,        1.80000000e+02\n"
    )
    csv = tmp_path / "port-S-single.csv"
    csv.write_text(content)
    return csv


def test_s_params_returns_figure_axes_tuple(port_s_csv: Path):
    result = s_params(str(port_s_csv))
    assert isinstance(result, tuple) and len(result) == 2
    fig, ax = result
    assert isinstance(fig, matplotlib.figure.Figure)
    assert isinstance(ax, matplotlib.axes.Axes)


def test_s_params_plots_two_traces_for_dual_port(port_s_csv: Path):
    fig, ax = s_params(str(port_s_csv))
    assert len(ax.lines) == 2
    labels = [l.get_label() for l in ax.lines]
    assert "|S11| (dB)" in labels
    assert "|S21| (dB)" in labels


def test_s_params_plots_one_trace_for_single_port(port_s_csv_single_port: Path):
    fig, ax = s_params(str(port_s_csv_single_port))
    assert len(ax.lines) == 1
    assert ax.lines[0].get_label() == "|S11| (dB)"


def test_s_params_does_not_call_plt_show(port_s_csv: Path, monkeypatch):
    calls = []
    monkeypatch.setattr(plt, "show", lambda: calls.append("show"))
    s_params(str(port_s_csv))
    assert calls == [], "s_params should not call plt.show()"


def test_s_params_uses_english_labels(port_s_csv: Path):
    fig, ax = s_params(str(port_s_csv))
    assert ax.get_xlabel() == "Frequency (GHz)"
    assert "Magnitude" in ax.get_ylabel()
    assert "S-parameter" in ax.get_title()