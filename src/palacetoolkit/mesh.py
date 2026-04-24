"""Gmsh utilities: boolean pipeline, mesh generation helpers."""

import gmsh


# ---------------------------------------------------------------------------
# Minimalistic meshwell-style entity + pipeline
# ---------------------------------------------------------------------------

class Entity:
    """A named geometric entity with priority (mesh_order) and tracked dimtags."""

    def __init__(self, name: str, dim: int, mesh_order: int, tags: list[int]):
        self.name = name
        self.dim = dim
        self.mesh_order = mesh_order
        self.dimtags = [(dim, t) for t in tags]

    def __repr__(self):
        return f"Entity({self.name!r}, dim={self.dim}, order={self.mesh_order}, tags={[t for _, t in self.dimtags]})"


def run_boolean_pipeline(entities: list[Entity]):
    """
    Meshwell-style boolean pipeline (minimalistic).

    1. Group entities by dimension (descending: 3 -> 0).
    2. Within each dimension, sort by mesh_order (ascending = higher priority).
    3. Priority cuts: each entity is cut by all previously processed entities
       in the same dimension (removeObject=True, removeTool=False).
    4. Fragment current dimension against all higher-dimension entities
       already processed, then update tags via the returned mapping.
    5. Accumulate processed entities for the next (lower) dimension.
    """
    gmsh.model.occ.synchronize()

    # Group by dimension
    dim_groups: dict[int, list[Entity]] = {3: [], 2: [], 1: [], 0: []}
    for e in entities:
        dim_groups[e.dim].append(e)

    # Sort each group by mesh_order (ascending = higher priority first)
    for dim in dim_groups:
        dim_groups[dim].sort(key=lambda e: e.mesh_order)

    processed_higher_dims: list[Entity] = []

    for dim in (3, 2, 1, 0):
        current_group = dim_groups[dim]
        if not current_group:
            continue

        # Move the fragment-against-higher-dims step to run BEFORE priority cuts so that all surface tags are refreshed from the fragment output map before any cut is attempted.

        # --- A. Priority cuts within same dimension ---
        processed_in_dim: list[Entity] = []
        for entity in current_group:
            # Collect tool dimtags from all previously processed entities in this dim
            tool_dimtags = [dt for prev in processed_in_dim for dt in prev.dimtags]

            if tool_dimtags and entity.dimtags:
                cut_result, _ = gmsh.model.occ.cut(
                    entity.dimtags,
                    tool_dimtags,
                    removeObject=True,
                    removeTool=False,
                )
                gmsh.model.occ.synchronize()
                entity.dimtags = list(set(cut_result))

            if entity.dimtags:
                processed_in_dim.append(entity)

        # --- B. Fragment against higher dimensions ---
        if processed_higher_dims and processed_in_dim:
            object_dimtags = [dt for e in processed_in_dim for dt in e.dimtags]
            tool_dimtags = [dt for e in processed_higher_dims for dt in e.dimtags]

            _, out_map = gmsh.model.occ.fragment(
                object_dimtags,
                tool_dimtags,
                removeObject=True,
                removeTool=True,
            )
            gmsh.model.occ.synchronize()

            # Update tags using the mapping (order: objects first, then tools)
            idx = 0
            for entity in processed_in_dim:
                new_dimtags = []
                for _ in entity.dimtags:
                    new_dimtags.extend(out_map[idx])
                    idx += 1
                entity.dimtags = list(set(new_dimtags))

            for entity in processed_higher_dims:
                new_dimtags = []
                for _ in entity.dimtags:
                    new_dimtags.extend(out_map[idx])
                    idx += 1
                entity.dimtags = list(set(new_dimtags))

        processed_higher_dims.extend(processed_in_dim)

    # --- Assign physical groups ---

    # 1. Volume physical groups (dim=3 only; dim=2 handled in step 3)
    for entity in entities:
        if entity.dim == 3 and entity.dimtags:
            tags = [t for d, t in entity.dimtags if d == 3]
            if tags:
                pg_tag = gmsh.model.addPhysicalGroup(3, tags, name=entity.name)
                print(f"  Physical group '{entity.name}' (dim=3): pg={pg_tag}, tags={tags}")

    # 2. Surface physical groups from volume boundaries
    #    Build a map: surface_tag -> list of volume entity names that own it
    vol_entities = [e for e in entities if e.dim == 3 and e.dimtags]
    surf_to_names: dict[int, list[str]] = {}
    for entity in vol_entities:
        for dt in entity.dimtags:
            boundary = gmsh.model.getBoundary(
                [dt], combined=False, oriented=False, recursive=False
            )
            for bdim, btag in boundary:
                if bdim == 2:
                    surf_to_names.setdefault(btag, [])
                    if entity.name not in surf_to_names[btag]:
                        surf_to_names[btag].append(entity.name)

    # 3. 2D entities keep their own name as the physical group
    surf_entities = [e for e in entities if e.dim == 2 and e.dimtags]
    assigned_surfs: set[int] = set()
    for entity in surf_entities:
        tags = [t for d, t in entity.dimtags if d == 2]
        if tags:
            pg_tag = gmsh.model.addPhysicalGroup(2, tags, name=entity.name)
            print(f"  Physical group '{entity.name}' (dim=2): pg={pg_tag}, tags={tags}")
            assigned_surfs.update(tags)

    # 4. Group remaining surfaces by their sorted owner name combination
    name_combo_to_surfs: dict[str, list[int]] = {}
    for stag, names in surf_to_names.items():
        if stag in assigned_surfs:
            continue
        if len(names) == 1:
            label = f"{names[0]}__None"
        else:
            label = "__".join(sorted(names))
        name_combo_to_surfs.setdefault(label, []).append(stag)

    for label, stags in name_combo_to_surfs.items():
        pg_tag = gmsh.model.addPhysicalGroup(2, stags, name=label)
        print(f"  Physical group '{label}' (dim=2): pg={pg_tag}, tags={stags}")

    # Build pg_map by reading back from gmsh (authoritative source for .msh tags)
    pg_map: dict[str, int] = {}
    for dim, pg_tag in gmsh.model.getPhysicalGroups():
        name = gmsh.model.getPhysicalName(dim, pg_tag)
        if name:
            pg_map[name] = pg_tag

    return pg_map


