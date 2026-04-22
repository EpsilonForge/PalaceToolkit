"""PalaceToolkit — utilities for Palace electromagnetic simulations.

Import as::

    from palace.analytic import cpw_impedance
    from palace.mesh import Entity, run_boolean_pipeline
    from palace.simulation import run_palace, generate_palace_config
    from palace.viz import view_mesh
    from palace.verify_topology import analyse_mesh
"""

from palace.analytic import *          # noqa: F401,F403
from palace.mesh import *              # noqa: F401,F403
from palace.simulation import *         # noqa: F401,F403
from palace.verify_topology import *   # noqa: F401,F403

# Optional submodules — silently skip when extra deps are missing
try:
    from palace.s_plot import *        # noqa: F401,F403
except ImportError:
    pass

try:
    from palace.viz import *           # noqa: F401,F403
except ImportError:
    pass
