"""modeforge — 2D waveguide mode solver using MFEM.

This package implements the Vardapetyan-Demkowicz eigenvalue formulation
for computing propagation constants and mode fields of waveguides with
arbitrary cross-sections.

Usage::

    from modeforge import WaveguideModeSolver

    solver = WaveguideModeSolver(
        mesh="waveguide.msh",
        order=2,
        pec_bdr=[1, 2],
        materials=[{"attrs": [1], "eps_r": 1.0}],
        omega=2 * np.pi * 10e9,
    )
    k_n = solver.solve(num_modes=3, mode_idx=1)
"""

from modeforge.mode_solver import WaveguideModeSolver

__all__ = ["WaveguideModeSolver"]