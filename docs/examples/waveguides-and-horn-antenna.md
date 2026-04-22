# Waveguides and Waveports

This tutorial covers rectangular waveguide simulation using Palace's
**waveport** boundary condition. You will learn:

1. How waveports work — the 2D eigenvalue problem on each port face.
2. How to mesh a rectangular waveguide (WR-90) with Gmsh.
3. How to set up and run a driven (frequency-domain) simulation.
4. How to build a pyramidal horn antenna with a waveport feed.

---

## Waveports Explained

A **waveport** is a special boundary condition where Palace solves a 2D
eigenvalue problem on the port cross-section to find the waveguide modes.
The resulting mode field pattern is used to:

- **Excite** the structure with a specific mode (e.g., TE₁₀).
- **Absorb** outgoing waves, acting as a matched termination.
- **Extract S-parameters** by decomposing the total field into incident
  and reflected mode amplitudes.

Unlike lumped ports (which assume a TEM-like feed), waveports correctly
handle dispersive waveguide modes, including cutoff behaviour.

### WR-90 Rectangular Waveguide

The WR-90 standard has dimensions $a = 22.86$ mm × $b = 10.16$ mm.
The TE₁₀ cutoff frequency is:

$$
f_c = \frac{c}{2a} = \frac{3 \times 10^8}{2 \times 22.86 \times 10^{-3}} \approx 6.56 \text{ GHz}
$$

The single-mode bandwidth extends from 6.56 to 13.12 GHz.


```python
from pathlib import Path
from IPython.display import HTML
from palace.viz import (
    render_mesh, render_multi_mesh, show_viewer,
    pv_from_meshio, COLOR_METAL, COLOR_PORT,
)

IMG_DIR = Path("img")
IMG_DIR.mkdir(exist_ok=True)
```

## Meshing a Rectangular Waveguide

We create the waveguide by drawing a rectangle and extruding it along the
propagation direction (z). The extrude approach gives us direct access to
the input face (waveport 1), output face (waveport 2), and lateral walls
(PEC metal).


```python
import gmsh
import os


def generate_waveguide_box(
    filename="waveguide_box.msh",
    width=22.86e-3,      # WR-90 broad wall (m)
    height=10.16e-3,     # WR-90 narrow wall (m)
    length=100e-3,       # propagation length (m)
):
    """Generate a WR-90 rectangular waveguide mesh via extrusion.

    Returns (output_path, pg_map) where pg_map maps physical-group
    names to their integer tags.
    """
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("waveguide_box")
    kernel = gmsh.model.occ

    # Draw input cross-section (this face becomes waveport 1)
    rect = kernel.addRectangle(-width / 2, -height / 2, 0, width, height)

    # Extrude along z to create the waveguide volume
    extruded = kernel.extrude([(2, rect)], 0, 0, length)
    kernel.synchronize()

    # Parse extrude results
    waveport_1_tag = rect              # original face at z=0
    waveport_2_tag = extruded[0][1]    # extruded copy at z=length
    metal_tags = [tag for dim, tag in extruded[2:] if dim == 2]
    vol_tag = extruded[1][1]

    # Physical groups (→ Palace attributes)
    pg_wp1 = gmsh.model.addPhysicalGroup(2, [waveport_1_tag], name="waveport_1")
    pg_wp2 = gmsh.model.addPhysicalGroup(2, [waveport_2_tag], name="waveport_2")
    pg_metal = gmsh.model.addPhysicalGroup(2, metal_tags, name="metal")
    pg_vol = gmsh.model.addPhysicalGroup(3, [vol_tag], name="waveguide_volume")

    pg_map = {
        "waveport_1": pg_wp1,
        "waveport_2": pg_wp2,
        "metal": pg_metal,
        "waveguide_volume": pg_vol,
    }

    # Mesh
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.005)
    gmsh.option.setNumber("Mesh.Algorithm", 4)
    gmsh.option.setNumber("Mesh.Algorithm3D", 2)
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(2)

    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.Binary", 0)
    gmsh.write(filename)

    print(f"Mesh written to {filename}")
    for name, tag in pg_map.items():
        print(f"  {name}: attribute {tag}")

    gmsh.finalize()
    return filename, pg_map


mesh_file, pg_map = generate_waveguide_box()
```

    Mesh written to waveguide_box.msh
      waveport_1: attribute 1
      waveport_2: attribute 2
      metal: attribute 3
      waveguide_volume: attribute 4



