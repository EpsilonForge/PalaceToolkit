"""Visualisation helpers for docs, notebooks, and interactive mesh viewing.

Provides:
  • PyVista mesh builders and standalone HTML export for docs/notebooks.
  • ``view_mesh()`` — interactive per-group coloured PyVista viewer for
    Gmsh ``.msh`` files, with transparency, red-highlight, and automatic
    boundary-face extraction from tetrahedral volume Physical Groups.
  • ``preview()`` — quick mesh-generate-and-view helper.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Styling constants
# ---------------------------------------------------------------------------
COLOR_SURFACE = "#4FC3F7"
COLOR_EDGES = "#263238"
COLOR_METAL = "#B0BEC5"
COLOR_PORT = "#FF7043"
COLOR_DIELECTRIC = "#81C784"
COLOR_AIR = "#E3F2FD"
IMG_SIZE = (700, 500)

# ---------------------------------------------------------------------------
# PyVista helpers
# ---------------------------------------------------------------------------

def _ensure_pyvista():
    """Import PyVista with off-screen rendering (headless-safe)."""
    import warnings

    import pyvista as pv

    pv.OFF_SCREEN = True
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pv.start_xvfb()
    except Exception:
        pass
    return pv


def pv_surface(verts, tris):
    """Build a PyVista PolyData from vertices and triangle connectivity."""
    import pyvista as pv

    faces = np.hstack([np.full((len(tris), 1), 3, dtype=int), tris]).ravel()
    return pv.PolyData(verts, faces)


def pv_volume(verts, tets):
    """Build a PyVista UnstructuredGrid from vertices and tet connectivity."""
    import pyvista as pv

    cells = np.hstack([np.full((len(tets), 1), 4, dtype=int), tets]).ravel()
    ctypes = np.full(len(tets), pv.CellType.TETRA)
    return pv.UnstructuredGrid(cells, ctypes, verts)


def pv_from_meshio(mesh_path: str | Path):
    """Read a Gmsh .msh file via meshio and return PyVista objects by physical group.

    Handles linear and higher-order triangles and quads (surface cells).

    Returns
    -------
    dict : name → pv.PolyData
    """
    import meshio
    import pyvista as pv

    m = meshio.read(str(mesh_path))
    pg_names = {v[0]: k for k, v in m.field_data.items()}
    result: dict[str, pv.PolyData] = {}

    # Surface cell types: use only first N nodes (linear connectivity)
    _surface_info = {
        "triangle": 3, "triangle6": 3, "triangle9": 3, "triangle10": 3,
        "quad": 4, "quad8": 4, "quad9": 4,
    }

    phys = m.cell_data.get("gmsh:physical", [])

    for i, cb in enumerate(m.cells):
        n_corners = _surface_info.get(cb.type)
        if n_corners is None or i >= len(phys):
            continue

        tags = phys[i]
        # Use only corner nodes for visualisation
        corners = cb.data[:, :n_corners]

        for tag in np.unique(tags):
            name = pg_names.get(int(tag), f"group_{tag}")
            mask = tags == tag
            faces = corners[mask]
            pv_faces = np.hstack(
                [np.full((len(faces), 1), n_corners, dtype=int), faces]
            ).ravel()
            if name in result:
                # Merge with existing PolyData for this group
                result[name] = result[name].merge(pv.PolyData(m.points, pv_faces))
            else:
                result[name] = pv.PolyData(m.points, pv_faces)

    return result


# ---------------------------------------------------------------------------
# Render functions → standalone HTML
# ---------------------------------------------------------------------------

def render_mesh(
    mesh,
    filepath: Path,
    title: str = "",
    color: str = COLOR_SURFACE,
    show_edges: bool = True,
):
    """Render a PyVista mesh to a standalone interactive HTML file."""
    pv = _ensure_pyvista()
    pl = pv.Plotter(off_screen=True, window_size=IMG_SIZE)
    pl.set_background("white")
    pl.add_mesh(mesh, color=color, show_edges=False, opacity=0.85)
    if show_edges:
        pl.add_mesh(mesh, style="wireframe", color=COLOR_EDGES, line_width=0.5)
    if title:
        pl.add_title(title, font_size=12, color="black")
    pl.camera.azimuth = 30
    pl.camera.elevation = 20
    pl.reset_camera()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    pl.export_html(str(filepath))
    pl.close()


def render_multi_mesh(
    meshes: dict[str, tuple],
    filepath: Path,
    title: str = "",
):
    """Render multiple named meshes with individual colors to HTML.

    Parameters
    ----------
    meshes : dict
        name → (pv_mesh, color, opacity)
    filepath : Path
        Output .htm file.
    title : str
        Plot title.
    """
    pv = _ensure_pyvista()
    pl = pv.Plotter(off_screen=True, window_size=IMG_SIZE)
    pl.set_background("white")
    for name, (mesh, color, opacity) in meshes.items():
        pl.add_mesh(mesh, color=color, opacity=opacity, label=name)
    if title:
        pl.add_title(title, font_size=12, color="black")
    pl.add_legend()
    pl.camera.azimuth = 30
    pl.camera.elevation = 20
    pl.reset_camera()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    pl.export_html(str(filepath))
    pl.close()


# ---------------------------------------------------------------------------
# Notebook iframe helpers
# ---------------------------------------------------------------------------

def viewer_iframe(src: str | Path, *, width: str | int = "100%", height: int = 500):
    """Return an IPython IFrame for a previously exported HTML viewer.

    This is the recommended notebook/docs display path after calling
    :func:`render_mesh` or :func:`render_multi_mesh`.
    """
    from IPython.display import IFrame

    return IFrame(src=str(src), width=width, height=height)


def show_viewer(name: str, *, prefix: str = "../img"):
    """Deprecated alias for :func:`viewer_iframe`.

    Parameters
    ----------
    name : str
        Basename of the ``.htm`` viewer file.
    prefix : str
        Relative folder path that contains exported viewer files.
    """
    import warnings

    warnings.warn(
        "show_viewer() is deprecated; use viewer_iframe() or IPython.display.IFrame directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return viewer_iframe(f"{prefix}/{name}.htm")


def show_viewers(name_a: str, name_b: str, *, prefix: str = "../img"):
    """Deprecated alias returning two IFrame objects."""
    import warnings

    warnings.warn(
        "show_viewers() is deprecated; create two IFrame objects directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return (
        viewer_iframe(f"{prefix}/{name_a}.htm"),
        viewer_iframe(f"{prefix}/{name_b}.htm"),
    )


def _in_notebook_session() -> bool:
    """Return True when running inside an interactive notebook kernel."""
    try:
        from IPython import get_ipython

        shell = get_ipython()
        if shell is None:
            return False
        return shell.__class__.__name__ == "ZMQInteractiveShell"
    except Exception:
        return False


class _FDCapture:
    """Capture stdout/stderr at the file-descriptor level.

    This is needed to silence C-extension output (like Gmsh's terminal
    printouts), which Python-level ``redirect_stdout`` cannot intercept.
    """

    def __init__(self):
        self._tmp = None
        self._saved_stdout_fd = None
        self._saved_stderr_fd = None

    def __enter__(self):
        import sys
        import tempfile

        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        self._tmp = tempfile.TemporaryFile(mode="w+b")
        # Redirect the real OS-level fds 1 and 2 directly. Under ipykernel,
        # ``sys.stdout`` is a ZMQ-backed stream without a real ``fileno()``,
        # but the underlying fds 1 and 2 are real pipes that the kernel
        # forwards to the client — and that is exactly where C extensions
        # like Gmsh write. Redirecting these fds reliably captures that
        # output regardless of how Python-level streams are wired up.
        self._stdout_fd = 1
        self._stderr_fd = 2
        self._saved_stdout_fd = os.dup(1)
        self._saved_stderr_fd = os.dup(2)
        os.dup2(self._tmp.fileno(), 1)
        os.dup2(self._tmp.fileno(), 2)
        return self

    def text(self) -> str:
        if self._tmp is None:
            return ""
        try:
            self._tmp.flush()
            self._tmp.seek(0)
            return self._tmp.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def __exit__(self, exc_type, exc, tb):
        import sys

        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        if self._saved_stdout_fd is not None:
            os.dup2(self._saved_stdout_fd, self._stdout_fd)
            os.close(self._saved_stdout_fd)
        if self._saved_stderr_fd is not None:
            os.dup2(self._saved_stderr_fd, self._stderr_fd)
            os.close(self._saved_stderr_fd)
        if self._tmp is not None:
            try:
                self._tmp.close()
            except Exception:
                pass


def run_with_scrollable_output(
    func,
    *args,
    title: str = "Mesh generation output",
    max_lines: int | None = 10,
    height_lines: int = 10,
    gmsh_verbosity: int = 2,
    **kwargs,
):
    """Run ``func`` and show its (otherwise verbose) output in a small
    scrollable notebook block.

    The helper:

    * Captures stdout/stderr at the **file-descriptor** level so it also
      catches the output of C extensions such as Gmsh.
    * Optionally lowers ``General.Verbosity`` while ``func`` runs so that
      Gmsh prints fewer "Info" lines in the first place.
    * Truncates the captured text to the last ``max_lines`` lines and
      displays the result inside a fixed-height, scrollable ``<pre>``
      element. The wrapped function's return value is passed through
      unchanged.

    Parameters
    ----------
    func, *args, **kwargs
        Callable and its arguments to execute.
    title
        Header shown above the captured output block.
    max_lines
        Maximum number of lines kept (most recent). ``None`` keeps all.
    height_lines
        Approximate visible height of the scroll block, in lines.
    gmsh_verbosity
        Value forced on ``General.Verbosity`` while ``func`` is running.
        ``2`` keeps only errors and warnings. Set to ``None`` to leave the
        current verbosity untouched.
    """
    import html

    capture = _FDCapture()
    with capture:
        result = func(*args, **kwargs)

    text = capture.text().strip("\n")
    if not text:
        return result

    lines = text.splitlines()
    if max_lines is not None and max_lines > 0 and len(lines) > max_lines:
        hidden = len(lines) - max_lines
        text = f"... {hidden} earlier lines hidden ...\n" + "\n".join(lines[-max_lines:])

    try:
        from IPython.display import HTML, display

        escaped = html.escape(text)
        display(
            HTML(
                (
                    f"<div style='margin:0.75em 0;'>"
                    f"<div style='font-weight:600;margin-bottom:0.25em'>{html.escape(title)}</div>"
                    f"<pre style='max-height:calc({max(5, int(height_lines))} * 1.35em);"
                    "overflow:auto;padding:0.6em;border:1px solid #d0d7de;"
                    "border-radius:6px;background:#f6f8fa;white-space:pre-wrap;"
                    "font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.85em;'>"
                    f"{escaped}</pre></div>"
                )
            )
        )
    except Exception:
        print(text)

    return result


# ---------------------------------------------------------------------------
# Interactive mesh viewer
# ---------------------------------------------------------------------------

# A qualitative palette that deliberately excludes red / warm-red tones.
# Red is reserved exclusively for highlighted (problematic) faces.
_NO_RED_COLORS = [
    "#1f77b4",  # muted blue
    "#2ca02c",  # green
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # grey
    "#bcbd22",  # olive
    "#17becf",  # cyan
    "#ff7f0e",  # orange  (warm but clearly not red)
    "#aec7e8",  # light blue
    "#98df8a",  # light green
    "#c5b0d5",  # light purple
    "#c49c94",  # light brown
    "#f7b6d2",  # light pink
    "#dbdb8d",  # light olive
    "#9edae5",  # light cyan
]


def _strip_json_comments(text: str) -> str:
    """Remove // comments while preserving quoted strings."""
    out: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _shade_color(hex_color: str, *, permittivity=None, conductivity=None) -> str:
    """Return a shade of the base color using εr/σ if available."""
    cond = _safe_float(conductivity)
    eps = _safe_float(permittivity)

    if cond is not None and cond > 0:
        intensity = np.clip(np.log10(1.0 + cond) / 8.0, 0.0, 1.0)
    elif eps is not None:
        intensity = np.clip((eps - 1.0) / 9.0, 0.0, 1.0)
    else:
        intensity = 0.55

    blend_to_white = 0.55 * (1.0 - intensity)
    base = np.array(_hex_to_rgb(hex_color), dtype=float)
    rgb = np.clip(base * (1.0 - blend_to_white) + 255.0 * blend_to_white, 0, 255)
    return _rgb_to_hex(tuple(int(round(v)) for v in rgb))


