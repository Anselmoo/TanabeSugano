"""Independent d^n ligand-field oracle in the Slater-determinant basis.

Nothing here comes from ``tanabesugano``: no import, no copied expression, no
hand-typed matrix element. The package writes one small matrix per (S, Gamma)
block by hand; this module instead builds the full many-electron Hamiltonian of
d^n in all ``C(10, n)`` determinants of the ten d spin-orbitals and lets
symmetry sort the eigenvalues afterwards. The two routes share only physics
(Condon-Shortley phases, Racah's B and C, the Oh field with 4-fold axes along
x, y, z), so agreement between them is evidence about ``matrices.py`` rather
than about a convention both happen to copy.

Construction, from first principles only:

* Wigner 3j symbols from Racah's closed formula with exact integer factorials,
  giving the Gaunt coefficients
  ``c^k(m, m') = (-1)^m 5 (2 k 2; 0 0 0)(2 k 2; -m, m-m', m')``.
* Electron repulsion in second quantisation with
  ``<ab|cd> = d(s_a,s_c) d(s_b,s_d) d(m_a+m_b, m_c+m_d) sum_k c^k(m_a,m_c) c^k(m_d,m_b) F^k``
  and ``F^2 = 49B + 7C``, ``F^4 = 63C/5`` (``F^0`` only shifts every level).
* The octahedral field as a one-electron operator in the complex basis:
  ``<±2|V|±2> = Dq``, ``<±1|V|±1> = -4Dq``, ``<0|V|0> = 6Dq``, ``<±2|V|∓2> = 5Dq``.
* Spin from ``S^2 = S_- S_+ + S_z^2 + S_z``; each multiplet is taken in its
  ``M_S = S`` sector, so every level appears once per orbital partner.
* Orbital symmetry from the full rotation group O: the 24 Wigner matrices
  ``D^2(g)`` are generated from C4(z) and C4(y), lifted to determinants as
  minors, and combined into the character projectors
  ``P_Gamma = (d_Gamma / 24) sum_g chi_Gamma(g) R(g)``. The isotypic subspaces
  are fixed by the group alone, so the labels do not depend on any parameter
  point and survive accidental degeneracies and level crossings.

Orbital order (fixes every determinant sign): spin-orbital ``i = 5 s + j`` with
``s = 0`` for alpha, ``1`` for beta, and ``m = 2 - j``.
"""

from __future__ import annotations

import functools
import itertools
import math

from dataclasses import dataclass
from fractions import Fraction

import numpy as np


L = 2
M_VALUES = (2, 1, 0, -1, -2)
N_ORB = 10
IRREPS = ("A_1", "A_2", "E", "T_1", "T_2")
IRREP_DIM = {"A_1": 1, "A_2": 1, "E": 2, "T_1": 3, "T_2": 3}
CLASSES = ("E", "C3", "C2", "C4", "C2'")
# Character table of O, the standard textbook table (e.g. Cotton, Chemical
# Applications of Group Theory), not derived from anything in this package.
CHARACTERS = {
    "A_1": (1, 1, 1, 1, 1),
    "A_2": (1, 1, 1, -1, -1),
    "E": (2, -1, 2, 0, 0),
    "T_1": (3, 0, -1, 1, -1),
    "T_2": (3, 0, -1, -1, 1),
}

# Symmetry-sorted eigenvalues are grouped in chunks of d_Gamma; a chunk whose
# members differ by more than this is a labelling failure, not noise.
_CHUNK_SPREAD_TOL = 1e-7


# --------------------------------------------------------------------------
# Angular momentum algebra
# --------------------------------------------------------------------------


def _fact(n: int) -> int:
    return math.factorial(n)


