"""
2D Waveguide Mode Solver using PyMFEM.

Implements the same block eigenvalue formulation as Palace
(palace/models/waveportoperator.cpp) for computing propagation constants
and mode fields of waveguides with arbitrary cross-sections.

The eigenvalue problem is:

    [Att  Atn] [et]         [Btt  0 ] [et]
    [Ant  Ann] [en] = -kn^2 [0    0 ] [en]

where et (Nédélec) and en (H1) are the tangential and normal electric field
components, and kn is the propagation constant.

Solved via shift-and-invert: (A - sigma*B)^{-1} B e = lambda e,
with lambda = 1/(-kn^2 - sigma).

References
----------
- Vardapetyan & Demkowicz, Math. Comput. 72 (2003).
- Halla & Monk, arXiv:2302.11994 (2023).
"""

import os

import numpy as np
from scipy.sparse import bmat, csc_matrix, csr_matrix, eye as speye
from scipy.sparse.linalg import eigs, splu, LinearOperator
import mfem.ser as mfem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mfem_to_scipy(sparse_mat):
    """Convert an mfem.SparseMatrix to a scipy.sparse.csc_matrix."""
    I = np.array(sparse_mat.GetIArray())   # row pointers (CSR)
    J = np.array(sparse_mat.GetJArray())   # column indices
    V = np.array(sparse_mat.GetDataArray())  # values
    m = sparse_mat.Height()
    n = sparse_mat.Width()
    mat = csr_matrix((V, J, I), shape=(m, n)).tocsc()
    return mat


def load_mesh_file(mesh_path: str) -> mfem.Mesh:
    """Load a mesh from a file into an ``mfem.Mesh``.

    Supports any format that MFEM can read, including Gmsh ``.msh`` (v2.2).

    Parameters
    ----------
    mesh_path : str
        Path to the mesh file.

    Returns
    -------
    mesh : mfem.Mesh
    """
    mesh_path = os.path.expanduser(mesh_path)
    if not os.path.isfile(mesh_path):
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")
    mesh = mfem.Mesh(mesh_path, 1, 1, True)
    return mesh


# ---------------------------------------------------------------------------
# Block matrix assembly
# ---------------------------------------------------------------------------

def _assemble_Att(nd_fes, mu_inv, eps, omega):
    """Att = (mu^{-1} curl_t u, curl_t v) - omega^2 (eps u, v).

    In 2D, the ND curl-curl integrator gives the scalar 2D curl.
    We combine curl-curl with a mass term via separate bilinear forms.
    """
    # Curl-curl part: (mu^{-1} curl u, curl v)
    a_cc = mfem.BilinearForm(nd_fes)
    mu_inv_coeff = mfem.ConstantCoefficient(mu_inv)
    a_cc.AddDomainIntegrator(mfem.CurlCurlIntegrator(mu_inv_coeff))
    a_cc.Assemble()
    a_cc.Finalize()
    Acc = _mfem_to_scipy(a_cc.SpMat())

    # Mass part: -omega^2 * eps * (u, v)
    mass_coeff_val = -omega**2 * eps
    a_m = mfem.BilinearForm(nd_fes)
    mass_coeff = mfem.ConstantCoefficient(mass_coeff_val)
    a_m.AddDomainIntegrator(mfem.VectorFEMassIntegrator(mass_coeff))
    a_m.Assemble()
    a_m.Finalize()
    Am = _mfem_to_scipy(a_m.SpMat())

    return Acc + Am


def _assemble_Att_piecewise(nd_fes, mesh, mu_inv_vals, eps_vals, omega):
    """Att with piecewise-constant material properties.

    mu_inv_vals : dict mapping attribute -> 1/mu value
    eps_vals    : dict mapping attribute -> eps value

    Uses PWConstCoefficient for attribute-based assembly.
    """
    nattr = mesh.attributes.Max()

    # Curl-curl: mu_inv per attribute
    cc_vec = mfem.Vector(nattr)
    cc_vec.Assign(0.0)
    for attr, mu_inv in mu_inv_vals.items():
        cc_vec[attr - 1] = mu_inv
    cc_coeff = mfem.PWConstCoefficient(cc_vec)

    a_cc = mfem.BilinearForm(nd_fes)
    a_cc.AddDomainIntegrator(mfem.CurlCurlIntegrator(cc_coeff))
    a_cc.Assemble()
    a_cc.Finalize()

    # Mass: -omega^2*eps per attribute
    m_vec = mfem.Vector(nattr)
    m_vec.Assign(0.0)
    for attr in eps_vals:
        eps = eps_vals[attr]
        m_vec[attr - 1] = -omega**2 * eps
    m_coeff = mfem.PWConstCoefficient(m_vec)

    a_m = mfem.BilinearForm(nd_fes)
    a_m.AddDomainIntegrator(mfem.VectorFEMassIntegrator(m_coeff))
    a_m.Assemble()
    a_m.Finalize()

    return _mfem_to_scipy(a_cc.SpMat()) + _mfem_to_scipy(a_m.SpMat())