def _collect_attributes(obj) -> list[int]:
    if isinstance(obj, dict):
        attrs = obj.get("Attributes", [])
    else:
        attrs = []
    if not isinstance(attrs, list):
        return []
    out: list[int] = []
    for a in attrs:
        try:
            out.append(int(a))
        except Exception:
            continue
    return out


def _load_palace_attr_styles(config_filename: str) -> dict[int, dict]:
    """Build per-attribute visual styles from a Palace config.json file."""
    cfg_path = Path(config_filename)
    text = cfg_path.read_text(encoding="utf-8")
    cfg = json.loads(_strip_json_comments(text))

    styles: dict[int, dict] = {}

    materials = cfg.get("Domains", {}).get("Materials", [])
    if isinstance(materials, list):
        for mat in materials:
            if not isinstance(mat, dict):
                continue
            attrs = _collect_attributes(mat)
            eps = mat.get("Permittivity")
            cond = mat.get("Conductivity")
            base = COLOR_AIR if (_safe_float(eps) is not None and _safe_float(eps) <= 1.05) else COLOR_DIELECTRIC
            for a in attrs:
                styles[a] = {
                    "kind": "material",
                    "color": _shade_color(base, permittivity=eps, conductivity=cond),
                    "opacity": 0.45 if base == COLOR_AIR else 0.7,
                }

    boundaries = cfg.get("Boundaries", {})
    if isinstance(boundaries, dict):
        for bname, bdef in boundaries.items():
            key = str(bname).lower()

            if key == "pec":
                if isinstance(bdef, dict):
                    for a in _collect_attributes(bdef):
                        styles[a] = {
                            "kind": "conductor",
                            "color": _shade_color("#b87333", conductivity=5.8e7),
                            "opacity": 1.0,
                        }

            elif key == "absorbing":
                if isinstance(bdef, dict):
                    for a in _collect_attributes(bdef):
                        styles[a] = {
                            "kind": "absorbing",
                            "color": COLOR_AIR,
                            "opacity": 0.12,
                        }

            elif key in ("lumpedport", "waveport"):
                entries = bdef if isinstance(bdef, list) else [bdef]
                for ent in entries:
                    if not isinstance(ent, dict):
                        continue
                    sigma = ent.get("Conductivity")
                    eps = ent.get("Permittivity")
                    for a in _collect_attributes(ent):
                        styles[a] = {
                            "kind": "port",
                            "color": _shade_color("#42A5F5", permittivity=eps, conductivity=sigma),
                            "opacity": 1.0,
                        }

            elif key == "periodic":
                if isinstance(bdef, dict):
                    for pair in bdef.get("BoundaryPairs", []):
                        if not isinstance(pair, dict):
                            continue
                        for field in ("DonorAttributes", "ReceiverAttributes"):
                            vals = pair.get(field, [])
                            if not isinstance(vals, list):
                                continue
                            for a in vals:
                                try:
                                    tag = int(a)
                                except Exception:
                                    continue
                                styles[tag] = {
                                    "kind": "periodic",
                                    "color": "#7E57C2",
                                    "opacity": 0.9,
                                }

    return styles


