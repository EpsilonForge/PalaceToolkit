import json
import os
import subprocess
from pathlib import Path

import numpy as np
import gmsh

from palacetoolkit.mesh import refine_near_surfaces as _refine_near_surfaces
from palacetoolkit.palace_runtime import resolve_palace_binary, resolve_palace_library_dir


_PALACE_EXEC_OVERRIDE: Path | None = None
_PALACE_SIF_OVERRIDE: Path | None = None


def _infer_exec_library_dir(exec_path: Path) -> Path | None:
    candidate = exec_path.resolve().parent.parent / "lib"
    if candidate.is_dir():
        return candidate
    return None


def set_palace_path(path: str | Path | None) -> None:
    """Set a global Palace runtime path override used by :func:`run_palace`.

    Rules:
    - ``None`` clears all overrides.
    - ``*.sif`` sets an Apptainer/Singularity image override.
    - Any other file path is treated as an executable override.
    """
    global _PALACE_EXEC_OVERRIDE, _PALACE_SIF_OVERRIDE

    if path is None:
        _PALACE_EXEC_OVERRIDE = None
        _PALACE_SIF_OVERRIDE = None
        return

    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Palace path not found at {resolved}")

    if resolved.suffix == ".sif":
        _PALACE_EXEC_OVERRIDE = None
        _PALACE_SIF_OVERRIDE = resolved
    else:
        _PALACE_EXEC_OVERRIDE = resolved
        _PALACE_SIF_OVERRIDE = None


