# Simulation Setup

Palace simulations are configured through JSON files.  PalaceToolkit
provides helpers to generate these configs and launch Palace from Python.

---

## Running Palace

```python
from palacetoolkit.simulation import run_palace

run_palace("config.json", num_procs=4)
```

This calls Palace via the Apptainer container pointed to by the
`PALACE_SIF` environment variable.

## Generating a config from entities

After meshing with the `Entity` pipeline, you can auto-generate a Palace
JSON config:

```python
from palacetoolkit.simulation import generate_palace_config_from_entities

config = generate_palace_config_from_entities(
    entity_defs=[
        {"name": "conductor",  "boundary_type": "pec"},
        {"name": "dielectric", "boundary_type": "dielectric", "eps_r": 2.1},
        {"name": "port_in",    "boundary_type": "lumped_port", "R": 50, "Direction": "+Z"},
    ],
    pg_map=pg_map,          # dict mapping physical group names → tags
    mesh_file="model.msh",
    output_file="config.json",
    freq_min=1.0,
    freq_max=10.0,
    freq_step=0.5,
)
```

## Boundary types

| Type | Description | Extra keys |
|:-----|:------------|:-----------|
| `"pec"` | Perfect electric conductor surface. | — |
| `"dielectric"` | Volumetric material. | `eps_r`, `mu_r`, `loss_tan` |
| `"lumped_port"` | Lumped port excitation. | `R`, `Direction`, `Excitation` |
| `"waveport"` | Wave port excitation. | `Mode`, `Excitation` |

Surfaces present in the mesh but not listed in `entity_defs` are
automatically treated as **absorbing boundary conditions**.

## Solver types

Palace supports several solver types, selected in the config JSON:

- **Driven** — frequency-domain sweep (S-parameters, impedance).
- **Eigenmode** — resonant frequencies, Q-factors, and field patterns.
- **Transient** — time-domain simulation of pulse propagation.
- **Electrostatic / Magnetostatic** — static field solutions.

## Config structure

A typical Palace JSON config has these top-level keys:

```json
{
  "Problem": { "Type": "Driven" },
  "Model": { "Mesh": "model.msh", "L0": 1e-3 },
  "Domains": { "Materials": [...] },
  "Boundaries": { "PEC": {...}, "LumpedPort": [...], "Absorbing": {...} },
  "Solver": { "Driven": { "MinFreq": 1.0, "MaxFreq": 10.0, "FreqStep": 0.5 } }
}
```

Refer to the [Palace documentation](https://awslabs.github.io/palace/) for
the full specification.
