#!/usr/bin/env python3
"""
Verify the topological consistency of a 3D tetrahedral mesh for Palace / MFEM.

A valid finite-element mesh requires a well-defined relationship between the
set of volume-element faces and the set of boundary elements.  Specifically,
the map  ``b : B → F``  from boundary elements to volume faces must be:

  1. **Total** — every boundary element must map to an existing volume face.
  2. **Injective** — no two boundary elements may map to the same volume face
     (unless the face is periodic).

Violation of (1) causes::

    MFEM abort: (r,c,f) = (A, B, C)

Violation of (2) causes::

    A non-periodic face cannot have multiple boundary elements!

This script checks both invariants from a single pass over the mesh and
produces a unified report.  When problems are found, offending faces are
optionally visualised in red using PyVista (via ``view_mesh``).

Usage
-----
    python verify_topology.py <mesh.msh> [palace_config.json] [--no-view]

Requirements: meshio, numpy
Optional:     pyvista (for visualisation), Palace JSON config (for periodic
              vertex identification and BC attribute cross-check).
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import meshio
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CANONICAL FACE MAP — the shared abstraction
# ═══════════════════════════════════════════════════════════════════════════════

def canonical_face(nodes) -> tuple[int, ...]:
    """Canonical (sorted) representation of a face defined by vertex indices.

    This is the operation that both ``STable3D::Push`` (via ``Sort3``) and
    the duplicate-boundary checker perform.  Sorting makes the representation
    independent of vertex ordering so that two faces sharing the same vertices
    always compare equal.
    """
    return tuple(sorted(int(n) for n in nodes))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MESH LOADING (meshio-based, works without MFEM Python bindings)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_mesh(
    mesh_path: str | Path,
) -> tuple[np.ndarray, np.ndarray, list[int], list[tuple[int, ...]], list[int], dict[int, str]]:
    """Read a Gmsh .msh file and return the raw arrays needed for both checks.

    Returns
    -------
    points : (N, 3) float array
    all_tets : (T, 4) int array — volume element connectivity
    tet_attrs : list[int] — physical-group tag per tet
    tri_nodes : list[tuple[int, ...]] — boundary triangle node tuples
    tri_attrs : list[int] — physical-group tag per boundary triangle
    pg_names : {tag: name} — physical-group name map
    """
    m = meshio.read(str(mesh_path))

    pg_names: dict[int, str] = {}
    for name, (tag, _dim) in (m.field_data or {}).items():
        pg_names[int(tag)] = name

    tet_cells: list[np.ndarray] = []
    tet_attrs: list[int] = []
    tri_nodes: list[tuple[int, ...]] = []
    tri_attrs: list[int] = []

    for i, cb in enumerate(m.cells):
        phys = m.cell_data["gmsh:physical"][i]
        if cb.type == "tetra":
            tet_cells.append(cb.data)
            tet_attrs.extend(int(p) for p in phys)
        elif cb.type == "triangle":
            for j, tri in enumerate(cb.data):
                tri_nodes.append(tuple(int(n) for n in tri))
                tri_attrs.append(int(phys[j]))

    all_tets = np.vstack(tet_cells) if tet_cells else np.empty((0, 4), dtype=int)
    return m.points, all_tets, tet_attrs, tri_nodes, tri_attrs, pg_names


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BUILD THE FACE → BOUNDARY MAP  (the single shared computation)
# ═══════════════════════════════════════════════════════════════════════════════

def build_face_boundary_map(
    all_tets: np.ndarray,
    tet_attrs: list[int],
    tri_nodes: list[tuple[int, ...]],
    tri_attrs: list[int],
    pg_names: dict[int, str],
    vert_map: dict[int, int] | None = None,
) -> dict:
    """Core routine: build the face→boundary-element map and diagnose both
    invariant violations in a single pass.

    Parameters
    ----------
    all_tets : (T, 4) int array
    tet_attrs : per-tet physical tag
    tri_nodes : per-boundary-triangle node tuples (original indices)
    tri_attrs : per-boundary-triangle physical tag
    pg_names : tag→name map
    vert_map : optional vertex identification map for periodic meshes
               ({receiver_vertex: donor_vertex})

    Returns
    -------
    dict with keys:
        face_to_tets      — {canonical_face: [tet_indices]}
        face_to_bdr_elems — {canonical_face: [entry_dicts]}
        orphans           — list of orphan boundary elements (violate totality)
        duplicates        — list of duplicate-face info dicts (violate injectivity)
        n_volume_faces    — number of unique volume faces
        n_internal_faces  — faces shared by exactly 2 tets
        n_skin_faces      — faces belonging to exactly 1 tet
    """
    vm = vert_map or {}

    def _map_node(n: int) -> int:
        return vm.get(n, n)

    # ── Build volume-face set ─────────────────────────────────────────────
    face_to_tets: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for tet_idx, tet in enumerate(all_tets):
        mapped = sorted(_map_node(int(n)) for n in tet)
        for combo in combinations(mapped, 3):
            face_to_tets[combo].append(tet_idx)

    n_internal = sum(1 for t in face_to_tets.values() if len(t) == 2)
    n_skin = sum(1 for t in face_to_tets.values() if len(t) == 1)

    # ── Map boundary elements onto volume faces ──────────────────────────
    face_to_bdr: dict[tuple[int, ...], list[dict]] = defaultdict(list)
    orphans: list[dict] = []

    for idx, (tri_raw, attr) in enumerate(zip(tri_nodes, tri_attrs)):
        mapped_face = canonical_face(_map_node(int(n)) for n in tri_raw)
        entry = {
            "tri_index": idx,
            "attribute": attr,
            "pg_name": pg_names.get(attr, f"attr_{attr}"),
            "original_nodes": canonical_face(tri_raw),
        }
        if mapped_face not in face_to_tets:
            # ── INVARIANT 1 VIOLATION: orphan boundary face ──────────
            entry["mapped_face"] = mapped_face
            orphans.append(entry)
        else:
            face_to_bdr[mapped_face].append(entry)

    # ── Find duplicate boundary faces (injectivity violation) ────────────
    duplicates: list[dict] = []
    for face, entries in face_to_bdr.items():
        if len(entries) <= 1:
            continue
        tet_idxs = face_to_tets.get(face, [])
        vol_attrs = [tet_attrs[t] for t in tet_idxs if t < len(tet_attrs)]
        duplicates.append({
            "face_nodes": face,
            "n_bdr_elems": len(entries),
            "boundary_elements": entries,
            "is_internal_face": len(tet_idxs) == 2,
            "tet_indices": tet_idxs,
            "tet_volume_attrs": vol_attrs,
        })

    return {
        "face_to_tets": face_to_tets,
        "face_to_bdr_elems": face_to_bdr,
        "orphans": orphans,
        "duplicates": duplicates,
        "n_volume_faces": len(face_to_tets),
        "n_internal_faces": n_internal,
        "n_skin_faces": n_skin,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PERIODIC VERTEX IDENTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def build_periodic_vertex_map(
    points: np.ndarray,
    config_path: str | Path | None,
) -> dict[int, int]:
    """Build a vertex identification map from periodic BC in a Palace config.

    When MFEM calls ``MakePeriodic`` it merges vertices on periodic faces.
    Two boundary triangles that look distinct in Gmsh may become the *same*
    face after this merge.

    Returns ``{v_receiver: v_donor}``; empty dict if no periodic BC.
    """
    if config_path is None:
        return {}

    with open(config_path) as f:
        cfg = json.load(f)

    periodic = cfg.get("Boundaries", {}).get("Periodic", {})
    if not periodic:
        return {}

    fwv = periodic.get("FloquetWaveVector", [0, 0, 0])
    axis = int(np.argmax(np.abs(fwv)))

    xmin, xmax = points[:, axis].min(), points[:, axis].max()
    period_length = xmax - xmin
    if period_length < 1e-12:
        return {}

    translation = np.zeros(3)
    translation[axis] = period_length
    tol = period_length * 1e-6

    coord_to_idx: dict[tuple, int] = {}
    for i, pt in enumerate(points):
        key = tuple(np.round(pt / tol).astype(int))
        coord_to_idx[key] = i

    vert_map: dict[int, int] = {}
    for i, pt in enumerate(points):
        donor_pt = pt - translation
        key = tuple(np.round(donor_pt / tol).astype(int))
        j = coord_to_idx.get(key)
        if j is not None and j != i:
            vert_map[i] = j

    return vert_map


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PALACE CONFIG HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_config_bc_attrs(config_path: str | Path) -> dict[str, list[int]]:
    """Extract boundary-condition attribute lists from a Palace JSON config."""
    with open(config_path) as f:
        cfg = json.load(f)
    bcs: dict[str, list[int]] = {}
    boundaries = cfg.get("Boundaries", {})
    for bc_name in ("PEC", "Absorbing", "Impedance", "Conductivity"):
        section = boundaries.get(bc_name, {})
        attrs = section.get("Attributes", [])
        if attrs:
            bcs[bc_name] = attrs
    periodic = boundaries.get("Periodic", {})
    for pair in periodic.get("BoundaryPairs", []):
        bcs.setdefault("Periodic (Donor)", []).extend(
            pair.get("DonorAttributes", [])
        )
        bcs.setdefault("Periodic (Receiver)", []).extend(
            pair.get("ReceiverAttributes", [])
        )
    for wp_key in ("WavePort", "WavePortBC"):
        for wp in boundaries.get(wp_key, []):
            bcs.setdefault("WavePort", []).extend(wp.get("Attributes", []))
    return bcs


# ═══════════════════════════════════════════════════════════════════════════════
# 6. FULL ANALYSIS — runs both passes
# ═══════════════════════════════════════════════════════════════════════════════

def verify(
    mesh_path: str | Path,
    config_path: str | Path | None = None,
) -> dict:
    """Run the complete topological verification on a mesh file.

    Returns a single result dict with all information from both passes.
    """
    points, all_tets, tet_attrs, tri_nodes, tri_attrs, pg_names = _load_mesh(
        mesh_path
    )

    # ── Pass 1: raw vertex indices ────────────────────────────────────────
    raw = build_face_boundary_map(
        all_tets, tet_attrs, tri_nodes, tri_attrs, pg_names
    )

    # ── Pass 2: after periodic vertex identification ──────────────────────
    vert_map = build_periodic_vertex_map(points, config_path)
    periodic = None
    if vert_map:
        periodic = build_face_boundary_map(
            all_tets, tet_attrs, tri_nodes, tri_attrs, pg_names,
            vert_map=vert_map,
        )

    # ── Compute centroids for problematic faces ──────────────────────────
    for face_list_key in ("orphans", "duplicates"):
        for entry in raw[face_list_key]:
            face = entry.get("face_nodes") or entry.get("original_nodes")
            if face:
                try:
                    entry["centroid"] = points[list(face)].mean(axis=0).tolist()
                except (IndexError, KeyError):
                    entry["centroid"] = [0.0, 0.0, 0.0]
    if periodic:
        for face_list_key in ("orphans", "duplicates"):
            for entry in periodic[face_list_key]:
                face = entry.get("face_nodes") or entry.get("original_nodes")
                if face:
                    try:
                        entry["centroid"] = points[list(face)].mean(axis=0).tolist()
                    except (IndexError, KeyError):
                        entry["centroid"] = [0.0, 0.0, 0.0]

    return {
        "mesh_path": str(mesh_path),
        "n_points": len(points),
        "n_tets": len(all_tets),
        "n_boundary_tris": len(tri_nodes),
        "physical_groups": pg_names,
        # Pass 1
        "raw_n_volume_faces": raw["n_volume_faces"],
        "raw_n_internal_faces": raw["n_internal_faces"],
        "raw_n_skin_faces": raw["n_skin_faces"],
        "raw_orphans": raw["orphans"],
        "raw_duplicates": raw["duplicates"],
        # Pass 2 (may be None)
        "n_periodic_vertices": len(vert_map),
        "periodic_orphans": periodic["orphans"] if periodic else [],
        "periodic_duplicates": periodic["duplicates"] if periodic else [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 7. REPORT PRINTING
# ═══════════════════════════════════════════════════════════════════════════════

_HEADER = """
╔══════════════════════════════════════════════════════════════════════╗
║              Mesh Topological Consistency Report                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