def _assemble_Atn(nd_fes, h1_fes, mu_inv):
    """Atn = -(mu^{-1} grad_t u, v) where u in H1, v in ND."""
    c = mfem.MixedBilinearForm(h1_fes, nd_fes)
    coeff = mfem.ConstantCoefficient(-mu_inv)
    c.AddDomainIntegrator(mfem.MixedVectorGradientIntegrator(coeff))
    c.Assemble()
    c.Finalize()
    return _mfem_to_scipy(c.SpMat())


def _assemble_Ant(nd_fes, h1_fes, eps):
    """Ant = -(eps u, grad_t v) where u in ND, v in H1.

    Implemented with MixedVectorWeakDivergenceIntegrator which computes
    +(eps u, grad v), and we take the negative.
    """
    c = mfem.MixedBilinearForm(nd_fes, h1_fes)
    coeff = mfem.ConstantCoefficient(eps)
    c.AddDomainIntegrator(mfem.MixedVectorWeakDivergenceIntegrator(coeff))
    c.Assemble()
    c.Finalize()
    # MixedVectorWeakDivergenceIntegrator gives -(u, grad v),
    # but with coeff=+eps it gives -(eps u, grad v) = Ant.
    # Actually the integrator computes -(c u, grad v), which is Ant already.
    return _mfem_to_scipy(c.SpMat())


def _assemble_Ann(h1_fes, eps):
    """Ann = -(eps u, v) where u, v in H1."""
    a = mfem.BilinearForm(h1_fes)
    coeff = mfem.ConstantCoefficient(-eps)
    a.AddDomainIntegrator(mfem.MassIntegrator(coeff))
    a.Assemble()
    a.Finalize()
    return _mfem_to_scipy(a.SpMat())


def _assemble_Btt(nd_fes, mu_inv):
    """Btt = (mu^{-1} u, v) where u, v in ND."""
    a = mfem.BilinearForm(nd_fes)
    coeff = mfem.ConstantCoefficient(mu_inv)
    a.AddDomainIntegrator(mfem.VectorFEMassIntegrator(coeff))
    a.Assemble()
    a.Finalize()
    return _mfem_to_scipy(a.SpMat())


def _assemble_Atn_piecewise(nd_fes, h1_fes, mesh, mu_inv_vals):
    """Atn with piecewise mu_inv using PWConstCoefficient."""
    nattr = mesh.attributes.Max()
    v = mfem.Vector(nattr)
    v.Assign(0.0)
    for attr, mu_inv in mu_inv_vals.items():
        v[attr - 1] = -mu_inv  # negative sign is part of the operator
    coeff = mfem.PWConstCoefficient(v)

    c = mfem.MixedBilinearForm(h1_fes, nd_fes)
    c.AddDomainIntegrator(mfem.MixedVectorGradientIntegrator(coeff))
    c.Assemble()
    c.Finalize()
    return _mfem_to_scipy(c.SpMat())


def _assemble_Ant_piecewise(nd_fes, h1_fes, mesh, eps_vals):
    """Ant with piecewise eps using PWConstCoefficient."""
    nattr = mesh.attributes.Max()
    v = mfem.Vector(nattr)
    v.Assign(0.0)
    for attr, eps in eps_vals.items():
        v[attr - 1] = eps  # MixedVectorWeakDivergenceIntegrator gives -(c u, grad v)
    coeff = mfem.PWConstCoefficient(v)

    c = mfem.MixedBilinearForm(nd_fes, h1_fes)
    c.AddDomainIntegrator(mfem.MixedVectorWeakDivergenceIntegrator(coeff))
    c.Assemble()
    c.Finalize()
    return _mfem_to_scipy(c.SpMat())


def _assemble_Ann_piecewise(h1_fes, mesh, eps_vals):
    """Ann with piecewise eps using PWConstCoefficient."""
    nattr = mesh.attributes.Max()
    v = mfem.Vector(nattr)
    v.Assign(0.0)
    for attr, eps in eps_vals.items():
        v[attr - 1] = -eps  # Ann = -(eps u, v)
    coeff = mfem.PWConstCoefficient(v)

    a = mfem.BilinearForm(h1_fes)
    a.AddDomainIntegrator(mfem.MassIntegrator(coeff))
    a.Assemble()
    a.Finalize()
    return _mfem_to_scipy(a.SpMat())


def _assemble_Btt_piecewise(nd_fes, mesh, mu_inv_vals):
    """Btt with piecewise mu_inv using PWConstCoefficient."""
    nattr = mesh.attributes.Max()
    v = mfem.Vector(nattr)
    v.Assign(0.0)
    for attr, mu_inv in mu_inv_vals.items():
        v[attr - 1] = mu_inv
    coeff = mfem.PWConstCoefficient(v)

    a = mfem.BilinearForm(nd_fes)
    a.AddDomainIntegrator(mfem.VectorFEMassIntegrator(coeff))
    a.Assemble()
    a.Finalize()
    return _mfem_to_scipy(a.SpMat())