# ---------------------------------------------------------------------------
# 3D mesh + Palace config helpers
# ---------------------------------------------------------------------------

def generate_3d_mesh(
    entities: list[Entity],
    mesh_sizes: dict[str, float],
    output_file: str,
    optimize: bool = True,
) -> None:
    """Set mesh sizes, generate and write a 3D mesh.

    Args:
        entities:    list of Entity objects with ``.name`` and ``.dimtags``.
        mesh_sizes:  mapping from entity name → characteristic length.
        output_file: path for the output .msh file.
        optimize:    whether to run Netgen optimisation (disable for complex
                     imported CAD to avoid segfaults in thin-volume meshes).
    """
    def _apply_point_sizes(*, use_entity_tags: bool = True) -> int:
        applied = 0
        for entity in entities:
            lc = mesh_sizes.get(entity.name)
            if lc is None:
                continue
            if use_entity_tags:
                dimtags = entity.dimtags
            else:
                dimtags = []
                for dim, pg_tag in gmsh.model.getPhysicalGroups(entity.dim):
                    pg_name = gmsh.model.getPhysicalName(dim, pg_tag)
                    if pg_name == entity.name:
                        dimtags.extend((entity.dim, t) for t in gmsh.model.getEntitiesForPhysicalGroup(dim, pg_tag))

            if not dimtags:
                continue

            try:
                pts = gmsh.model.getBoundary(
                    dimtags, combined=False, oriented=False, recursive=True
                )
            except Exception:
                continue

            point_dimtags = [(d, t) for d, t in pts if d == 0]
            if point_dimtags:
                gmsh.model.mesh.setSize(point_dimtags, lc)
                applied += 1

        return applied

    _apply_point_sizes(use_entity_tags=True)

    try:
        gmsh.model.mesh.generate(3)
    except Exception as exc:
        msg = str(exc).lower()
        if "invalid boundary mesh" not in msg and "overlapping facets" not in msg:
            raise

        print("  Meshing failed with overlapping facets; attempting OCC repair + retry...")
        gmsh.model.mesh.clear()
        try:
            gmsh.model.occ.removeAllDuplicates()
        except Exception:
            pass
        try:
            gmsh.model.occ.healShapes()
        except Exception:
            pass
        gmsh.model.occ.synchronize()

        applied = _apply_point_sizes(use_entity_tags=False)
        if applied == 0 and mesh_sizes:
            # Last-resort sizing when entity tags are no longer valid after repair.
            gmsh.model.mesh.setSize(gmsh.model.getEntities(0), min(mesh_sizes.values()))

        gmsh.model.mesh.generate(3)

    if optimize:
        gmsh.model.mesh.optimize("Netgen")
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(output_file)
    print(f"Mesh saved to {output_file}")
    print(f"  Nodes: {len(gmsh.model.mesh.getNodes()[0])}")
    elems = gmsh.model.mesh.getElements()
    print(f"  Elements: {sum(len(e) for e in elems[1])}")


