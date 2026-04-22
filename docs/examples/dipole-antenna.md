# Antenna Simulations

This tutorial demonstrates how to simulate wire antennas with Palace
using lumped-port excitation. You will learn:

1. The **voltage-gap** feed model for thin-wire antennas.
2. How to mesh a half-wave dipole with a lumped port.
3. How to extract input impedance from S-parameters.
4. How to set up an absorbing boundary condition for radiation.

---

## The Voltage-Gap Feed

For thin-wire antennas like dipoles and monopoles, the feed is modelled as
a **lumped port** — a small rectangle bridging the gap between the two arms.
Palace applies a uniform electric field across this gap, effectively imposing
a voltage source.

The antenna input impedance is then extracted from the port S-parameters:

$$
Z_{\text{ant}} = Z_0 \frac{1 + S_{11}}{1 - S_{11}}
$$

where $Z_0 = 50\,\Omega$ is the lumped-port reference impedance and
$S_{11}$ is the complex reflection coefficient.

### Half-Wave Dipole Reference Values

For a thin half-wave dipole at resonance:

- $Z_{\text{ant}} \approx 73 + j\,42.5\;\Omega$
- Resonant length $\approx 0.48\lambda$ (slightly shorter than $\lambda/2$
  due to fringing)


```python
from pathlib import Path
from IPython.display import HTML
from palace.viz import (
    render_mesh, render_multi_mesh, show_viewer,
    pv_from_meshio, COLOR_METAL, COLOR_PORT, COLOR_AIR,
)

IMG_DIR = Path("img")
IMG_DIR.mkdir(exist_ok=True)
```

## Meshing a Half-Wave Dipole

The dipole geometry consists of:

- Two cylindrical arms along the z-axis, each of length $\lambda/4$.
- A thin rectangular gap between them (the lumped port).
- A spherical air domain with an absorbing boundary condition.

After creating these primitives, we **fragment** the geometry so that the
rectangular port surface is properly embedded in the volume mesh.