# ---------------------------------------------------------------------------
# Anisotropic (tensor) permittivity support
# ---------------------------------------------------------------------------

def _parse_eps_entry(val):
    """Normalise a single permittivity value to (eps_tt, eps_nn).

    Accepted formats
    ----------------
    * scalar  – isotropic:  eps_tt = s*I(2), eps_nn = s
    * (2,2) array-like – transverse tensor supplied directly;
      eps_nn must be provided separately (defaults to eps_tt mean).
    * (3,3) array-like – full 3D tensor; the [0:2,0:2] sub-block is eps_tt
      and [2,2] is eps_nn.

    Returns
    -------
    eps_tt : ndarray (2,2)
    eps_nn : float
    is_aniso : bool   – True if eps_tt is not proportional to I.
    """
    a = np.asarray(val, dtype=float)
    if a.ndim == 0:                       # scalar
        s = float(a)
        return np.eye(2) * s, s, False
    if a.shape == (3, 3):                 # full 3×3 tensor
        eps_tt = a[:2, :2].copy()
        eps_nn = float(a[2, 2])
    elif a.shape == (2, 2):               # transverse 2×2 only
        eps_tt = a.copy()
        eps_nn = float(0.5 * (a[0, 0] + a[1, 1]))  # default: mean diag
    else:
        raise ValueError(f"eps entry has unsupported shape {a.shape}; "
                         "expected scalar, (2,2), or (3,3).")
    # Anisotropic if eps_tt is not proportional to I *or* eps_nn differs
    # from the transverse diagonal (the normal component matters for Ann).
    tt_iso = np.allclose(eps_tt, eps_tt[0, 0] * np.eye(2))
    nn_matches_tt = np.isclose(eps_nn, eps_tt[0, 0]) if tt_iso else False
    is_aniso = not (tt_iso and nn_matches_tt)
    return eps_tt, eps_nn, is_aniso


def _parse_eps(eps, mesh):
    """Parse the *eps* argument into per-attribute tt / nn data.

    Returns
    -------
    eps_tt : dict  attr -> ndarray (2,2)
    eps_nn : dict  attr -> float
    eps_scalar : dict  attr -> float  (the isotropic-equivalent value, used
                 by legacy code paths when the material is in fact isotropic)
    any_aniso : bool
    """
    attrs = list(range(1, mesh.attributes.Max() + 1))

    if isinstance(eps, (int, float)):     # uniform scalar
        s = float(eps)
        return ({a: np.eye(2) * s for a in attrs},
                {a: s for a in attrs},
                {a: s for a in attrs},
                False)

    if isinstance(eps, dict):
        eps_tt, eps_nn, eps_scalar = {}, {}, {}
        any_aniso = False
        for a in attrs:
            v = eps.get(a, 1.0)
            tt, nn, aniso = _parse_eps_entry(v)
            eps_tt[a] = tt
            eps_nn[a] = nn
            eps_scalar[a] = float(tt[0, 0]) if not aniso else None
            if aniso:
                any_aniso = True
        return eps_tt, eps_nn, eps_scalar, any_aniso

    # Uniform non-scalar (array-like)
    tt, nn, aniso = _parse_eps_entry(eps)
    return ({a: tt for a in attrs},
            {a: nn for a in attrs},
            {a: float(tt[0, 0]) if not aniso else None for a in attrs},
            aniso)


# ---- tensor-aware assembly helpers ----------------------------------------

def _make_eps_tt_coeff(eps_tt_dict, mesh, scale=1.0):
    """Build an MFEM MatrixCoefficient for the 2×2 eps_tt tensor.

    If all attributes have the same tensor, returns a single
    MatrixConstantCoefficient.  Otherwise returns a PWMatrixCoefficient.
    """
    vals = list(eps_tt_dict.values())
    all_same = all(np.allclose(v, vals[0]) for v in vals)

    if all_same:
        M = mfem.DenseMatrix(2, 2)
        M[0, 0] = scale * vals[0][0, 0]
        M[0, 1] = scale * vals[0][0, 1]
        M[1, 0] = scale * vals[0][1, 0]
        M[1, 1] = scale * vals[0][1, 1]
        return mfem.MatrixConstantCoefficient(M)

    pw = mfem.PWMatrixCoefficient(2)  # 2D
    coeffs = []  # prevent GC
    for attr, tt in eps_tt_dict.items():
        M = mfem.DenseMatrix(2, 2)
        M[0, 0] = scale * tt[0, 0]
        M[0, 1] = scale * tt[0, 1]
        M[1, 0] = scale * tt[1, 0]
        M[1, 1] = scale * tt[1, 1]
        mc = mfem.MatrixConstantCoefficient(M)
        coeffs.append(mc)
        pw.UpdateCoefficient(attr, mc)
    pw._keep = coeffs  # prevent GC of children
    return pw