```python
groups = pv_from_meshio(mesh_file)

render_multi_mesh(
    {
        "Metal walls": (groups["metal"], COLOR_METAL, 0.3),
        "Waveport 1": (groups["waveport_1"], COLOR_PORT, 1.0),
        "Waveport 2": (groups["waveport_2"], "#42A5F5", 1.0),
    },
    IMG_DIR / "waveguide_box_mesh.htm",
    title="WR-90 Rectangular Waveguide",
)

HTML(show_viewer("waveguide_box_mesh"))
```

    


    /home/martin/Desktop/palace-course/palace/viz.py:40: PyVistaDeprecationWarning: This function is deprecated and will be removed in future version of PyVista. Use vtk with osmesa instead.
      pv.start_xvfb()


    /home/martin/Desktop/palace-course/.venv/lib/python3.12/site-packages/IPython/core/display.py:447: UserWarning: Consider using IPython.display.IFrame instead
      warnings.warn("Consider using IPython.display.IFrame instead")





<iframe src="img/waveguide_box_mesh.htm" loading="lazy" style="width:100%;height:500px;border:1px solid #ccc;border-radius:8px;"></iframe>



*Interactive viewer — drag to rotate. The orange face is the excited waveport.*

## Palace Configuration for a Waveguide

The key difference from the coaxial cable is the **WavePort** boundary
instead of **LumpedPort**. Each waveport specifies:

- `Mode`: which eigensolution to use (1 = fundamental TE₁₀).
- `Excitation`: whether this port drives the structure.
- `Offset`: frequency-dependent phase de-embedding offset.


```python
import json


def generate_waveguide_palace_config(pg_map, mesh_file, output_file="waveguide_box.json"):
    """Write a Palace JSON config for a hollow rectangular waveguide."""
    config = {
        "Problem": {
            "Type": "Driven",
            "Verbose": 2,
            "Output": "postpro/waveguide_box",
        },
        "Model": {
            "Mesh": mesh_file,
            "L0": 1.0,  # mesh is in metres
            "Refinement": {},
        },
        "Domains": {
            "Materials": [
                {
                    "Attributes": [pg_map["waveguide_volume"]],
                    "Permeability": 1.0,
                    "Permittivity": 1.0,
                    "LossTan": 0.0,
                }
            ],
        },
        "Boundaries": {
            "PEC": {"Attributes": [pg_map["metal"]]},
            "WavePort": [
                {
                    "Index": 1,
                    "Attributes": [pg_map["waveport_1"]],
                    "Mode": 1,
                    "Offset": 0.0,
                    "Excitation": True,
                },
                {
                    "Index": 2,
                    "Attributes": [pg_map["waveport_2"]],
                    "Mode": 1,
                    "Offset": 0.0,
                },
            ],
        },
        "Solver": {
            "Order": 2,
            "Device": "CPU",
            "Driven": {
                "MinFreq": 6.0,
                "MaxFreq": 15.0,
                "FreqStep": 0.5,
                "SaveStep": 1,
                "AdaptiveTol": 0.001,
            },
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": 1e-8,
                "MaxIts": 200,
            },
        },
    }

    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Palace config written to {output_file}")
    return config


config = generate_waveguide_palace_config(pg_map, mesh_file)
print(json.dumps(config, indent=2))
```

    Palace config written to waveguide_box.json
    {
      "Problem": {
        "Type": "Driven",
        "Verbose": 2,
        "Output": "postpro/waveguide_box"
      },
      "Model": {
        "Mesh": "waveguide_box.msh",
        "L0": 1.0,
        "Refinement": {}
      },
      "Domains": {
        "Materials": [
          {
            "Attributes": [
              4
            ],
            "Permeability": 1.0,
            "Permittivity": 1.0,
            "LossTan": 0.0
          }
        ]
      },
      "Boundaries": {
        "PEC": {
          "Attributes": [
            3
          ]
        },
        "WavePort": [
          {
            "Index": 1,
            "Attributes": [
              1
            ],
            "Mode": 1,
            "Offset": 0.0,
            "Excitation": true
          },
          {
            "Index": 2,
            "Attributes": [
              2
            ],
            "Mode": 1,
            "Offset": 0.0
          }
        ]
      },
      "Solver": {
        "Order": 2,
        "Device": "CPU",
        "Driven": {
          "MinFreq": 6.0,
          "MaxFreq": 15.0,
          "FreqStep": 0.5,
          "SaveStep": 1,
          "AdaptiveTol": 0.001
        },
        "Linear": {
          "Type": "Default",
          "KSPType": "GMRES",
          "Tol": 1e-08,
          "MaxIts": 200
        }
      }
    }


