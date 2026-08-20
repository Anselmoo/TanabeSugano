"""Racah free-ion term energies for d2..d8, and their octahedral reduction.

At Dq = 0 the ligand field vanishes and every octahedral level collapses onto
the free-ion term it descends from. That correspondence is what lets a level be
labelled 3T_1g(F) or 3T_1g(P) -- the notation the literature actually uses --
instead of the positional 3T_1g(a) / 3T_1g(b), whose ordinal carries no
chemistry and changes meaning if the level ordering ever changes.

Provenance of the numbers
-------------------------
These are transcriptions of Racah's published closed forms, in his own
variables, relative to each configuration's ground term (Racah A shifts every
term of a configuration equally and so cancels -- which is why ``solver()`` can
report ground-referred energies at all).

They were previously kept in ``test_matrices_invariants.py`` as an absolute
oracle for the solver, and they still serve that purpose: that module asserts
solver eigenvalues against these expressions and is the only place that does.
Moving the transcription into ``src`` does not weaken the oracle, because the
independence comes from the two sides being *derived* differently -- a
literature transcription here, a numerical diagonalisation of the Coulomb
matrices in :mod:`tanabesugano.matrices` -- not from which directory the
transcription sits in. What must not happen is a second copy: an expression
asserted in two places at two tolerances lets the looser one mask the tighter.

The d2/d8 table is new (the others were ported unchanged). It was verified
against the solver in both energy and Oh irrep decomposition before being
written down:

    3F  0            -> A_2 + T_1 + T_2      1D   5B + 2C  -> E + T_2
    3P  15B          -> T_1                  1G  12B + 2C  -> A_1 + E + T_1 + T_2
    1S  22B + 7C     -> A_1

Ambiguity is real and is not papered over
-----------------------------------------
d3 and d7 place 2H and 2P at exactly 9B + 3C, for every B and C -- the
coincidence is structural, not an artefact of one parameter choice. Energy
therefore cannot say which of the three 2T_1 levels there descends from 2P.
:func:`parent_candidates` returns every term consistent with a level rather
than picking one, so a caller can label the unambiguous cases and say so
plainly for the rest.
"""

from __future__ import annotations

import math

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tanabesugano.terms import FreeIonTerm


if TYPE_CHECKING:
    from collections.abc import Iterable


DEGENERACY_TOL_CM1: float = 1e-6
"""Two free-ion energies closer than this count as one degenerate group.

Racah's coincidences (d3/d7's 2H == 2P) are exact in closed form, so this only
absorbs floating-point noise in the radicals -- it is not a physical width.
"""

OH_REDUCTION: dict[FreeIonTerm, tuple[str, ...]] = {
    FreeIonTerm.S: ("A_1",),
    FreeIonTerm.P: ("T_1",),
    FreeIonTerm.D: ("E", "T_2"),
    FreeIonTerm.F: ("A_2", "T_1", "T_2"),
    FreeIonTerm.G: ("A_1", "E", "T_1", "T_2"),
    FreeIonTerm.H: ("E", "T_1", "T_1", "T_2"),
    FreeIonTerm.I: ("A_1", "A_2", "E", "T_1", "T_2", "T_2"),
}
"""How each free-ion L reduces in Oh. Multiset: H yields T_1 twice, I yields T_2 twice.

Character-table arithmetic, not measurement. ``test_free_ion.py`` checks each
row by summing irrep dimensions to 2L+1, so a dropped or duplicated entry
cannot survive.
"""


@dataclass(frozen=True)
class FreeIonLevel:
    """One free-ion term of a d^n configuration at a given (B, C).

    ``ordinal`` distinguishes repeats of the same ``(multiplicity, orbital)``
    within one configuration -- d4/d6 carry two 3F terms (the conjugate roots of
    one quadratic) and d5 carries two 2G at unrelated energies. It is 0 for a
    term that occurs once, matching how the literature omits the prime.
    """

    multiplicity: int
    orbital: FreeIonTerm
    energy_cm1: float
    ordinal: int = 0

    @property
    def symbol(self) -> str:
        """``3F``, or ``2G'`` for the second occurrence. Spectroscopic notation."""
        return f"{self.multiplicity}{self.orbital.value}{"'" * self.ordinal}"

    @property
    def latex(self) -> str:
        """``$^{3}F$`` -- matplotlib mathtext, also valid LaTeX math."""
        return f"$^{{{self.multiplicity}}}{self.orbital.value}{"'" * self.ordinal}$"

    @property
    def oh_irreps(self) -> tuple[str, ...]:
        """Octahedral irreps this term splits into. One entry per solver level."""
        return OH_REDUCTION[self.orbital]

    @property
    def degeneracy(self) -> int:
        """(2S+1)(2L+1) -- the microstate count this term accounts for.

        Summed over a configuration these must give C(10, n) exactly; that is
        the completeness oracle, and it is independent of this package.
        """
        return self.multiplicity * (2 * self.orbital.orbital_L + 1)


