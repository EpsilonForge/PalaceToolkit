"""
Palace-backed 2D Waveguide Mode Solver.

Computes propagation constants and mode fields by calling Palace's native
BoundaryMode solver.  Replaces the previous MFEM-based implementation
(now extracted to the standalone ``modeforge`` package).

The solver generates a Palace JSON config, runs the Palace binary, and
parses the output CSVs (``mode-kn.csv``, ``mode-Z.csv``, ``mode-V.csv``).
"""

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from palacetoolkit.simulation import run_palace


@dataclass
class ModeMetrics:
    """Propagation metrics for a single mode."""

    k_n: complex
    """Propagation constant (1/m)."""

    n_eff: complex
    """Effective index."""

    eta_eff: complex
    """Effective impedance (Ohms)."""


class WaveguideModeSolver:
    """2D cross-section waveguide mode solver backed by the Palace binary.

    Generates a Palace ``BoundaryMode`` configuration, runs the solver,
    and parses the output.

    Parameters
    ----------
    mesh_file : str
        Path to a 2D Gmsh ``.msh`` file with physical groups for
        volumes (dielectric domains) and boundaries (PEC, absorbing).
    order : int
        Polynomial order for the finite element spaces (``Solver.Order``).
    pec_bdr : list of int or 'all'
        Boundary physical-group tags that are PEC.  Pass ``'all'`` to
        treat every boundary as PEC.
    materials : list of dict
        Material definitions for each volumetric physical group.  Each
        entry::

            {"attrs": [tag, ...], "eps_r": float, "mu_r": float, "loss_tan": float}

        ``eps_r`` defaults to 1.0, ``mu_r`` to 1.0, ``loss_tan`` to 0.0.
    omega : float
        Normalized free-space wavenumber :math:`k_0 = \\omega / c` in the
        same (natural) length units as the mesh coordinates, with ``c = 1``.
        The Palace config ``BoundaryMode.Freq`` is derived from it as
        ``Freq [GHz] = omega * c_0 / (2 * pi * L0 * 1e9)`` so that the
        normalized eigenvalue problem matches the SI one Palace solves.
    L0 : float
        Model length scale in meters (``Model.L0``).  Defaults to ``1.0``
        for meshes whose coordinates are already in meters.
    """

    _C0_SI = 3.0e8  # speed of light in m/s

    def __init__(
        self,
        mesh_file: str,
        order: int = 2,
        pec_bdr: list[int] | str | None = None,
        materials: list[dict[str, Any]] | None = None,
        omega: float = 2 * math.pi * 10e9,
        L0: float = 1.0,
    ):
        self.mesh_file = str(Path(mesh_file).expanduser().resolve())
        self.order = order
        self.omega = omega
        self.L0 = float(L0)
        self.pec_bdr: list[int] = []
        if pec_bdr == "all":
            try:
                import meshio

                m = meshio.read(self.mesh_file)
                all_bdr = set()
                for cell_block in m.cells:
                    if cell_block.type in ("triangle", "quad", "line", "polygon"):
                        continue
                for key in m.cell_data_dict.get("gmsh:physical", {}):
                    all_bdr.update(m.cell_data_dict["gmsh:physical"][key])
                self.pec_bdr = sorted(all_bdr)
            except Exception:
                self.pec_bdr = []
        elif pec_bdr is not None:
            self.pec_bdr = list(pec_bdr)
        self.materials = materials or []

    def solve(
        self,
        num_modes: int = 5,
        mode_idx: int | None = None,
        target: float = 0.0,
        output_dir: str | Path | None = None,
        work_dir: str | Path | None = None,
        num_procs: int = 4,
        save: int = 0,
    ) -> dict[int, ModeMetrics]:
        """Run the Palace BoundaryMode solver and return mode metrics.

        Parameters
        ----------
        num_modes : int
            Number of modes to compute (``BoundaryMode.N``).
        mode_idx : int, optional
            If set, only return the single mode at this 1-based index.
        target : float
            Target effective index for the shift-invert spectral
            transformation (``BoundaryMode.Target``).  Values ``<= 0``
            leave the key unset so Palace computes the shift from the
            material properties (0 is not accepted by the config schema).
        output_dir : str or Path, optional
            Output directory for Palace results.  Defaults to a
            subdirectory next to the mesh file.
        work_dir : str or Path, optional
            Working directory for Palace execution.  Defaults to the
            parent of *output_dir*.
        num_procs : int
            Number of MPI processes.
        save : int
            Number of mode field profiles to save to disk.

        Returns
        -------
        dict[int, ModeMetrics]
            Mapping from mode index (1-based) to mode metrics.
        """
        mesh_path = Path(self.mesh_file)
        if output_dir is None:
            output_dir = mesh_path.parent / f"{mesh_path.stem}_modes"
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        config = self._build_config(num_modes, target, save, output_dir)
        config_path = output_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        run_palace(
            config_file=config_path,
            num_procs=num_procs,
            work_dir=str(work_dir or output_dir),
        )

        return self._parse_results(output_dir, mode_idx)

    # ------------------------------------------------------------------
    # Config generation
    # ------------------------------------------------------------------

    def _build_config(
        self,
        num_modes: int,
        target: float,
        save: int,
        output_dir: Path,
    ) -> dict[str, Any]:
        freq_ghz = self.omega * self._C0_SI / (2 * math.pi * self.L0 * 1e9)
        boundary_mode: dict[str, Any] = {
            "Freq": freq_ghz,
            "N": num_modes,
            "Save": save,
            "Tol": 1e-8,
            "Type": "Default",
        }
        if target is not None and target > 0.0:
            boundary_mode["Target"] = target
        config: dict[str, Any] = {
            "Problem": {
                "Type": "BoundaryMode",
                "Verbose": 2,
                "Output": str(output_dir / "postpro"),
            },
            "Model": {
                "Mesh": self.mesh_file,
                "L0": self.L0,
                "Refinement": {},
            },
            "Domains": {"Materials": []},
            "Boundaries": {},
            "Solver": {
                "Order": self.order,
                "Device": "CPU",
                "BoundaryMode": boundary_mode,
                "Linear": {
                    "Type": "Default",
                    "KSPType": "GMRES",
                    "Tol": 1e-8,
                    "MaxIts": 500,
                },
            },
        }

        for mat in self.materials:
            entry: dict[str, Any] = {
                "Attributes": list(mat.get("attrs", [])),
                "Permittivity": mat.get("eps_r", 1.0),
                "Permeability": mat.get("mu_r", 1.0),
            }
            lt = mat.get("loss_tan", 0.0)
            if lt:
                entry["LossTan"] = lt
            config["Domains"]["Materials"].append(entry)

        boundaries: dict[str, Any] = {}
        if self.pec_bdr:
            boundaries["PEC"] = {"Attributes": sorted(self.pec_bdr)}
        # Remaining boundary groups not listed in pec_bdr get absorbing BC.
        # Palace auto-assigns absorbing for any boundary attribute not
        # listed in an explicit boundary section.
        if boundaries:
            config["Boundaries"] = boundaries

        return config

    # ------------------------------------------------------------------
    # Results parsing
    # ------------------------------------------------------------------

    def _parse_results(
        self,
        output_dir: Path,
        mode_idx: int | None,
    ) -> dict[int, ModeMetrics]:
        postpro = output_dir / "postpro"
        if not postpro.is_dir():
            # Palace may have written output relative to config location
            postpro = output_dir / "postpro"
            if not postpro.is_dir():
                postpro = output_dir

        kn_csv = postpro / "mode-kn.csv"
        if not kn_csv.is_file():
            # Try parent of output_dir
            kn_csv = output_dir / "mode-kn.csv"
        if not kn_csv.is_file():
            raise FileNotFoundError(
                f"mode-kn.csv not found in {postpro} or {output_dir}. "
                "Palace may have failed to produce output."
            )

        modes: dict[int, ModeMetrics] = {}
        with open(kn_csv, newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                # Palace pads CSV column headers with whitespace; strip keys so
                # the lookups below match regardless of the exact header text.
                row = {k.strip(): v for k, v in row.items()}
                kn_re = float(row.get("Re{kn} (1/m)", row.get("Re{kn}", "nan")))
                kn_im = float(row.get("Im{kn} (1/m)", row.get("Im{kn}", "0")))
                n_re = float(row.get("Re{n_eff}", "nan"))
                n_im = float(row.get("Im{n_eff}", "0"))

                k_n = complex(kn_re, kn_im)
                n_eff = complex(n_re, n_im)
                eta_eff = 376.730313668 / n_eff if not np.isnan(n_eff) else complex(np.nan, np.nan)

                modes[idx] = ModeMetrics(k_n=k_n, n_eff=n_eff, eta_eff=eta_eff)

        if mode_idx is not None:
            if mode_idx not in modes:
                raise KeyError(
                    f"Mode index {mode_idx} not found in results "
                    f"(available indices: {sorted(modes)})"
                )
            return {mode_idx: modes[mode_idx]}

        return modes