def print_report(
    result: dict,
    config_bcs: dict[str, list[int]] | None = None,
) -> bool:
    """Pretty-print the verification result.  Returns True if all checks pass."""
    pg = result["physical_groups"]
    print(_HEADER)
    print(f"  Mesh file:             {result['mesh_path']}")
    print(f"  Vertices:              {result['n_points']:,}")
    print(f"  Tetrahedra:            {result['n_tets']:,}")
    print(f"  Boundary triangles:    {result['n_boundary_tris']:,}")
    print(f"  Unique volume faces:   {result['raw_n_volume_faces']:,}")
    print(f"    interior (2 tets):   {result['raw_n_internal_faces']:,}")
    print(f"    skin     (1 tet):    {result['raw_n_skin_faces']:,}")
    n_pv = result.get("n_periodic_vertices", 0)
    if n_pv:
        print(f"  Periodic vertices:     {n_pv:,}")
    print()

    # ── Physical groups ──
    if pg:
        print("  Physical groups (2-D):")
        for attr, name in sorted(pg.items()):
            print(f"    attr {attr:3d} = {name}")
        print()

    # ── Palace BC cross-check ──
    if config_bcs:
        print("  Palace boundary conditions:")
        all_bc_attrs: set[int] = set()
        for bc_name, attrs in sorted(config_bcs.items()):
            names = [pg.get(a, f"attr_{a}") for a in attrs]
            print(f"    {bc_name}: {attrs}  ({', '.join(names)})")
            all_bc_attrs.update(attrs)
        unassigned = set(pg.keys()) - all_bc_attrs
        if unassigned:
            print(f"    Unassigned: {sorted(unassigned)}  "
                  f"({', '.join(pg.get(a, '?') for a in sorted(unassigned))})")
        print()

    ok = True
    sep = "─" * 70

    # ══════════════════════════════════════════════════════════════════════
    # CHECK 1 — Totality:  b(B) ⊆ F
    # ══════════════════════════════════════════════════════════════════════
    print(sep)
    print("  CHECK 1  —  Totality:  every boundary face ∈ volume faces")
    print("              (violation → MFEM abort: (r,c,f) = …)")
    print(sep)

    orphans = result["raw_orphans"]
    if not orphans:
        print("  ✅  Pass 1 (raw): all boundary faces found among volume faces.")
    else:
        ok = False
        print(f"  ❌  Pass 1 (raw): {len(orphans)} ORPHAN boundary face(s)!")
        _print_orphan_details(orphans, pg)

    p_orphans = result["periodic_orphans"]
    if n_pv == 0:
        print("  ⓘ   Pass 2 (periodic): skipped — no periodic BC.")
    elif not p_orphans:
        print("  ✅  Pass 2 (periodic): no new orphans after vertex identification.")
    else:
        ok = False
        print(f"  ❌  Pass 2 (periodic): {len(p_orphans)} ORPHAN(S) after vertex merge!")
        _print_orphan_details(p_orphans, pg)

    print()

    # ══════════════════════════════════════════════════════════════════════
    # CHECK 2 — Injectivity:  b is one-to-one
    # ══════════════════════════════════════════════════════════════════════
    print(sep)
    print("  CHECK 2  —  Injectivity:  each volume face has ≤ 1 boundary element")
    print("              (violation → \"…cannot have multiple boundary elements!\")")
    print(sep)

    dups = result["raw_duplicates"]
    if not dups:
        print("  ✅  Pass 1 (raw): no duplicate boundary faces.")
    else:
        ok = False
        print(f"  ❌  Pass 1 (raw): {len(dups)} DUPLICATE boundary face(s)!")
        _print_duplicate_details(dups, pg)

    p_dups = result["periodic_duplicates"]
    if n_pv == 0:
        print("  ⓘ   Pass 2 (periodic): skipped — no periodic BC.")
    elif not p_dups:
        print("  ✅  Pass 2 (periodic): no duplicates after vertex identification.")
    else:
        ok = False
        print(f"  ❌  Pass 2 (periodic): {len(p_dups)} DUPLICATE(S) after vertex merge!")
        print("      MFEM MakePeriodic merges vertices which causes boundary")
        print("      triangles on different surfaces to collapse onto the same face.")
        _print_duplicate_details(p_dups, pg)

    print()

    # ── Final verdict ──
    verdict = "─" * 70
    print(verdict)
    if ok:
        print("  ✅  RESULT: Mesh passes both topological checks.")
    else:
        print("  ❌  RESULT: Mesh has topological problems — see details above.")
    print(verdict)
    return ok