def _quad(b: float, c: float, bb: float, bc: float, cc: float) -> float:
    """sqrt(bb*B^2 + bc*B*C + cc*C^2) -- the radicals in Racah's table."""
    return math.sqrt(bb * b * b + bc * b * c + cc * c * c)


def _d2_d8(b: float, c: float) -> list[FreeIonLevel]:
    """Free-ion terms of d2 and d8, relative to 3F.

    3F  0        1D   5B + 2C    3P  15B
    1G  12B + 2C 1S  22B + 7C
    """
    return [
        FreeIonLevel(3, FreeIonTerm.F, 0.0),
        FreeIonLevel(1, FreeIonTerm.D, 5 * b + 2 * c),
        FreeIonLevel(3, FreeIonTerm.P, 15 * b),
        FreeIonLevel(1, FreeIonTerm.G, 12 * b + 2 * c),
        FreeIonLevel(1, FreeIonTerm.S, 22 * b + 7 * c),
    ]


def _d3_d7(b: float, c: float) -> list[FreeIonLevel]:
    """Free-ion terms of d3 and d7, relative to 4F (= 3A - 15B).

    Racah's table, in his own variables:
        4F  3A - 15B      4P  3A            2H  3A -  6B + 3C
        2G  3A - 11B + 3C 2F  3A +  9B + 3C 2P  3A -  6B + 3C
        2D  3A +  5B + 5C +/- (193 B^2 + 8 B C + 4 C^2)^(1/2)

    2H and 2P land on the same energy for every (B, C); see the module
    docstring.
    """
    root = _quad(b, c, 193.0, 8.0, 4.0)
    return [
        FreeIonLevel(4, FreeIonTerm.F, 0.0),
        FreeIonLevel(4, FreeIonTerm.P, 15 * b),
        FreeIonLevel(2, FreeIonTerm.G, 4 * b + 3 * c),
        FreeIonLevel(2, FreeIonTerm.H, 9 * b + 3 * c),
        FreeIonLevel(2, FreeIonTerm.P, 9 * b + 3 * c),
        FreeIonLevel(2, FreeIonTerm.F, 24 * b + 3 * c),
        FreeIonLevel(2, FreeIonTerm.D, 20 * b + 5 * c - root),
        FreeIonLevel(2, FreeIonTerm.D, 20 * b + 5 * c + root, ordinal=1),
    ]


def _d4_d6(b: float, c: float) -> list[FreeIonLevel]:
    """Free-ion terms of d4 and d6, relative to 5D (= 6A - 21B).

    Racah's table, in his own variables:
        5D  6A - 21B          3H  6A - 17B + 4C     3G  6A - 12B + 4C
        3D  6A -  5B + 4C     1I  6A - 15B + 6C     1F  6A +  6C
        3F  6A -  5B + 11C/2 +/- (3/2)(68 B^2 + 4 B C +   C^2)^(1/2)
        3P  6A -  5B + 11C/2 +/- (1/2)(912 B^2 - 24 B C + 9 C^2)^(1/2)
        1G  6A -  5B + 15C/2 +/- (1/2)(708 B^2 - 12 B C + 9 C^2)^(1/2)
        1D  6A +  9B + 15C/2 +/- (3/2)(144 B^2 + 8 B C +   C^2)^(1/2)
        1S  6A + 10B + 10C   +/-     2(193 B^2 + 8 B C + 4 C^2)^(1/2)
    """
    f_root = 1.5 * _quad(b, c, 68.0, 4.0, 1.0)
    p_root = 0.5 * _quad(b, c, 912.0, -24.0, 9.0)
    g_root = 0.5 * _quad(b, c, 708.0, -12.0, 9.0)
    d_root = 1.5 * _quad(b, c, 144.0, 8.0, 1.0)
    s_root = 2.0 * _quad(b, c, 193.0, 8.0, 4.0)
    triplet_centre = 16 * b + 5.5 * c
    return [
        FreeIonLevel(5, FreeIonTerm.D, 0.0),
        FreeIonLevel(3, FreeIonTerm.H, 4 * b + 4 * c),
        FreeIonLevel(3, FreeIonTerm.G, 9 * b + 4 * c),
        FreeIonLevel(3, FreeIonTerm.F, triplet_centre - f_root),
        FreeIonLevel(3, FreeIonTerm.F, triplet_centre + f_root, ordinal=1),
        FreeIonLevel(3, FreeIonTerm.P, triplet_centre - p_root),
        FreeIonLevel(3, FreeIonTerm.P, triplet_centre + p_root, ordinal=1),
        FreeIonLevel(3, FreeIonTerm.D, 16 * b + 4 * c),
        FreeIonLevel(1, FreeIonTerm.I, 6 * b + 6 * c),
        FreeIonLevel(1, FreeIonTerm.G, 16 * b + 7.5 * c - g_root),
        FreeIonLevel(1, FreeIonTerm.G, 16 * b + 7.5 * c + g_root, ordinal=1),
        FreeIonLevel(1, FreeIonTerm.F, 21 * b + 6 * c),
        FreeIonLevel(1, FreeIonTerm.D, 30 * b + 7.5 * c - d_root),
        FreeIonLevel(1, FreeIonTerm.D, 30 * b + 7.5 * c + d_root, ordinal=1),
        FreeIonLevel(1, FreeIonTerm.S, 31 * b + 10 * c - s_root),
        FreeIonLevel(1, FreeIonTerm.S, 31 * b + 10 * c + s_root, ordinal=1),
    ]


