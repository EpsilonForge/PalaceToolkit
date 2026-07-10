import gmsh

from dataclasses import dataclass
from math import cos, pi, sin


@dataclass(frozen=True)
class Face:
    """A selected boundary face — a (dim, tag) pair with dim=2.

    Returned by :class:`Selector` methods.  The ``tag`` is the Gmsh OCC
    surface tag, and ``dim`` is always 2.
    """
    dim: int
    tag: int

    @property
    def dimtag(self) -> tuple[int, int]:
        return (self.dim, self.tag)

    def __iter__(self):
        return iter((self.dim, self.tag))


class Selector:
    """build123d / cadquery-style face selector for the current gmsh model.

    Works on the bounding-box of each surface entity in the OCC kernel.
    When bound to a volume (dim=3), only considers the boundary faces of
    that volume — just like ``part.faces(">Z")`` in build123d/cadquery.

    Typical usage::

        # Bound to a volume (recommended after boolean operations):
        sel = Selector((3, vol_tag))
        top_face = sel.faces_zmax()[0]

        # Unbound (all surfaces in the model):
        sel = Selector()
    """

    def __init__(self, dimtag: tuple[int, int] | None = None):
        gmsh.model.occ.synchronize()
        if dimtag is not None:
            # Bound to a specific volume: get its boundary faces only.
            # This mirrors build123d/cadquery where selectors operate on a
            # specific shape, not the entire model.
            boundary = gmsh.model.getBoundary(
                [dimtag], combined=False, oriented=False, recursive=False
            )
            self._dimtags = [(2, abs(t)) for d, t in boundary if d == 2]
        else:
            self._dimtags = [(2, t) for _, t in gmsh.model.getEntities(2)]

    # -- internal helpers -------------------------------------------------
    def _bbox(self, tag: int) -> tuple[float, float, float, float, float, float]:
        return gmsh.model.occ.getBoundingBox(2, tag)

    def _filter(self, predicate) -> list[Face]:
        result: list[Face] = []
        for _, tag in self._dimtags:
            if predicate(tag):
                result.append(Face(2, tag))
        return result

    # -- axis-value selectors ---------------------------------------------
    def faces_at_x(self, x: float, tol: float = 1e-6) -> list[Face]:
        """All faces whose bounding box lies entirely at ``x``."""
        return self._filter(
            lambda t: abs(self._bbox(t)[0] - x) < tol and abs(self._bbox(t)[3] - x) < tol
        )

    def faces_at_y(self, y: float, tol: float = 1e-6) -> list[Face]:
        return self._filter(
            lambda t: abs(self._bbox(t)[1] - y) < tol and abs(self._bbox(t)[4] - y) < tol
        )

    def faces_at_z(self, z: float, tol: float = 1e-6) -> list[Face]:
        return self._filter(
            lambda t: abs(self._bbox(t)[2] - z) < tol and abs(self._bbox(t)[5] - z) < tol
        )

    # -- extrema selectors ------------------------------------------------
    def faces_xmin(self) -> list[Face]:
        xs = [self._bbox(t)[0] for _, t in self._dimtags]
        if not xs:
            return []
        return self.faces_at_x(min(xs))

    def faces_xmax(self) -> list[Face]:
        xs = [self._bbox(t)[3] for _, t in self._dimtags]
        if not xs:
            return []
        return self.faces_at_x(max(xs))

    def faces_ymin(self) -> list[Face]:
        ys = [self._bbox(t)[1] for _, t in self._dimtags]
        if not ys:
            return []
        return self.faces_at_y(min(ys))

    def faces_ymax(self) -> list[Face]:
        ys = [self._bbox(t)[4] for _, t in self._dimtags]
        if not ys:
            return []
        return self.faces_at_y(max(ys))

    def faces_zmin(self) -> list[Face]:
        zs = [self._bbox(t)[2] for _, t in self._dimtags]
        if not zs:
            return []
        return self.faces_at_z(min(zs))

    def faces_zmax(self) -> list[Face]:
        zs = [self._bbox(t)[5] for _, t in self._dimtags]
        if not zs:
            return []
        return self.faces_at_z(max(zs))

    # -- convenience ------------------------------------------------------
    def all(self) -> list[Face]:
        return [Face(2, t) for _, t in self._dimtags]