def _make_eps_nn_coeff(eps_nn_dict, mesh, scale=1.0):
    """Build a scalar MFEM Coefficient for eps_nn."""
    vals = list(eps_nn_dict.values())
    all_same = len(set(vals)) == 1
    if all_same:
        return mfem.ConstantCoefficient(scale * vals[0])
    nattr = mesh.attributes.Max()
    v = mfem.Vector(nattr)
    v.Assign(0.0)
    for attr, nn in eps_nn_dict.items():
        v[attr - 1] = scale * nn
    return mfem.PWConstCoefficient(v)


def _assemble_Att_aniso(nd_fes, mesh, mu_inv_vals, eps_tt_dict, omega):
    """Att with tensor eps_tt: curl-curl + tensor mass on ND space."""
    # Curl-curl part (uses scalar mu_inv, unchanged)
    nattr = mesh.attributes.Max()
    cc_vec = mfem.Vector(nattr)
    cc_vec.Assign(0.0)
    for attr, mu_inv in mu_inv_vals.items():
        cc_vec[attr - 1] = mu_inv
    cc_coeff = mfem.PWConstCoefficient(cc_vec)

    a_cc = mfem.BilinearForm(nd_fes)
    a_cc.AddDomainIntegrator(mfem.CurlCurlIntegrator(cc_coeff))
    a_cc.Assemble()
    a_cc.Finalize()

    # Mass part: -omega^2 * eps_tt (2×2 matrix coefficient)
    eps_coeff = _make_eps_tt_coeff(eps_tt_dict, mesh, scale=-omega**2)

    a_m = mfem.BilinearForm(nd_fes)
    a_m.AddDomainIntegrator(mfem.VectorFEMassIntegrator(eps_coeff))
    a_m.Assemble()
    a_m.Finalize()

    return _mfem_to_scipy(a_cc.SpMat()) + _mfem_to_scipy(a_m.SpMat())


def _assemble_Ant_aniso(nd_fes, h1_fes, mesh, eps_tt_dict):
    """Ant = -(eps_tt u, grad v) with tensor eps_tt.

    MixedVectorWeakDivergenceIntegrator(c) computes -(c u, grad v),
    so we pass c = eps_tt directly.
    """
    eps_coeff = _make_eps_tt_coeff(eps_tt_dict, mesh, scale=1.0)
    c = mfem.MixedBilinearForm(nd_fes, h1_fes)
    c.AddDomainIntegrator(
        mfem.MixedVectorWeakDivergenceIntegrator(eps_coeff))
    c.Assemble()
    c.Finalize()
    return _mfem_to_scipy(c.SpMat())


def _assemble_Ann_aniso(h1_fes, mesh, eps_nn_dict):
    """Ann = -(eps_nn u, v) with normal-projected scalar eps_nn."""
    coeff = _make_eps_nn_coeff(eps_nn_dict, mesh, scale=-1.0)
    a = mfem.BilinearForm(h1_fes)
    a.AddDomainIntegrator(mfem.MassIntegrator(coeff))
    a.Assemble()
    a.Finalize()
    return _mfem_to_scipy(a.SpMat())


# ---------------------------------------------------------------------------
# Essential (Dirichlet / PEC) boundary condition elimination
# ---------------------------------------------------------------------------

def _get_essential_dofs(nd_fes, h1_fes, pec_bdr_marker):
    """Get combined essential DOF list for ND+H1 block system.

    Parameters
    ----------
    nd_fes : mfem.FiniteElementSpace (ND)
    h1_fes : mfem.FiniteElementSpace (H1)
    pec_bdr_marker : mfem.intArray
        Marker array of length mesh.bdr_attributes.Max(), with 1 for PEC.

    Returns
    -------
    ess_nd : numpy array of ND essential true DOFs
    ess_h1 : numpy array of H1 essential true DOFs
    ess_block : numpy array of combined essential DOFs (ND offset + H1)
    """
    ess_nd_list = mfem.intArray()
    nd_fes.GetEssentialTrueDofs(pec_bdr_marker, ess_nd_list)
    ess_nd = np.array(ess_nd_list.ToList())

    ess_h1_list = mfem.intArray()
    h1_fes.GetEssentialTrueDofs(pec_bdr_marker, ess_h1_list)
    ess_h1 = np.array(ess_h1_list.ToList())

    nd_size = nd_fes.GetTrueVSize()
    ess_block = np.concatenate([ess_nd, ess_h1 + nd_size])
    return ess_nd, ess_h1, ess_block


def _eliminate_essential_dofs(M, ess_dofs, diag_value=1.0):
    """Zero rows/columns of sparse matrix at essential DOFs, set diagonal.

    Parameters
    ----------
    M : scipy.sparse.csc_matrix
        The matrix to modify (modified in-place via return).
    ess_dofs : array-like
        DOF indices to eliminate.
    diag_value : float
        Value to place on diagonal (1.0 for A, 0.0 for B).

    Returns
    -------
    M : scipy.sparse.csc_matrix
        Modified matrix.
    """
    if len(ess_dofs) == 0:
        return M

    M = M.tolil()
    for d in ess_dofs:
        M[d, :] = 0
        M[:, d] = 0
        M[d, d] = diag_value
    return M.tocsc()