def check_palace_runtime(timeout: float = 20.0) -> dict[str, str]:
    """Validate that the configured Palace runtime is available and executable.

    This performs a lightweight smoke test by invoking ``--version`` using the
    same runtime selection order as :func:`run_palace`.

    Returns:
        A metadata dictionary with keys ``mode``, ``path``, and ``version``.
    """
    selected_exec: Path | None = None
    palace_sif_path: Path | None = None

    if _PALACE_EXEC_OVERRIDE is not None:
        selected_exec = _PALACE_EXEC_OVERRIDE
    elif _PALACE_SIF_OVERRIDE is not None:
        palace_sif_path = _PALACE_SIF_OVERRIDE

    local_palace = resolve_palace_binary() if selected_exec is None else None
    if selected_exec is None and local_palace is not None:
        selected_exec = local_palace

    if selected_exec is not None:
        run_env = os.environ.copy()
        if local_palace is not None:
            lib_dir = _infer_exec_library_dir(local_palace) or resolve_palace_library_dir()
        else:
            lib_dir = None
        if lib_dir is not None:
            prior = run_env.get("LD_LIBRARY_PATH", "")
            run_env["LD_LIBRARY_PATH"] = f"{lib_dir}:{prior}" if prior else str(lib_dir)

        cmd = [str(selected_exec), "--version"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=run_env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Palace executable not found: {selected_exec}") from exc

        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            raise RuntimeError(
                f"Palace runtime check failed with code {result.returncode}: {output}"
            )
        version_line = output.splitlines()[0] if output else "(no version output)"
        return {
            "mode": "executable",
            "path": str(selected_exec),
            "version": version_line,
        }

    if palace_sif_path is None:
        palace_sif = os.environ.get("PALACE_SIF")
        if not palace_sif:
            raise RuntimeError(
                "No Palace executable found. Set one with set_palace_path(...), "
                "install a packaged binary, or set PALACE_SIF."
            )
        palace_sif_path = Path(palace_sif).expanduser().resolve()

    if not palace_sif_path.is_file():
        raise FileNotFoundError(f"Palace.sif not found at {palace_sif_path}")

    cmd = ["apptainer", "exec", str(palace_sif_path), "palace", "--version"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError("apptainer command not found for Palace SIF runtime") from exc

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        raise RuntimeError(
            f"Palace SIF runtime check failed with code {result.returncode}: {output}"
        )

    version_line = output.splitlines()[0] if output else "(no version output)"
    return {
        "mode": "sif",
        "path": str(palace_sif_path),
        "version": version_line,
    }


class Simulation:
    """Minimal Palace simulation helper.

    Provides a tiny stateful wrapper to:

    - set an output directory,
    - apply default gmsh mesh options,
    - wrap near-surface mesh refinement,
    - and assemble/write a Palace config file.
    """

    def __init__(self, output_dir: str | Path = "."):
        self.output_dir = Path(output_dir)
        self.config: dict = {
            "Problem": {
                "Type": "Driven",
                "Verbose": 2,
                "Output": "/work/results/",
            },
            "Model": {
                "Mesh": "/work/model.msh",
                "L0": 1.0,
                "Refinement": {},
            },
            "Domains": {
                "Materials": [],
            },
            "Boundaries": {},
            "Solver": {
                "Order": 2,
                "Device": "CPU",
                "Driven": {
                    "MinFreq": 1.0,
                    "MaxFreq": 2.0,
                    "FreqStep": 0.1,
                    "AdaptiveTol": 1.0e-3,
                },
                "Linear": {
                    "Type": "Default",
                    "KSPType": "GMRES",
                    "Tol": 1.0e-8,
                    "MaxIts": 200,
                    "ComplexCoarseSolve": True,
                },
            },
        }

        self.set_output_dir(output_dir)
        self.apply_default_mesh_options()

    def set_output_dir(self, output_dir: str | Path) -> Path:
        """Set and create the simulation output directory."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        self.output_dir = out
        return self.output_dir

    def apply_default_mesh_options(self) -> None:
        """Apply minimal gmsh defaults for deterministic ASCII Palace meshes."""
        gmsh.option.setNumber("Mesh.Algorithm", 6)    # Frontal-Delaunay for 2D
        gmsh.option.setNumber("Mesh.Algorithm3D", 2)  # Frontal-Delaunay for 3D
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.Binary", 0)

    def refine_near_surfaces(
        self,
        surface_dimtags: list[tuple[int, int]],
        wavelength: float,
        ppw_near: int = 20,
        ppw_far: int = 5,
        transition_distance: float | None = None,
        set_as_background: bool = True,
    ) -> int:
        """Wrapper around :func:`palacetoolkit.mesh.refine_near_surfaces`."""
        return _refine_near_surfaces(
            surface_dimtags=surface_dimtags,
            wavelength=wavelength,
            ppw_near=ppw_near,
            ppw_far=ppw_far,
            transition_distance=transition_distance,
            set_as_background=set_as_background,
        )

    def set_mesh_file(self, mesh_file: str) -> None:
        """Set the mesh path used in the Palace model section."""
        self.config.setdefault("Model", {})["Mesh"] = mesh_file

    def set_config_option(self, dotted_key: str, value) -> None:
        """Set a nested config value using dotted keys.

        Example:
            sim.set_config_option("Solver.Driven.MinFreq", 3.0)
        """
        keys = dotted_key.split(".")
        if not keys:
            raise ValueError("dotted_key must not be empty")

        node = self.config
        for key in keys[:-1]:
            child = node.get(key)
            if not isinstance(child, dict):
                child = {}
                node[key] = child
            node = child
        node[keys[-1]] = value

    def write_config(self, filename: str = "palace.conf") -> Path:
        """Write the Palace config into the output directory."""
        cfg_path = self.output_dir / filename
        with open(cfg_path, "w") as f:
            json.dump(self.config, f, indent=2)
        print(f"Palace config written to {cfg_path}")
        return cfg_path


def run_palace(
    config_file: str | Path,
    num_procs: int = 4,
    work_dir: str | Path | None = None,
) -> None:
    """Run Palace using a configured executable, packaged binary, or SIF.

    Args:
        config_file: Path to the Palace JSON config.
        num_procs:   Number of MPI processes.
        work_dir:    Working directory (defaults to config file's parent).

    Runtime selection order:
    1. Path set with :func:`set_palace_path` (exec or ``.sif``)
    2. Packaged/fetched local binary
    3. ``PALACE_SIF`` environment variable
    """
    config_path = Path(config_file).resolve()
    if work_dir is None:
        work_dir = str(config_path.parent)
    else:
        work_dir = str(Path(work_dir).resolve())
    config_name = config_path.name

    selected_exec: Path | None = None
    palace_sif_path: Path | None = None

    if _PALACE_EXEC_OVERRIDE is not None:
        selected_exec = _PALACE_EXEC_OVERRIDE
    elif _PALACE_SIF_OVERRIDE is not None:
        palace_sif_path = _PALACE_SIF_OVERRIDE

    local_palace = resolve_palace_binary() if selected_exec is None else None
    if selected_exec is None and local_palace is not None:
        selected_exec = local_palace

    if selected_exec is not None:
        run_env = os.environ.copy()
        # Only inject packaged library path when using the packaged binary.
        if local_palace is not None:
            lib_dir = _infer_exec_library_dir(local_palace) or resolve_palace_library_dir()
        else:
            lib_dir = None
        if lib_dir is not None:
            prior = run_env.get("LD_LIBRARY_PATH", "")
            run_env["LD_LIBRARY_PATH"] = f"{lib_dir}:{prior}" if prior else str(lib_dir)

        if num_procs > 1:
            cmd = ["mpirun", "-np", str(num_procs), str(selected_exec), str(config_path)]
        else:
            cmd = [str(selected_exec), str(config_path)]
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=work_dir, capture_output=False, env=run_env)
        if result.returncode != 0:
            raise RuntimeError(f"Palace exited with code {result.returncode}")
        return

    if palace_sif_path is None:
        palace_sif = os.environ.get("PALACE_SIF")
        if not palace_sif:
            raise RuntimeError(
                "No Palace executable found. Set one with set_palace_path(...), "
                "install a packaged binary, or set PALACE_SIF."
            )
        palace_sif_path = Path(palace_sif).expanduser().resolve()

    if not palace_sif_path.is_file():
        raise FileNotFoundError(f"Palace.sif not found at {palace_sif_path}")

    if num_procs > 1:
        cmd = [
            "apptainer", "exec", "--pwd", "/work",
            "--bind", f"{work_dir}:/work",
            str(palace_sif_path),
            "mpirun", "-np", str(num_procs),
            "/opt/palace/bin/palace-x86_64.bin",
            f"/work/{config_name}",
        ]
    else:
        cmd = [
            "apptainer", "exec", "--pwd", "/work",
            "--bind", f"{work_dir}:/work",
            str(palace_sif_path),
            "palace", f"/work/{config_name}",
        ]

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=work_dir, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"Palace exited with code {result.returncode}")


def extract_impedance(postpro_dir: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Read Palace port CSVs and return (freq_ghz, z_ant) arrays.

    Uses:
        Z0_ref  = V_inc / I_inc   (from port-V.csv, port-I.csv)
        S11     = |S11| * exp(j * phase)
        Z_ant   = Z0_ref * (1 + S11) / (1 - S11)

    Returns:
        freq_ghz: 1-D array of frequencies in GHz.
        z_ant:    1-D complex array of antenna impedance.
    """
    postpro = Path(postpro_dir)

    S = np.loadtxt(postpro / "port-S.csv", delimiter=",", skiprows=1, ndmin=2)
    V = np.loadtxt(postpro / "port-V.csv", delimiter=",", skiprows=1, ndmin=2)
    I = np.loadtxt(postpro / "port-I.csv", delimiter=",", skiprows=1, ndmin=2)

    freq_ghz      = S[:, 0]
    s11_dB        = S[:, 1]
    s11_phase_deg = S[:, 2]

    # Port reference impedance (constant vs frequency; use first row)
    Z0_ref = V[0, 1] / I[0, 1]

    s11_mag = 10 ** (s11_dB / 20.0)
    s11     = s11_mag * np.exp(1j * np.deg2rad(s11_phase_deg))

    z_ant = Z0_ref * (1 + s11) / (1 - s11)
    return freq_ghz, z_ant


def generate_palace_config_from_entities(
    entity_defs: list[dict],
    pg_map: dict[str, int],
    mesh_file: str,
    output_file: str,
    freq_min: float,
    freq_max: float,
    freq_step: float,
    L0: float = 1e-3,
    solver_order: int = 2,
    absorbing_order: int = 2,
) -> dict:
    """Build and write a Palace JSON config from entity definitions.

    Each entry in *entity_defs* is a dict with at least::

        {"name": str, "boundary_type": str}

    Supported ``boundary_type`` values:

    - ``"pec"``         — perfect electric conductor surface.
    - ``"dielectric"``  — volumetric material.  Extra keys:
      ``eps_r`` (default 1.0), ``mu_r`` (default 1.0), ``loss_tan`` (default 0.0).
    - ``"lumped_port"`` — lumped port excitation surface.  Extra keys:
      ``R`` (Ω), ``Direction`` (e.g. "+X"), ``Excitation`` (bool, default True).
    - ``"waveport"``    — wave-port excitation surface.  Extra keys:
      ``Mode`` (default 1), ``Excitation`` (bool, default True).

    Physical group names present in *pg_map* but **not** matching any
    ``entity_defs`` name are treated as absorbing BC surfaces (auto-generated
    outer faces from the boolean pipeline).

    Returns:
        The configuration dictionary that was also written to *output_file*.
    """
    # Build lookup: entity name → definition
    defs_by_name = {e["name"]: e for e in entity_defs}

    pec_attrs: list[int] = []
    absorbing_attrs: list[int] = []
    materials: list[dict] = []
    lumped_ports: list[dict] = []
    wave_ports: list[dict] = []
    lumped_idx = 0
    wave_idx = 0

    for name, tag in sorted(pg_map.items()):
        edef = defs_by_name.get(name)
        if edef is None:
            # Auto-generated surface (e.g. "air__None") → absorbing BC
            absorbing_attrs.append(tag)
            continue

        btype = edef.get("boundary_type")

        if btype == "pec":
            pec_attrs.append(tag)

        elif btype == "dielectric":
            materials.append({
                "Attributes":   [tag],
                "Permeability":  edef.get("mu_r", 1.0),
                "Permittivity":  edef.get("eps_r", 1.0),
                "LossTan":       edef.get("loss_tan", 0.0),
            })

        elif btype == "lumped_port":
            lumped_idx += 1
            entry = {
                "Index":      lumped_idx,
                "Attributes": [tag],
                "R":          edef.get("R", 50.0),
                "Excitation": edef.get("Excitation", True),
                "Direction":  edef.get("Direction", "+X"),
            }
            lumped_ports.append(entry)

        elif btype == "waveport":
            wave_idx += 1
            entry = {
                "Index":      wave_idx,
                "Attributes": [tag],
                "Mode":       edef.get("Mode", 1),
                "Offset":     edef.get("Offset", 0.0),
            }
            if edef.get("Excitation", wave_idx == 1):
                entry["Excitation"] = True
            wave_ports.append(entry)

    # Boundaries section
    boundaries: dict = {
        "PEC":       {"Attributes": sorted(pec_attrs)},
        "Absorbing": {"Attributes": sorted(absorbing_attrs), "Order": absorbing_order},
    }
    if lumped_ports:
        boundaries["LumpedPort"] = lumped_ports
    if wave_ports:
        boundaries["WavePort"] = wave_ports

    output_stem = Path(output_file).stem
    output_folder = f"postpro/{output_stem}"

    config = {
        "Problem": {
            "Type": "Driven",
            "Verbose": 2,
            "Output": output_folder,
        },
        "Model": {
            "Mesh": mesh_file,
            "L0": L0,
            "Refinement": {},
        },
        "Domains": {
            "Materials": materials,
        },
        "Boundaries": boundaries,
        "Solver": {
            "Order": solver_order,
            "Device": "CPU",
            "Driven": {
                "MinFreq": freq_min,
                "MaxFreq": freq_max,
                "FreqStep": freq_step,
                "SaveStep": 5,
                "AdaptiveTol": 1e-3,
            },
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": 1e-8,
                "MaxIts": 500,
            },
        },
    }

    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Palace config written to {output_file}")
    return config


def generate_palace_config(
    pg_map: dict[str, int],
    mesh_file: str,
    output_file: str,
    eps_r: float,
    conductor_names: set[str],
    freq_min: float = 2.0,
    freq_max: float = 10.0,
    freq_step: float = 0.5,
) -> dict:
    """Build and write a Palace-compatible JSON configuration file.

    Classifies physical groups from *pg_map* using the naming conventions
    established by :func:`run_meshing_pipeline`:

    - Plain names (no ``__``) that don't start with ``waveport`` → 3D volume
      (material domain).
    - ``A__B`` or ``A__None`` names → 2D surface interface.
    - ``waveport_*`` names → wave-port excitation surfaces.

    PEC boundaries are 2D PGs whose name components include a conductor name.
    ``air__None`` is assigned as the absorbing (ABC) boundary.

    Args:
        pg_map:          name → physical-group tag, as returned by
                         :func:`run_meshing_pipeline`.
        mesh_file:       path to the .msh file (stored in ``Model.Mesh``).
        output_file:     destination JSON path.
        eps_r:           substrate relative permittivity.
        conductor_names: set of entity names that are perfect conductors.
        freq_min:        start frequency [GHz].
        freq_max:        end frequency [GHz].
        freq_step:       frequency step [GHz].

    Returns:
        The configuration dictionary that was written to *output_file*.
    """
    pec_attrs: list[int] = []
    absorbing_attrs: list[int] = []
    waveports: list[tuple[str, int]] = []
    air_tag: int | None = None
    substrate_tag: int | None = None

    for name, tag in sorted(pg_map.items()):
        parts = name.split("__")

        if name.startswith("waveport"):
            waveports.append((name, tag))
        elif len(parts) >= 2:
            # 2D surface interface PG
            non_none = [p for p in parts if p != "None"]
            if any(p in conductor_names for p in non_none):
                pec_attrs.append(tag)
            elif name == "air__None":
                absorbing_attrs.append(tag)
        else:
            # 3D volume or planar conductor surface PG
            if name == "air":
                air_tag = tag
            elif name == "substrate":
                substrate_tag = tag
            elif name in conductor_names:
                pec_attrs.append(tag)

    waveports.sort(key=lambda x: x[0])  # deterministic port numbering

    materials = []
    if air_tag is not None:
        materials.append({
            "Attributes": [air_tag],
            "Permeability": 1.0,
            "Permittivity": 1.0,
            "LossTan": 0.0,
        })
    if substrate_tag is not None:
        materials.append({
            "Attributes": [substrate_tag],
            "Permeability": 1.0,
            "Permittivity": float(eps_r),
            "LossTan": 0.0,
        })

    waveport_entries = []
    for idx, (wp_name, wp_tag) in enumerate(waveports, start=1):
        entry: dict = {
            "Index": idx,
            "Attributes": [wp_tag],
            "Mode": 1,
            "Offset": 0.0,
        }
        if idx == 1:
            entry["Excitation"] = True
        waveport_entries.append(entry)

    output_stem = Path(output_file).stem       # e.g. "cpw" from "cpw.json"
    output_folder = f"postpro/{output_stem}"

    config = {
        "Problem": {
            "Type": "Driven",
            "Verbose": 2,
            "Output": output_folder,
        },
        "Model": {
            "Mesh": mesh_file,
            "L0": 1e-6,
            "Refinement": {},
        },
        "Domains": {
            "Materials": materials,
        },
        "Boundaries": {
            "PEC":       {"Attributes": sorted(pec_attrs)},
            "Absorbing": {"Attributes": sorted(absorbing_attrs), "Order": 1},
            "WavePort":  waveport_entries,
        },
        "Solver": {
            "Order": 2,
            "Device": "CPU",
            "Driven": {
                "MinFreq": freq_min,
                "MaxFreq": freq_max,
                "FreqStep": freq_step,
                "SaveStep": 1,
                "AdaptiveTol": 0.001,
            },
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": 1e-8,
                "MaxIts": 200,
            },
        },
    }

    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Palace config written to {output_file}")
    return config