```python
import math
import gmsh


def extract_tag(obj):
    """Extract Gmsh tag from a dimtag or single-element list."""
    if isinstance(obj, list) and len(obj) == 1:
        return extract_tag(obj[0])
    elif isinstance(obj, tuple):
        return obj[1]
    raise ValueError("Expected a tuple or single-element list")


# Bounding-box helpers
def xmin(dt): return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[0]
def ymin(dt): return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[1]
def zmin(dt): return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[2]
def xmax(dt): return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[3]
def ymax(dt): return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[4]
def zmax(dt): return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[5]


def generate_dipole_mesh(
    filename="dipole.msh",
    wavelength=4.0,
    arm_length=None,
    arm_radius=None,
    gap_size=None,
    outer_boundary_radius=None,
):
    """Generate a half-wave dipole antenna mesh.

    The mesh consists of two cylindrical arms separated by a rectangular
    gap (the lumped port), enclosed in a spherical absorbing boundary.
    """
    if arm_length is None:
        arm_length = wavelength / 4
    if arm_radius is None:
        arm_radius = arm_length / 20
    if gap_size is None:
        gap_size = arm_length / 100
    if outer_boundary_radius is None:
        outer_boundary_radius = 1.5 * wavelength

    gmsh.initialize()
    kernel = gmsh.model.occ
    gmsh.option.setNumber("General.Verbosity", 0)

    if "dipole" in gmsh.model.list():
        gmsh.model.setCurrent("dipole")
        gmsh.model.remove()
    gmsh.model.add("dipole")

    n_circle = 12
    n_farfield = 3

    # Create geometry
    outer = kernel.addSphere(0, 0, 0, outer_boundary_radius)
    top_arm = kernel.addCylinder(0, 0, gap_size / 2, 0, 0, arm_length, arm_radius)
    bot_arm = kernel.addCylinder(0, 0, -gap_size / 2, 0, 0, -arm_length, arm_radius)

    # Gap rectangle (port) — created on XY plane, then rotated to XZ
    gap_rect = kernel.addRectangle(-arm_radius, -gap_size / 2, 0, 2 * arm_radius, gap_size)
    kernel.rotate([(2, gap_rect)], 0, 0, 0, 1, 0, 0, math.pi / 2)

    # Fragment to embed surfaces in volumes
    kernel.fragment([(3, outer)], [(3, top_arm), (3, bot_arm), (2, gap_rect)])
    kernel.synchronize()

    # Identify regions by bounding box
    all_2d = kernel.getEntities(2)
    all_3d = kernel.getEntities(3)

    def spans_domain(x):
        return math.isclose(xmin(x), -outer_boundary_radius, abs_tol=outer_boundary_radius / 100)

    top_arm_surfs = [x for x in all_2d if zmin(x) > 0]
    bot_arm_surfs = [x for x in all_2d if zmax(x) < 0]
    outer_sphere = [x for x in all_2d if spans_domain(x)]
    domain = [x for x in all_3d if spans_domain(x)]

    eps = gap_size / 100
    gap_rect_surfs = [
        x for x in all_2d
        if (math.isclose(xmin(x), -arm_radius, abs_tol=eps)
            and math.isclose(xmax(x), arm_radius, abs_tol=eps)
            and math.isclose(ymin(x), 0, abs_tol=eps)
            and math.isclose(ymax(x), 0, abs_tol=eps)
            and math.isclose(zmin(x), -gap_size / 2, abs_tol=eps)
            and math.isclose(zmax(x), gap_size / 2, abs_tol=eps))
    ]

    # Physical groups
    pg_top = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in top_arm_surfs], -1, "top_arm")
    pg_bot = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in bot_arm_surfs], -1, "bot_arm")
    pg_port = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in gap_rect_surfs], -1, "port")
    pg_abc = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in outer_sphere], -1, "absorbing")
    pg_vol = gmsh.model.addPhysicalGroup(3, [extract_tag(x) for x in domain], -1, "air")

    # Mesh size
    gmsh.option.setNumber("Mesh.MeshSizeMin", 2 * math.pi * arm_radius / n_circle / 2)
    gmsh.option.setNumber("Mesh.MeshSizeMax", wavelength / n_farfield)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", n_circle)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)

    # Size field: grade from antenna surface to outer boundary
    gmsh.model.mesh.field.add("Extend", 1)
    gmsh.model.mesh.field.setNumbers(
        1, "SurfacesList",
        [extract_tag(x) for x in top_arm_surfs + bot_arm_surfs + gap_rect_surfs],
    )
    gmsh.model.mesh.field.setNumber(1, "DistMax", outer_boundary_radius)
    gmsh.model.mesh.field.setNumber(1, "SizeMax", wavelength / n_farfield)
    gmsh.model.mesh.field.setAsBackgroundMesh(1)

    gmsh.option.setNumber("Mesh.Algorithm3D", 1)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(3)

    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.Binary", 1)
    gmsh.write(filename)

    print(f"Dipole mesh written to {filename}")
    gmsh.finalize()
    return filename


dipole_mesh = generate_dipole_mesh(wavelength=4.0)
```

    Dipole mesh written to dipole.msh



```python
groups = pv_from_meshio(dipole_mesh)
print("Physical groups:", list(groups.keys()))

meshes = {}
if "top_arm" in groups:
    meshes["Top arm (PEC)"] = (groups["top_arm"], COLOR_METAL, 0.8)
if "bot_arm" in groups:
    meshes["Bottom arm (PEC)"] = (groups["bot_arm"], COLOR_METAL, 0.8)
if "port" in groups:
    meshes["Lumped port"] = (groups["port"], COLOR_PORT, 1.0)
if "absorbing" in groups:
    meshes["Absorbing BC"] = (groups["absorbing"], COLOR_AIR, 0.1)

render_multi_mesh(
    meshes,
    IMG_DIR / "dipole_mesh.htm",
    title="Half-Wave Dipole Antenna",
)

HTML(show_viewer("dipole_mesh"))
```

    


    Physical groups: ['top_arm', 'bot_arm', 'port', 'absorbing']


    /home/martin/Desktop/palace-course/palace/viz.py:40: PyVistaDeprecationWarning: This function is deprecated and will be removed in future version of PyVista. Use vtk with osmesa instead.
      pv.start_xvfb()


    /home/martin/Desktop/palace-course/.venv/lib/python3.12/site-packages/IPython/core/display.py:447: UserWarning: Consider using IPython.display.IFrame instead
      warnings.warn("Consider using IPython.display.IFrame instead")





<iframe src="img/dipole_mesh.htm" loading="lazy" style="width:100%;height:500px;border:1px solid #ccc;border-radius:8px;"></iframe>



*Interactive viewer — the two cylindrical arms are separated by the orange lumped port.*

## Palace Configuration for the Dipole

The dipole uses a driven (frequency-domain) simulation with:

- **PEC** on the arm surfaces.
- **Absorbing BC** (2nd order) on the outer sphere.
- **Lumped port** at the gap rectangle with $Z_0 = 50\,\Omega$, direction `+Z`.
- A single-frequency solve at $f = c / \lambda$.