def _print_orphan_details(orphans: list[dict], pg: dict[int, str]):
    """Print detail about orphan boundary elements."""
    by_attr = Counter(o["attribute"] for o in orphans)
    print()
    print("    By boundary attribute:")
    for attr, count in by_attr.most_common():
        name = pg.get(attr, f"attr_{attr}")
        print(f"      attr {attr} ({name}): {count} orphan(s)")
    n_show = min(10, len(orphans))
    print(f"\n    First {n_show}:")
    for o in orphans[:n_show]:
        face = o.get("mapped_face") or o.get("original_nodes", "?")
        cx, cy, cz = o.get("centroid", (0, 0, 0))
        print(f"      tri_index={o['tri_index']}, attr={o['attribute']} "
              f"({o['pg_name']}), face={face}, "
              f"centroid=({cx:.1f}, {cy:.1f}, {cz:.1f})")
    if len(orphans) > n_show:
        print(f"      … and {len(orphans) - n_show} more.")
    print()


def _print_duplicate_details(dups: list[dict], pg: dict[int, str]):
    """Print detail about duplicate boundary faces."""
    attr_combos = Counter()
    for dup in dups:
        attrs = tuple(sorted(e["attribute"] for e in dup["boundary_elements"]))
        attr_combos[attrs] += 1

    print()
    print("    By attribute combination:")
    for attrs, count in attr_combos.most_common():
        names = [pg.get(a, f"attr_{a}") for a in attrs]
        print(f"      attrs {attrs} ({', '.join(names)}): {count} dup(s)")

    n_show = min(15, len(dups))
    print(f"\n    First {n_show}:")
    for i, dup in enumerate(dups[:n_show]):
        entries = dup["boundary_elements"]
        cx, cy, cz = dup.get("centroid", (0, 0, 0))
        internal = "internal" if dup["is_internal_face"] else "skin"
        attr_str = " & ".join(
            f"{e['attribute']} ({e['pg_name']})" for e in entries
        )
        vol_str = ", ".join(str(a) for a in dup["tet_volume_attrs"])
        print(f"      [{i+1:3d}] face={dup['face_nodes']}  "
              f"centroid=({cx:.1f}, {cy:.1f}, {cz:.1f})")
        print(f"            attrs: {attr_str}  [{internal}, vol: {vol_str}]")
        for e in entries:
            orig = e.get("original_nodes")
            if orig and orig != dup["face_nodes"]:
                print(f"            original nodes: {orig} (before vertex merge)")
    if len(dups) > n_show:
        print(f"      … and {len(dups) - n_show} more.")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. VISUALISATION