def wigner_3j(j1: int, j2: int, j3: int, m1: int, m2: int, m3: int) -> float:
    """Wigner 3j symbol for integer arguments, Racah's formula, exact up to the final root."""
    if m1 + m2 + m3 != 0:
        return 0.0
    if not abs(j1 - j2) <= j3 <= j1 + j2:
        return 0.0
    if abs(m1) > j1 or abs(m2) > j2 or abs(m3) > j3:
        return 0.0
    # Squared prefactor, kept exact.
    tri = Fraction(
        _fact(j1 + j2 - j3) * _fact(j1 - j2 + j3) * _fact(-j1 + j2 + j3),
        _fact(j1 + j2 + j3 + 1),
    )
    pref2 = tri * (
        _fact(j1 + m1)
        * _fact(j1 - m1)
        * _fact(j2 + m2)
        * _fact(j2 - m2)
        * _fact(j3 + m3)
        * _fact(j3 - m3)
    )
    total = Fraction(0)
    t_min = max(0, j2 - j3 - m1, j1 - j3 + m2)
    t_max = min(j1 + j2 - j3, j1 - m1, j2 + m2)
    for t in range(t_min, t_max + 1):
        den = (
            _fact(t)
            * _fact(j3 - j2 + t + m1)
            * _fact(j3 - j1 + t - m2)
            * _fact(j1 + j2 - j3 - t)
            * _fact(j1 - t - m1)
            * _fact(j2 - t + m2)
        )
        total += Fraction((-1) ** t, den)
    phase = (-1) ** (j1 - j2 - m3)
    # value = phase * total * sqrt(pref2); square exactly, then take one root.
    value2 = total * total * pref2
    sign = phase * (1 if total >= 0 else -1)
    return sign * math.sqrt(value2)


def gaunt_ck(k: int, m: int, mp: int) -> float:
    """``c^k(l m, l m')`` for l = 2 (Condon & Shortley)."""
    return (
        (-1) ** m * (2 * L + 1) * wigner_3j(L, k, L, 0, 0, 0) * wigner_3j(L, k, L, -m, m - mp, mp)
    )


def wigner_small_d(j: int, beta: float) -> np.ndarray:
    """``d^j_{m'm}(beta)``, rows m' and columns m in ``M_VALUES`` order (Wigner's formula)."""
    ms = list(range(j, -j - 1, -1))
    out = np.zeros((len(ms), len(ms)))
    c, s = math.cos(beta / 2), math.sin(beta / 2)
    for a, mp in enumerate(ms):
        for b, m in enumerate(ms):
            pref = math.sqrt(_fact(j + mp) * _fact(j - mp) * _fact(j + m) * _fact(j - m))
            acc = 0.0
            for k in range(max(0, m - mp), min(j + m, j - mp) + 1):
                den = _fact(j + m - k) * _fact(k) * _fact(j - k - mp) * _fact(k - m + mp)
                acc += (
                    (-1) ** (k - m + mp)
                    * c ** (2 * j - 2 * k + m - mp)
                    * s ** (2 * k - m + mp)
                    / den
                )
            out[a, b] = pref * acc
    return out


def crystal_field_matrix() -> np.ndarray:
    """One-electron Oh field per unit Dq, complex d basis in ``M_VALUES`` order."""
    v = np.diag([1.0, -4.0, 6.0, -4.0, 1.0])
    v[0, 4] = v[4, 0] = 5.0
    return v


def _close_group(generators: tuple[np.ndarray, ...], expected: int) -> list[np.ndarray]:
    """All products of ``generators``; fails if they do not close at ``expected`` elements."""
    elements = [np.eye(generators[0].shape[0], dtype=complex)]
    frontier = list(elements)
    # Bounded: a wrong generator (an angle that is not a symmetry of the cube)
    # generates an infinite group, and closure must fail rather than spin.
    while frontier and len(elements) <= expected:
        new: list[np.ndarray] = []
        for g in frontier:
            for h in generators:
                p = h @ g
                if not any(np.allclose(p, e, atol=1e-10) for e in elements + new):
                    new.append(p)
        elements += new
        frontier = new
    if len(elements) != expected:
        msg = f"generated {len(elements)} rotations, expected {expected}"
        raise AssertionError(msg)
    return elements


