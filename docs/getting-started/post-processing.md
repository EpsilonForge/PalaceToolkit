# Post-processing

PalaceToolkit includes modules for extracting and visualising simulation
results.

---

## Impedance extraction

Extract antenna input impedance from Palace port output files:

```python
from palace.simulation import extract_impedance

freq_ghz, z_ant = extract_impedance("postpro/my_antenna")
```

This reads `port-S.csv`, `port-V.csv`, and `port-I.csv`, computes the
reference impedance $Z_0$, and returns the complex antenna impedance:

$$
Z_\text{ant} = Z_0 \frac{1 + S_{11}}{1 - S_{11}}
$$

## S-parameter plots

```python
from palace.s_plot import plot_s_params

plot_s_params("postpro/my_antenna/port-S.csv")
```

Generates magnitude plots of $|S_{11}|$ (and $|S_{21}|$ when available)
versus frequency.

## Analytic reference values

Compare simulation results against closed-form expressions:

```python
from palace.analytic import cpw_impedance, cpw_effective_index

Z0 = cpw_impedance(w=44e-6, s=25e-6, h=500e-6, eps_r=11.7)
n_eff = cpw_effective_index(w=44e-6, s=25e-6, h=500e-6, eps_r=11.7)
```

These use conformal-mapping formulas for coplanar waveguide (CPW) lines.

## 3D mesh visualisation

### Interactive viewer (notebooks)

```python
from palace.view_mesh import view_mesh

view_mesh("model.msh", transparent_groups=["air"])
```

### Static HTML export (docs)

```python
from palace.viz import render_mesh, render_multi_mesh

render_mesh(mesh_path, output_html, title="My Model")
```

The exported `.htm` files are self-contained PyVista viewers that can be
embedded via `<iframe>` in documentation pages.