```python
import json

wavelength = 4.0  # metres
freq_ghz = 0.3 / wavelength  # c / λ in GHz (with c ≈ 0.3 GHz·m)

dipole_config = {
    "Problem": {
        "Type": "Driven",
        "Verbose": 2,
        "Output": "postpro/dipole",
    },
    "Model": {
        "Mesh": "dipole.msh",
        "L0": 1.0,  # mesh is in metres
    },
    "Domains": {
        "Materials": [{"Attributes": [5]}],  # air volume
    },
    "Boundaries": {
        "PEC": {"Attributes": [1, 2]},       # top + bottom arm surfaces
        "Absorbing": {"Attributes": [4], "Order": 2},
        "LumpedPort": [
            {
                "Index": 1,
                "R": 50.0,
                "Excitation": True,
                "Attributes": [3],
                "Direction": "+Z",
            }
        ],
        "Postprocessing": {
            "FarField": {
                "Attributes": [4],
                "NSample": 64800,
            },
        },
    },
    "Solver": {
        "Order": 2,
        "Device": "CPU",
        "Driven": {
            "Samples": [{"Type": "Point", "Freq": [round(freq_ghz, 4)], "SaveStep": 1}],
        },
        "Linear": {
            "Type": "Default",
            "KSPType": "GMRES",
            "Tol": 1e-10,
            "MaxIts": 100,
        },
    },
}

with open("dipole.json", "w") as f:
    json.dump(dipole_config, f, indent=2)

print(f"Simulation frequency: {freq_ghz:.4f} GHz")
print(json.dumps(dipole_config, indent=2))
```

    Simulation frequency: 0.0750 GHz
    {
      "Problem": {
        "Type": "Driven",
        "Verbose": 2,
        "Output": "postpro/dipole"
      },
      "Model": {
        "Mesh": "dipole.msh",
        "L0": 1.0
      },
      "Domains": {
        "Materials": [
          {
            "Attributes": [
              5
            ]
          }
        ]
      },
      "Boundaries": {
        "PEC": {
          "Attributes": [
            1,
            2
          ]
        },
        "Absorbing": {
          "Attributes": [
            4
          ],
          "Order": 2
        },
        "LumpedPort": [
          {
            "Index": 1,
            "R": 50.0,
            "Excitation": true,
            "Attributes": [
              3
            ],
            "Direction": "+Z"
          }
        ],
        "Postprocessing": {
          "FarField": {
            "Attributes": [
              4
            ],
            "NSample": 64800
          }
        }
      },
      "Solver": {
        "Order": 2,
        "Device": "CPU",
        "Driven": {
          "Samples": [
            {
              "Type": "Point",
              "Freq": [
                0.075
              ],
              "SaveStep": 1
            }
          ]
        },
        "Linear": {
          "Type": "Default",
          "KSPType": "GMRES",
          "Tol": 1e-10,
          "MaxIts": 100
        }
      }
    }


## Extracting Input Impedance

After running the simulation, PalaceToolkit provides a helper to read
the port CSV files and compute the antenna impedance:

```python
from palace.simulation import run_palace, extract_impedance

run_palace("dipole.json", num_procs=4)

freq_ghz, z_ant = extract_impedance("postpro/dipole")
print(f"Z_ant = {z_ant[0].real:.1f} + j{z_ant[0].imag:.1f} Ω")
```

The `extract_impedance` function:

1. Reads `port-S.csv` for $|S_{11}|$ and phase.
2. Reads `port-V.csv` and `port-I.csv` to determine the reference impedance $Z_0$.
3. Computes $Z_{\text{ant}} = Z_0 (1 + S_{11}) / (1 - S_{11})$.

## The Art of the Lumped Port

The accuracy of the impedance result depends critically on the port geometry.
Key considerations:

- **Gap size**: the port rectangle should be small relative to $\lambda$
  but large enough for at least 2-3 mesh elements across it.
- **Port direction**: must match the expected E-field orientation (`+Z` for
  a z-oriented dipole).
- **Mesh convergence**: reduce element size near the port and check that
  the impedance converges.

A practical workflow:

1. Run a **port-only** simulation (no PEC arms, just the port in free space)
   to verify the port impedance equals $Z_0$.
2. Enable the PEC arms and check convergence with port size.
3. Compare against the known dipole impedance.

---

**Next:** [Coplanar Waveguide →](coplanar-waveguide.md)