def _style_for_tag(
    tag: int,
    group_name: str,
    *,
    style_by_attr: dict[int, dict],
    name_to_tag: dict[str, int],
    transparent_groups: list[str],
    fallback_index: int,
) -> dict:
    style = style_by_attr.get(int(tag))

    if style is None and group_name.startswith("Bnd_"):
        parent = group_name[4:]
        parent_tag = name_to_tag.get(parent)
        if parent_tag is not None:
            style = style_by_attr.get(int(parent_tag))

    if style is not None:
        return style

    if group_name in transparent_groups:
        hash_val = int(hashlib.md5(group_name.encode()).hexdigest()[:6], 16)
        color = f"#{hash_val:06x}"
        return {"kind": "transparent", "color": color, "opacity": 0.2}

    return {
        "kind": "default",
        "color": _NO_RED_COLORS[fallback_index % len(_NO_RED_COLORS)],
        "opacity": 1.0,
    }


def _boundary_faces_from_tets(m):
    """Extract boundary triangle faces from tetrahedral volume Physical Groups.

    For every tetrahedral volume group, find the boundary faces (faces that
    are either on the exterior or at the interface between two different
    volume groups) and return them as synthetic triangle cells.

    Interface faces are emitted only once, assigned to the *smaller* volume
    (fewest tetrahedra) so that embedded structures are always visible.

    Uses fully vectorized NumPy operations for speed.

    Returns
    -------
    extra_tri_cells : np.ndarray, shape (N, 3)
    extra_tri_tags  : np.ndarray, shape (N,)
    extra_field_data : dict[str, tuple[int, int]]
        New ``field_data`` entries (name → (tag, dim=2)).
    """
    tag_to_name = {idx: name for name, (idx, dim) in m.field_data.items()}

    # ── Gather all tetrahedra and their volume tags ───────────────────────
    tet_cells_list: list = []
    tet_tags_list:  list = []
    for i, cb in enumerate(m.cells):
        if cb.type in ("tetra", "tetra10"):
            phys = m.cell_data.get("gmsh:physical", [])
            if i < len(phys):
                tet_cells_list.append(cb.data[:, :4])
                tet_tags_list.append(phys[i])

    if not tet_cells_list:
        return np.empty((0, 3), dtype=np.int64), np.empty(0, dtype=np.int32), {}

    all_tets     = np.vstack(tet_cells_list)        # (T, 4)
    all_vol_tags = np.concatenate(tet_tags_list)    # (T,)

    vol_tags_in_tets = set(np.unique(all_vol_tags).tolist())
    print(f"Extracting boundary faces for {len(vol_tags_in_tets)} volume group(s) …")

    # ── Explode every tet into its 4 triangular faces ─────────────────────
    _FACE_IDX = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]])
    faces          = all_tets[:, _FACE_IDX].reshape(-1, 3)   # (4T, 3)
    face_vol_tags  = np.repeat(all_vol_tags, 4)               # (4T,)
    faces_sorted   = np.sort(faces, axis=1)                   # canonical order

    # Encode each face as a single int64 key
    npts      = len(m.points)
    face_keys = (faces_sorted[:, 0].astype(np.int64) * (npts + 1)
                 + faces_sorted[:, 1].astype(np.int64)) * (npts + 1) \
                + faces_sorted[:, 2].astype(np.int64)

    sort_idx      = np.argsort(face_keys)
    face_keys_s   = face_keys[sort_idx]
    face_vol_s    = face_vol_tags[sort_idx]
    faces_sorted_s = faces_sorted[sort_idx]

    uniq_keys, start_idx, counts = np.unique(
        face_keys_s, return_index=True, return_counts=True
    )

    # ── Exterior faces (appear exactly once globally) ─────────────────────
    ext_indices = start_idx[counts == 1]
    ext_tri  = faces_sorted_s[ext_indices]
    ext_tags = face_vol_s[ext_indices]

    # ── Interface faces (appear exactly twice, different volume tags) ──────
    # Assign to the *smaller* volume (fewer tets); lower tag as tiebreaker.
    vol_unique, vol_tet_counts = np.unique(all_vol_tags, return_counts=True)
    vol_count_map = dict(zip(vol_unique.tolist(), vol_tet_counts.tolist()))

    pair_start  = start_idx[counts == 2]
    pair_first  = pair_start
    pair_second = pair_start + 1
    diff_mask   = face_vol_s[pair_first] != face_vol_s[pair_second]
    intf_first  = pair_first[diff_mask]
    intf_second = pair_second[diff_mask]

    if len(intf_first) > 0:
        tag_a = face_vol_s[intf_first]
        tag_b = face_vol_s[intf_second]
        max_tag   = int(max(vol_count_map.keys())) + 1
        count_lut = np.zeros(max_tag + 1, dtype=np.int64)
        for vt, cnt in vol_count_map.items():
            count_lut[vt] = cnt
        count_a = count_lut[tag_a.astype(int)]
        count_b = count_lut[tag_b.astype(int)]
        a_wins      = (count_a < count_b) | ((count_a == count_b) & (tag_a < tag_b))
        winner_idx  = np.where(a_wins, intf_first, intf_second)
        intf_tri  = faces_sorted_s[winner_idx]
        intf_tags = face_vol_s[winner_idx]
    else:
        intf_tri  = np.empty((0, 3), dtype=faces_sorted_s.dtype)
        intf_tags = np.empty(0, dtype=face_vol_s.dtype)

    # ── Combine ───────────────────────────────────────────────────────────
    if len(ext_tri) == 0 and len(intf_tri) == 0:
        return np.empty((0, 3), dtype=np.int64), np.empty(0, dtype=np.int32), {}

    boundary_tri = np.vstack([ext_tri, intf_tri])
    boundary_vol = np.concatenate([ext_tags, intf_tags])

    # ── Assign synthetic surface tags (Bnd_<VolumeName>) ─────────────────
    max_existing = max(
        (idx for _n, (idx, _d) in m.field_data.items()), default=0
    )
    next_tag         = max_existing + 1
    vol_tag_to_synth = {}
    extra_field_data: dict = {}

    for vt in sorted(vol_tags_in_tets):
        vol_name  = tag_to_name.get(vt, str(vt))
        synth_tag = next_tag;  next_tag += 1
        vol_tag_to_synth[vt]          = synth_tag
        extra_field_data[f"Bnd_{vol_name}"] = (synth_tag, 2)

    max_vol = int(boundary_vol.max()) + 1
    lookup  = np.zeros(max_vol + 1, dtype=np.int32)
    for vt, st in vol_tag_to_synth.items():
        lookup[vt] = st
    synth_tags = lookup[boundary_vol.astype(int)]

    for vt in sorted(vol_tags_in_tets):
        vol_name = tag_to_name.get(vt, str(vt))
        st = vol_tag_to_synth[vt]
        n  = int((synth_tags == st).sum())
        print(f"  Bnd_{vol_name} (tag {st}): {n} boundary triangles")

    return boundary_tri.astype(np.int64), synth_tags, extra_field_data


