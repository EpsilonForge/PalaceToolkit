# Geometry & Meshing

PalaceToolkit uses [Gmsh](https://gmsh.info/) with its OpenCASCADE kernel to
create parametric 3D finite-element meshes entirely from Python scripts.

---

## The `Entity` abstraction

Every geometric region — conductors, dielectrics, air boxes, ports — is
represented as an `Entity`:

```python
from palacetoolkit.mesh import Entity, run_meshing_pipeline

conductor = Entity(name="conductor", dim=3, mesh_order=0, tags=[1])
dielectric = Entity(name="dielectric", dim=3, mesh_order=1, tags=[2])
air = Entity(name="air", dim=3, mesh_order=2, tags=[3])
```

| Parameter    | Description |
|:-------------|:------------|
| `name`       | Becomes the physical group label that Palace references. |
| `dim`        | Geometric dimension (3 = volume, 2 = surface, …). |
| `mesh_order` | Priority for the boolean pipeline (lower = higher priority). |
| `tags`       | Gmsh geometry tags returned by `gmsh.model.occ.*` calls. |

## Boolean pipeline

After defining entities, call `run_meshing_pipeline` to perform automatic
priority-based cuts and fragmentation:

```python
run_meshing_pipeline([conductor, dielectric, air])
```

The pipeline:

1. **Groups** entities by dimension (3 → 0).
2. **Sorts** within each dimension by `mesh_order` (ascending = higher priority).
3. **Cuts** each entity against all previously processed entities in the
   same dimension (`removeObject=True`, `removeTool=False`).
4. **Fragments** lower-dimensional entities against higher-dimensional ones so
   that boundary surfaces are shared.
5. **Assigns physical groups** — volumes get their entity name; surfaces
   at material interfaces are auto-labelled (e.g. `"conductor__dielectric"`).

!!! tip
    The `mesh_order` controls which material wins at overlapping regions.
    Think of it as a z-index: small number = highest priority = never cut.

## Mesh generation

After the pipeline runs, generate the mesh and write it to disk:

```python
import gmsh

gmsh.model.mesh.generate(3)
gmsh.write("my_model.msh")
gmsh.finalize()
```

## Mesh topology verification

Before running Palace, verify the mesh is valid:

```python
from palacetoolkit.verify_topology import analyse_mesh

analyse_mesh("my_model.msh")
```

This checks that:

- Every boundary element maps to an existing volume face (**totality**).
- No two boundary elements map to the same face (**injectivity**).

## Mesh visualisation

```python
from palacetoolkit.viz import view_mesh

view_mesh("my_model.msh")
```

For static HTML exports (used in the docs site):

```python
from IPython.display import IFrame

from palacetoolkit.viz import render_mesh

render_mesh(mesh, Path("img") / "my_model.htm", title="My Model")
IFrame(src="img/my_model.htm", width="100%", height=500)
```