def extract_tag(obj):
    """
    Extract the Gmsh tag from an object.

    If object contains only one tag, return it as an integer, otherwise, preserve its
    container.

    Most gmsh functions return list of tuples like [(2, 5), (2, 8), (2, 10), ...], where the
    first number is dimensionality and the second is the integer tag associated to that object.

    Examples
    --------
    >>> extract_tag((3, 6))
    6

    >>> entities = [(2, 5), (2, 8), (2, 10)]
    >>> [extract_tag(e) for e in entities]
    [5, 8, 10]
    """
    if isinstance(obj, list) and len(obj) == 1:
        return extract_tag(obj[0])
    elif isinstance(obj, tuple):
        return obj[1]
    else:
        raise ValueError("Expected a tuple or single-element list")


# ---------------------------------------------------------------------------
# Bounding-box convenience functions
# ---------------------------------------------------------------------------
def xmin(dimtag):
    """Return the minimum x-coordinate of the entity's bounding box."""
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[0]

def ymin(dimtag):
    """Return the minimum y-coordinate of the entity's bounding box."""
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[1]

def zmin(dimtag):
    """Return the minimum z-coordinate of the entity's bounding box."""
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[2]

def xmax(dimtag):
    """Return the maximum x-coordinate of the entity's bounding box."""
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[3]

def ymax(dimtag):
    """Return the maximum y-coordinate of the entity's bounding box."""
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[4]

def zmax(dimtag):
    """Return the maximum z-coordinate of the entity's bounding box."""
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[5]


# ---------------------------------------------------------------------------
# Convenience geometry builders
# ---------------------------------------------------------------------------
def make_polygonal_tube(
    r_inner: float,
    r_outer: float,
    length: float,
    n_sides: int = 32,
    z0: float = 0.0,
) -> int:
    """Build a coaxial (annular) tube as a polygonal prism extruded along z.

    Uses a polygonal approximation of the circular cross-section to avoid
    the OCC cylinder seam that produces duplicated facets during 3D meshing.

    Args:
        r_inner: Inner radius of the annulus.
        r_outer: Outer radius of the annulus.
        length:  Length of the tube along z.
        n_sides: Number of polygon sides per circle (default 32).
        z0:      Starting z-coordinate (default 0).

    Returns:
        The Gmsh volume tag of the extruded annular prism.
    """
    occ = gmsh.model.occ

    # Outer polygon vertices
    outer_pts = []
    for i in range(n_sides):
        a = 2 * pi * i / n_sides
        outer_pts.append(occ.addPoint(r_outer * cos(a), r_outer * sin(a), z0))

    # Inner polygon vertices
    inner_pts = []
    for i in range(n_sides):
        a = 2 * pi * i / n_sides
        inner_pts.append(occ.addPoint(r_inner * cos(a), r_inner * sin(a), z0))

    # Lines
    outer_lines = [occ.addLine(outer_pts[i], outer_pts[(i + 1) % n_sides]) for i in range(n_sides)]
    inner_lines = [occ.addLine(inner_pts[i], inner_pts[(i + 1) % n_sides]) for i in range(n_sides)]

    # Annular surface
    outer_loop = occ.addCurveLoop(outer_lines)
    inner_loop = occ.addCurveLoop(inner_lines)
    surf = occ.addPlaneSurface([outer_loop, inner_loop])
    occ.synchronize()

    # Extrude along z
    out = occ.extrude([(2, surf)], 0, 0, length)
    occ.synchronize()

    vol_tags = [t for d, t in out if d == 3]
    return vol_tags[0] if vol_tags else -1


