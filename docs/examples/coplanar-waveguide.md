# Planar Microwave Circuits — Coplanar Waveguide

This tutorial demonstrates three ways to simulate a **Coplanar Waveguide**
(CPW) using Palace:

1. **2D cross-section** — extract the quasi-static mode shape.
2. **Driven (waveport)** — full 3D frequency-domain S-parameter sweep.
3. **Eigenmode** — periodic unit cell with Bloch boundary conditions to
   extract the propagation constant and effective index.

You will learn:

- How to model planar PEC conductors on a dielectric substrate.
- How to use `Entity`-based geometry for structured boolean pipelines.
- How to apply periodic boundary conditions and prescribe a Floquet phase.
- How to compare numerical results with closed-form conformal-mapping
  formulas.

---

## CPW Geometry

A symmetric CPW has three coplanar conductors on a dielectric substrate:

| Parameter | Symbol | Value |
| --- | --- | --- |
| Centre trace width | $W$ | 600 µm |
| Gap | $S$ | 200 µm |
| Ground-plane width | — | 2500 µm |
| Substrate thickness | $h$ | 508 µm (≈ 20 mil) |
| Permittivity | $\varepsilon_r$ | 3.48 (Rogers RO4003C) |

The conductors are infinitely thin (planar PEC). The air region above
the substrate is extended to capture fringing fields.

### Conformal-Mapping Formulas

