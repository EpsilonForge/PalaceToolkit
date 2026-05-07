"""PalaceToolkit — utilities for Palace electromagnetic simulations.

Import as::

    from palacetoolkit.analytic import cpw_impedance
    from palacetoolkit.mesh import Entity, run_meshing_pipeline
    from palacetoolkit.simulation import run_palace, generate_palace_config
    from palacetoolkit.viz import view_mesh
    from palacetoolkit.verify_topology import analyse_mesh
"""

from palacetoolkit.analytic import *          # noqa: F401,F403
from palacetoolkit.mesh import *              # noqa: F401,F403
from palacetoolkit.simulation import *         # noqa: F401,F403
from palacetoolkit.verify_topology import *   # noqa: F401,F403

# Optional submodules — silently skip when extra deps are missing
try:
    from palacetoolkit.s_plot import *        # noqa: F401,F403
except ImportError:
    pass

try:
    from palacetoolkit.viz import *           # noqa: F401,F403
except ImportError:
    pass