## Expected Results

After running Palace (`run_palace("waveguide_box.json", num_procs=4)`) the
`postpro/waveguide_box/port-S.csv` file contains the S-parameters:

- **Below cutoff** (< 6.56 GHz): $|S_{21}|$ drops sharply, $|S_{11}| \approx 0$ dB.
- **Above cutoff**: $|S_{21}| \approx 0$ dB (lossless transmission),
  $|S_{11}| \ll -30$ dB.
- The waveguide acts as a **high-pass filter** with a sharp cutoff.

---

## Horn Antenna

A pyramidal horn antenna is a natural extension of a rectangular waveguide:
the cross-section flares out to create a larger aperture, producing a
directive radiation pattern.

The geometry consists of:

1. A rectangular waveguide feed section.
2. A pyramidal flare connecting the waveguide to the aperture.
3. An air sphere surrounding the antenna (with absorbing BC).
4. A waveport on the waveguide input face.

### Building the Horn Geometry

We construct the horn by defining two rectangular cross-sections
(waveguide face and aperture face), connecting them with ruled surfaces,
and then fragmenting with an outer air sphere.


```python
import math


def extract_tag(obj):
    """Extract the Gmsh tag from a dimtag or single-element list."""
    if isinstance(obj, list) and len(obj) == 1:
        return extract_tag(obj[0])
    elif isinstance(obj, tuple):
        return obj[1]
    raise ValueError("Expected a tuple or single-element list")


def xmin(dt):
    return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[0]

def zmin(dt):
    return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[2]

def zmax(dt):
    return gmsh.model.occ.getBoundingBox(dt[0], dt[1])[5]


def generate_horn_antenna(
    filename="horn_antenna.msh",
    lc=0.005,
    waveguide_length=0.05,
    waveguide_width=22.86e-3,
    waveguide_height=10.16e-3,
    flare_length=0.1,
    flare_width=0.08,
    flare_height=0.06,
    freq_ghz=10.0,
):
    """Generate a pyramidal horn antenna mesh.

    The horn is modelled as two rectangular cross-sections connected
    by ruled surfaces, enclosed in an air sphere with absorbing BC.
    """
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("horn_antenna")
    kernel = gmsh.model.occ

    c0 = 3e8
    lambda_0 = c0 / (freq_ghz * 1e9)

    # Waveguide face (horn throat) at z=0
    for i, (x, y) in enumerate([
        (-waveguide_width/2, -waveguide_height/2),
        ( waveguide_width/2, -waveguide_height/2),
        ( waveguide_width/2,  waveguide_height/2),
        (-waveguide_width/2,  waveguide_height/2),
    ]):
        kernel.addPoint(x, y, 0, lc, i + 1)

    for i in range(4):
        kernel.addLine(i + 1, (i + 1) % 4 + 1, i + 1)
    kernel.addCurveLoop([1, 2, 3, 4], 1)
    kernel.addPlaneSurface([1], 1)

    # Aperture face at z=flare_length
    for i, (x, y) in enumerate([
        (-flare_width/2, -flare_height/2),
        ( flare_width/2, -flare_height/2),
        ( flare_width/2,  flare_height/2),
        (-flare_width/2,  flare_height/2),
    ]):
        kernel.addPoint(x, y, flare_length, lc, i + 5)

    for i in range(4):
        kernel.addLine(i + 5, (i + 1) % 4 + 5, i + 5)
    kernel.addCurveLoop([5, 6, 7, 8], 2)
    kernel.addPlaneSurface([2], 2)

    # Connect throat to aperture (flare walls)
    for i in range(4):
        kernel.addLine(i + 1, i + 5, i + 9)

    for i in range(4):
        j = (i + 1) % 4
        kernel.addCurveLoop([i + 1, j + 9, -(i + 5), -(i + 9)], i + 3)
        kernel.addPlaneSurface([i + 3], i + 3)

    kernel.addSurfaceLoop([1, 2, 3, 4, 5, 6], 1)
    flare = kernel.addVolume([1], 1)

    # Waveguide feed (extrude throat backwards)
    waveguide = kernel.extrude([(2, 1)], 0, 0, -waveguide_length)

    # Air sphere
    outer_radius = flare_length
    outer_boundary = kernel.addSphere(0, 0, flare_length / 2, outer_radius)

    # Fragment everything
    kernel.fragment([(3, outer_boundary)], [(3, flare), waveguide[1]])
    kernel.synchronize()

    # Identify regions by bounding-box queries
    all_2d = gmsh.model.getEntities(2)
    all_3d = gmsh.model.getEntities(3)

    def spans_domain(x):
        return math.isclose(xmin(x), -outer_radius, abs_tol=flare_length / 100)

    outer_sphere = [x for x in all_2d if spans_domain(x)]
    domain = [x for x in all_3d if spans_domain(x)]
    waveport = [x for x in all_2d
                if math.isclose(zmin(x), -waveguide_length, abs_tol=1e-6)
                and math.isclose(zmax(x), -waveguide_length, abs_tol=1e-6)]
    waveguide_surfs = [x for x in all_2d
                       if zmin(x) < 0 and zmax(x) < flare_length / 3
                       and x not in waveport
                       and not (math.isclose(zmin(x), 0, abs_tol=1e-6)
                                and math.isclose(zmax(x), 0, abs_tol=1e-6))]
    flare_surfs = [x for x in all_2d
                   if zmax(x) > flare_length / 2
                   and zmax(x) < 1.25 * flare_length
                   and zmin(x) < flare_length / 2]

    # Physical groups
    pg_wg = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in waveguide_surfs], -1, "waveguide_pec")
    pg_fl = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in flare_surfs], -1, "flare_pec")
    pg_abc = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in outer_sphere], -1, "absorbing")
    pg_wp = gmsh.model.addPhysicalGroup(2, [extract_tag(x) for x in waveport], -1, "waveport")
    pg_vol = gmsh.model.addPhysicalGroup(3, [extract_tag(x) for x in domain], -1, "air")

    # Mesh size from wavelength
    gmsh.option.setNumber("Mesh.MeshSizeMax", lambda_0 / 4)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
    gmsh.option.setNumber("Mesh.Algorithm3D", 1)
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(2)

    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.Binary", 1)
    gmsh.write(filename)

    print(f"Horn antenna mesh written to {filename}")
    gmsh.finalize()
    return filename


horn_mesh = generate_horn_antenna()
```

    Horn antenna mesh written to horn_antenna.msh