def _order(g: np.ndarray) -> int:
    p = g.copy()
    for k in range(1, 7):
        if np.allclose(p, np.eye(g.shape[0]), atol=1e-10):
            return k
        p = p @ g
    msg = "rotation of order > 6 in O"
    raise AssertionError(msg)


def rotation_group() -> list[tuple[str, np.ndarray]]:
    """The 24 proper rotations of O as ``(class, D^2(g))``, generated from C4(z), C4(y).

    Classes from element order alone: 1 -> E, 3 -> C3, 4 -> C4; an element of
    order 2 is a C2 if it is the square of a C4 (rotation by pi about a 4-fold
    axis), otherwise a C2' (about a 2-fold axis).
    """
    c4z = np.diag([np.exp(-1j * m * np.pi / 2) for m in M_VALUES])
    c4y = wigner_small_d(L, np.pi / 2).astype(complex)
    elements = _close_group((c4z, c4y), expected=24)
    orders = [_order(g) for g in elements]
    squares_of_c4 = [g @ g for g, o in zip(elements, orders, strict=True) if o == 4]
    by_order = {1: "E", 3: "C3", 4: "C4"}
    out = []
    for g, o in zip(elements, orders, strict=True):
        if o in by_order:
            cls = by_order[o]
        elif any(np.allclose(g, sq, atol=1e-10) for sq in squares_of_c4):
            cls = "C2"
        else:
            cls = "C2'"
        out.append((cls, g))
    return out


# --------------------------------------------------------------------------
# Second quantisation on bitmask determinants
# --------------------------------------------------------------------------


def _spin(i: int) -> int:
    return i // 5


def _m(i: int) -> int:
    return M_VALUES[i % 5]


def determinants(n: int) -> list[int]:
    """All n-electron determinants as bitmasks, in a fixed order."""
    return [sum(1 << i for i in occ) for occ in itertools.combinations(range(N_ORB), n)]


def _annihilate(det: int, i: int) -> tuple[int, int] | None:
    if not (det >> i) & 1:
        return None
    sign = -1 if (det & ((1 << i) - 1)).bit_count() % 2 else 1
    return sign, det & ~(1 << i)


def _create(det: int, i: int) -> tuple[int, int] | None:
    if (det >> i) & 1:
        return None
    sign = -1 if (det & ((1 << i) - 1)).bit_count() % 2 else 1
    return sign, det | (1 << i)


def _apply_string(det: int, ops: tuple[tuple[str, int], ...]) -> tuple[int, int] | None:
    """Apply operators right-to-left; ``ops`` is written left-to-right as in a formula."""
    sign = 1
    for kind, i in reversed(ops):
        res = _annihilate(det, i) if kind == "a" else _create(det, i)
        if res is None:
            return None
        s, det = res
        sign *= s
    return sign, det


def _one_electron(det: int, v: np.ndarray, index: dict[int, int]) -> list[tuple[int, float]]:
    """``sum_{ab, same spin} V_ab a+_a a_b |det>`` as (row, value) pairs."""
    out = []
    for bb in range(N_ORB):
        for aa in range(N_ORB):
            val = v[aa % 5, bb % 5]
            if _spin(aa) != _spin(bb) or val == 0.0:
                continue
            res = _apply_string(det, (("c", aa), ("a", bb)))
            if res is not None:
                out.append((index[res[1]], res[0] * val))
    return out