# ---------------------------------------------------------------------------
# Main solver class
# ---------------------------------------------------------------------------

class WaveguideModeSolver:
    """2D cross-section waveguide mode solver.

    Computes propagation constants and mode fields by solving the generalized
    eigenvalue problem from Vardapetyan & Demkowicz (2003), using the same
    formulation as the Palace wave port operator.

    Parameters
    ----------
    mesh : str or mfem.Mesh
        Either a path to a mesh file (e.g. Gmsh ``.msh``) or an already-
        loaded ``mfem.Mesh``.  When a string is provided the mesh is loaded
        via :func:`load_mesh_file`.
    order : int
        Polynomial order for ND and H1 finite element spaces.
    mu_inv : float or dict
        Inverse permeability. If float, uniform. If dict, maps element
        attribute -> 1/mu value.
    eps : float, array-like, or dict
        Permittivity.  Accepts several formats:

        * **scalar** (float) -- uniform isotropic permittivity.
        * **(3, 3) array** -- uniform anisotropic tensor.  The [0:2, 0:2]
          block is the transverse tensor :math:`\\bar{\\bar{\\varepsilon}}_{tt}`
          and [2, 2] is the normal component :math:`\\varepsilon_{nn}`.
        * **(2, 2) array** -- transverse tensor only; :math:`\\varepsilon_{nn}`
          defaults to the mean of the diagonal.
        * **dict** mapping element attribute -> any of the above.  Entries
          may freely mix scalars and arrays (piecewise anisotropic).

        The block-diagonal (transverse vs. normal) decomposition matches what
        Palace implements: :math:`\\bar{\\bar{\\varepsilon}}_{tt}` enters the
        mass part of :math:`A_{tt}` and the coupling :math:`A_{nt}`, while
        :math:`\\varepsilon_{nn}` enters :math:`A_{nn}`.  Off-diagonal
        transverse--normal coupling (:math:`\\varepsilon_{tn}`) is not
        modelled (it would require a quadratic eigenvalue problem).
    pec_bdr : list of int or 'all'
        List of boundary attributes that are PEC. Use 'all' for all boundaries.
    """

    def __init__(self, mesh, order=1, mu_inv=1.0, eps=1.0, pec_bdr='all'):
        # Accept either a file path (str) or an mfem.Mesh object
        if isinstance(mesh, str):
            mesh = load_mesh_file(mesh)
        self.mesh = mesh
        self.order = order
        self.dim = mesh.Dimension()
        if self.dim != 2:
            raise ValueError("Solver requires a 2D mesh")

        # Material properties — mu_inv is always scalar
        if isinstance(mu_inv, (int, float)):
            attrs = list(range(1, mesh.attributes.Max() + 1))
            self.mu_inv_vals = {a: float(mu_inv) for a in attrs}
        else:
            self.mu_inv_vals = {k: float(v) for k, v in mu_inv.items()}

        # Permittivity: scalar, dict-of-scalars, 2×2/3×3 array, or dict of
        # arrays.  _parse_eps normalises everything into per-attribute
        # eps_tt (2×2), eps_nn (scalar), and eps_scalar (scalar or None).
        (self.eps_tt_dict,
         self.eps_nn_dict,
         self.eps_scalar_dict,
         self.is_anisotropic) = _parse_eps(eps, mesh)

        # Legacy eps_vals (scalar per attribute) — used by isotropic paths
        if not self.is_anisotropic:
            self.eps_vals = {a: float(self.eps_tt_dict[a][0, 0])
                            for a in self.eps_tt_dict}
        else:
            # For shift calculation we still need a scalar "max eps"
            self.eps_vals = {a: float(np.max(np.linalg.eigvalsh(tt)))
                            for a, tt in self.eps_tt_dict.items()}

        # FE spaces
        self.nd_fec = mfem.ND_FECollection(order, 2)
        self.h1_fec = mfem.H1_FECollection(order, 2)
        self.nd_fes = mfem.FiniteElementSpace(mesh, self.nd_fec)
        self.h1_fes = mfem.FiniteElementSpace(mesh, self.h1_fec)

        self.nd_size = self.nd_fes.GetTrueVSize()
        self.h1_size = self.h1_fes.GetTrueVSize()
        self.total_size = self.nd_size + self.h1_size

        print(f"  FE spaces: ND dofs = {self.nd_size}, H1 dofs = {self.h1_size}, "
              f"total = {self.total_size}"
              f"{', anisotropic eps' if self.is_anisotropic else ''}")

        # PEC boundary marker
        bdr_attr_max = mesh.bdr_attributes.Max()
        self.pec_marker = mfem.intArray(bdr_attr_max)
        if pec_bdr == 'all':
            self.pec_marker.Assign(1)
        else:
            self.pec_marker.Assign(0)
            for b in pec_bdr:
                if 1 <= b <= bdr_attr_max:
                    self.pec_marker[b - 1] = 1

        # Get essential DOFs
        self.ess_nd, self.ess_h1, self.ess_block = _get_essential_dofs(
            self.nd_fes, self.h1_fes, self.pec_marker
        )
        print(f"  Essential DOFs: ND = {len(self.ess_nd)}, "
              f"H1 = {len(self.ess_h1)}, total = {len(self.ess_block)}")

        # Pre-assemble frequency-independent operators
        self._assemble_static_operators()

    def _is_uniform(self, vals_dict):
        """Check if all values in dict are the same."""
        v = list(vals_dict.values())
        return len(set(v)) == 1

    def _uniform_val(self, vals_dict):
        """Return the single value if uniform."""
        return list(vals_dict.values())[0]

    def _assemble_static_operators(self):
        """Assemble operators that do not depend on frequency."""
        mu_inv_uniform = self._is_uniform(self.mu_inv_vals)

        # Atn and Btt depend only on mu_inv (always scalar)
        if mu_inv_uniform:
            mu_inv = self._uniform_val(self.mu_inv_vals)
            self.Atn = _assemble_Atn(self.nd_fes, self.h1_fes, mu_inv)
            self.Btt = _assemble_Btt(self.nd_fes, mu_inv)
        else:
            self.Atn = _assemble_Atn_piecewise(
                self.nd_fes, self.h1_fes, self.mesh, self.mu_inv_vals)
            self.Btt = _assemble_Btt_piecewise(
                self.nd_fes, self.mesh, self.mu_inv_vals)

        # Ant and Ann depend on eps — use tensor path if anisotropic
        if self.is_anisotropic:
            print("  Using anisotropic (tensor) permittivity assembly")
            self.Ant = _assemble_Ant_aniso(
                self.nd_fes, self.h1_fes, self.mesh, self.eps_tt_dict)
            self.Ann = _assemble_Ann_aniso(
                self.h1_fes, self.mesh, self.eps_nn_dict)
        else:
            eps_uniform = self._is_uniform(self.eps_vals)
            if eps_uniform:
                eps = self._uniform_val(self.eps_vals)
                self.Ant = _assemble_Ant(self.nd_fes, self.h1_fes, eps)
                self.Ann = _assemble_Ann(self.h1_fes, eps)
            else:
                self.Ant = _assemble_Ant_piecewise(
                    self.nd_fes, self.h1_fes, self.mesh, self.eps_vals)
                self.Ann = _assemble_Ann_piecewise(
                    self.h1_fes, self.mesh, self.eps_vals)

    def solve(self, omega, num_modes=5, mode_idx=1):
        """Solve for waveguide modes at angular frequency omega.

        Parameters
        ----------
        omega : float
            Angular frequency (rad/s in natural units, or normalized).
        num_modes : int
            Number of eigenvalues to compute.
        mode_idx : int
            1-based index of the desired mode (ranked by decreasing Re{kn}).

        Returns
        -------
        results : dict with keys:
            'kn'       : array of propagation constants (complex)
            'kn_selected' : the selected mode's kn
            'Et'       : GridFunction (ND) for the selected mode tangential E
            'En'       : GridFunction (H1) for the selected mode normal E
            'eigenvalues' : raw eigenvalues from the shift-and-invert problem
        """
        if mode_idx < 1:
            raise ValueError("mode_idx must be >= 1 (1-based indexing)")
        if num_modes < mode_idx:
            raise ValueError(f"num_modes ({num_modes}) must be >= mode_idx ({mode_idx})")

        # Compute shift: sigma = -omega^2 * max(mu*eps)
        # For anisotropic eps use the max eigenvalue of eps_tt as the
        # scalar "eps" for the shift estimate.
        mu_eps_max = max(
            self.eps_vals[a] / self.mu_inv_vals[a]
            for a in self.eps_vals
        )
        sigma = -omega**2 * mu_eps_max * 1.1  # safety factor

        # Assemble Att (frequency-dependent due to omega)
        if self.is_anisotropic:
            Att = _assemble_Att_aniso(
                self.nd_fes, self.mesh, self.mu_inv_vals,
                self.eps_tt_dict, omega)
        else:
            mu_inv_uniform = self._is_uniform(self.mu_inv_vals)
            eps_uniform = self._is_uniform(self.eps_vals)
            if mu_inv_uniform and eps_uniform:
                mu_inv = self._uniform_val(self.mu_inv_vals)
                eps = self._uniform_val(self.eps_vals)
                Att = _assemble_Att(self.nd_fes, mu_inv, eps, omega)
            else:
                Att = self._assemble_Att_piecewise(omega)

        # Build block system matrices
        # A = [Att  Atn]    B = [Btt  0  ]
        #     [Ant  Ann]        [0    0  ]
        Dnn = csc_matrix((self.h1_size, self.h1_size))  # zero block

        A = bmat([[Att,      self.Atn],
                  [self.Ant, self.Ann]], format='csc')

        B = bmat([[self.Btt, None],
                  [None,     Dnn]], format='csc')

        # Eliminate essential (PEC) DOFs
        A = _eliminate_essential_dofs(A, self.ess_block, diag_value=1.0)
        B = _eliminate_essential_dofs(B, self.ess_block, diag_value=0.0)

        # Solve the generalized eigenvalue problem: A e = mu B e
        # where mu = -kn^2.
        #
        # We use shift-and-invert: (A - sigma*B)^{-1} B e = lambda e
        # where lambda = 1/(mu - sigma), so mu = sigma + 1/lambda.
        #
        # The shift sigma should be near the desired mu = -kn^2.
        # For propagating modes, kn^2 > 0, so mu < 0.
        # We choose sigma = -omega^2 * max(mu*eps) * 1.1
        print(f"  Solving eigenvalue problem (omega = {omega:.6g}, "
              f"sigma = {sigma:.6g}, size = {A.shape[0]})...")

        AminusSigmaB = (A - sigma * B).tocsc()

        # Use sparse LU for the shift-and-invert operator
        # OPinv implements (A - sigma*B)^{-1}
        lu = splu(AminusSigmaB)

        def matvec(x):
            return lu.solve(x)

        n = A.shape[0]
        OPinv = LinearOperator((n, n), matvec=matvec)

        # Request more eigenvalues for reliability
        k = min(max(2 * num_modes + 1, num_modes + 5), n - 2)
        k = max(k, num_modes)

        # scipy.sparse.linalg.eigs(A, M=B, sigma=sigma, OPinv=OPinv)
        # solves A x = lambda B x using shift-and-invert.
        # OPinv should implement (A - sigma*B)^{-1}.
        # The returned eigenvalues are already back-transformed by scipy.
        # With 'which=LM', we find eigenvalues closest to sigma.
        eigenvalues, eigenvectors = eigs(
            A, k=k, M=B, sigma=sigma, OPinv=OPinv,
            which='LM',
            tol=1e-10,
            maxiter=1000
        )

        # eigenvalues are mu = -kn^2 (the eigenvalues of A x = mu B x)
        # scipy already back-transforms from shift-and-invert
        kn_squared = -eigenvalues
        kn_all = np.sqrt(kn_squared.astype(complex))

        # Ensure Re{kn} >= 0 (propagation direction convention)
        for i in range(len(kn_all)):
            if kn_all[i].real < 0:
                kn_all[i] = -kn_all[i]

        # Sort by decreasing Re{kn} (most propagating first)
        sort_idx = np.argsort(-kn_all.real)
        kn_all = kn_all[sort_idx]
        eigenvectors = eigenvectors[:, sort_idx]

        # Filter out spurious modes (very large imaginary part)
        valid = []
        for i in range(len(kn_all)):
            if abs(kn_all[i].imag) < 10 * abs(kn_all[i].real) + 1e-6:
                valid.append(i)
        if len(valid) >= num_modes:
            kn_filtered = kn_all[valid][:num_modes]
            vecs_filtered = eigenvectors[:, valid][:, :num_modes]
        else:
            kn_filtered = kn_all[:num_modes]
            vecs_filtered = eigenvectors[:, :num_modes]

        print(f"  Found {len(kn_filtered)} modes:")
        for i, kn in enumerate(kn_filtered):
            marker = " <-- selected" if i == mode_idx - 1 else ""
            print(f"    Mode {i+1}: kn = {kn.real:+.8e} {kn.imag:+.8e}j{marker}")

        # Extract selected mode
        sel = mode_idx - 1
        kn_sel = kn_filtered[sel]
        e_vec = vecs_filtered[:, sel]

        # Split into et and en, transform: Et = et, En = en / (i*kn)
        et = e_vec[:self.nd_size]
        en = e_vec[self.nd_size:]
        En_phys = en / (1j * kn_sel)

        # Create MFEM grid functions
        Et_gf = mfem.GridFunction(self.nd_fes)
        En_gf = mfem.GridFunction(self.h1_fes)
        Et_gf.Assign(mfem.Vector(et.real))
        En_gf.Assign(mfem.Vector(En_phys.real))

        return {
            'kn': kn_filtered,
            'kn_selected': kn_sel,
            'Et_gf': Et_gf,
            'En_gf': En_gf,
            'Et_vec': et,
            'En_vec': En_phys,
            'eigenvalues': eigenvalues,
            'eigenvectors_raw': vecs_filtered,
        }

    def _assemble_Att_piecewise(self, omega):
        """Assemble Att with piecewise materials using PWConstCoefficient."""
        nattr = self.mesh.attributes.Max()

        # Curl-curl: mu_inv per attribute
        cc_vec = mfem.Vector(nattr)
        cc_vec.Assign(0.0)
        for attr, mu_inv in self.mu_inv_vals.items():
            cc_vec[attr - 1] = mu_inv
        cc_coeff = mfem.PWConstCoefficient(cc_vec)

        a_cc = mfem.BilinearForm(self.nd_fes)
        a_cc.AddDomainIntegrator(mfem.CurlCurlIntegrator(cc_coeff))
        a_cc.Assemble()
        a_cc.Finalize()

        # Mass: -omega^2*eps per attribute
        m_vec = mfem.Vector(nattr)
        m_vec.Assign(0.0)
        for attr in self.eps_vals:
            eps = self.eps_vals[attr]
            m_vec[attr - 1] = -omega**2 * eps
        m_coeff = mfem.PWConstCoefficient(m_vec)

        a_m = mfem.BilinearForm(self.nd_fes)
        a_m.AddDomainIntegrator(mfem.VectorFEMassIntegrator(m_coeff))
        a_m.Assemble()
        a_m.Finalize()

        return _mfem_to_scipy(a_cc.SpMat()) + _mfem_to_scipy(a_m.SpMat())

    def compute_cutoff_frequency(self, mode_kn, c0=1.0):
        """Compute cutoff frequency from the propagation constant.

        At cutoff, kn = 0, so omega_c = kc * c0 where kc is the transverse
        wavenumber. From kn^2 = omega^2*mu*eps - kc^2.

        Parameters
        ----------
        mode_kn : complex
            Propagation constant at the solved frequency.
        c0 : float
            Speed of light in the medium.

        Returns
        -------
        fc : float
            Cutoff frequency (returns 0 if the mode is evanescent at this
            frequency, i.e. kn is imaginary and kc cannot be determined
            without a separate zero-frequency solve).
        """
        # kn^2 = omega^2 * mu * eps - kc^2
        # => kc^2 = omega^2 * mu * eps - kn^2
        omega = 2.0 * np.pi * self.freq
        kc_sq = omega**2 * self.mu_val * self.eps_val - mode_kn**2
        if np.real(kc_sq) < 0:
            return 0.0
        kc = np.sqrt(np.real(kc_sq))
        fc = kc * c0 / (2.0 * np.pi)
        return float(fc)

    def get_field_on_grid(self, Et_vec, En_vec, nx=50, ny=50):
        """Evaluate mode fields on a regular grid for plotting.

        Parameters
        ----------
        Et_vec : complex ndarray, shape (nd_size,)
            Tangential electric field DOF values.
        En_vec : complex ndarray, shape (h1_size,)
            Normal electric field DOF values.
        nx, ny : int
            Grid resolution.

        Returns
        -------
        X, Y : ndarray
            Grid coordinates.
        Ex, Ey, Ez : ndarray
            Electric field components on the grid.
        """
        # Get mesh bounding box
        mesh = self.mesh
        vertices = np.array([mesh.GetVertexArray(i) for i in range(mesh.GetNV())])
        xmin, ymin = vertices.min(axis=0)[:2]
        xmax, ymax = vertices.max(axis=0)[:2]

        # Shrink slightly to avoid boundary issues
        dx = (xmax - xmin) * 0.001
        dy = (ymax - ymin) * 0.001
        xs = np.linspace(xmin + dx, xmax - dx, nx)
        ys = np.linspace(ymin + dy, ymax - dy, ny)
        X, Y = np.meshgrid(xs, ys)

        # Create grid functions for real and imaginary parts
        Et_gf_r = mfem.GridFunction(self.nd_fes)
        Et_gf_r.Assign(mfem.Vector(Et_vec.real.copy()))
        Et_gf_i = mfem.GridFunction(self.nd_fes)
        Et_gf_i.Assign(mfem.Vector(Et_vec.imag.copy()))

        En_gf_r = mfem.GridFunction(self.h1_fes)
        En_gf_r.Assign(mfem.Vector(En_vec.real.copy()))
        En_gf_i = mfem.GridFunction(self.h1_fes)
        En_gf_i.Assign(mfem.Vector(En_vec.imag.copy()))

        # Build array of all grid points: shape (npts, 2)
        pts = np.column_stack([X.ravel(), Y.ravel()])

        # Use FindPoints to locate all points at once
        count, elem_ids, ips = mesh.FindPoints(pts)

        # Initialize output arrays
        Ex = np.full(nx * ny, np.nan, dtype=complex)
        Ey = np.full(nx * ny, np.nan, dtype=complex)
        Ez = np.full(nx * ny, np.nan, dtype=complex)

        val_vec = mfem.Vector(2)  # for ND vector field

        for k in range(len(elem_ids)):
            e_id = elem_ids[k]
            if e_id < 0:
                continue
            ip = ips[k]
            T = mesh.GetElementTransformation(e_id)
            T.SetIntPoint(ip)

            # Real parts
            Et_gf_r.GetVectorValue(T, ip, val_vec)
            ex_r, ey_r = val_vec[0], val_vec[1]
            ez_r = En_gf_r.GetValue(T, ip)

            # Imaginary parts
            Et_gf_i.GetVectorValue(T, ip, val_vec)
            ex_i, ey_i = val_vec[0], val_vec[1]
            ez_i = En_gf_i.GetValue(T, ip)

            Ex[k] = ex_r + 1j * ex_i
            Ey[k] = ey_r + 1j * ey_i
            Ez[k] = ez_r + 1j * ez_i

        # Reshape to grid
        Ex = Ex.reshape(ny, nx)
        Ey = Ey.reshape(ny, nx)
        Ez = Ez.reshape(ny, nx)

        return X, Y, Ex, Ey, Ez