```python
horn_groups = pv_from_meshio(horn_mesh)
print("Physical groups:", list(horn_groups.keys()))

meshes_to_render = {}
if "waveguide_pec" in horn_groups:
    meshes_to_render["Waveguide PEC"] = (horn_groups["waveguide_pec"], COLOR_METAL, 0.6)
if "flare_pec" in horn_groups:
    meshes_to_render["Flare PEC"] = (horn_groups["flare_pec"], COLOR_METAL, 0.4)
if "waveport" in horn_groups:
    meshes_to_render["Waveport"] = (horn_groups["waveport"], COLOR_PORT, 1.0)
if "absorbing" in horn_groups:
    meshes_to_render["Absorbing BC"] = (horn_groups["absorbing"], "#E3F2FD", 0.15)

render_multi_mesh(
    meshes_to_render,
    IMG_DIR / "horn_antenna_mesh.htm",
    title="Pyramidal Horn Antenna",
)

HTML(show_viewer("horn_antenna_mesh"))
```

    


    Physical groups: ['waveguide_pec', 'flare_pec', 'absorbing', 'waveport']


    /home/martin/Desktop/palace-course/palace/viz.py:40: PyVistaDeprecationWarning: This function is deprecated and will be removed in future version of PyVista. Use vtk with osmesa instead.
      pv.start_xvfb()
    /home/martin/Desktop/palace-course/.venv/lib/python3.12/site-packages/IPython/core/display.py:447: UserWarning: Consider using IPython.display.IFrame instead
      warnings.warn("Consider using IPython.display.IFrame instead")





<iframe src="img/horn_antenna_mesh.htm" loading="lazy" style="width:100%;height:500px;border:1px solid #ccc;border-radius:8px;"></iframe>



*Interactive viewer — the horn flare opens into the air sphere.*

## Key Takeaways

| Feature | Lumped Port | Wave Port |
|---------|------------|----------|
| Mode type | TEM only | TE, TM, TEM |
| Port geometry | Small gap/rectangle | Full waveguide cross-section |
| Cutoff behaviour | N/A | Naturally captured |
| Impedance reference | User-specified R | Mode impedance from eigensolver |
| Use case | Coax feeds, antenna gaps | Waveguides, horn feeds |

---

**Next:** [Dipole Antenna →](dipole-antenna.md)