def _d5(b: float, c: float) -> list[FreeIonLevel]:
    """Free-ion terms of d5, relative to 6S (= 10A - 35B).

    Racah's table, in his own variables:
        6S  10A - 35B        4G  10A - 25B +  5C   4F  10A - 13B +  7C
        4D  10A - 18B +  5C  4P  10A - 28B +  7C   2I  10A - 24B +  8C
        2H  10A - 22B + 10C  2G  10A - 13B +  8C   2G' 10A +  3B + 10C
        2F  10A -  9B +  8C  2F' 10A - 25B + 10C   2D' 10A -  4B + 10C
        2P  10A + 20B + 10C  2S  10A -  3B +  8C
        2D  10A -  3B + 11C +/- 3(57 B^2 + 2 B C + C^2)^(1/2)

    Note the shape: 2D occurs THREE times but as a quadratic PAIR plus a
    separate singleton 2D', not as a cubic triple. 2G and 2F each occur twice,
    at unrelated energies rather than as conjugate roots.
    """
    root = 3.0 * _quad(b, c, 57.0, 2.0, 1.0)
    return [
        FreeIonLevel(6, FreeIonTerm.S, 0.0),
        FreeIonLevel(4, FreeIonTerm.G, 10 * b + 5 * c),
        FreeIonLevel(4, FreeIonTerm.P, 7 * b + 7 * c),
        FreeIonLevel(4, FreeIonTerm.D, 17 * b + 5 * c),
        FreeIonLevel(4, FreeIonTerm.F, 22 * b + 7 * c),
        FreeIonLevel(2, FreeIonTerm.I, 11 * b + 8 * c),
        FreeIonLevel(2, FreeIonTerm.H, 13 * b + 10 * c),
        FreeIonLevel(2, FreeIonTerm.G, 22 * b + 8 * c),
        FreeIonLevel(2, FreeIonTerm.G, 38 * b + 10 * c, ordinal=1),
        FreeIonLevel(2, FreeIonTerm.F, 26 * b + 8 * c),
        FreeIonLevel(2, FreeIonTerm.F, 10 * b + 10 * c, ordinal=1),
        FreeIonLevel(2, FreeIonTerm.D, 32 * b + 11 * c - root),
        FreeIonLevel(2, FreeIonTerm.D, 32 * b + 11 * c + root, ordinal=1),
        FreeIonLevel(2, FreeIonTerm.D, 31 * b + 10 * c, ordinal=2),
        FreeIonLevel(2, FreeIonTerm.P, 55 * b + 10 * c),
        FreeIonLevel(2, FreeIonTerm.S, 32 * b + 8 * c),
    ]


_TABLES = {2: _d2_d8, 3: _d3_d7, 4: _d4_d6, 5: _d5, 6: _d4_d6, 7: _d3_d7, 8: _d2_d8}


def free_ion_levels(d_count: int, B: float, C: float) -> tuple[FreeIonLevel, ...]:
    """Every free-ion term of ``d_count`` at ``(B, C)``, ground term at zero.

    Ordered by energy. Hole conjugation is exact here -- d2/d8, d3/d7 and d4/d6
    share a table -- because the free-ion Coulomb problem does not see the
    ligand field that distinguishes them.
    """
    if d_count not in _TABLES:
        msg = f"no free-ion table for d{d_count}; d2..d8 are supported"
        raise ValueError(msg)
    return tuple(sorted(_TABLES[d_count](B, C), key=lambda t: t.energy_cm1))


def parent_candidates(
    level_energy_cm1: float,
    term_key: str,
    free_ion: Iterable[FreeIonLevel],
) -> tuple[FreeIonLevel, ...]:
    """Free-ion terms a zero-field level could descend from. May be more than one.

    A candidate must match on all three of energy, spin multiplicity and irrep:
    a level cannot descend from a term that does not reduce to its irrep. That
    third filter is what separates 2H from 2P for the 2E and 2T_2 levels of
    d3/d7 -- 2P reduces to T_1 alone. It cannot separate them for the 2T_1
    levels, and this returns both rather than guessing.

    ``term_key`` is an octahedral solver key such as ``"2_T_1"``.
    """
    multiplicity = int(str(term_key).split("_", 1)[0])
    irrep = str(term_key).split("_", 1)[1]
    return tuple(
        term
        for term in free_ion
        if term.multiplicity == multiplicity
        and irrep in term.oh_irreps
        and abs(term.energy_cm1 - level_energy_cm1) <= DEGENERACY_TOL_CM1
    )
