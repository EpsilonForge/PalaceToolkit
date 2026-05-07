"""Analytic closed-form expressions for transmission line parameters."""

import numpy as np

def _K_over_Kp(k: float, kp: float) -> float:
    """Approximate ratio K(k)/K(k') using the Hilberg formula."""
    def _s(x: float) -> float:
        return np.log(
            2 * (np.sqrt(1 + x) + (4 * x) ** 0.25)
            / (np.sqrt(1 + x) - (4 * x) ** 0.25)
        )

    if k >= 1.0 / np.sqrt(2):
        return _s(k) / (2 * np.pi)
    else:
        return 2 * np.pi / _s(kp)

def cpw_impedance(w: float, s: float, h: float, eps_r: float) -> float:
    """Compute the characteristic impedance of a CPW line.

    Uses the conformal mapping approach with elliptic integral ratios K(k)/K(k').

    Args:
        w:     Centre conductor width.
        s:     Gap between centre conductor and ground.
        h:     Substrate thickness.
        eps_r: Relative permittivity of the substrate.

    Returns:
        Z0: Characteristic impedance in Ohms.
    """
    k  = w / (w + 2 * s)
    k1 = np.sinh(np.pi * w / (4 * h)) / np.sinh(np.pi * (w + 2 * s) / (4 * h))

    kp  = np.sqrt(1 - k ** 2)
    k1p = np.sqrt(1 - k1 ** 2)

    kok  = _K_over_Kp(k,  kp)
    k1ok = _K_over_Kp(k1, k1p)

    eps_eff = 1 + ((eps_r - 1) / 2) * k1ok / kok
    Z0 = 30 * np.pi / (kok * np.sqrt(eps_eff))
    return Z0


def cpw_effective_index(w: float, s: float, h: float, eps_r: float) -> float:
    """Return the effective refractive index of a CPW line.

    Uses the same conformal-mapping model as :func:`cpw_impedance`.
    """
    k  = w / (w + 2 * s)
    k1 = np.sinh(np.pi * w / (4 * h)) / np.sinh(np.pi * (w + 2 * s) / (4 * h))

    kp  = np.sqrt(1 - k ** 2)
    k1p = np.sqrt(1 - k1 ** 2)
    kok  = _K_over_Kp(k,  kp)
    k1ok = _K_over_Kp(k1, k1p)

    eps_eff = 1 + ((eps_r - 1) / 2) * k1ok / kok
    return np.sqrt(eps_eff)