# ═══════════════════════════════════════════════════════════════════════════════

def visualise_problems(
    mesh_path: str | Path,
    result: dict,
    *,
    transparent_groups: list[str] | None = None,
    exclude_expected_periodic: bool = True,
):
    """Open the mesh in PyVista with all problematic faces highlighted in red.

    Collects both orphan and duplicate faces from both raw and periodic passes
    and passes them to ``view_mesh.view_mesh(highlight_faces=...)``.
    """
    from palacetoolkit.viz import view_mesh

    pg = result.get("physical_groups", {})
    periodic_pg_names = {name for name in pg.values()
                         if name.startswith("periodic")}

    def _is_expected_periodic(dup: dict) -> bool:
        return all(
            e.get("pg_name", "") in periodic_pg_names
            for e in dup.get("boundary_elements", [])
        )

    faces: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()

    def _add(face: tuple[int, ...]):
        if face not in seen:
            seen.add(face)
            faces.append(face)

    # Orphans (both passes)
    for o in result.get("raw_orphans", []):
        _add(o.get("original_nodes") or o.get("mapped_face", ()))
    for o in result.get("periodic_orphans", []):
        _add(o.get("original_nodes", ()))

    # Duplicates (both passes)
    for dup_list_key in ("raw_duplicates", "periodic_duplicates"):
        for dup in result.get(dup_list_key, []):
            if exclude_expected_periodic and _is_expected_periodic(dup):
                continue
            # For periodic dups, highlight each boundary element's original face
            for entry in dup.get("boundary_elements", []):
                orig = entry.get("original_nodes")
                if orig:
                    _add(orig)
            # Also add the (possibly merged) canonical face
            fn = dup.get("face_nodes")
            if fn:
                _add(fn)

    if not faces:
        print("No problematic faces to highlight — mesh is clean.")
        return

    n_orphan = len(result.get("raw_orphans", [])) + len(result.get("periodic_orphans", []))
    n_dup = len(result.get("raw_duplicates", [])) + len(result.get("periodic_duplicates", []))
    print(f"\nVisualising {len(faces)} face(s) in red "
          f"({n_orphan} orphan + {n_dup} duplicate) …")

    view_mesh(
        str(mesh_path),
        transparent_groups=transparent_groups or ["air__None"],
        highlight_faces=faces,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    do_view = True
    positional: list[str] = []
    for arg in sys.argv[1:]:
        if arg == "--no-view":
            do_view = False
        elif arg == "--view":
            do_view = True
        else:
            positional.append(arg)

    if not positional:
        print(f"Usage: {sys.argv[0]} <mesh.msh> [palace_config.json] [--no-view]")
        sys.exit(1)

    mesh_path = Path(positional[0])
    config_path = Path(positional[1]) if len(positional) > 1 else None

    if not mesh_path.exists():
        print(f"Error: mesh file not found: {mesh_path}")
        sys.exit(1)

    result = verify(mesh_path, config_path)

    config_bcs = None
    if config_path and config_path.exists():
        config_bcs = load_config_bc_attrs(config_path)

    ok = print_report(result, config_bcs)

    has_problems = (
        result["raw_orphans"]
        or result["raw_duplicates"]
        or result["periodic_orphans"]
        or result["periodic_duplicates"]
    )
    if do_view and has_problems:
        visualise_problems(mesh_path, result)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
