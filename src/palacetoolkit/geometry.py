import gmsh

from dataclasses import dataclass


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
    Typical usage::

        sel = Selector()
        top_face = sel.faces_at_z(z=h).first()
        bottom_face = sel.faces_at_z(z=0).first()
    """

    def __init__(self, dimtags: list[tuple[int, int]] | None = None):
        gmsh.model.occ.synchronize()
        if dimtags is None:
            dimtags = list(gmsh.model.getEntities(2))
        self._dimtags = [(2, t) for _, t in dimtags]

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