def _two_electron(det: int, index: dict[int, int]) -> list[tuple[int, int, int, int, int, int]]:
    """Non-vanishing terms of ``sum <ab|cd> a+_a a+_b a_d a_c |det>``.

    Returns (row, sign, m-index of a, b, c, d); spin and M_L conservation are
    imposed here, the radial-angular factor by the caller.
    """
    out = []
    occ = [i for i in range(N_ORB) if (det >> i) & 1]
    for cc, dd in itertools.permutations(occ, 2):
        msum = _m(cc) + _m(dd)
        for aa in range(5 * _spin(cc), 5 * _spin(cc) + 5):
            mb = msum - _m(aa)
            if abs(mb) > L:
                continue
            bb = 5 * _spin(dd) + (L - mb)
            res = _apply_string(det, (("c", aa), ("c", bb), ("a", dd), ("a", cc)))
            if res is not None:
                out.append((index[res[1]], res[0], aa % 5, bb % 5, cc % 5, dd % 5))
    return out


@dataclass(frozen=True)
class Operators:
    """Coefficient matrices of the d^n Hamiltonian in the determinant basis.

    ``H = Dq * dq + B * b + C * c`` up to a constant (F^0) that shifts every
    level equally.
    """

    n: int
    dets: tuple[int, ...]
    dq: np.ndarray
    b: np.ndarray
    c: np.ndarray
    s2: np.ndarray
    sz: np.ndarray


@functools.cache
def operators(n: int) -> Operators:
    """Build the one-, two-electron and spin operators of d^n."""
    dets = determinants(n)
    index = {d: k for k, d in enumerate(dets)}
    dim = len(dets)
    v = crystal_field_matrix()
    ck = {
        k: np.array([[gaunt_ck(k, ma, mb) for mb in M_VALUES] for ma in M_VALUES]) for k in (2, 4)
    }

    h_dq = np.zeros((dim, dim))
    g = {2: np.zeros((dim, dim)), 4: np.zeros((dim, dim))}
    s_plus = np.zeros((dim, dim))

    for col, det in enumerate(dets):
        for row, val in _one_electron(det, v, index):
            h_dq[row, col] += val
        for row, sign, ia, ib, ic, id_ in _two_electron(det, index):
            for k in (2, 4):
                g[k][row, col] += 0.5 * sign * ck[k][ia, ic] * ck[k][id_, ib]
        # S_+ = sum_m a+_{m alpha} a_{m beta}
        for j in range(5):
            res = _apply_string(det, (("c", j), ("a", 5 + j)))
            if res is not None:
                s_plus[index[res[1]], col] += res[0]

    sz = np.diag([0.5 * ((d & 0b11111).bit_count() - (d >> 5).bit_count()) for d in dets])
    s2 = s_plus.T @ s_plus + sz @ sz + sz
    # F^2 = 49 B + 7 C, F^4 = 63 C / 5
    h_b = 49.0 * g[2]
    h_c = 7.0 * g[2] + 63.0 / 5.0 * g[4]
    return Operators(n=n, dets=tuple(dets), dq=h_dq, b=h_b, c=h_c, s2=s2, sz=sz)


# --------------------------------------------------------------------------
# Symmetry blocks
# --------------------------------------------------------------------------


def _subset_rotation(rot: np.ndarray, k: int) -> tuple[list[tuple[int, ...]], np.ndarray]:
    """``R`` on k-electron single-spin determinants: matrix of minors of ``rot``."""
    subsets = list(itertools.combinations(range(5), k))
    out = np.zeros((len(subsets), len(subsets)), dtype=complex)
    for a, rows in enumerate(subsets):
        for b, cols in enumerate(subsets):
            out[a, b] = np.linalg.det(rot[np.ix_(rows, cols)]) if k else 1.0
    return subsets, out


@dataclass(frozen=True)
class Block:
    """One (S, Gamma) block: orthonormal basis and projected coefficient matrices."""

    multiplicity: int
    irrep: str
    dq: np.ndarray
    b: np.ndarray
    c: np.ndarray

    @property
    def key(self) -> str:
        return f"{self.multiplicity}_{self.irrep}"

    def levels(self, dq: float, b: float, c: float) -> np.ndarray:
        h = dq * self.dq + b * self.b + c * self.c
        ev = np.linalg.eigvalsh(h)
        d = IRREP_DIM[self.irrep]
        chunks = ev.reshape(-1, d)
        spread = float(np.ptp(chunks, axis=1).max()) if chunks.size else 0.0
        if spread > _CHUNK_SPREAD_TOL * max(1.0, float(np.abs(ev).max())):
            msg = f"{self.key}: partner levels split by {spread} -- labelling failed"
            raise AssertionError(msg)
        return chunks.mean(axis=1)