def refine_surfaces(surf_tags, lc) -> float:

    gmsh.model.mesh.setSize(gmsh.model.getEntities(0), lc)

    if surf_tags:
        port_boundary = gmsh.model.getBoundary(
            [(2, t) for t in surf_tags],
            combined = False, oriented = False, recursive = True
        )
        surf_points = [e[1] for e in port_boundary if e[0] == 0]
        if surf_points:
            gmsh.model.mesh.setSize([(0, p) for p in surf_points], lc/10)
    return lc

def refine_near_surfaces(
    surface_dimtags: list[tuple[int, int]],
    wavelength: float,
    ppw_near: int = 20,
    ppw_far: int = 5,
    transition_distance: float | None = None,
    set_as_background: bool = True,
) -> int:
    """Set up mesh refinement that clusters elements near conductor boundary curves.

    Creates Distance + Threshold background mesh fields so that elements are
    finest (``wavelength / ppw_near``) right at the boundary curves of the
    given surfaces and grade quickly to the coarse size
    (``wavelength / ppw_far``) over ``transition_distance``.

    When *set_as_background* is True (default), the field is immediately
    installed as the background mesh and meshing options are configured.
    Set it to False to compose multiple fields with a ``Min`` field before
    calling :func:`set_mesh_field_as_background` yourself.

    Args:
        surface_dimtags:     List of ``(dim, tag)`` pairs for the surfaces whose
                             boundary curves drive the refinement (typically PEC
                             and port surfaces).
        wavelength:          Operating wavelength in model units.
        ppw_near:            Points per wavelength on the conductor boundary curves.
        ppw_far:             Points per wavelength far from conductors.
        transition_distance: Distance over which the mesh size grades from fine
                             to coarse.  Defaults to ``wavelength / 4``.
        set_as_background:   If True, install the threshold field as the
                             background mesh and configure meshing options.

    Returns:
        The gmsh field ID of the Threshold field.
    """
    if transition_distance is None:
        transition_distance = 0.25 * wavelength

    lc_near = wavelength / ppw_near
    lc_far = wavelength / ppw_far

    # Collect unique boundary curves from the given surfaces
    edge_set: set[int] = set()
    for dt in surface_dimtags:
        for _, et in gmsh.model.getBoundary([dt], combined=False, oriented=False, recursive=False):
            edge_set.add(abs(et))
    edge_list = sorted(edge_set)
    print(f"  {len(edge_list)} conductor boundary curves")

    # Distance field from conductor boundary curves
    dist_field = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist_field, "CurvesList", edge_list)
    gmsh.model.mesh.field.setNumber(dist_field, "Sampling", 200)

    # Threshold: transition from lc_near → lc_far
    thresh_field = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thresh_field, "InField", dist_field)
    gmsh.model.mesh.field.setNumber(thresh_field, "SizeMin", lc_near)
    gmsh.model.mesh.field.setNumber(thresh_field, "SizeMax", lc_far)
    gmsh.model.mesh.field.setNumber(thresh_field, "DistMin", 0.0)
    gmsh.model.mesh.field.setNumber(thresh_field, "DistMax", transition_distance)

    print(f"  ppw_near={ppw_near}  ppw_far={ppw_far}")
    print(f"  SizeMin={lc_near:.4f} ({ppw_near} pts/λ)")
    print(f"  SizeMax={lc_far:.4f} ({ppw_far} pts/λ)")
    print(f"  Transition distance: 0 → {transition_distance:.4f}")

    if set_as_background:
        set_mesh_field_as_background(thresh_field)

    return thresh_field