def view_mesh(
    mesh_filename: str = "straight_microstrip.msh",
    palace_config_filename: str | None = None,
    transparent_groups: list[str] | None = None,
    highlight_faces: list[tuple[int, ...]] | None = None,
) -> None:
    """Interactive PyVista viewer for Gmsh ``.msh`` files.

    Renders surface Physical Groups colour-coded by group name.  For meshes
    that only carry tetrahedral volume Physical Groups (no surface triangles),
    boundary faces are automatically extracted so every region is visible.

    Parameters
    ----------
    mesh_filename : str
        Path to the ``.msh`` file.
    palace_config_filename : str | None
        Optional Palace config ``.json`` path. If provided, boundary/material
        attributes are used to select colors and opacities.
    transparent_groups : list[str] | None
        Physical group names to render semi-transparently (opacity = 0.2).
    highlight_faces : list[tuple[int, ...]] | None
        Triangular faces to overlay in solid red.  Each entry must be a
        **sorted** 3-tuple of vertex indices (as produced by
        :func:`palace.verify_topology.analyse_mesh`).
    """
    import meshio

    pv = _ensure_pyvista()

    if transparent_groups is None:
        transparent_groups = ["air_none", "air_plastic_enclosure"]
    highlight_faces_set = set(highlight_faces) if highlight_faces else set()

    print(f"Loading mesh file: {mesh_filename}")
    if transparent_groups:
        print(f"Groups to render transparent: {transparent_groups}")
    if palace_config_filename:
        print(f"Using Palace config styles from: {palace_config_filename}")
    if highlight_faces_set:
        print(f"Faces to highlight in red: {len(highlight_faces_set)}")

    style_by_attr: dict[int, dict] = {}
    if palace_config_filename:
        try:
            style_by_attr = _load_palace_attr_styles(palace_config_filename)
            print(f"Loaded style mapping for {len(style_by_attr)} attribute(s)")
        except Exception as exc:
            print(f"Warning: could not parse Palace config '{palace_config_filename}': {exc}")
            style_by_attr = {}

    m = meshio.read(mesh_filename)
    print(f"Mesh loaded successfully with {len(m.cells)} cell blocks")

    # ── Collect existing triangle cells ───────────────────────────────────
    triangle_cells_list: list = []
    triangle_tags_list:  list = []
    found_triangles = False

    phys = m.cell_data.get("gmsh:physical", [])
    for i, cb in enumerate(m.cells):
        block_tags = (
            np.asarray(phys[i], dtype=int)
            if i < len(phys)
            else np.full(len(cb.data), -1, dtype=int)
        )

        if "triangle" in cb.type:
            found_triangles = True
            triangle_cells_list.append(cb.data[:, :3])
            triangle_tags_list.append(block_tags)
            continue

        if "quad" in cb.type:
            # Triangulate quads so mixed triangle/quad surface meshes are visible.
            found_triangles = True
            quad = cb.data[:, :4]
            tri_a = quad[:, [0, 1, 2]]
            tri_b = quad[:, [0, 2, 3]]
            triangle_cells_list.append(np.vstack([tri_a, tri_b]))
            triangle_tags_list.append(np.repeat(block_tags, 2))

    if not found_triangles:
        print("No triangle cells found in the mesh.")

        # ── Synthesise boundary surfaces from tet volumes ─────────────────────
        if any(cb.type in ("tetra", "tetra10") for cb in m.cells):
            extra_tri, extra_tags, extra_fd = _boundary_faces_from_tets(m)
            if len(extra_tri) > 0:
                triangle_cells_list.append(extra_tri)
                triangle_tags_list.append(extra_tags)
                m.field_data.update(extra_fd)
                found_triangles = True
                print(f"Added {len(extra_tri)} synthetic boundary triangles "
                    f"from {len(extra_fd)} volume group(s)")

    if not found_triangles:
        raise RuntimeError("No triangle or tetrahedron cells found in the mesh.")

    triangle_cells = np.vstack(triangle_cells_list)
    triangle_tags  = np.concatenate(triangle_tags_list)
    print(f"Found {len(triangle_cells)} triangles total")

    # ── Build PyVista UnstructuredGrid ────────────────────────────────────
    tri_face_keys = [tuple(sorted(int(n) for n in tri)) for tri in triangle_cells]
    n_tri    = triangle_cells.shape[0]
    cells_pv = np.hstack([np.full((n_tri, 1), 3), triangle_cells]).astype(np.int64).flatten()
    celltypes = np.full(n_tri, pv.CellType.TRIANGLE, dtype=np.uint8)
    grid = pv.UnstructuredGrid(cells_pv, celltypes, m.points)
    grid.cell_data["physical_group"] = triangle_tags

    tag_to_name = {idx: name for name, (idx, dim) in m.field_data.items()}
    unique_tags = np.unique(triangle_tags)
    print("Physical group tags in mesh:",
          dict(zip(unique_tags.tolist(),
                   [tag_to_name.get(t, str(t)) for t in unique_tags])))

    # ── Highlight mask ────────────────────────────────────────────────────
    highlight_mask = np.zeros(n_tri, dtype=bool)
    if highlight_faces_set:
        for i, key in enumerate(tri_face_keys):
            if key in highlight_faces_set:
                highlight_mask[i] = True
        print(f"Matched {int(highlight_mask.sum())} triangles for red highlighting")

    # ── Plotter ───────────────────────────────────────────────────────────
    in_notebook = _in_notebook_session()
    # When running inside a notebook (interactive or papermill), use the
    # off-screen renderer so screenshots/static backend produce reliable
    # output across CI, docs builds, and headless servers.
    plotter = pv.Plotter(
        notebook=in_notebook,
        off_screen=in_notebook or bool(os.environ.get("DOCS_BUILD")),
        window_size=list(IMG_SIZE),
    )

    name_to_tag = {name: int(tag) for name, (tag, _dim) in m.field_data.items()}
    fallback_idx = 0
    have_legend_items = False

    for tag in unique_tags:
        group_name = tag_to_name.get(int(tag), str(tag))
        group_mask = (triangle_tags == tag) & ~highlight_mask
        if not np.any(group_mask):
            continue

        style = _style_for_tag(
            int(tag),
            group_name,
            style_by_attr=style_by_attr,
            name_to_tag=name_to_tag,
            transparent_groups=transparent_groups,
            fallback_index=fallback_idx,
        )
        fallback_idx += 1

        legend_label = f"{group_name} ({int(tag)})"
        plotter.add_mesh(
            grid.extract_cells(np.where(group_mask)[0]),
            color=style["color"],
            show_edges=True,
            edge_color=style["color"],
            line_width=0.6,
            opacity=float(style["opacity"]),
            label=legend_label,
        )
        have_legend_items = True

    if np.any(highlight_mask):
        plotter.add_mesh(
            grid.extract_cells(np.where(highlight_mask)[0]),
            color="#e31a1c",
            show_edges=True,
            edge_color="#b71c1c",
            line_width=2,
            opacity=1.0,
            label="⚠ Duplicate faces",
        )
        have_legend_items = True

    if have_legend_items:
        plotter.add_legend(bcolor="white", face="triangle", size=(0.28, 0.28))

    plotter.show_axes()
    plotter.camera.azimuth = 30
    plotter.camera.elevation = 20
    plotter.reset_camera()

    # Rendering strategy (mirrors the dolfinx-tutorial pattern):
    #   * In a notebook kernel, render a static PNG screenshot directly into
    #     the cell output via ``jupyter_backend="static"``. This is the only
    #     mode that survives papermill execution + MkDocs rendering, so the
    #     mesh is *always* visible in the published docs.
    #   * In a plain Python script with a display, fall back to the regular
    #     interactive window.
    #   * In headless scripts, dump a PNG next to the working directory.
    if in_notebook:
        try:
            from IPython.display import Image, display

            img_dir = Path("img")
            img_dir.mkdir(parents=True, exist_ok=True)
            out_file = img_dir / f"view_mesh_{int(time.time() * 1000)}.png"
            plotter.screenshot(str(out_file), window_size=list(IMG_SIZE))
            plotter.close()
            display(Image(filename=str(out_file)))
            return
        except Exception as exc:
            print(f"Mesh PNG render failed ({exc}).")
            try:
                plotter.close()
            except Exception:
                pass
            return

    try:
        plotter.show()
    except Exception as exc:
        print(f"Interactive render failed ({exc}); writing PNG screenshot instead.")
        img_dir = Path("img")
        img_dir.mkdir(parents=True, exist_ok=True)
        out_file = img_dir / f"view_mesh_{int(time.time())}.png"
        try:
            plotter.screenshot(str(out_file), window_size=list(IMG_SIZE))
            print(f"Mesh screenshot saved to: {out_file}")
        finally:
            plotter.close()


def preview() -> None:
    """Generate a mesh (via :func:`palace.mesh.generate_and_save_mesh`) and
    immediately open it in the interactive viewer."""
    from palacetoolkit.mesh import generate_and_save_mesh

    print("\nGenerating mesh preview…")
    ts        = int(time.time())
    file_name = f"temp_preview_{ts}"
    try:
        generated = generate_and_save_mesh(f"meshes/{file_name}")
        if generated:
            print(f"✓ Mesh generated: meshes/{file_name}.msh")
        else:
            print("✗ Mesh generation failed")
    except Exception as exc:
        print(f"✗ Mesh generation error: {exc}")
        generated = False

    if generated:
        mesh_file = f"meshes/{file_name}.msh"
        print(f"Opening viewer for {mesh_file}")
        try:
            view_mesh(mesh_filename=mesh_file)
        except Exception as exc:
            print(f"Could not open mesh viewer: {exc}")
        if os.path.exists(mesh_file):
            print(f"Temporary mesh file saved as: {mesh_file}")
