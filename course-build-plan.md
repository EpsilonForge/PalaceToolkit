# PalaceToolkit Online Course — Build Plan

## Overview

**Course:** "Master Electromagnetic Simulation with Palace — From Zero to Production"
**Delivery:** Hotmart (video course + downloadable materials + 1-on-1 capstone consultation)
**Production:** RISE live coding (Reveal.js slides in Jupyter, recorded via OBS)
**Target:** RF engineers, graduate students, PCB designers, antenna hobbyists
**Prerequisite:** Python, basic EM theory (Maxwell's equations, transmission lines)

---

## 1. Repository Structure (`palace-course`)

```
palace-course/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .github/workflows/
│   └── verify_notebooks.yml       # CI: pip install + papermill all notebooks
│
├── notebooks/
│   ├── 01_classic_gmsh.ipynb
│   ├── 02_entity_pipeline.ipynb
│   ├── 03_deep_mesh_validation.ipynb
│   ├── 04_2d_mode_solver.ipynb
│   ├── 05_waveports.ipynb
│   ├── 06_lumped_ports.ipynb
│   ├── 07_radiation_bcs.ipynb
│   └── 08_postprocessing_and_real_world.ipynb
│
├── exercises/
│   ├── 01_rebuild_raw_gmsh.ipynb
│   ├── 02_build_with_entities.ipynb
│   ├── 03_fix_broken_mesh.ipynb
│   ├── 04_analyze_waveguide_modes.ipynb
│   ├── 05_waveport_design.ipynb
│   ├── 06_lumped_port_sweep.ipynb
│   ├── 07_airbox_convergence.ipynb
│   └── 08_parametric_extraction.ipynb
│
├── solutions/
│   └── (mirrors exercises/, instructor-only, git-crypt or private submodule)
│
├── meshes/
│   ├── broken/
│   │   ├── orphan_faces.msh
│   │   ├── duplicate_bounds.msh
│   │   └── non_manifold.msh
│   └── reference/
│       ├── coax.msh
│       ├── microstrip.msh
│       ├── patch_antenna.msh
│       └── horn_antenna.msh
│
├── capstone/
│   ├── brief.md
│   ├── template.ipynb
│   └── rubric.md
│
└── assets/
    ├── logo.png
    └── diagrams/
        ├── totality_vs_injectivity.png
        ├── boolean_pipeline_flow.png
        ├── airbox_distance_rule.png
        └── mode_solver_workflow.png
```

### `pyproject.toml`

```toml
[project]
name = "palace-course"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "palace-toolkit[plot]>=0.2.0",
    "jupyter",
    "rise",
    "papermill",
    "nb-clean",
    "pyvista",
    "ipywidgets",
]

[tool.papermill]
kernel_name = "palace-course"
```

### `requirements.txt`

```
palace-toolkit[plot]>=0.2.0
jupyter>=1.0
rise>=5.7
papermill>=2.4
nb-clean>=3.0
pyvista>=0.40
ipywidgets>=8.0
```

---

## 2. Each Notebook Template (RISE Slide Metadata)

Every module notebook follows this cell structure:

```
Cell 1:    [slide]     Module title, instructor name, learning objectives
Cell 2:    [slide]     Motivational hook / "why this matters"
Cell 3-N:  [slide]     Concept explanations (text + LaTeX equations)
Cell N+1:  [subslide]  Code demo (live execution)
Cell N+2:  [fragment]  Incremental reveal of results
Cell N+3:  [notes]     Speaker notes (what to say, where to pause)
...
Cell M-2:  [slide]     "Key Takeaways" summary box
Cell M-1:  [slide]     "Exercise" link to exercises/ folder
Cell M:    [notes]     Recording notes (post-processing, transitions)
```

**RISE configuration** (add to first code cell in each notebook):

```python
# RISE slide config
from IPython.display import display, HTML
display(HTML("""
<style>
.reveal h1 { font-size: 2.5em; color: #1a73e8; }
.reveal h2 { font-size: 1.8em; color: #333; }
.reveal code { font-size: 0.85em; }
.reveal .slide-background { background: #fafafa; }
</style>
"""))
```

---

## 3. Module-by-Module Detailed Specification

### Module 1: Classic Gmsh Meshing (The "Before" Picture)

**Duration:** ~1.5 hours video
**Hook:** "This is the way everyone starts — and where everyone gets stuck."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "Classic Gmsh Meshing — The Pain Points" |
| 2 | slide | Why raw Gmsh? The open-source mesh standard |
| 3 | subslide | Gmsh Python API intro: `gmsh.initialize()`, `gmsh.model.occ.addBox()`, etc. |
| 4 | slide | Building a coax geometry raw: cylinders, rectangles, booleans |
| 5 | code | Live: raw Gmsh coax script, step-by-step |
| 6 | fragment | Show the resulting mesh in `view_mesh()` |
| 7 | slide | **Problem 1: Physical group management** |
| 8 | subslide | Manual `gmsh.model.addPhysicalGroup()` calls — fragile, easy to mis-match |
| 9 | fragment | Demo: mis-matched physical group → Palace silently ignores a boundary |
| 10 | slide | **Problem 2: Boolean operation chaos** |
| 11 | subslide | `gmsh.model.occ.cut()` / `gmsh.model.occ.fragment()` — entity tags change, retagging needed |
| 12 | fragment | Demo: cut a conductor from a dielectric, then re-assign tags — error-prone |
| 13 | slide | **Problem 3: No validation** |
| 14 | subslide | You run Palace → it crashes → you have no idea why |
| 15 | fragment | The two MFEM abort messages (introduce them, don't solve yet) |
| 16 | slide | **Problem 4: Material metadata is scattered** |
| 17 | subslide | `eps_r`, `mu_r`, `loss_tan` in comments, not in code — no single source of truth |
| 18 | slide | **Key Takeaways** |
| 19 | slide | **Exercise:** `exercises/01_rebuild_raw_gmsh.ipynb` — build a microstrip step-in-width the raw way |

**Speaker notes key points:**
- "I built my first 10 meshes this way. Every single one had at least one of these problems."
- "The coax example seems simple. But when you scale to 5 materials and 3 ports, this approach breaks."
- "This is the motivation for everything that follows."

**Code references:**
- `gmsh.model.occ.addCylinder()`, `gmsh.model.occ.addBox()`, `gmsh.model.occ.cut()`, `gmsh.model.occ.fragment()`
- `gmsh.model.addPhysicalGroup()`, `gmsh.model.mesh.generate()`, `gmsh.write()`
- `palacetoolkit.viz.view_mesh()` for visualization

---

### Module 2: The Declarative Entity Pipeline

**Duration:** ~1.5 hours video
**Hook:** "What if you could describe your geometry and let the computer figure out the booleans?"

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "The Entity Pipeline — Declarative Geometry" |
| 2 | slide | The core idea: `Entity(name, dim, btype, mesh_order, tags)` |
| 3 | subslide | `mesh_order` = z-index for materials (lower = higher priority) |
| 4 | code | Live: define a coax with 3 entities (conductor, dielectric, air) |
| 5 | fragment | Call `run_entity_pipeline()` — show the auto-assigned physical groups |
| 6 | slide | **How the pipeline works internally** |
| 7 | subslide | Step 1: Group by dimension (3D → 2D → 1D → 0D) |
| 8 | fragment | Step 2: Sort by `mesh_order` ascending |
| 9 | fragment | Step 3: Priority cuts — higher priority cuts lower |
| 10 | fragment | Step 4: Fragment against higher dimensions |
| 11 | fragment | Step 5: Auto-assign physical groups (volumes by name, interfaces as `A__B`) |
| 12 | slide | **The interface naming convention**: `conductor__dielectric` |
| 13 | subslide | PalaceToolkit generates these automatically — no manual retagging |
| 14 | code | Live: rebuild the coax from Module 1 using entities |
| 15 | fragment | Compare: 20 lines of raw Gmsh vs 8 lines of entities |
| 16 | slide | **Adding material properties** |
| 17 | subslide | `Entity("substrate", dim=3, btype="dielectric", eps_r=2.2, loss_tan=0.001, ...)` |
| 18 | code | Live: rebuild the microstrip step-in-width with entities |
| 19 | slide | **Generating the Palace config from entities** |
| 20 | subslide | `generate_palace_config_from_entities(entity_defs, pg_map, mesh_file, ...)` |
| 21 | fragment | Auto-classifies: PEC, dielectric, lumped port, waveport, absorbing |
| 22 | code | Live: generate config, inspect the JSON output |
| 23 | slide | **Key Takeaways** |
| 24 | slide | **Exercise:** `exercises/02_build_with_entities.ipynb` — rebuild the patch antenna from entities |

**Code references:**
- `palacetoolkit.mesh.Entity`, `palacetoolkit.mesh.run_entity_pipeline()`
- `palacetoolkit.mesh.generate_3d_mesh()`
- `palacetoolkit.simulation.generate_palace_config_from_entities()`
- `palacetoolkit.viz.view_mesh()`

**Example notebook to adapt:** `docs/examples/coax.ipynb`, `docs/examples/step_in_width.ipynb`

---

### Module 3: Deep Mesh Validation

**Duration:** ~2 hours video
**Hook:** "95% of Palace crashes are caused by 3 mesh topology bugs. Here's how to catch them before they waste your time."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "Deep Mesh Validation — Why Palace Crashes" |
| 2 | slide | The two MFEM abort messages again (now we solve them) |
| 3 | subslide | Abort 1: `(r,c,f) = (A, B, C)` — totality violation |
| 4 | subslide | Abort 2: "A non-periodic face cannot have multiple boundary elements!" — injectivity violation |
| 5 | subslide | Abort 3: "Interior triangular face found connecting elements A, B, C" — non-manifold |
| 6 | slide | **Mathematical model: the face map** |
| 7 | subslide | `b: B → F` — boundary elements to volume faces |
| 8 | fragment | Total: every `b ∈ B` maps to some `f ∈ F` |
| 9 | fragment | Injective: no two `b₁, b₂` map to the same `f` |
| 10 | slide | **Totality violation — orphan boundary elements** |
| 11 | subslide | Cause: boundary triangle whose vertices don't match any tet face |
| 12 | fragment | Root cause: boolean operations that leave surface fragments behind |
| 13 | code | Live: load `meshes/broken/orphan_faces.msh`, run `verify()` |
| 14 | fragment | Show the red report — "Found 12 orphan boundary elements" |
| 15 | fragment | Use `visualise_problems()` — red faces on the mesh |
| 16 | slide | **Injectivity violation — duplicate boundary elements** |
| 17 | subslide | Cause: two boundary triangles map to the same tet face |
| 18 | fragment | Root cause: overlapping surface tags (e.g., two PEC surfaces on same face) |
| 19 | code | Live: load `meshes/broken/duplicate_bounds.msh`, run `verify()` |
| 20 | slide | **Non-manifold faces — 3+ tets sharing a face** |
| 21 | subslide | Cause: non-manifold geometry (T-junctions, pinch points) |
| 22 | code | Live: load `meshes/broken/non_manifold.msh`, run `verify()` |
| 23 | slide | **The `verify_topology.py` tool** |
| 24 | subslide | `build_face_boundary_map()` — single-pass algorithm |
| 25 | fragment | `print_report()` — green/red verdicts, count summaries |
| 26 | fragment | `visualise_problems()` — PyVista red highlighting |
| 27 | slide | **Using validation with the entity pipeline** |
| 28 | subslide | Run `verify()` after every `run_entity_pipeline()` + `generate_3d_mesh()` |
| 29 | code | Live: build a mesh with entities, verify, run Palace — success |
| 30 | slide | **Validation as a CI step** |
| 31 | subslide | Add `verify(mesh_path, config_path)` to your pre-Palace script |
| 32 | slide | **Key Takeaways** |
| 33 | slide | **Exercise:** `exercises/03_fix_broken_mesh.ipynb` — given 3 broken meshes, identify and fix each topology violation |

**Code references:**
- `palacetoolkit.verify_topology.verify()`
- `palacetoolkit.verify_topology.build_face_boundary_map()`
- `palacetoolkit.verify_topology.print_report()`
- `palacetoolkit.verify_topology.visualise_problems()`
- `palacetoolkit.verify_topology.load_config_bc_attrs()` (for periodic BCs)

**Source file:** `src/palacetoolkit/verify_topology.py` (793 lines)

**Broken mesh generation** (for the `meshes/broken/` directory):

Create each broken mesh programmatically using Gmsh:

```python
# orphan_faces.msh — generate a mesh, then manually add a stray triangle
import gmsh, meshio
gmsh.initialize()
# ... build a valid mesh ...
gmsh.model.mesh.generate(3)
gmsh.write("valid.msh")
# Load, add an extra boundary triangle, save
m = meshio.read("valid.msh")
# ... inject a stray triangle with vertices not in any tet ...
meshio.write("orphan_faces.msh", m)
```

```python
# duplicate_bounds.msh — assign two physical groups to the same face
gmsh.model.addPhysicalGroup(2, [face_tag], tag=10)
gmsh.model.addPhysicalGroup(2, [face_tag], tag=11)  # same face, two groups
```

```python
# non_manifold.msh — create two tets sharing an edge, creating a non-manifold face
# Use gmsh.model.occ.addBox() + gmsh.model.occ.addBox() intersecting at a face
```

---

### Module 4: 2D Mode Solver — Understanding Transmission Lines & Waveguides

**Duration:** ~2.5 hours video
**Hook:** "Before you can excite a wave, you need to understand what modes it supports."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "2D Mode Analysis — The Foundation of Waveguide Design" |
| 2 | slide | Why 2D? A cross-section tells you everything about propagation |
| 3 | subslide | Palace `Problem.Type: "BoundaryMode"` — native 2D eigensolver in Palace v0.17+ |
| 4 | slide | **TE, TM, TEM, and hybrid modes** |
| 5 | subslide | TE: no E_z component (cutoff, propagation constant) |
| 6 | fragment | TM: no H_z component |
| 7 | fragment | TEM: both E_z and H_z zero (coax, microstrip at low freq) |
| 8 | fragment | Hybrid: all 6 field components nonzero |
| 9 | slide | **The `WaveguideModeSolver` class** |
| 10 | subslide | `WaveguideModeSolver(mesh_file, order, pec_bdr, materials, omega)` |
| 11 | fragment | `.solve(num_modes, target, save)` → `{mode_idx: ModeMetrics}` |
| 12 | fragment | `ModeMetrics`: `k_n` (propagation constant), `n_eff` (effective index), `eta_eff` (impedance) |
| 13 | code | Live: solve a hollow rectangular waveguide, print modes |
| 14 | slide | **Hollow rectangular waveguide** |
| 15 | subslide | Analytic TE_10 cutoff: `f_c = c / (2a)` |
| 16 | code | Live: compare Palace results to analytic TE/TM cutoff formulas |
| 17 | fragment | Plot: dispersion diagram (beta vs frequency) |
| 18 | slide | **Microstrip — quasi-TEM mode** |
| 19 | subslide | Cross-section: PEC strip on dielectric, ground plane, absorbing sides |
| 20 | code | Live: solve microstrip modes, extract effective dielectric constant |
| 21 | fragment | Compare to analytic approximation: `eps_eff approx (eps_r + 1)/2 + (eps_r - 1)/2 * 1/sqrt(1 + 12h/w)` |
| 22 | slide | **Slotline — odd/even modes** |
| 23 | subslide | Two conductors, open boundaries — hybrid mode, non-TEM |
| 24 | code | Live: solve slotline, show mode fields, discuss utility |
| 25 | slide | **Dielectric waveguide — guided modes** |
| 26 | subslide | Rectangular dielectric core in cladding |
| 27 | code | Live: solve, classify modes (E^x_{pq}, E^y_{pq}), compare to Marcatili |
| 28 | slide | **Differential microstrip — coupled modes** |
| 29 | subslide | Two coupled strips: even mode and odd mode |
| 30 | fragment | Even mode: both strips same polarity |
| 31 | fragment | Odd mode: opposite polarity |
| 32 | code | Live: solve, extract even/odd effective indices, compute coupling length |
| 33 | slide | **Mode field visualization** |
| 34 | subslide | Use `view_fields_2d()` from `utils.py` |
| 35 | code | Live: plot E_z, H_z, and vector E-field for each mode |
| 36 | slide | **Key Takeaways** |
| 37 | slide | **Exercise:** `exercises/04_analyze_waveguide_modes.ipynb` — choose a waveguide cross-section, compute its modes, plot dispersion, compare to theory |

**Code references:**
- `palacetoolkit.mode_solver.WaveguideModeSolver` (271 lines)
- `palacetoolkit.mode_solver.ModeMetrics`
- `palacetoolkit.utils.view_fields_2d()`
- `palacetoolkit.utils.view_fe_mesh_2d()`

**Example notebooks to adapt:**
- `docs/examples/hollow_waveguide_modes.ipynb`
- `docs/examples/microstrip_modes.ipynb`
- `docs/examples/slotline_modes.ipynb`
- `docs/examples/dielectric_waveguide_modes.ipynb`
- `docs/examples/differential_microstrip_modes.ipynb`

**Palace config for 2D mode solver (generated by `WaveguideModeSolver._build_config()`):**

```json
{
  "Problem": { "Type": "BoundaryMode", "Output": "postpro" },
  "Model": { "Mesh": "cross_section.msh", "L0": 1.0 },
  "Domains": {
    "Materials": [
      { "Attributes": [1], "Permittivity": 2.2, "LossTan": 0.001 }
    ]
  },
  "Boundaries": {
    "PEC": { "Attributes": [2, 3] }
  },
  "Solver": {
    "Order": 2,
    "BoundaryMode": {
      "Freq": 10.0, "N": 5, "Target": 0.0, "Tol": 1e-8, "Type": "Default"
    }
  }
}
```

---

### Module 5: Waveport Boundary Conditions

**Duration:** ~2 hours video
**Hook:** "Now you understand modes — let's excite them at the boundary."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "Waveport Boundary Conditions — Exciting Waveguide Modes" |
| 2 | slide | What is a waveport? A boundary where a specific waveguide mode is injected |
| 3 | subslide | Palace solves the 2D eigenproblem on the port face to determine the mode |
| 4 | slide | **Waveport vs Lumped Port — when to use each** |
| 5 | subslide | Waveport: waveguide feeds, coax, microstrip, any well-defined transmission line |
| 6 | fragment | Lumped port: simple feeds, antennas, non-TLM structures |
| 7 | slide | **Waveport parameters in Palace** |
| 8 | subslide | `Mode`: which mode to excite (1 = fundamental) |
| 9 | fragment | `Offset`: distance from port to de-embed reference plane |
| 10 | fragment | `Excitation`: which ports are excited (vs. terminated) |
| 11 | slide | **Coax waveport — TEM mode** |
| 12 | subslide | Coax cross-section: center conductor + outer shield |
| 13 | code | Live: coax with waveport, run driven simulation, plot S11 |
| 14 | fragment | Expected: S11 near 0 (matched), Z0 = 50Ω |
| 15 | slide | **Horn antenna — waveguide-to-free-space transition** |
| 16 | subslide | WR-90 waveguide + flare + waveport at the waveguide end |
| 17 | code | Live: horn antenna with waveport, run, plot S11 |
| 18 | fragment | Expected: S11 dip at design frequency, matching the flare |
| 19 | slide | **Coax-to-waveguide transition** |
| 20 | subslide | Coax feed launches into rectangular waveguide — mode conversion |
| 21 | code | Live: coax-to-waveguide, two waveports, S11 and S21 |
| 22 | fragment | Discuss: mode mismatch at the transition |
| 23 | slide | **Multi-mode waveports** |
| 24 | subslide | When higher-order modes matter (near discontinuities, mm-wave) |
| 25 | code | Live: request `Mode: 3`, observe higher-order mode effects on S-params |
| 26 | slide | **De-embedding with Offset** |
| 27 | subslide | Shift the reference plane to remove port discontinuity |
| 28 | code | Live: compare S11 with and without Offset |
| 29 | slide | **Key Takeaways** |
| 30 | slide | **Exercise:** `exercises/05_waveport_design.ipynb` — design a microstrip-to-waveguide transition, analyze mode matching |

**Code references:**
- `palacetoolkit.simulation.generate_palace_config_from_entities()` with `boundary_type: "waveport"`
- `palacetoolkit.simulation.run_palace()`
- `palacetoolkit.postpro.s_params()`

**Example notebooks to adapt:**
- `docs/examples/coax.ipynb`
- `docs/examples/horn_antenna.ipynb`
- `docs/examples/coax_to_waveguide.ipynb`

---

### Module 6: Lumped Port Boundary Conditions

**Duration:** ~1.5 hours video
**Hook:** "Simple, fast, and works for most antenna feeds."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "Lumped Port Boundary Conditions — Simple Antenna Feeds" |
| 2 | slide | What is a lumped port? A voltage-gap source with a specified impedance |
| 3 | subslide | Palace creates a small gap in the PEC, applies a voltage across it |
| 4 | slide | **Lumped port parameters** |
| 5 | subslide | `R`: reference impedance (Ω) — typically 50Ω |
| 6 | fragment | `Direction`: orientation of the E-field (e.g., "+Z", "+X") |
| 7 | fragment | `Excitation`: true = driven, false = passive termination |
| 8 | slide | **Dipole antenna — classic lumped port** |
| 9 | subslide | Two arms, small gap at the center, lumped port across the gap |
| 10 | code | Live: build dipole from entities, lumped port at center, run |
| 11 | fragment | Plot S11, extract impedance — find the resonant frequency |
| 12 | fragment | Compare to theory: λ/2 dipole, Z_ant ≈ 73Ω at resonance |
| 13 | slide | **Patch antenna — inset-fed** |
| 14 | subslide | Rectangular patch, substrate, ground plane, feed line |
| 15 | code | Live: patch antenna with lumped port at feed edge |
| 16 | fragment | S11 plot — observe the resonant dip |
| 17 | slide | **L-shaped antenna — bent wire** |
| 18 | subslide | Monopole with a bent top — compact, wideband |
| 19 | code | Live: L-antenna with lumped port, run, extract impedance |
| 20 | slide | **Open-ended microstrip stub** |
| 21 | subslide | Lumped port at the input, observe the stub resonance |
| 22 | code | Live: stub S11, extract the resonant frequency |
| 23 | slide | **Lumped port limitations** |
| 24 | subslide | Only works for TEM-like fields at the port |
| 25 | fragment | Not suitable for waveguide modes (use waveport) |
| 26 | fragment | The port gap must be small relative to wavelength |
| 27 | slide | **Key Takeaways** |
| 28 | slide | **Exercise:** `exercises/06_lumped_port_sweep.ipynb` — parameterize the patch antenna feed position, find the optimal inset depth for 50Ω match |

**Code references:**
- `palacetoolkit.simulation.generate_palace_config_from_entities()` with `boundary_type: "lumped_port"`
- `palacetoolkit.simulation.extract_impedance()`
- `palacetoolkit.postpro.s_params()`

**Example notebooks to adapt:**
- `docs/examples/dipole_antenna.ipynb`
- `docs/examples/patch_antenna.ipynb`
- `docs/examples/l_antenna.ipynb`
- `docs/examples/open_ended_stub.ipynb`

---

### Module 7: Radiation Boundary Conditions & Far-Field

**Duration:** ~2 hours video
**Hook:** "How far is far enough? The answer affects accuracy, simulation time, and your sanity."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "Radiation Boundary Conditions — Simulating Open Space" |
| 2 | slide | The problem: computers can't model infinite space |
| 3 | subslide | Absorbing BCs (ABC): truncate the domain, absorb outgoing waves |
| 4 | slide | **Palace absorbing BCs** |
| 5 | subslide | First-order ABC: absorbs normally-incident waves |
| 6 | fragment | Second-order ABC: better absorption at oblique angles |
| 7 | fragment | Configured via `Boundaries.Absorbing.Order` |
| 8 | slide | **The critical question: how big should the airbox be?** |
| 9 | subslide | Rule of thumb: λ/4 minimum from the radiator to the ABC |
| 10 | fragment | Safe: λ/2 — good for most antennas |
| 11 | fragment | Conservative: λ — when you need accurate far-field patterns |
| 12 | fragment | Frequency-dependent: λ = c/f, so the box grows at lower frequencies |
| 13 | slide | **Airbox convergence study** |
| 14 | subslide | Vary airbox size: λ/8, λ/4, λ/2, λ, 2λ |
| 15 | code | Live: dipole antenna with 5 different airbox sizes |
| 16 | fragment | Plot S11 convergence — λ/4 is good, λ/2 is safe |
| 17 | fragment | Plot far-field pattern convergence — λ is better for pattern accuracy |
| 18 | slide | **Far-field setup in Palace** |
| 19 | subslide | `Boundaries.Postprocessing.FarField` — references the absorbing surfaces |
| 20 | fragment | `NSample`: number of far-field sampling points (default 16000) |
| 21 | fragment | Palace computes the far-field via the Stratton-Chu formula |
| 22 | slide | **Far-field post-processing** |
| 23 | subslide | `palacetoolkit.plot_farfield.polar_plots()` — E-plane and H-plane cuts |
| 24 | fragment | `palacetoolkit.plot_farfield.three_d_plot()` — 3D radiation pattern |
| 25 | code | Live: horn antenna far-field, polar plot, 3D plot |
| 26 | slide | **Dipole far-field pattern** |
| 27 | subslide | Classic doughnut pattern — verify against theory |
| 28 | code | Live: dipole far-field, compare to analytic dipole pattern |
| 29 | slide | **Patch antenna radiation** |
| 30 | subslide | Broadside radiation, front-to-back ratio |
| 31 | code | Live: patch far-field, E-plane and H-plane |
| 32 | slide | **Vivaldi antenna — end-fire radiation** |
| 33 | subslide | Tapered slot, end-fire pattern, wideband |
| 34 | code | Live: Vivaldi far-field, show gain vs frequency |
| 35 | slide | **Key Takeaways** |
| 36 | slide | **Exercise:** `exercises/07_airbox_convergence.ipynb` — pick an antenna, run airbox convergence, produce a plot of S11 vs airbox size, recommend the minimum box size |

**Code references:**
- `palacetoolkit.simulation.generate_palace_config_from_entities()` with `farfield=True`
- `palacetoolkit.plot_farfield.polar_plots()`
- `palacetoolkit.plot_farfield.three_d_plot()`
- `palacetoolkit.plot_farfield.compute_field_magnitude()`
- `palacetoolkit.plot_farfield.compute_db()`
- `palacetoolkit.plot_farfield.extract_eplane()`
- `palacetoolkit.plot_farfield.extract_hplane()`

**Example notebooks to adapt:**
- `docs/examples/horn_antenna.ipynb`
- `docs/examples/dipole_antenna.ipynb`
- `docs/examples/patch_antenna.ipynb`
- `docs/examples/vivaldi_antenna.ipynb`

---

### Module 8: Post-Processing & Real-World Applications

**Duration:** ~2.5 hours video
**Hook:** "A simulation is only useful if you can extract the right numbers from it."

**Slide flow:**

| Slide | Type | Content |
|-------|------|---------|
| 1 | slide | Title: "Post-Processing & Real-World Applications" |
| 2 | slide | Palace output structure: CSV files, VTU files |
| 3 | subslide | `port-S.csv`: S-parameters (magnitude + phase) |
| 4 | fragment | `port-V.csv`, `port-I.csv`: port voltage and current |
| 5 | fragment | VTU files: field data on the mesh |
| 6 | slide | **S-parameter plots** |
| 7 | subslide | `palacetoolkit.postpro.s_params()` — quick matplotlib plots |
| 8 | code | Live: load S11, S21 from a driven simulation, plot |
| 9 | slide | **Characteristic impedance extraction** |
| 10 | subslide | `extract_impedance()` — reads port CSVs, computes Z_ant |
| 11 | fragment | Formula: `Z_ant = Z0 * (1 + S11) / (1 - S11)` |
| 12 | fragment | `Z0 = V_inc / I_inc` from port-V.csv and port-I.csv |
| 13 | code | Live: extract dipole impedance, plot Z_ant vs frequency |
| 14 | slide | **Analytic reference comparison** |
| 15 | subslide | `palacetoolkit.analytic.cpw_impedance()` — CPW closed-form via conformal mapping |
| 16 | fragment | `palacetoolkit.analytic.cpw_effective_index()` — effective index |
| 17 | code | Live: compare Palace CPW simulation to analytic formula |
| 18 | slide | **VTU field visualization** |
| 19 | subslide | `palacetoolkit.postpro_vtu.discover_paraview_datasets()` |
| 20 | fragment | `load_boundary_field_data()` — fields on surfaces |
| 21 | fragment | `load_volume_field_data()` — fields in volume |
| 22 | fragment | `extract_plane_slice()` — 2D slices through the volume |
| 23 | fragment | `plot_boundary_field()` / `plot_volume_slice()` |
| 24 | code | Live: load E-field on a patch antenna, plot a slice through the substrate |
| 25 | slide | **Parasitic extraction workflow** |
| 26 | subslide | Use impedance extraction to characterize pad parasitics |
| 27 | code | Live: CPW pad → extract capacitance and inductance from Z_ant |
| 28 | slide | **Parametric sweeps** |
| 29 | subslide | Use the `Simulation` class with `set_config_option()` |
| 30 | code | Live: sweep patch antenna feed position, collect S11 at each point |
| 31 | fragment | Plot: S11 vs feed position, find optimal match |
| 32 | slide | **Mesh convergence study** |
| 33 | subslide | Vary `create_graded_mesh()` ppw parameter (points per wavelength) |
| 34 | code | Live: run 5 mesh densities, plot S11 convergence |
| 35 | fragment | Discuss: accuracy vs simulation time trade-off |
| 36 | slide | **Key Takeaways** |
| 37 | slide | **Exercise:** `exercises/08_parametric_extraction.ipynb` — parameterize a geometry, run a sweep, plot the optimal design point |

**Code references:**
- `palacetoolkit.postpro.s_params()`
- `palacetoolkit.simulation.extract_impedance()`
- `palacetoolkit.analytic.cpw_impedance()`, `cpw_effective_index()`
- `palacetoolkit.postpro_vtu.*` (all functions)
- `palacetoolkit.simulation.Simulation` (stateful wrapper)
- `palacetoolkit.mesh.create_graded_mesh()`

**Example notebooks to adapt:**
- All 15 examples, reused for post-processing demos

---

### Capstone: 1-on-1 Project

**Deliverable:** A single notebook demonstrating the complete pipeline.

**Design Brief:**
> *"Design and characterize a 2.45 GHz inset-fed microstrip patch antenna on FR4 (eps_r = 4.4, h = 1.6 mm, loss_tan = 0.02)."*

**Deliverable checklist:**

| # | Requirement | Tests Against |
|---|-------------|---------------|
| 1 | Entity-based geometry (patch, substrate, ground, feed, airbox) | `run_entity_pipeline()` succeeds |
| 2 | Mesh validation passes all 3 checks | `verify()` returns all green |
| 3 | 2D mode analysis of the feed line | Effective dielectric constant within 10% of analytic |
| 4 | Driven simulation with waveport + far-field BCs | Palace runs without error |
| 5 | S11 plot with resonant frequency identified | S11 dip within 5% of 2.45 GHz |
| 6 | Impedance extraction at resonance | Z_ant ≈ 50Ω at resonance |
| 7 | Far-field pattern (E-plane + H-plane) | Max gain direction identified |
| 8 | Parametric sweep of inset depth | Optimal inset depth for 50Ω match |
| 9 | Mesh convergence plot | S11 variation < 1% between finest two meshes |

**1-on-1 consultation structure:**
1. **Kickoff call (30 min):** Clarify the brief, suggest initial approach, answer questions
2. **Review call (30 min):** Walk through the notebook, discuss results, suggest improvements
3. **Follow-up (async):** Written feedback on the final deliverable

**Rubric (`capstone/rubric.md`):**

```markdown
# Capstone Rubric

## Pass (student demonstrates competence)
- [ ] Entity pipeline produces correct geometry
- [ ] Topology verification passes all checks
- [ ] 2D mode solver gives reasonable eps_eff
- [ ] Waveport simulation runs without error
- [ ] S11 dip is identified near 2.45 GHz
- [ ] Far-field pattern is plotted

## Distinction (student demonstrates mastery)
- [ ] Impedance extraction shows Z_ant ≈ 50Ω at resonance
- [ ] Parametric sweep finds optimal inset depth
- [ ] Mesh convergence shows < 1% S11 variation
- [ ] Far-field shows correct broadside pattern

## Excellence (student demonstrates deep understanding)
- [ ] Airbox size is justified (convergence study)
- [ ] Mode analysis is used to inform feed line design
- [ ] Results are compared to analytic reference values
- [ ] Discussion of sources of error and their magnitude
```

---

## 4. Production Checklist

### Pre-Recording Setup

- [ ] Install RISE: `pip install RISE`
- [ ] Register RISE with Jupyter: `jupyter-nbextension install rise --py --sys-prefix`
- [ ] Enable RISE: `jupyter-nbextension enable rise --py --sys-prefix`
- [ ] Install Palace runtime: `python -m palacetoolkit.cli palace_toolkit_install_binary`
- [ ] Verify all notebooks execute: `just nbrun` (from PalaceToolkit repo) or `papermill` each course notebook
- [ ] Set up OBS with:
  - Browser source pointing to `http://localhost:8888/notebooks/...`
  - Microphone input (noise gate, compressor)
  - Screen capture for code typing

### Recording Session Workflow

1. Open the notebook in Jupyter, start RISE (Alt+R)
2. OBS records the RISE browser window
3. Present slides, live-code in the code cells
4. Use `[notes]` cells as teleprompter (visible to you, invisible to students)
5. After recording, stop OBS, move video to `videos/` folder

### Post-Recording

- [ ] Trim video (remove dead air, mistakes)
- [ ] Add intro/outro bumper (consistent branding)
- [ ] Export to MP4 (H.264, 1080p, 30fps)
- [ ] Upload to Hotmart
- [ ] Strip notebook outputs: `nb-clean clean --remove-empty-cells --preserve-cell-metadata tags`

### Hotmart Course Structure

```
Section 1: Foundations (Modules 1-2)
  ├── 01_Classic_Gmsh.mp4
  ├── 02_Entity_Pipeline.mp4
  └── Download: notebooks_01_02.zip

Section 2: Mesh Validation (Module 3)
  ├── 03_Deep_Mesh_Validation.mp4
  └── Download: broken_meshes.zip, notebooks_03.zip

Section 3: Mode Analysis (Module 4)
  ├── 04_2D_Mode_Solver.mp4
  └── Download: notebooks_04.zip

Section 4: Boundary Conditions (Modules 5-7)
  ├── 05_Waveports.mp4
  ├── 06_Lumped_Ports.mp4
  ├── 07_Radiation_BCs.mp4
  └── Download: notebooks_05_06_07.zip

Section 5: Post-Processing (Module 8)
  ├── 08_Postprocessing.mp4
  └── Download: notebooks_08.zip

Section 6: Capstone
  ├── capstone_brief.pdf
  ├── capstone_template.ipynb
  └── Book 1:1 Consultation → [Hotmart scheduling link]
```

---

## 5. Key Code Paths Reference

For the AI agent building each notebook, here are the exact API surfaces to use:

### Module 1 — Raw Gmsh

```python
import gmsh
gmsh.initialize()
# Geometry
cyl = gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, 1, 0.5)
box = gmsh.model.occ.addBox(-1, -1, 0, 2, 2, 1)
gmsh.model.occ.cut([(3, box)], [(3, cyl)], removeObject=True, removeTool=False)
gmsh.model.occ.synchronize()
# Physical groups (manual)
gmsh.model.addPhysicalGroup(3, [1], tag=1, name="air")
gmsh.model.addPhysicalGroup(3, [2], tag=2, name="conductor")
# Mesh
gmsh.model.mesh.generate(3)
gmsh.write("raw_coax.msh")
gmsh.finalize()
```

### Module 2 — Entity Pipeline

```python
from palacetoolkit.mesh import Entity, run_entity_pipeline, generate_3d_mesh

conductor = Entity("conductor", dim=3, btype="pec", mesh_order=0, tags=[1])
dielectric = Entity("dielectric", dim=3, btype="dielectric", mesh_order=1,
                     tags=[2], eps_r=2.2, loss_tan=0.001)
air = Entity("air", dim=3, btype="pec", mesh_order=2, tags=[3])

run_entity_pipeline([conductor, dielectric, air])
pg_map = generate_3d_mesh("coax.msh")
# pg_map returned: {"conductor": 1, "dielectric": 2, "air": 3,
#                    "conductor__dielectric": 4, "dielectric__air": 5, ...}

from palacetoolkit.simulation import generate_palace_config_from_entities
config = generate_palace_config_from_entities(
    entity_defs=[
        {"name": "conductor", "boundary_type": "pec"},
        {"name": "dielectric", "boundary_type": "dielectric", "eps_r": 2.2},
        {"name": "port_in", "boundary_type": "waveport", "Mode": 1},
    ],
    pg_map=pg_map, mesh_file="coax.msh", output_file="config.json",
    freq_min=1.0, freq_max=10.0, freq_step=0.1,
)
```

### Module 3 — Topology Verification

```python
from palacetoolkit.verify_topology import verify

# Returns a dict with: "totality", "injectivity", "manifoldness" verdicts
report = verify("coax.msh", config_path="config.json")
print(report)
# Optional: visualise
from palacetoolkit.verify_topology import visualise_problems
# (called internally when verify() finds problems and --view is on)
```

### Module 4 — 2D Mode Solver

```python
from palacetoolkit.mode_solver import WaveguideModeSolver

solver = WaveguideModeSolver(
    mesh_file="cross_section.msh",
    order=2,
    pec_bdr=[1, 2],           # boundary physical group tags
    materials=[{"attrs": [3], "eps_r": 2.2}],
    omega=2 * np.pi * 10e9,
)
modes = solver.solve(num_modes=5, save=2)
for idx, m in modes.items():
    print(f"Mode {idx}: k_n={m.k_n:.3f}, n_eff={m.n_eff:.3f}, Z={m.eta_eff:.1f}Ω")
```

### Module 5-7 — BCs (common pattern)

```python
# Common simulation pattern
from palacetoolkit.simulation import run_palace, generate_palace_config_from_entities

config = generate_palace_config_from_entities(
    entity_defs=[
        {"name": "conductor", "boundary_type": "pec"},
        {"name": "dielectric", "boundary_type": "dielectric", "eps_r": 4.4},
        {"name": "port", "boundary_type": "waveport", "Mode": 1},
        # or for lumped: {"name": "port", "boundary_type": "lumped_port", "R": 50, "Direction": "+Z"},
    ],
    pg_map=pg_map, mesh_file="model.msh", output_file="config.json",
    freq_min=2.0, freq_max=3.0, freq_step=0.01,
    farfield=True,  # adds FarField postprocessing
)

run_palace("config.json", num_procs=4)
```

### Module 8 — Post-Processing

```python
# S-parameters
from palacetoolkit.postpro import s_params
fig, ax = s_params("postpro/model/port-S.csv")

# Impedance extraction
from palacetoolkit.simulation import extract_impedance
freq_ghz, z_ant = extract_impedance("postpro/model")

# Analytic reference
from palacetoolkit.analytic import cpw_impedance
Z0 = cpw_impedance(w=44e-6, s=25e-6, h=500e-6, eps_r=11.7)

# Far-field plots
from palacetoolkit.plot_farfield import polar_plots, three_d_plot
polar_plots("postpro/model/port-farfield.csv")
three_d_plot("postpro/model/port-farfield.csv")

# VTU field visualization
from palacetoolkit.postpro_vtu import (
    discover_paraview_datasets, load_boundary_field_data,
    extract_plane_slice, plot_boundary_field, plot_volume_slice,
)
datasets = discover_paraview_datasets("postpro/model")
fields = load_boundary_field_data(datasets, entity_name="patch")
```

---

## 6. Exercise Breakdown

### Exercise 1: `01_rebuild_raw_gmsh.ipynb`
- Build a microstrip step-in-width using only raw Gmsh API
- No `Entity` class, no pipeline
- Struggle with physical group assignment
- **Goal:** Experience the pain that the Entity pipeline solves

### Exercise 2: `02_build_with_entities.ipynb`
- Rebuild the same microstrip step using the `Entity` class
- Run `run_entity_pipeline()` and `generate_3d_mesh()`
- Generate Palace config from entities
- **Goal:** Experience the contrast

### Exercise 3: `03_fix_broken_mesh.ipynb`
- Given 3 broken meshes from `meshes/broken/`
- Run `verify()` on each
- Identify the violation type (totality, injectivity, non-manifold)
- Fix each mesh and re-verify
- **Goal:** Master mesh debugging

### Exercise 4: `04_analyze_waveguide_modes.ipynb`
- Choose a waveguide cross-section (rectangular, microstrip, slotline, or dielectric)
- Build the 2D mesh
- Run `WaveguideModeSolver` for 5 modes
- Plot dispersion diagram
- Compare to analytic theory
- **Goal:** Understand mode propagation

### Exercise 5: `05_waveport_design.ipynb`
- Design a microstrip-to-waveguide transition
- Use waveports at both ends
- Run driven simulation
- Analyze S11 and S21, discuss mode matching
- **Goal:** Apply waveport knowledge

### Exercise 6: `06_lumped_port_sweep.ipynb`
- Patch antenna with lumped port
- Parameterize the feed position
- Sweep 5 positions, collect S11
- Find the optimal inset depth for 50Ω match
- **Goal:** Apply lumped port knowledge

### Exercise 7: `07_airbox_convergence.ipynb`
- Choose any antenna
- Run with 5 airbox sizes: λ/8, λ/4, λ/2, λ, 2λ
- Plot S11 and far-field gain vs airbox size
- Recommend minimum box size
- **Goal:** Master radiation BC placement

### Exercise 8: `08_parametric_extraction.ipynb`
- Parameterize a geometry (e.g., stub length, patch width)
- Run a parametric sweep
- Extract impedance/S-parameters at each point
- Plot the optimal design point
- **Goal:** Apply the full pipeline

---

## 7. CI Configuration

```yaml
# .github/workflows/verify_notebooks.yml
name: Verify Course Notebooks
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m palacetoolkit.cli palace_toolkit_install_binary
      - name: Execute all notebooks
        run: |
          find notebooks -name "*.ipynb" -exec papermill {} {} -k python3 \;
      - name: Check for broken meshes
        run: |
          for msh in meshes/broken/*.msh; do
            python -c "from palacetoolkit.verify_topology import verify; v=verify('$msh'); assert not v['totality']['pass'] or not v['injectivity']['pass']"
          done
```

---

## 8. RISE Keyboard Shortcuts Reference

| Key | Action |
|-----|--------|
| Alt+R | Start/exit RISE slideshow |
| Space / → | Next slide |
| Shift+Space / ← | Previous slide |
| Ctrl+Enter | Execute current cell (in slideshow mode) |
| s | Open speaker notes window |
| b | Pause/blank screen |
| o | Toggle overview |
| f | Fullscreen |

---

## 9. Deliberately Broken Mesh Generation Scripts

### `orphan_faces.msh` — Generate a valid mesh, then inject stray triangles

```python
import gmsh, meshio, numpy as np

gmsh.initialize()
# Build a valid mesh (e.g., a single box)
box = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
gmsh.model.occ.synchronize()
gmsh.model.addPhysicalGroup(3, [1], name="volume")
gmsh.model.mesh.generate(3)
gmsh.write("_valid.msh")
gmsh.finalize()

# Read, add orphan boundary triangles
m = meshio.read("_valid.msh")
points = m.points  # (N, 3)
# Add 3 new points far from the mesh
new_pts = np.array([[10, 10, 10], [10.1, 10, 10], [10, 10.1, 10]])
m.points = np.vstack([m.points, new_pts])
# Add a triangle using these new points (orphan — no tet contains these vertices)
new_tri = np.array([[len(points), len(points)+1, len(points)+2]], dtype=int)
# Find the triangle cell block or create one
tri_found = False
for i, cb in enumerate(m.cells):
    if cb.type == "triangle":
        m.cells[i] = meshio.CellBlock("triangle", np.vstack([cb.data, new_tri]))
        m.cell_data["gmsh:physical"][i] = np.append(m.cell_data["gmsh:physical"][i], 99)
        tri_found = True
        break
if not tri_found:
    m.cells.append(meshio.CellBlock("triangle", new_tri))
    m.cell_data["gmsh:physical"] = list(m.cell_data.get("gmsh:physical", []))
    m.cell_data["gmsh:physical"].append(np.array([99]))
m.field_data["orphan_bc"] = np.array([99, 2])
meshio.write("orphan_faces.msh", m)
```

### `duplicate_bounds.msh` — Assign two different physical groups to the same face

```python
import gmsh

gmsh.initialize()
box = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
gmsh.model.occ.synchronize()
# Get face tags
faces = gmsh.model.getBoundary([(3, box)], oriented=False)
face_tag = faces[0][1]  # first face
# Assign TWO physical groups to the same face
gmsh.model.addPhysicalGroup(2, [face_tag], tag=10, name="bc_one")
gmsh.model.addPhysicalGroup(2, [face_tag], tag=11, name="bc_two")
gmsh.model.addPhysicalGroup(3, [box], tag=1, name="volume")
gmsh.model.mesh.generate(3)
gmsh.write("duplicate_bounds.msh")
gmsh.finalize()
```

### `non_manifold.msh` — Two boxes sharing a face (4 tets sharing that face)

```python
import gmsh

gmsh.initialize()
# Two boxes that share a face
box1 = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
box2 = gmsh.model.occ.addBox(1, 0, 0, 1, 1, 1)  # shares x=1 face
gmsh.model.occ.fragment([(3, box1)], [(3, box2)])  # merge them
gmsh.model.occ.synchronize()
gmsh.model.addPhysicalGroup(3, [1, 2], tag=1, name="volume")
gmsh.model.mesh.generate(3)
gmsh.write("non_manifold.msh")
gmsh.finalize()
```

---

## 10. Timeline Estimate

| Task | Estimated Effort |
|------|-----------------|
| Repository setup (pyproject.toml, CI, README) | 1 day |
| Write 8 notebook templates (empty RISE-ready structure) | 2 days |
| Generate 3 broken meshes | 0.5 day |
| Generate reference meshes | 0.5 day |
| Write 8 exercise notebooks (student version) | 2 days |
| Write 8 solution notebooks (instructor version) | 2 days |
| Capstone brief + template + rubric | 1 day |
| Record Module 1 (raw Gmsh) | 1 day (recording + editing) |
| Record Module 2 (Entity pipeline) | 1 day |
| Record Module 3 (mesh validation) | 1.5 days |
| Record Module 4 (2D mode solver) | 2 days |
| Record Module 5 (waveports) | 1.5 days |
| Record Module 6 (lumped ports) | 1 day |
| Record Module 7 (radiation BCs) | 1.5 days |
| Record Module 8 (post-processing) | 2 days |
| Edit + upload all videos to Hotmart | 2 days |
| **Total** | **~22 days** |
