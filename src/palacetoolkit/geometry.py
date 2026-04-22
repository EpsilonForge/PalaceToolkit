import gmsh

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


# Convenience functions to extract extrema of the bounding box of an entity
def xmin(dimtag):
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[0]

def ymin(dimtag):
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[1]

def zmin(dimtag):
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[2]

def xmax(dimtag):
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[3]

def ymax(dimtag):
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[4]

def zmax(dimtag):
    return gmsh.model.occ.getBoundingBox(dimtag[0], dimtag[1])[5]