def set_mesh_field_as_background(field_id: int) -> None:
    """Install a gmsh mesh field as the background mesh and configure options.

    Disables point / curvature / boundary-extension sizing so that the
    background field has full control over element sizes.
    """
    gmsh.model.mesh.field.setAsBackgroundMesh(field_id)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.Algorithm", 1)    # MeshAdapt
    gmsh.option.setNumber("Mesh.Algorithm3D", 1)  # Delaunay


def generate_2d_mesh(
    name_to_surfs: dict[str, list[int]],
    mesh_sizes: dict[str, float],
    output_file: str,
) -> None:
    """Set mesh sizes, generate and write a 2D mesh.

    Args:
        name_to_surfs: mapping from area name → list of surface tags.
        mesh_sizes:    mapping from area name → characteristic length.
        output_file:   path for the output .msh file.
    """
    # Process regions from coarsest → finest so that fine mesh sizes on shared
    # boundary points always override coarser ones.
    sorted_names = sorted(
        name_to_surfs.keys(),
        key=lambda n: mesh_sizes.get(n, 0.0),
        reverse=True,
    )
    for name in sorted_names:
        stags = name_to_surfs[name]
        lc = mesh_sizes.get(name)
        if lc is None:
            continue
        for stag in stags:
            pts = gmsh.model.getBoundary(
                [(2, stag)], combined=False, oriented=False, recursive=True
            )
            gmsh.model.mesh.setSize([(d, t) for d, t in pts if d == 0], lc)

    gmsh.model.mesh.generate(2)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(output_file)
    print(f"  Cross-section saved to {output_file}")
    print(f"    Nodes: {len(gmsh.model.mesh.getNodes()[0])}")
    elems = gmsh.model.mesh.getElements()
    print(f"    Elements: {sum(len(e) for e in elems[1])}")


def make_xz_rect(x0: float, x1: float, y: float, z0: float, z1: float) -> int:
    """Create a rectangular surface in the XZ plane at given y coordinate."""
    return make_rect(
        (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1),
    )


def make_yz_rect(x: float, y0: float, y1: float, z0: float, z1: float) -> int:
    """Create a rectangular surface in the YZ plane at given x coordinate."""
    return make_rect(
        (x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1),
    )


def make_rect(
    c0: tuple[float, float, float],
    c1: tuple[float, float, float],
    c2: tuple[float, float, float],
    c3: tuple[float, float, float],
) -> int:
    """Create a planar rectangular surface from four corner points.

    The corners must be given in order (either CW or CCW) so that
    consecutive corners share an edge.

    Args:
        c0, c1, c2, c3: (x, y, z) coordinates of the four corners.

    Returns:
        The Gmsh OCC surface tag.
    """
    p1 = gmsh.model.occ.addPoint(*c0)
    p2 = gmsh.model.occ.addPoint(*c1)
    p3 = gmsh.model.occ.addPoint(*c2)
    p4 = gmsh.model.occ.addPoint(*c3)
    loop = gmsh.model.occ.addCurveLoop([
        gmsh.model.occ.addLine(p1, p2),
        gmsh.model.occ.addLine(p2, p3),
        gmsh.model.occ.addLine(p3, p4),
        gmsh.model.occ.addLine(p4, p1),
    ])
    return gmsh.model.occ.addPlaneSurface([loop])