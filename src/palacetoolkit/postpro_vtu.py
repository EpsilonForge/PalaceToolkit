"""VTU/PVTU postprocessing helpers for Palace field visualization.

This module focuses on a minimal workflow:
1) Discover Paraview datasets under ``postpro/<run>/paraview``.
2) Resolve boundary selectors from entity names using ``pg_map`` and Palace config.
3) Load boundary field data for a selected frequency step.
4) Provide a small PyVista plotting utility for quick visual inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET

import numpy as np


@dataclass(frozen=True)
class ParaviewStep:
    """One time/frequency step in a Paraview timeline."""

    index: int
    timestep: float
    mesh_file: Path


@dataclass(frozen=True)
class ParaviewDataset:
    """A discovered Paraview dataset (for example ``driven_boundary``)."""

    name: str
    kind: str
    pvd_file: Path
    steps: tuple[ParaviewStep, ...]


@dataclass(frozen=True)
class SelectorContext:
    """Context used to resolve user selectors to boundary attribute tags."""

    pg_map: dict[str, int]
    boundaries_by_type: dict[str, tuple[int, ...]]


@dataclass
class BoundaryFieldData:
    """Loaded boundary mesh + metadata for a selected step/selector."""

    mesh: Any
    dataset_name: str
    step_index: int
    timestep: float
    selected_attributes: tuple[int, ...]

    @property
    def point_arrays(self) -> tuple[str, ...]:
        return tuple(self.mesh.point_data.keys())

    @property
    def cell_arrays(self) -> tuple[str, ...]:
        return tuple(self.mesh.cell_data.keys())


@dataclass
class VolumeFieldData:
    """Loaded volume mesh + metadata for a selected step."""

    mesh: Any
    dataset_name: str
    step_index: int
    timestep: float

    @property
    def point_arrays(self) -> tuple[str, ...]:
        return tuple(self.mesh.point_data.keys())

    @property
    def cell_arrays(self) -> tuple[str, ...]:
        return tuple(self.mesh.cell_data.keys())


def _require_pyvista() -> Any:
    try:
        import pyvista as pv
    except Exception as exc:  # pragma: no cover - import failure is environment-specific
        raise ImportError("pyvista is required for VTU postprocessing") from exc
    return pv


def _parse_pvd(pvd_file: Path) -> tuple[ParaviewStep, ...]:
    tree = ET.parse(pvd_file)
    root = tree.getroot()
    coll = root.find("Collection")
    if coll is None:
        raise ValueError(f"Invalid PVD file: missing Collection node in {pvd_file}")

    steps: list[ParaviewStep] = []
    for i, ds in enumerate(coll.findall("DataSet")):
        file_attr = ds.attrib.get("file")
        if not file_attr:
            continue
        timestep_raw = ds.attrib.get("timestep", "nan")
        try:
            timestep = float(timestep_raw)
        except ValueError:
            timestep = float("nan")
        mesh_file = (pvd_file.parent / file_attr).resolve()
        steps.append(ParaviewStep(index=i, timestep=timestep, mesh_file=mesh_file))

    if not steps:
        raise ValueError(f"No DataSet entries found in {pvd_file}")
    return tuple(steps)


def discover_paraview_datasets(postpro_dir: str | Path) -> dict[str, ParaviewDataset]:
    """Discover Paraview timelines under ``<postpro_dir>/paraview``.

    Returns
    -------
    dict[str, ParaviewDataset]
        Keys are dataset folder names (for example ``driven`` or ``driven_boundary``).
    """
    postpro = Path(postpro_dir)
    paraview_dir = postpro / "paraview" 
    if not paraview_dir.is_dir():
        raise FileNotFoundError(f"Paraview directory not found: {paraview_dir}")

    datasets: dict[str, ParaviewDataset] = {}
    for child in sorted(paraview_dir.iterdir()):
        if not child.is_dir():
            continue
        pvd_file = child / f"{child.name}.pvd"
        if not pvd_file.is_file():
            continue

        steps = _parse_pvd(pvd_file)
        kind = "boundary" if "boundary" in child.name.lower() else "volume"
        datasets[child.name] = ParaviewDataset(
            name=child.name,
            kind=kind,
            pvd_file=pvd_file,
            steps=steps,
        )

    if not datasets:
        raise FileNotFoundError(
            f"No Paraview datasets found in {paraview_dir}; expected folders with <name>.pvd"
        )
    return datasets


def load_dataset_step(
    postpro_dir: str | Path,
    dataset_name: str,
    step_index: int = 0,
) -> tuple[Any, ParaviewDataset, ParaviewStep]:
    """Load a mesh for one step from a named dataset."""
    pv = _require_pyvista()
    datasets = discover_paraview_datasets(postpro_dir)

    if dataset_name not in datasets:
        names = ", ".join(sorted(datasets.keys()))
        raise KeyError(f"Dataset '{dataset_name}' not found. Available: {names}")

    dataset = datasets[dataset_name]
    nsteps = len(dataset.steps)
    if step_index < 0 or step_index >= nsteps:
        raise IndexError(
            f"step_index {step_index} out of range for dataset '{dataset_name}' (0..{nsteps - 1})"
        )

    step = dataset.steps[step_index]
    if not step.mesh_file.is_file():
        raise FileNotFoundError(f"Mesh step file not found: {step.mesh_file}")

    mesh = pv.read(str(step.mesh_file))
    # If the mesh has no point data, it might be a PVTU that pyvista couldn't
    # resolve. Try reading individual VTU files referenced inside the PVTU.
    if mesh.n_points == 0 or len(mesh.point_data) == 0:
        if step.mesh_file.suffix.lower() == ".pvtu":
            vtu_files = sorted(step.mesh_file.parent.glob("proc*.vtu"))
            if vtu_files:
                meshes = [pv.read(str(f)) for f in vtu_files]
                if len(meshes) > 1:
                    mesh = meshes[0].merge(meshes[1:])
                else:
                    mesh = meshes[0]
            if mesh.n_points == 0 or len(mesh.point_data) == 0:
                vtu_files = sorted(step.mesh_file.parent.glob("*.vtu"))
                if vtu_files:
                    mesh = pv.read(str(vtu_files[0]))
    return mesh, dataset, step


def nearest_step_index(dataset: ParaviewDataset, timestep: float) -> int:
    """Return the step index with closest timestep value."""
    if not dataset.steps:
        raise ValueError(f"Dataset '{dataset.name}' has no steps")
    vals = np.array([s.timestep for s in dataset.steps], dtype=float)
    return int(np.argmin(np.abs(vals - float(timestep))))


def resolve_synced_step_indices(
    postpro_dir: str | Path,
    *,
    boundary_dataset: str = "driven_boundary",
    volume_dataset: str = "driven",
    step_index: int | None = None,
    timestep: float | None = None,
) -> tuple[int, int]:
    """Resolve boundary and volume step indices for synchronized plotting.

    If ``step_index`` is provided, that index is used for both datasets.
    If ``timestep`` is provided, nearest-step matching is used per dataset.
    """
    if step_index is None and timestep is None:
        step_index = 0

    datasets = discover_paraview_datasets(postpro_dir)
    if boundary_dataset not in datasets:
        raise KeyError(f"Boundary dataset '{boundary_dataset}' not found")
    if volume_dataset not in datasets:
        raise KeyError(f"Volume dataset '{volume_dataset}' not found")

    bset = datasets[boundary_dataset]
    vset = datasets[volume_dataset]

    if step_index is not None:
        bmax = len(bset.steps) - 1
        vmax = len(vset.steps) - 1
        if step_index < 0 or step_index > bmax or step_index > vmax:
            raise IndexError(
                f"step_index {step_index} out of range for synchronized datasets "
                f"(boundary: 0..{bmax}, volume: 0..{vmax})"
            )
        return int(step_index), int(step_index)

    assert timestep is not None
    return nearest_step_index(bset, timestep), nearest_step_index(vset, timestep)


def _coerce_config(config: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, dict):
        return config
    cfg_path = Path(config)
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _attrs_from_boundary_section(section: Any) -> list[int]:
    attrs: list[int] = []
    if isinstance(section, dict):
        for a in section.get("Attributes", []):
            attrs.append(int(a))
        return attrs

    if isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                for a in item.get("Attributes", []):
                    attrs.append(int(a))
        return attrs

    return attrs


def build_selector_context(
    palace_config: str | Path | dict[str, Any],
    pg_map: dict[str, int],
) -> SelectorContext:
    """Create a selector context from Palace config plus ``pg_map``.

    Notes
    -----
    ``pg_map`` is treated as authoritative for entity-name selectors.
    """
    cfg = _coerce_config(palace_config)
    boundaries = cfg.get("Boundaries", {}) if isinstance(cfg, dict) else {}

    boundaries_by_type: dict[str, tuple[int, ...]] = {}
    for key, section in boundaries.items():
        attrs = tuple(sorted(set(_attrs_from_boundary_section(section))))
        if attrs:
            boundaries_by_type[key] = attrs

    return SelectorContext(pg_map=dict(pg_map), boundaries_by_type=boundaries_by_type)


def resolve_entity_attributes(
    entity_names: str | Iterable[str],
    context: SelectorContext,
) -> tuple[int, ...]:
    """Resolve entity name(s) to physical attribute tags using ``pg_map``."""
    if isinstance(entity_names, str):
        names = [entity_names]
    else:
        names = list(entity_names)

    missing = [name for name in names if name not in context.pg_map]
    if missing:
        known = ", ".join(sorted(context.pg_map.keys()))
        raise KeyError(
            f"Unknown entity selector(s): {missing}. Known entity names: {known}"
        )

    attrs = sorted({int(context.pg_map[name]) for name in names})
    return tuple(attrs)


def resolve_boundary_type_attributes(
    boundary_type: str,
    context: SelectorContext,
) -> tuple[int, ...]:
    """Resolve a Palace boundary type (for example ``PEC``) to tags."""
    if boundary_type not in context.boundaries_by_type:
        known = ", ".join(sorted(context.boundaries_by_type.keys()))
        raise KeyError(
            f"Boundary type '{boundary_type}' not found in config. Known: {known}"
        )
    return context.boundaries_by_type[boundary_type]


def extract_boundary_cells(
    mesh: Any,
    attributes: Iterable[int],
    attribute_array: str = "attribute",
) -> Any:
    """Extract boundary cells whose ``attribute`` value is in ``attributes``."""
    attrs = set(int(a) for a in attributes)
    if not attrs:
        raise ValueError("No attributes provided for boundary extraction")

    if attribute_array not in mesh.cell_data:
        available = ", ".join(mesh.cell_data.keys())
        raise KeyError(
            f"Cell array '{attribute_array}' not found. Available cell arrays: {available}"
        )

    values = np.asarray(mesh.cell_data[attribute_array]).astype(int)
    ids = np.where(np.isin(values, list(attrs)))[0]
    if ids.size == 0:
        raise ValueError(
            f"No cells matched attributes {sorted(attrs)} in cell array '{attribute_array}'"
        )

    return mesh.extract_cells(ids)


def load_boundary_field_data(
    postpro_dir: str | Path,
    selector_context: SelectorContext,
    *,
    entity_names: str | Iterable[str] | None = None,
    boundary_type: str | None = None,
    attributes: Iterable[int] | None = None,
    dataset_name: str = "driven_boundary",
    step_index: int = 0,
    strict_boundary: bool = True,
) -> BoundaryFieldData:
    """Load boundary-only field data for selected faces.

    Selection priority: ``attributes`` > ``entity_names`` > ``boundary_type``.
    """
    mesh, dataset, step = load_dataset_step(
        postpro_dir=postpro_dir,
        dataset_name=dataset_name,
        step_index=step_index,
    )

    if strict_boundary and dataset.kind != "boundary":
        raise ValueError(
            f"Dataset '{dataset.name}' is '{dataset.kind}', not boundary. "
            "Strict boundary mode requires a boundary dataset (for example 'driven_boundary')."
        )

    if attributes is not None:
        selected = tuple(sorted({int(a) for a in attributes}))
    elif entity_names is not None:
        selected = resolve_entity_attributes(entity_names, selector_context)
    elif boundary_type is not None:
        selected = resolve_boundary_type_attributes(boundary_type, selector_context)
    else:
        raise ValueError(
            "Provide one selector: attributes, entity_names, or boundary_type"
        )

    boundary_mesh = extract_boundary_cells(mesh, selected, attribute_array="attribute")

    return BoundaryFieldData(
        mesh=boundary_mesh,
        dataset_name=dataset.name,
        step_index=step.index,
        timestep=step.timestep,
        selected_attributes=selected,
    )


def load_volume_field_data(
    postpro_dir: str | Path,
    *,
    dataset_name: str = "driven",
    step_index: int = 0,
    strict_volume: bool = True,
) -> VolumeFieldData:
    """Load volume field data for slice and volume rendering workflows."""
    mesh, dataset, step = load_dataset_step(
        postpro_dir=postpro_dir,
        dataset_name=dataset_name,
        step_index=step_index,
    )

    if strict_volume and dataset.kind != "volume":
        raise ValueError(
            f"Dataset '{dataset.name}' is '{dataset.kind}', not volume. "
            "Strict volume mode requires a volume dataset (for example 'driven')."
        )

    return VolumeFieldData(
        mesh=mesh,
        dataset_name=dataset.name,
        step_index=step.index,
        timestep=step.timestep,
    )


def extract_axis_slice(
    data: VolumeFieldData,
    axis: str,
    value: float,
) -> Any:
    """Extract an axis-aligned slice from volume data."""
    axis = axis.lower()
    if axis not in ("x", "y", "z"):
        raise ValueError("axis must be one of: x, y, z")

    origin = [0.0, 0.0, 0.0]
    normal_map = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
    idx = {"x": 0, "y": 1, "z": 2}[axis]
    origin[idx] = float(value)

    return data.mesh.slice(normal=normal_map[axis], origin=tuple(origin))


def extract_axis_cutplane(
    data: VolumeFieldData,
    axis: str,
    value: float,
) -> Any:
    """Backward-compatible alias for :func:`extract_axis_slice`."""
    return extract_axis_slice(data=data, axis=axis, value=value)


def extract_plane_slice(
    data: VolumeFieldData,
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
) -> Any:
    """Extract an arbitrary plane slice from volume data."""
    return data.mesh.slice(normal=normal, origin=origin)


def extract_slice_contours(
    slice_mesh: Any,
    scalar_field: str,
    n_contours: int = 20,
    field_name: str | None = None,
) -> Any:
    """Extract contour lines from a sliced mesh for a scalar field."""
    if scalar_field is None:
        scalar_field = field_name or ""

    if scalar_field not in slice_mesh.point_data:
        available = ", ".join(slice_mesh.point_data.keys())
        raise KeyError(
            f"Scalar field '{scalar_field}' not found on slice. Available: {available}"
        )

    return slice_mesh.contour(isosurfaces=int(n_contours), scalars=scalar_field)


def resolve_scalar_field(
    mesh: Any,
    *,
    scalar_field: str | None = None,
    vector_field: str | None = None,
    component: str = "mag",
    output_name: str | None = None,
    field_name: str | None = None,
) -> str:
    """Resolve a scalar field name from scalar or vector input.

    If ``vector_field`` is provided, a scalar component array is created.
    """
    if scalar_field is None:
        scalar_field = field_name

    if scalar_field is not None and vector_field is not None:
        raise ValueError("Provide either scalar_field or vector_field, not both")

    if scalar_field is not None:
        if scalar_field not in mesh.point_data:
            available = ", ".join(mesh.point_data.keys())
            raise KeyError(
                f"Scalar field '{scalar_field}' not found. Available point arrays: {available}"
            )
        return scalar_field

    if vector_field is not None:
        return activate_vector_component(
            mesh,
            field_name=vector_field,
            component=component,
            output_name=output_name,
        )

    raise ValueError("Provide one of: scalar_field or vector_field")


def activate_vector_component(
    mesh: Any,
    field_name: str,
    component: str = "mag",
    output_name: str | None = None,
) -> str:
    """Create a scalar array from a vector field and return its array name.

    Parameters
    ----------
    component
        One of ``mag``, ``x``, ``y``, ``z``.
    """
    if field_name not in mesh.point_data:
        available = ", ".join(mesh.point_data.keys())
        print(f"Field '{field_name}' not found. Available point arrays: {available}")
        # Try common vector field names as fallback
        for candidate in ("E", "H", "J", "E_field", "H_field", "efield", "hfield"):
            if candidate in mesh.point_data:
                vec = np.asarray(mesh.point_data[candidate])
                if vec.ndim == 2 and vec.shape[1] >= 3:
                    print(f"Using '{candidate}' instead.")
                    field_name = candidate
                    break
        else:
            raise KeyError(f"Point field not found. Available: {available}")

    vec = np.asarray(mesh.point_data[field_name])
    if vec.ndim != 2 or vec.shape[1] < 3:
        raise ValueError(f"Field '{field_name}' is not a vector field with 3 components")

    if output_name is None:
        output_name = f"{field_name}_{component}"

    if component == "mag":
        scal = np.linalg.norm(vec[:, :3], axis=1)
    elif component == "x":
        scal = vec[:, 0]
    elif component == "y":
        scal = vec[:, 1]
    elif component == "z":
        scal = vec[:, 2]
    else:
        raise ValueError("component must be one of: mag, x, y, z")

    mesh.point_data[output_name] = scal
    return output_name


def plot_boundary_field(
    data: BoundaryFieldData,
    scalar_field: str | None = None,
    *,
    vector_field: str | None = None,
    component: str = "mag",
    output_name: str | None = None,
    cmap: str = "viridis",
    clim: tuple[float, float] | None = None,
    opacity: float = 1.0,
    show_edges: bool = False,
    log_scale: bool = False,
    scalar_bar_title: str | None = None,
    off_screen: bool = True,
    screenshot: str | Path | None = None,
    field_name: str | None = None,
) -> Any:
    """Render a selected boundary field with PyVista and return the plotter.

    Notes
    -----
    If ``log_scale=True`` and the selected scalar contains non-positive values,
    they are clamped to a small positive floor derived from the minimum positive
    value so logarithmic coloring remains well-defined.
    """
    pv = _require_pyvista()

    scalar_name = resolve_scalar_field(
        data.mesh,
        scalar_field=scalar_field,
        vector_field=vector_field,
        component=component,
        output_name=output_name,
        field_name=field_name,
    )

    scalar_name_for_plot = scalar_name
    if log_scale:
        vals = np.asarray(data.mesh.point_data[scalar_name], dtype=float)
        if np.any(vals <= 0.0):
            pos = vals[vals > 0.0]
            if pos.size == 0:
                raise ValueError(
                    f"Cannot use log scale for '{scalar_name}': no positive values found"
                )
            floor = float(np.min(pos)) * 1e-6
            safe_name = f"{scalar_name}_logsafe"
            data.mesh.point_data[safe_name] = np.where(vals > 0.0, vals, floor)
            scalar_name_for_plot = safe_name

    pl = pv.Plotter(off_screen=off_screen)
    pl.set_background("white")
    pl.add_mesh(
        data.mesh,
        scalars=scalar_name_for_plot,
        cmap=cmap,
        clim=clim,
        opacity=opacity,
        show_edges=show_edges,
        log_scale=log_scale,
        scalar_bar_args={"title": scalar_bar_title or scalar_name},
    )
    pl.add_axes()
    pl.camera_position = "iso"

    if screenshot is not None:
        pl.screenshot(str(screenshot))

    return pl


def plot_volume_slice(
    data: VolumeFieldData,
    scalar_field: str | None = None,
    *,
    vector_field: str | None = None,
    component: str = "mag",
    output_name: str | None = None,
    axis: str = "z",
    value: float = 0.0,
    cmap: str = "viridis",
    clim: tuple[float, float] | None = None,
    opacity: float = 1.0,
    show_edges: bool = False,
    scalar_bar_title: str | None = None,
    off_screen: bool = True,
    screenshot: str | Path | None = None,
    field_name: str | None = None,
) -> Any:
    """Render an axis-aligned volume slice with a scalar field."""
    pv = _require_pyvista()
    slice_mesh = extract_axis_slice(data, axis=axis, value=value)

    scalar_name = resolve_scalar_field(
        slice_mesh,
        scalar_field=scalar_field,
        vector_field=vector_field,
        component=component,
        output_name=output_name,
        field_name=field_name,
    )

    pl = pv.Plotter(off_screen=off_screen)
    pl.set_background("white")
    pl.add_mesh(
        slice_mesh,
        scalars=scalar_name,
        cmap=cmap,
        clim=clim,
        opacity=opacity,
        show_edges=show_edges,
        scalar_bar_args={"title": scalar_bar_title or scalar_name},
    )
    pl.add_axes()
    pl.camera_position = "iso"

    if screenshot is not None:
        pl.screenshot(str(screenshot))

    return pl


def plot_volume_contours(
    data: VolumeFieldData,
    scalar_field: str | None = None,
    *,
    vector_field: str | None = None,
    component: str = "mag",
    output_name: str | None = None,
    axis: str = "z",
    value: float = 0.0,
    n_contours: int = 20,
    line_width: float = 1.2,
    color: str = "black",
    off_screen: bool = True,
    screenshot: str | Path | None = None,
    field_name: str | None = None,
) -> Any:
    """Render contour lines extracted from an axis slice."""
    pv = _require_pyvista()
    slice_mesh = extract_axis_slice(data, axis=axis, value=value)
    scalar_name = resolve_scalar_field(
        slice_mesh,
        scalar_field=scalar_field,
        vector_field=vector_field,
        component=component,
        output_name=output_name,
        field_name=field_name,
    )
    contour_mesh = extract_slice_contours(
        slice_mesh,
        scalar_field=scalar_name,
        n_contours=n_contours,
    )

    pl = pv.Plotter(off_screen=off_screen)
    pl.set_background("white")
    pl.add_mesh(contour_mesh, color=color, line_width=float(line_width))
    pl.add_axes()
    pl.camera_position = "iso"

    if screenshot is not None:
        pl.screenshot(str(screenshot))

    return pl


def generate_transient_video(
    postpro_dir: str | Path,
    output_file: str | Path = "transient.gif",
    *,
    field_name: str = "E",
    hidden_attrs: list[int] | None = None,
    geometry_attrs: dict[int, dict] | None = None,
    cmap: str = "turbo",
    clim_scale: float = 0.6,
    fps: int = 10,
    window_size: tuple[int, int] = (1400, 900),
) -> Path:
    """Generate a 3D field animation from a transient PALACE simulation.

    Uses boundary surface data, hides the air-box/farfield, and overlays
    the antenna geometry as wireframe outlines.

    Parameters
    ----------
    postpro_dir : str | Path
        Path to the simulation postprocessing directory
        (e.g. ``postpro/l_antenna_transient``).
    output_file : str | Path
        Output GIF path.
    field_name : str
        Field to visualize (``"E"``, ``"B"``, ``"S"``, ``"U_e"``, ``"U_m"``).
    hidden_attrs : list[int] | None
        Attribute tags to hide (air-box farfield). Default: ``[8]``.
    geometry_attrs : dict[int, dict] | None
        Attribute tags for geometry overlay with ``name``, ``color``, ``opacity``.
    cmap : str
        Matplotlib colormap name.
    clim_scale : float
        Fraction of global max for colorbar upper limit.
    fps : int
        Frames per second.
    window_size : tuple[int, int]
        Render window size in pixels.

    Returns
    -------
    Path
        Path to the generated GIF.
    """
    import pyvista as pv
    import numpy as np
    from pathlib import Path

    if hidden_attrs is None:
        hidden_attrs = [8]
    if geometry_attrs is None:
        geometry_attrs = {
            3: {"name": "Ground Plane", "color": "#888888", "opacity": 0.3},
            4: {"name": "Patch",        "color": "#cc0000", "opacity": 0.4},
            5: {"name": "Port 1",       "color": "#00cc00", "opacity": 0.6},
            6: {"name": "Port 2",       "color": "#0000cc", "opacity": 0.6},
        }

    out = Path(output_file)
    postpro = Path(postpro_dir)
    paraview_dir = postpro / "paraview"

    # Use boundary dataset (transient_boundary)
    bound_dirs = [d for d in sorted(paraview_dir.glob("*/")) if "boundary" in d.name.lower()]
    base_dir = bound_dirs[0] if bound_dirs else sorted(paraview_dir.glob("*/"))[0]
    cycle_dirs = sorted(base_dir.glob("Cycle*"))
    if not cycle_dirs:
        raise FileNotFoundError(f"No Cycle* directories found in {base_dir}")

    def _find_vtus(cycle_dir: Path) -> list[Path]:
        files = sorted(cycle_dir.glob("proc*.vtu"))
        if not files:
            files = sorted(cycle_dir.glob("*.vtu"))
        if not files:
            files = sorted(cycle_dir.glob("data.pvtu"))
        return files

    # Load first mesh to validate field
    first_files = _find_vtus(cycle_dirs[-1])
    if not first_files:
        raise FileNotFoundError(f"No VTU files found in {cycle_dirs[-1]}")
    ref_mesh = pv.read(str(first_files[0]))
    if field_name not in ref_mesh.array_names:
        for candidate in ["E", "B", "S", "U_e", "U_m"]:
            if candidate in ref_mesh.array_names:
                print(f"Field '{field_name}' not found, using '{candidate}'")
                field_name = candidate
                break

    # Compute global range (sample frames)
    print("Computing global field range (excluding air box)...")
    sample_cycles = cycle_dirs[::max(1, len(cycle_dirs) // 20)]
    if cycle_dirs[-1] not in sample_cycles:
        sample_cycles.append(cycle_dirs[-1])
    global_max = 0.0
    for cdir in sample_cycles:
        files = _find_vtus(cdir)
        if not files:
            continue
        mesh = pv.read(str(files[0]))
        attrs = mesh["attribute"]
        keep = np.ones(mesh.n_cells, dtype=bool)
        for a in hidden_attrs:
            keep &= (attrs != a)
        if not keep.any():
            continue
        filt = mesh.extract_cells(keep)
        fld = filt[field_name]
        mag = np.linalg.norm(fld, axis=1) if fld.ndim > 1 else np.abs(fld)
        global_max = max(global_max, float(mag.max()))
    global_max = global_max or 1.0
    print(f"Global max |{field_name}|: {global_max:.4e}")

    # Extract reference geometry overlay
    geo_parts: dict[int, dict] = {}
    ref_attrs = ref_mesh["attribute"]
    for attr_val, props in geometry_attrs.items():
        mask = ref_attrs == attr_val
        if mask.any():
            geo = ref_mesh.extract_cells(mask)
            edges = geo.extract_feature_edges(
                boundary_edges=True, feature_edges=True, manifold_edges=False
            )
            if edges.n_cells > 0:
                geo_parts[attr_val] = {"mesh": edges, **props}

    # Camera from filtered mesh
    ref_keep = np.ones(ref_mesh.n_cells, dtype=bool)
    for a in hidden_attrs:
        ref_keep &= (ref_mesh["attribute"] != a)
    ref_filt = ref_mesh.extract_cells(ref_keep) if ref_keep.any() else ref_mesh
    bounds = ref_filt.bounds
    cx = (bounds[0] + bounds[1]) / 2
    cy = (bounds[2] + bounds[3]) / 2
    cz = (bounds[4] + bounds[5]) / 2
    dist = max(bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]) * 2.0
    camera_pos = [(cx + dist*0.6, cy - dist*0.5, cz + dist*0.9), (cx, cy, cz), (0, 0, 1)]

    # Render
    n_steps = len(cycle_dirs)
    max_frames = 150
    step = max(1, n_steps // max_frames)
    selected = list(range(0, n_steps, step))
    if selected[-1] != n_steps - 1:
        selected.append(n_steps - 1)

    print(f"Rendering {len(selected)} frames at {fps} fps...")
    plotter = pv.Plotter(off_screen=True, window_size=window_size)
    plotter.set_background("white", top="lightblue")
    plotter.open_gif(str(out), fps=fps)

    for idx in selected:
        cdir = cycle_dirs[idx]
        files = _find_vtus(cdir)
        if not files:
            continue
        mesh = pv.read(str(files[0]))
        attrs = mesh["attribute"]
        keep = np.ones(mesh.n_cells, dtype=bool)
        for a in hidden_attrs:
            keep &= (attrs != a)
        if not keep.any():
            continue
        filt = mesh.extract_cells(keep)
        fld = filt[field_name]
        mag = np.linalg.norm(fld, axis=1) if fld.ndim > 1 else np.abs(fld)
        filt["mag"] = mag

        plotter.clear()
        plotter.add_mesh(
            filt, scalars="mag", cmap=cmap,
            clim=[0, global_max * clim_scale],
            show_edges=False, opacity=1.0,
            scalar_bar_args={
                "title": f"|{field_name}|",
                "title_font_size": 16, "label_font_size": 12,
                "position_x": 0.82, "position_y": 0.15,
                "width": 0.12, "height": 0.6, "fmt": "%.1e",
            },
        )
        for part in geo_parts.values():
            plotter.add_mesh(
                part["mesh"], color="black", line_width=2.0,
                opacity=1.0, label=part["name"],
            )
        plotter.add_text(
            f"Cycle {idx}", position="upper_left",
            font_size=16, color="black",
        )
        plotter.add_text(
            f"L-Antenna |{field_name}|", position="upper_edge",
            font_size=14, color="black",
        )
        plotter.camera_position = camera_pos
        plotter.write_frame()

    plotter.close()
    print(f"Saved: {out.resolve()}")
    return out