Closed-form expressions using elliptic-integral ratios $K(k)/K(k')$
give the quasi-static impedance and effective index:

$$
Z_0 = \frac{30\pi}{\sqrt{\varepsilon_{\text{eff}}}} \cdot \frac{1}{K(k)/K(k')}
$$

$$
n_{\text{eff}} = \sqrt{\varepsilon_{\text{eff}}}
$$

where $k = W/(W + 2S)$ and $\varepsilon_{\text{eff}}$ accounts for
the filling fraction through the substrate mapping $k_1$.


```python
from pathlib import Path
from IPython.display import HTML
from palace.viz import (
    render_mesh, render_multi_mesh, show_viewer, show_viewers,
    pv_from_meshio,
    COLOR_METAL, COLOR_PORT, COLOR_AIR, COLOR_DIELECTRIC,
)

IMG_DIR = Path("img")
IMG_DIR.mkdir(exist_ok=True)
```

## Analytical Reference Values

PalaceToolkit's `analytic` module provides the conformal-mapping formulas.
Let's compute the reference values first:


```python
import numpy as np
from palace.analytic import cpw_impedance, cpw_effective_index

# CPW dimensions (µm)
trace_width = 600.0
gap = 200.0
substrate_thickness = 508.0
eps_r = 3.48

Z0_analytic = cpw_impedance(w=trace_width, s=gap, h=substrate_thickness, eps_r=eps_r)
n_eff_analytic = cpw_effective_index(w=trace_width, s=gap, h=substrate_thickness, eps_r=eps_r)

print(f"Analytical Z₀     = {Z0_analytic:.2f} Ω")
print(f"Analytical n_eff  = {n_eff_analytic:.4f}")
print(f"Analytical ε_eff  = {n_eff_analytic**2:.4f}")
```

    Analytical Z₀     = 74.57 Ω
    Analytical n_eff  = 1.4404
    Analytical ε_eff  = 2.0747


## Building the CPW Geometry with Entities

The `Entity` class in `palace.mesh` provides a declarative way to define
geometry primitives and let the boolean pipeline handle fragmentation
and physical-group assignment automatically.

Each `Entity` has:
- **`name`** — becomes the physical group name.
- **`dim`** — topological dimension (2 = surface, 3 = volume).
- **`mesh_order`** — priority in the boolean fragment (lower = embedded first).
- **`tags`** — initial Gmsh OCC tags for any primitive.


```python
import gmsh
from palace.mesh import (
    Entity, run_boolean_pipeline, generate_3d_mesh,
    make_yz_rect, set_periodic_mesh, refine_near_surfaces,
)

# Geometry parameters (µm)
substrate_length = 2000.0
substrate_width = 10000.0
ground_width = 2500.0
air_gap_y = 3000.0
air_gap_z = 8000.0

# Mesh sizes
mesh_size_map = {
    "ground_left":  10.0,
    "signal":       10.0,
    "ground_right": 10.0,
    "substrate":    300.0,
    "air":          300.0,
}


def build_cpw_geometry():
    """Create CPW primitives and return Gmsh OCC tags."""
    kernel = gmsh.model.occ

    sub = kernel.addBox(0, 0, 0, substrate_length, substrate_width, substrate_thickness)
    air = kernel.addBox(
        0, -air_gap_y, 0,
        substrate_length,
        substrate_width + 2 * air_gap_y,
        substrate_thickness + air_gap_z,
    )

    total_cpw = ground_width + gap + trace_width + gap + ground_width
    y0 = (substrate_width - total_cpw) / 2.0

    gl = kernel.addRectangle(0, y0, substrate_thickness, substrate_length, ground_width)
    sig = kernel.addRectangle(
        0, y0 + ground_width + gap, substrate_thickness,
        substrate_length, trace_width,
    )
    gr = kernel.addRectangle(
        0, y0 + ground_width + gap + trace_width + gap, substrate_thickness,
        substrate_length, ground_width,
    )
    return dict(substrate=sub, air_box=air, ground_left=gl, signal=sig, ground_right=gr)


print("Geometry builder defined.")
```

    Geometry builder defined.


## Mode 1: Driven Simulation with Wave Ports

In driven mode we create YZ-plane rectangles at $x = 0$ and
$x = L$ as wave ports. The boolean pipeline fragments the geometry
and assigns physical groups for Palace.


```python
gmsh.initialize()
gmsh.option.setNumber("General.Verbosity", 0)
gmsh.model.add("cpw_driven")

tags = build_cpw_geometry()

# Wave port faces
wp_left = make_yz_rect(
    x=0,
    y0=-air_gap_y, y1=substrate_width + air_gap_y,
    z0=0, z1=substrate_thickness + air_gap_z,
)
wp_right = make_yz_rect(
    x=substrate_length,
    y0=-air_gap_y, y1=substrate_width + air_gap_y,
    z0=0, z1=substrate_thickness + air_gap_z,
)

entities = [
    Entity("ground_left",    dim=2, mesh_order=0, tags=[tags["ground_left"]]),
    Entity("signal",         dim=2, mesh_order=0, tags=[tags["signal"]]),
    Entity("ground_right",   dim=2, mesh_order=0, tags=[tags["ground_right"]]),
    Entity("substrate",      dim=3, mesh_order=1, tags=[tags["substrate"]]),
    Entity("air",            dim=3, mesh_order=2, tags=[tags["air_box"]]),
    Entity("waveport_left",  dim=2, mesh_order=0, tags=[wp_left]),
    Entity("waveport_right", dim=2, mesh_order=0, tags=[wp_right]),
]

pg_map = run_boolean_pipeline(entities)

mesh_file = "cpw_driven.msh"
generate_3d_mesh(entities, mesh_size_map, mesh_file)
gmsh.finalize()

print(f"\nPhysical groups: {pg_map}")
```

      Physical group 'substrate' (dim=3): pg=1, tags=[1]
      Physical group 'air' (dim=3): pg=2, tags=[2]
      Physical group 'ground_left' (dim=2): pg=3, tags=[13]
      Physical group 'signal' (dim=2): pg=4, tags=[14]
      Physical group 'ground_right' (dim=2): pg=5, tags=[15]
      Physical group 'waveport_left' (dim=2): pg=6, tags=[16, 17]
      Physical group 'waveport_right' (dim=2): pg=7, tags=[18, 19]
      Physical group 'air__substrate' (dim=2): pg=8, tags=[3, 4, 21, 22, 23, 24]
      Physical group 'substrate__None' (dim=2): pg=9, tags=[20]
      Physical group 'air__None' (dim=2): pg=10, tags=[25, 26, 27, 28, 29]


    Mesh saved to cpw_driven.msh
      Nodes: 11593
      Elements: 64286
    
    Physical groups: {'ground_left': 3, 'signal': 4, 'ground_right': 5, 'waveport_left': 6, 'waveport_right': 7, 'air__substrate': 8, 'substrate__None': 9, 'air__None': 10, 'substrate': 1, 'air': 2}



```python
groups = pv_from_meshio(mesh_file)

meshes = {}
for name in ["ground_left", "signal", "ground_right"]:
    for gname, gdata in groups.items():
        if name in gname:
            meshes[name] = (gdata, COLOR_METAL, 1.0)
            break

for gname, gdata in groups.items():
    if "substrate" in gname and "None" not in gname:
        meshes["substrate"] = (gdata, COLOR_DIELECTRIC, 0.3)
        break

for gname, gdata in groups.items():
    if "waveport" in gname:
        meshes[gname] = (gdata, COLOR_PORT, 0.5)

render_multi_mesh(meshes, IMG_DIR / "cpw_driven.htm", title="CPW — Driven Mode")
HTML(show_viewer("cpw_driven"))
```

    


    /home/martin/Desktop/palace-course/palace/viz.py:40: PyVistaDeprecationWarning: This function is deprecated and will be removed in future version of PyVista. Use vtk with osmesa instead.
      pv.start_xvfb()


    /home/martin/Desktop/palace-course/.venv/lib/python3.12/site-packages/IPython/core/display.py:447: UserWarning: Consider using IPython.display.IFrame instead
      warnings.warn("Consider using IPython.display.IFrame instead")





<iframe src="img/cpw_driven.htm" loading="lazy" style="width:100%;height:500px;border:1px solid #ccc;border-radius:8px;"></iframe>



## Mode 2: Eigenmode with Periodic Boundaries

For eigenmode analysis we use a short unit cell of length $d$, with
**Bloch periodic boundary conditions** on the two end faces.

### Choosing the Unit-Cell Length

The Bloch phase advance per cell is:

$$
\varphi = \beta \, d = \frac{2\pi f_0 \, n_{\text{eff}} \, d}{c_0}
$$

We want $\pi/4 \lesssim \varphi \lesssim 3\pi/4$ for numerical
stability. Targeting $\varphi = \pi/2$:

$$
d = \frac{\varphi \, c_0}{2\pi f_0 \, n_{\text{eff}} \, L_0}
$$

where $L_0 = 10^{-6}$ m/µm converts from mesh to SI units.


```python
# Physical constants
c0 = 299_792_458.0    # speed of light (m/s)
L0 = 1e-6             # µm → m

# Eigenmode parameters
eigen_target = 5.0    # GHz
phi_target = np.pi / 2

# Derive unit-cell length
d_mesh = round(
    phi_target * c0 / (2 * np.pi * eigen_target * 1e9 * n_eff_analytic * L0)
)

# Floquet wave-vector
kx_floquet = phi_target / d_mesh

# Exact Bloch phase after rounding
phi_exact = 2 * np.pi * eigen_target * 1e9 * n_eff_analytic * d_mesh * L0 / c0

print(f"Unit-cell length:   d = {d_mesh:.0f} µm = {d_mesh * L0 * 1e3:.3f} mm")
print(f"Bloch phase:        φ = {phi_exact:.4f} rad ({np.degrees(phi_exact):.2f}°)")
print(f"Floquet kx:         {kx_floquet:.6e} rad/µm")
```

    Unit-cell length:   d = 10407 µm = 10.407 mm
    Bloch phase:        φ = 1.5708 rad (90.00°)
    Floquet kx:         1.509365e-04 rad/µm



```python
# Build eigenmode mesh with periodic boundary conditions
gmsh.initialize()
gmsh.option.setNumber("General.Verbosity", 0)
gmsh.model.add("cpw_eigenmode")

# Override substrate_length to unit-cell size
old_length = substrate_length
substrate_length_eigen = float(d_mesh)

# Re-create geometry at unit-cell length
kernel = gmsh.model.occ
sub = kernel.addBox(0, 0, 0, substrate_length_eigen, substrate_width, substrate_thickness)
air = kernel.addBox(
    0, -air_gap_y, 0,
    substrate_length_eigen,
    substrate_width + 2 * air_gap_y,
    substrate_thickness + air_gap_z,
)

total_cpw = ground_width + gap + trace_width + gap + ground_width
y0 = (substrate_width - total_cpw) / 2.0

gl = kernel.addRectangle(0, y0, substrate_thickness, substrate_length_eigen, ground_width)
sig = kernel.addRectangle(
    0, y0 + ground_width + gap, substrate_thickness,
    substrate_length_eigen, trace_width,
)
gr = kernel.addRectangle(
    0, y0 + ground_width + gap + trace_width + gap, substrate_thickness,
    substrate_length_eigen, ground_width,
)

# Periodic faces
periodic_left = make_yz_rect(
    x=0,
    y0=-air_gap_y, y1=substrate_width + air_gap_y,
    z0=0, z1=substrate_thickness + air_gap_z,
)
periodic_right = make_yz_rect(
    x=substrate_length_eigen,
    y0=-air_gap_y, y1=substrate_width + air_gap_y,
    z0=0, z1=substrate_thickness + air_gap_z,
)

entities_eigen = [
    Entity("ground_left",     dim=2, mesh_order=0, tags=[gl]),
    Entity("signal",          dim=2, mesh_order=0, tags=[sig]),
    Entity("ground_right",    dim=2, mesh_order=0, tags=[gr]),
    Entity("substrate",       dim=3, mesh_order=1, tags=[sub]),
    Entity("air",             dim=3, mesh_order=2, tags=[air]),
    Entity("periodic_left",   dim=2, mesh_order=0, tags=[periodic_left]),
    Entity("periodic_right",  dim=2, mesh_order=0, tags=[periodic_right]),
]

pg_map_eigen = run_boolean_pipeline(entities_eigen)

# Enforce periodic mesh
left_ent = [e for e in entities_eigen if e.name == "periodic_left"][0]
right_ent = [e for e in entities_eigen if e.name == "periodic_right"][0]
set_periodic_mesh(left_ent, right_ent, translation=(substrate_length_eigen, 0, 0))

# Graded refinement near conductors
guided_wavelength = c0 / (eigen_target * 1e9 * n_eff_analytic) / L0  # µm

cond_dimtags = []
for e in entities_eigen:
    if e.name in {"ground_left", "signal", "ground_right"} and e.dimtags:
        cond_dimtags.extend(e.dimtags)

refine_near_surfaces(
    surface_dimtags=cond_dimtags,
    wavelength=guided_wavelength,
    ppw_near=2000, ppw_far=8,
    transition_distance=0.25 * guided_wavelength,
)

gmsh.model.mesh.generate(3)
gmsh.model.mesh.optimize("Netgen")
gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)

eigen_mesh_file = "cpw_eigenmode.msh"
gmsh.write(eigen_mesh_file)

n_nodes = len(gmsh.model.mesh.getNodes()[0])
print(f"Eigenmode mesh: {n_nodes} nodes")
print(f"Physical groups: {pg_map_eigen}")
gmsh.finalize()
```

      Physical group 'substrate' (dim=3): pg=1, tags=[1]
      Physical group 'air' (dim=3): pg=2, tags=[2]
      Physical group 'ground_left' (dim=2): pg=3, tags=[13]
      Physical group 'signal' (dim=2): pg=4, tags=[14]
      Physical group 'ground_right' (dim=2): pg=5, tags=[15]
      Physical group 'periodic_left' (dim=2): pg=6, tags=[16, 17]
      Physical group 'periodic_right' (dim=2): pg=7, tags=[18, 19]
      Physical group 'air__substrate' (dim=2): pg=8, tags=[3, 4, 21, 22, 23, 24]
      Physical group 'substrate__None' (dim=2): pg=9, tags=[20]
      Physical group 'air__None' (dim=2): pg=10, tags=[25, 26, 27, 28, 29]
      Periodic mesh: surface 16 → 18
      Periodic mesh: surface 17 → 19
      Matched 2 periodic surface pairs
      12 conductor boundary curves
      ppw_near=2000  ppw_far=8
      SizeMin=20.8135 (2000 pts/λ)
      SizeMax=5203.3835 (8 pts/λ)
      Transition distance: 0 → 10406.7669


    Eigenmode mesh: 33616 nodes
    Physical groups: {'ground_left': 3, 'signal': 4, 'ground_right': 5, 'periodic_left': 6, 'periodic_right': 7, 'air__substrate': 8, 'substrate__None': 9, 'air__None': 10, 'substrate': 1, 'air': 2}



```python
groups_eigen = pv_from_meshio(eigen_mesh_file)

meshes_eigen = {}
for gname, gdata in groups_eigen.items():
    if any(c in gname for c in ["ground", "signal"]) and "periodic" not in gname:
        meshes_eigen[gname] = (gdata, COLOR_METAL, 1.0)
    elif "substrate" in gname and "None" not in gname:
        meshes_eigen[gname] = (gdata, COLOR_DIELECTRIC, 0.3)

render_multi_mesh(meshes_eigen, IMG_DIR / "cpw_eigenmode.htm", title="CPW — Eigenmode Unit Cell")
HTML(show_viewer("cpw_eigenmode"))
```

    


    /home/martin/Desktop/palace-course/palace/viz.py:40: PyVistaDeprecationWarning: This function is deprecated and will be removed in future version of PyVista. Use vtk with osmesa instead.
      pv.start_xvfb()
    /home/martin/Desktop/palace-course/.venv/lib/python3.12/site-packages/IPython/core/display.py:447: UserWarning: Consider using IPython.display.IFrame instead
      warnings.warn("Consider using IPython.display.IFrame instead")





<iframe src="img/cpw_eigenmode.htm" loading="lazy" style="width:100%;height:500px;border:1px solid #ccc;border-radius:8px;"></iframe>



## Palace Configuration for Eigenmode

The eigenmode config specifies:

- **Periodic BCs** with a Floquet wave-vector `[kx, 0, 0]`.
- **PEC** on all conductor surfaces.
- **Absorbing** on the non-periodic exterior faces.
- **Eigenmode solver** targeting one mode near $f_0$.


```python
import json

# Classify physical groups
conductor_names = {"ground_left", "signal", "ground_right"}
pec_attrs = []
absorbing_attrs = []
periodic_donor = []
periodic_receiver = []
air_tag = None
substrate_tag = None

for name, tag in sorted(pg_map_eigen.items()):
    parts = name.split("__")
    if name == "periodic_left":
        periodic_donor.append(tag)
    elif name == "periodic_right":
        periodic_receiver.append(tag)
    elif name.startswith("periodic"):
        continue
    elif len(parts) >= 2:
        has_none = "None" in parts
        non_none = [p for p in parts if p != "None"]
        if any(p in conductor_names for p in non_none):
            pec_attrs.append(tag)
        elif any(p.startswith("periodic") for p in parts):
            continue
        elif has_none:
            absorbing_attrs.append(tag)
    else:
        if name == "air":
            air_tag = tag
        elif name == "substrate":
            substrate_tag = tag
        elif name in conductor_names:
            pec_attrs.append(tag)

eigenmode_config = {
    "Problem": {"Type": "Eigenmode", "Verbose": 2, "Output": "postpro/cpw_eigenmode"},
    "Model": {"Mesh": eigen_mesh_file, "L0": L0},
    "Domains": {
        "Materials": [
            {"Attributes": [air_tag], "Permeability": 1.0, "Permittivity": 1.0, "LossTan": 0.0},
            {"Attributes": [substrate_tag], "Permeability": 1.0, "Permittivity": float(eps_r), "LossTan": 0.0},
        ],
    },
    "Boundaries": {
        "PEC": {"Attributes": sorted(pec_attrs)},
        "Absorbing": {"Attributes": sorted(absorbing_attrs), "Order": 1},
        "Periodic": {
            "FloquetWaveVector": [kx_floquet, 0.0, 0.0],
            "BoundaryPairs": [{
                "DonorAttributes": sorted(periodic_donor),
                "ReceiverAttributes": sorted(periodic_receiver),
            }],
        },
    },
    "Solver": {
        "Order": 1,
        "Device": "CPU",
        "Eigenmode": {
            "Target": eigen_target,
            "N": 1,
            "Tol": 1e-6,
            "MaxIts": 100,
            "Save": 1,
        },
        "Linear": {
            "Type": "STRUMPACK",
            "MGMaxLevels": 1,
            "KSPType": "GMRES",
            "Tol": 1e-8,
            "MaxIts": 2000,
        },
    },
}

with open("cpw_eigenmode.json", "w") as f:
    json.dump(eigenmode_config, f, indent=2)

print(json.dumps(eigenmode_config, indent=2))
```

    {
      "Problem": {
        "Type": "Eigenmode",
        "Verbose": 2,
        "Output": "postpro/cpw_eigenmode"
      },
      "Model": {
        "Mesh": "cpw_eigenmode.msh",
        "L0": 1e-06
      },
      "Domains": {
        "Materials": [
          {
            "Attributes": [
              2
            ],
            "Permeability": 1.0,
            "Permittivity": 1.0,
            "LossTan": 0.0
          },
          {
            "Attributes": [
              1
            ],
            "Permeability": 1.0,
            "Permittivity": 3.48,
            "LossTan": 0.0
          }
        ]
      },
      "Boundaries": {
        "PEC": {
          "Attributes": [
            3,
            4,
            5
          ]
        },
        "Absorbing": {
          "Attributes": [
            9,
            10
          ],
          "Order": 1
        },
        "Periodic": {
          "FloquetWaveVector": [
            0.00015093651645958455,
            0.0,
            0.0
          ],
          "BoundaryPairs": [
            {
              "DonorAttributes": [
                6
              ],
              "ReceiverAttributes": [
                7
              ]
            }
          ]
        }
      },
      "Solver": {
        "Order": 1,
        "Device": "CPU",
        "Eigenmode": {
          "Target": 5.0,
          "N": 1,
          "Tol": 1e-06,
          "MaxIts": 100,
          "Save": 1
        },
        "Linear": {
          "Type": "STRUMPACK",
          "MGMaxLevels": 1,
          "KSPType": "GMRES",
          "Tol": 1e-08,
          "MaxIts": 2000
        }
      }
    }


## Post-Processing Eigenmode Results

After running Palace, the eigenfrequency and domain energies are written
to `eig.csv` and `domain-E.csv`. The propagation constant is extracted
from the Bloch phase:

$$
\beta = \frac{\varphi}{d \cdot L_0}
\qquad
n_{\text{eff}} = \frac{c_0 \, \beta}{\omega}
= \frac{c_0 \, \varphi}{\omega \, d \, L_0}
$$

The energy ratio $W_H / W_E \approx 1$ confirms a TEM-like mode.


```python
def postprocess_eigenmode(postpro_dir, phi, d_mesh_um, L0_val, c0_val):
    """Extract effective index from Palace eigenmode output."""
    postpro = Path(postpro_dir)

    eig = np.loadtxt(postpro / "eig.csv", delimiter=",", skiprows=1, ndmin=2)
    dom = np.loadtxt(postpro / "domain-E.csv", delimiter=",", skiprows=1, ndmin=2)

    f_ghz = eig[0, 1]
    f_im  = eig[0, 2]
    Q     = eig[0, 3]
    E_elec = dom[0, 1]
    E_mag  = dom[0, 2]

    omega = 2 * np.pi * f_ghz * 1e9
    d_SI = d_mesh_um * L0_val
    beta = phi / d_SI
    n_eff = c0_val * beta / omega
    vp = omega / beta

    print(f"Eigenfrequency:  {f_ghz:.4f} + j{f_im:.4f} GHz  (Q = {Q:.1f})")
    print(f"Bloch phase:     φ = {phi:.4f} rad")
    print(f"β = {beta:.2f} rad/m")
    print(f"n_eff = {n_eff:.4f}")
    print(f"v_p = {vp:.4e} m/s  ({vp/c0_val:.4f} c)")
    print(f"Energy ratio:    W_H/W_E = {E_mag/E_elec:.4f}")

    return dict(f_ghz=f_ghz, n_eff=n_eff, beta=beta, vp=vp,
                E_elec=E_elec, E_mag=E_mag)


# Example usage (uncomment after running Palace):
# results = postprocess_eigenmode("postpro/cpw_eigenmode", phi_exact, d_mesh, L0, c0)
# print(f"\nComparison: FEM n_eff = {results['n_eff']:.4f} vs "
#       f"Analytical = {n_eff_analytic:.4f} "
#       f"(Δ = {abs(results['n_eff'] - n_eff_analytic)/n_eff_analytic*100:.2f}%)")
print("Post-processing function defined. Run Palace, then call postprocess_eigenmode().")
```

    Post-processing function defined. Run Palace, then call postprocess_eigenmode().


## Key Concepts

| Concept | Description |
| --- | --- |
| **Entity pipeline** | Declarative geometry → automatic boolean → physical groups |
| **Periodic BC** | Bloch phase $\varphi = k_x d$ couples donor/receiver faces |
| **Floquet wave-vector** | `[kx, 0, 0]` prescribed in Palace config (rad/mesh-unit) |
| **Eigenmode extraction** | $n_{\text{eff}} = c_0 \beta / \omega$ from single-mode solve |
| **Energy ratio** | $W_H / W_E \approx 1$ confirms TEM-like propagation |
| **Impedance caveat** | Cannot extract $Z_0$ from eigenmode — needs V/I integrals |

---

**Previous:** [← Dipole Antenna](dipole-antenna.md)