def addNonPeriodicCylinder(
    x: float,
    y: float,
    z: float,
    dx: float,
    dy: float,
    dz: float,
    r: float,
) -> int:
    """Create a cylinder and split its OCC seam to prevent meshing duplication.

    OCC cylindrical surfaces have an implicit seam at theta=0.  When a
    cylinder is involved in a boolean cut (e.g. coaxial geometry), the
    2D mesher can create duplicated triangles at this seam, causing the
    3D mesher to fail with "overlapping facets".

    This helper creates a standard OCC cylinder, then fragments it against
    a planar rectangle aligned with the cylinder axis at the seam location.
    The fragment forces OCC to split the cylindrical surface into two
    semi-cylindrical patches, eliminating the seam duplication.

    .. note::
       If you plan to boolean-cut this cylinder against another, perform
       the cut first on plain ``addCylinder`` volumes, then call
       :func:`splitCylinderSeam` on the result.  Applying the split before
       a cut has no effect — the cut re-creates the seam.

    Args:
        x, y, z:  Coordinates of the cylinder base centre.
        dx, dy, dz: Direction vector of the cylinder axis (need not be
                    normalised — only its direction matters).
        r:        Cylinder radius.

    Returns:
        The Gmsh volume tag of the cylinder.
    """
    occ = gmsh.model.occ

    # Create the standard OCC cylinder
    vol = occ.addCylinder(x, y, z, dx, dy, dz, r)
    occ.synchronize()

    # Split the seam
    return splitCylinderSeam(vol, x, y, z, dx, dy, dz, r)


def splitCylinderSeam(
    vol: int,
    x: float,
    y: float,
    z: float,
    dx: float,
    dy: float,
    dz: float,
    r: float,
) -> int:
    """Split a volume's cylindrical surfaces at the OCC seam (theta=0).

    Fragments the volume against a planar rectangle that passes through
    the cylinder axis, forcing OCC to split any cylindrical surface into
    two semi-cylindrical patches.  This prevents the duplicated facets
    that occur when meshing boolean-cut cylinders.

    Call this **after** any boolean operations (cut, fuse, etc.) that
    involve cylindrical surfaces.

    Args:
        vol: Gmsh volume tag to split.
        x, y, z:  Base centre of the original cylinder.
        dx, dy, dz: Axis direction of the original cylinder.
        r:        Radius of the original cylinder.

    Returns:
        The Gmsh volume tag of the split volume.
    """
    import math

    occ = gmsh.model.occ

    # Normalise the axis direction
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if norm == 0:
        raise ValueError("Cylinder axis direction must be non-zero.")
    ux, uy, uz = dx / norm, dy / norm, dz / norm

    # Compute the volume bounding box
    bb = occ.getBoundingBox(3, vol)
    xmin, ymin, zmin, xmax, ymax, zmax = bb
    margin = max(xmax - xmin, ymax - ymin, zmax - zmin) * 0.1 + r * 0.1

    # Build a cutting rectangle in the cross-section plane (perpendicular to
    # the cylinder axis) at the base.  The rectangle spans the full diameter
    # in one transverse direction and the full length in the other, so that
    # the fragment creates a vertical planar cut through the cylinder axis,
    # splitting the cylindrical surface at theta=0 (the OCC seam).
    if abs(uz) > 0.5:
        # Axis along z — rectangle in xy-plane at z=z_base
        # x spans the diameter, y spans the length
        rect = occ.addRectangle(
            xmin - margin, y, z,
            (xmax - xmin) + 2 * margin,
            norm + 2 * margin,
        )
    elif abs(ux) > 0.5:
        # Axis along x — rectangle in yz-plane at x=x_base
        # y spans the diameter, z spans the length
        rect = occ.addRectangle(
            ymin - margin, zmin - margin, x,
            (ymax - ymin) + 2 * margin,
            norm + 2 * margin,
        )
    else:
        # Axis along y — rectangle in xz-plane at y=y_base
        # x spans the diameter, z spans the length
        rect = occ.addRectangle(
            xmin - margin, zmin - margin, y,
            (xmax - xmin) + 2 * margin,
            norm + 2 * margin,
        )

    occ.synchronize()

    # Fragment the volume with the rectangle — splits the seam
    result, _ = occ.fragment([(3, vol)], [(2, rect)], removeObject=True, removeTool=True)
    occ.synchronize()

    vol_tags = [t for d, t in result if d == 3]
    return vol_tags[0] if vol_tags else vol