@functools.cache
def blocks(n: int) -> tuple[Block, ...]:
    """Every (S, Gamma) block of d^n, labelled by group projectors."""
    ops = operators(n)
    group = rotation_group()
    out: list[Block] = []
    two_s_max = min(n, 10 - n)
    for two_s in range(two_s_max, -1, -2):
        s = two_s / 2
        n_up = (n + two_s) // 2
        n_dn = n - n_up
        # Sector M_S = S, in (alpha subset, beta subset) product order.
        up_sets, _ = _subset_rotation(np.eye(5), n_up)
        dn_sets, _ = _subset_rotation(np.eye(5), n_dn)
        sector_dets = [
            sum(1 << i for i in u) + sum(1 << (5 + i) for i in d) for u in up_sets for d in dn_sets
        ]
        index = {d: k for k, d in enumerate(ops.dets)}
        sel = [index[d] for d in sector_dets]

        def restrict(x: np.ndarray, sel: list[int] = sel) -> np.ndarray:
            return x[np.ix_(sel, sel)]

        w, vecs = np.linalg.eigh(restrict(ops.s2))
        q_s = vecs[:, np.abs(w - s * (s + 1)) < 1e-8]
        if q_s.shape[1] == 0:
            continue

        lifted = []
        for cls, rot in group:
            _, r_up = _subset_rotation(rot, n_up)
            _, r_dn = _subset_rotation(rot, n_dn)
            lifted.append((cls, np.kron(r_up, r_dn)))

        for irrep in IRREPS:
            chi = dict(zip(CLASSES, CHARACTERS[irrep], strict=True))
            proj = sum(chi[cls] * r for cls, r in lifted) * (IRREP_DIM[irrep] / 24)
            u, sv, _ = np.linalg.svd(proj @ q_s, full_matrices=False)
            basis = u[:, sv > 0.5]
            if basis.shape[1] == 0:
                continue
            if basis.shape[1] % IRREP_DIM[irrep]:
                msg = f"d{n} S={s} {irrep}: rank {basis.shape[1]} not a multiple of its dimension"
                raise AssertionError(msg)

            def project(x: np.ndarray, basis: np.ndarray = basis) -> np.ndarray:
                return basis.conj().T @ restrict(x) @ basis

            out.append(
                Block(
                    multiplicity=two_s + 1,
                    irrep=irrep,
                    dq=project(ops.dq),
                    b=project(ops.b),
                    c=project(ops.c),
                ),
            )
    return tuple(out)


def term_levels(n: int, dq: float, b: float, c: float) -> dict[str, np.ndarray]:
    """``{"<2S+1>_<Gamma>": ascending energies}``, absolute (F^0 = 0), one per level."""
    return {blk.key: np.sort(blk.levels(dq, b, c)) for blk in blocks(n)}


def relative_term_levels(n: int, dq: float, b: float, c: float) -> dict[str, np.ndarray]:
    """As :func:`term_levels`, referenced to the ground state."""
    raw = term_levels(n, dq, b, c)
    ground = min(float(v.min()) for v in raw.values())
    return {k: v - ground for k, v in raw.items()}


def full_spectrum(n: int, dq: float, b: float, c: float) -> np.ndarray:
    """All ``C(10, n)`` eigenvalues of the unprojected determinant Hamiltonian."""
    ops = operators(n)
    return np.linalg.eigvalsh(dq * ops.dq + b * ops.b + c * ops.c)
