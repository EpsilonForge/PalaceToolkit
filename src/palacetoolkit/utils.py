"""General helpers shared by notebooks and examples."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import meshio
import numpy as np


def write_and_finalize_gmsh(filename: str | None = None, prefix: str = "mesh_") -> str:
    """Write current gmsh model as ASCII v2.2 and finalize gmsh.

    Parameters
    ----------
    filename : str | None
        Output file path. If None, a temporary ``.msh`` file is created.
    prefix : str
        Temporary-file prefix when *filename* is None.

    Returns
    -------
    str
        Absolute path of the written mesh file.
    """
    import gmsh

    if filename is None:
        fd, filename = tempfile.mkstemp(suffix=".msh", prefix=prefix)
        os.close(fd)

    mesh_path = str(Path(filename).resolve())
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.Binary", 0)
    gmsh.write(mesh_path)
    gmsh.finalize()
    return mesh_path


def _cell_edge_keys(cell_type: str, conn_row: np.ndarray) -> list[tuple[int, int]]:
    """Return canonical edge keys for one 2D cell connectivity row."""
    if cell_type.startswith("triangle"):
        c = [int(conn_row[0]), int(conn_row[1]), int(conn_row[2])]
        pairs = [(c[0], c[1]), (c[1], c[2]), (c[2], c[0])]
    elif cell_type.startswith("quad"):
        c = [int(conn_row[0]), int(conn_row[1]), int(conn_row[2]), int(conn_row[3])]
        pairs = [(c[0], c[1]), (c[1], c[2]), (c[2], c[3]), (c[3], c[0])]
    else:
        return []
    return [tuple(sorted(p)) for p in pairs]


def _eps_to_scalar(val) -> float:
    """Map a scalar/tensor permittivity specification to one scalar value."""
    arr = np.asarray(val, dtype=float)
    if arr.ndim == 0:
        return float(arr)
    if arr.shape == (2, 2):
        return float(0.5 * (arr[0, 0] + arr[1, 1]))
    if arr.shape == (3, 3):
        return float((arr[0, 0] + arr[1, 1] + arr[2, 2]) / 3.0)
    return float(np.mean(arr))


def _normalise_eps_map(eps) -> dict[int, float]:
    """Convert *eps* input to a dict[attr -> scalar eps]."""
    if eps is None:
        return {}
    if isinstance(eps, dict):
        out = {}
        for k, v in eps.items():
            try:
                out[int(k)] = _eps_to_scalar(v)
            except Exception:
                continue
        return out
    return {}


def _read_line_groups(mesh_file: str):
    """Read 1D physical groups and adjacency to 2D material attributes."""
    m = meshio.read(mesh_file)

    line_tag_to_name = {}
    surf_tag_to_name = {}
    for name, value in m.field_data.items():
        tag = int(value[0])
        dim = int(value[1])
        if dim == 1:
            line_tag_to_name[tag] = name
        elif dim == 2:
            surf_tag_to_name[tag] = name

    # Build edge -> adjacent surface physical tags.
    edge_to_surface_attrs: dict[tuple[int, int], set[int]] = {}
    phys = m.cell_data.get("gmsh:physical", [])
    for i, cb in enumerate(m.cells):
        if not (cb.type.startswith("triangle") or cb.type.startswith("quad")):
            continue
        if i >= len(phys):
            continue
        surf_tags = phys[i]
        for k, sattr in enumerate(surf_tags):
            for edge in _cell_edge_keys(cb.type, cb.data[k]):
                edge_to_surface_attrs.setdefault(edge, set()).add(int(sattr))

    groups = {}
    for i, cb in enumerate(m.cells):
        if cb.type not in ("line", "line3", "line4", "line5"):
            continue
        if i >= len(phys):
            continue

        tags = phys[i]
        for k, tag in enumerate(tags):
            bdr_attr = int(tag)
            name = line_tag_to_name.get(bdr_attr, f"line_group_{bdr_attr}")
            # Use end points only; this is robust for higher-order line cells.
            n0 = int(cb.data[k, 0])
            n1 = int(cb.data[k, -1])
            p0 = m.points[n0, :2]
            p1 = m.points[n1, :2]
            edge = tuple(sorted((n0, n1)))
            surf_attrs = edge_to_surface_attrs.get(edge, set())
            groups.setdefault(bdr_attr, {
                "name": name,
                "segments": [],
                "surface_attrs": set(),
            })
            groups[bdr_attr]["segments"].append((p0, p1))
            groups[bdr_attr]["surface_attrs"].update(surf_attrs)

    # Convert sets to sorted lists for deterministic ordering.
    out = {}
    for bdr_attr, info in groups.items():
        out[bdr_attr] = {
            "name": info["name"],
            "segments": info["segments"],
            "surface_attrs": sorted(info["surface_attrs"]),
            "surface_names": [surf_tag_to_name.get(a, f"surface_{a}") for a in sorted(info["surface_attrs"])],
        }
    return out


def view_fe_mesh_2d(
    mesh_file: str,
    eps=None,
    title: str = "2D FE Mesh and Materials",
    show_edges: bool = True,
):
    """Plot a 2D FE mesh colored by material physical groups.

    Parameters
    ----------
    mesh_file : str
        Path to a Gmsh mesh file.
    eps : dict or None
        Optional mapping ``material_attr -> permittivity``. If provided,
        materials are colored by permittivity. Otherwise, they are colored
        by material attribute id.
    title : str
        Figure title.
    show_edges : bool
        If True, draw FE element edges.
    """
    m = meshio.read(mesh_file)
    eps_map = _normalise_eps_map(eps)

    surf_tag_to_name = {}
    for name, value in m.field_data.items():
        tag = int(value[0])
        dim = int(value[1])
        if dim == 2:
            surf_tag_to_name[tag] = name

    phys = m.cell_data.get("gmsh:physical", [])
    tri_conn = []
    tri_attr = []

    for i, cb in enumerate(m.cells):
        if i >= len(phys):
            continue

        attrs = phys[i]
        ctype = cb.type
        if ctype.startswith("triangle"):
            for k, attr in enumerate(attrs):
                tri = [int(cb.data[k, 0]), int(cb.data[k, 1]), int(cb.data[k, 2])]
                tri_conn.append(tri)
                tri_attr.append(int(attr))
        elif ctype.startswith("quad"):
            for k, attr in enumerate(attrs):
                q = [int(cb.data[k, 0]), int(cb.data[k, 1]), int(cb.data[k, 2]), int(cb.data[k, 3])]
                tri_conn.append([q[0], q[1], q[2]])
                tri_conn.append([q[0], q[2], q[3]])
                a = int(attr)
                tri_attr.extend([a, a])

    if not tri_conn:
        raise ValueError("No 2D elements found in mesh for FE material view")

    tri_conn = np.asarray(tri_conn, dtype=int)
    tri_attr = np.asarray(tri_attr, dtype=int)
    pts = np.asarray(m.points[:, :2], dtype=float)

    use_eps = bool(eps_map)
    if use_eps:
        face_values = np.asarray([eps_map.get(a, np.nan) for a in tri_attr], dtype=float)
        finite_vals = face_values[np.isfinite(face_values)]
        if finite_vals.size == 0:
            use_eps = False

    if not use_eps:
        face_values = tri_attr.astype(float)

    fig, ax = plt.subplots(figsize=(8, 4))
    edge_color = "k" if show_edges else "none"
    lw = 0.22 if show_edges else 0.0

    cmap = "viridis" if use_eps else "tab20"
    tpc = ax.tripcolor(
        pts[:, 0],
        pts[:, 1],
        tri_conn,
        facecolors=face_values,
        shading="flat",
        cmap=cmap,
        edgecolors=edge_color,
        linewidth=lw,
    )

    cb = fig.colorbar(tpc, ax=ax, fraction=0.046)
    cb.set_label("eps" if use_eps else "material attribute")

    unique_attrs = sorted(set(int(a) for a in tri_attr))
    legend_lines = []
    for a in unique_attrs:
        name = surf_tag_to_name.get(a, f"material_{a}")
        if use_eps and a in eps_map:
            legend_lines.append(f"{a}: {name} (eps={eps_map[a]:.4g})")
        else:
            legend_lines.append(f"{a}: {name}")

    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal")
    ax.set_xlim(np.min(pts[:, 0]), np.max(pts[:, 0]))
    ax.set_ylim(np.min(pts[:, 1]), np.max(pts[:, 1]))

    if legend_lines:
        text = "Materials\n" + "\n".join(legend_lines)
        ax.text(
            0.01,
            0.99,
            text,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "0.7"},
        )

    plt.tight_layout()
    plt.show()


def _plot_boundary_overlays(ax, line_groups, eps=None, pec_bdr="all"):
    """Overlay boundary physical groups using eps- and PEC-aware styling."""
    eps_map = _normalise_eps_map(eps)

    if pec_bdr == "all":
        pec_set = set(line_groups.keys())
    else:
        pec_set = {int(a) for a in pec_bdr}

    # Build eps range used for non-PEC color mapping.
    eps_vals = [v for v in eps_map.values() if np.isfinite(v)]
    if eps_vals:
        eps_min = min(eps_vals)
        eps_max = max(eps_vals)
    else:
        eps_min = 1.0
        eps_max = 1.0

    cmap = plt.get_cmap("viridis")

    def _eps_color(eps_value: float) -> tuple[float, float, float, float]:
        if eps_max <= eps_min + 1e-15:
            t = 0.5
        else:
            t = (eps_value - eps_min) / (eps_max - eps_min)
        return cmap(float(np.clip(t, 0.0, 1.0)))

    legend_handles = []

    for bdr_attr in sorted(line_groups.keys()):
        info = line_groups[bdr_attr]
        name = info["name"]
        segs = info["segments"]
        sattrs = info["surface_attrs"]

        is_pec = bdr_attr in pec_set
        if is_pec:
            color = "white"
            lw = 2.2
            ls = "-"
            label = f"{name} (PEC)"
        else:
            s_eps = [eps_map[a] for a in sattrs if a in eps_map]
            eps_local = float(np.mean(s_eps)) if s_eps else eps_min
            color = _eps_color(eps_local)
            lw = 1.2
            ls = ":"
            if s_eps:
                label = f"{name} (eps~{eps_local:.3g})"
            else:
                label = name

        first = True
        for p0, p1 in segs:
            handle = ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=color, linewidth=lw, linestyle=ls,
                             label=(label if first else None))[0]
            if first:
                legend_handles.append(handle)
                first = False

    return legend_handles


def view_fields_2d(
    solver,
    results: dict,
    mesh_file: str,
    eps=None,
    pec_bdr="all",
    include_streamplot: bool = False,
    streamplot_density: float = 1.2,
    streamplot_linewidth: float = 0.8,
    streamplot_arrowsize: float = 0.9,
    streamplot_show_arrows: bool = True,
    streamplot_normalize: bool = False,
    streamplot_seed_from_field: bool = True,
    streamplot_seed_frac: float = 0.2,
    streamplot_seed_stride: int = 3,
    streamplot_mask_weak: bool = True,
    streamplot_min_frac: float = 0.08,
    num_modes: int = 3,
    nx: int = 80,
    ny: int = 60,
    cmap: str = "hot",
    title: str = "2D Mode Fields",
):
    """Plot |Et| and |En| from precomputed 2D eigenmode results.

    This function reuses ``results['eigenvectors_raw']`` and ``results['kn']``
    and does not call the solver again.
    """
    if "eigenvectors_raw" not in results or "kn" not in results:
        raise ValueError("results must contain 'eigenvectors_raw' and 'kn'")

    n_plot = min(num_modes, len(results["kn"]))
    if n_plot <= 0:
        raise ValueError("No modes available to plot")

    line_groups = _read_line_groups(mesh_file)

    fig, axes = plt.subplots(2, n_plot, figsize=(5 * n_plot, 8))
    if n_plot == 1:
        axes = axes.reshape(2, 1)

    fig.suptitle(title, fontsize=14)

    for mode_i in range(n_plot):
        e_vec = results["eigenvectors_raw"][:, mode_i]
        kn_mode = results["kn"][mode_i]

        et = e_vec[:solver.nd_size]
        en = e_vec[solver.nd_size:]
        en_phys = en / (1j * kn_mode)

        X, Y, Ex, Ey, Ez = solver.get_field_on_grid(et, en_phys, nx=nx, ny=ny)
        Et_mag = np.sqrt(np.abs(Ex) ** 2 + np.abs(Ey) ** 2)
        En_mag = np.abs(Ez)

        ax_t = axes[0, mode_i]
        im_t = ax_t.pcolormesh(X, Y, Et_mag, cmap=cmap, shading="auto")
        handles_t = _plot_boundary_overlays(ax_t, line_groups, eps=eps, pec_bdr=pec_bdr)
        if include_streamplot:
            # For complex eigenmodes, raw Re{E} depends on arbitrary global phase.
            # Phase-lock first, then optionally normalise to emphasize topology.
            phi_ref = np.angle(np.nansum(Ex) + 1j * np.nansum(Ey))
            Ex_q = np.real(Ex * np.exp(-1j * phi_ref))
            Ey_q = np.real(Ey * np.exp(-1j * phi_ref))

            mag_raw = np.sqrt(Ex_q ** 2 + Ey_q ** 2)
            if streamplot_mask_weak:
                mref = np.nanmax(mag_raw)
                if np.isfinite(mref) and mref > 0:
                    weak = mag_raw < (streamplot_min_frac * mref)
                    Ex_q = np.where(weak, np.nan, Ex_q)
                    Ey_q = np.where(weak, np.nan, Ey_q)

            if streamplot_normalize:
                mag_q = np.sqrt(Ex_q ** 2 + Ey_q ** 2)
                Ex_q = Ex_q / (mag_q + 1e-14)
                Ey_q = Ey_q / (mag_q + 1e-14)

            # Keep streamlines in low-field regions (e.g. air) by not masking.
            u = np.nan_to_num(Ex_q, nan=0.0)
            v = np.nan_to_num(Ey_q, nan=0.0)
            arrowstyle = "-|>" if streamplot_show_arrows else "-"
            arrowsize = streamplot_arrowsize if streamplot_show_arrows else 1e-6
            stream_kwargs = {
                "x": X[0, :],
                "y": Y[:, 0],
                "u": u,
                "v": v,
                "color": "white",
                "density": streamplot_density,
                "linewidth": streamplot_linewidth,
                "arrowsize": arrowsize,
                "arrowstyle": arrowstyle,
                "minlength": 0.1,
                "integration_direction": "both",
            }

            if streamplot_seed_from_field:
                mag = np.sqrt(u ** 2 + v ** 2)
                y_profile = np.nanmean(mag, axis=1)
                if np.any(np.isfinite(y_profile)):
                    iy = int(np.nanargmax(y_profile))
                    mline = mag[iy, :]
                    mmax = np.nanmax(mline)
                    if np.isfinite(mmax) and mmax > 0:
                        mask = mline >= (streamplot_seed_frac * mmax)
                        idx = np.where(mask)[0][::max(1, int(streamplot_seed_stride))]
                        if idx.size >= 2:
                            start_points = np.column_stack([X[iy, idx], Y[iy, idx]])
                            stream_kwargs["start_points"] = start_points

            ax_t.streamplot(**stream_kwargs)
        ax_t.set_title(f"|Et| mode {mode_i + 1}")
        ax_t.set_aspect("equal")
        if mode_i == 0 and handles_t:
            ax_t.legend(loc="upper right", fontsize=8)
        fig.colorbar(im_t, ax=ax_t, fraction=0.046)

        ax_n = axes[1, mode_i]
        im_n = ax_n.pcolormesh(X, Y, En_mag, cmap=cmap, shading="auto")
        _plot_boundary_overlays(ax_n, line_groups, eps=eps, pec_bdr=pec_bdr)
        ax_n.set_title(f"|En| mode {mode_i + 1}")
        ax_n.set_aspect("equal")
        fig.colorbar(im_n, ax=ax_n, fraction=0.046)

    plt.tight_layout()
    plt.show()
