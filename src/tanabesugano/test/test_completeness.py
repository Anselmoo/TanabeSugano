"""Completeness of the term manifold, checked against pure combinatorics.

Every level the solver emits carries a degeneracy of (2S+1) x dim(Gamma). Summed
over all levels of a d^n configuration, that MUST equal the number of ways to
place n electrons in 10 spin-orbitals -- C(10, n):

    d2 45   d3 120   d4 210   d5 252   d6 210   d7 120   d8 45

This is the strongest oracle in the suite, for one reason: **the expected value
comes from `math.comb`, which has no contact with this package.** Contrast the
existing level-count test (11/20/43/43/43/20/11), whose numbers were obtained by
MEASURING the solver -- that pins regressions but cannot detect a manifold that
was wrong from the start.

It is also a COMPLETENESS check rather than a value check, so it catches a class
nothing else does:

  * a term omitted from a solver's return dict (degeneracy goes missing);
  * a term returned twice, or a matrix sized wrong (degeneracy over-counts);
  * an irrep mislabelled in a way that changes its dimension -- an E written as
    an A, or a T as an E. This is close to the 1_T_3 / 5_E_1 family, but caught
    by ARITHMETIC rather than by spelling, so it would fire even for a
    well-spelled key attached to the wrong block.

What it cannot see: any edit that preserves degeneracies, which includes every
numeric change to a matrix element. Those need the absolute-value oracles
inventoried in test_oracle_coverage.py.
"""

from __future__ import annotations

from math import comb

import pytest

from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.terms import Irrep
from tanabesugano.terms import TermKey


ALL_D = tuple(range(2, 9))

# Dimensions of the Mulliken irreducible representations in Oh. Group theory,
# not measurement: A is non-degenerate, E is doubly, T is triply degenerate.
IRREP_DIMENSION: dict[Irrep, int] = {Irrep.A: 1, Irrep.E: 2, Irrep.T: 3}

# Spin-orbitals available to a 3d shell: 5 orbitals x 2 spins.
SPIN_ORBITALS = 10


def solved(d_count: int, dq: float = 1000.0) -> dict:
    cfg = DEFAULTS[d_count]
    return compute_point(d_count, dq, float(cfg["default_B"]), float(cfg["default_C"]))


def total_degeneracy(states: dict) -> int:
    """Sum (2S+1) * dim(Gamma) over every level in the manifold."""
    total = 0
    for key, energies in states.items():
        term = TermKey(key)
        total += term.multiplicity * IRREP_DIMENSION[term.irrep] * len(energies)
    return total


class TestMicrostateCount:
    @pytest.mark.parametrize("d_count", ALL_D)
    def test_manifold_accounts_for_every_microstate(self, d_count: int) -> None:
        """The expected value is C(10, n) -- independent of this package."""
        expected = comb(SPIN_ORBITALS, d_count)
        assert total_degeneracy(solved(d_count)) == expected

    @pytest.mark.parametrize("d_count", ALL_D)
    @pytest.mark.parametrize("dq", [0.0, 500.0, 2500.0, 6000.0])
    def test_count_is_invariant_under_the_crystal_field(
        self,
        d_count: int,
        dq: float,
    ) -> None:
        """A crystal field redistributes energies; it cannot create or destroy states.

        This also exercises the spin crossover, where the per-config correction
        blocks rewrite whole manifolds by hand.
        """
        assert total_degeneracy(solved(d_count, dq)) == comb(SPIN_ORBITALS, d_count)

    @pytest.mark.parametrize(("d_a", "d_b"), [(2, 8), (3, 7), (4, 6)])
    def test_hole_conjugate_pairs_have_equal_counts(self, d_a: int, d_b: int) -> None:
        """C(10, n) == C(10, 10-n): d^n and d^(10-n) span the same space."""
        assert total_degeneracy(solved(d_a)) == total_degeneracy(solved(d_b))

    def test_d5_is_the_largest_manifold(self) -> None:
        """252 states -- the half-filled shell, the maximum of C(10, n)."""
        counts = {d: total_degeneracy(solved(d)) for d in ALL_D}
        assert counts[5] == 252
        assert max(counts.values()) == counts[5]


class TestNoDoubleCounting:
    @pytest.mark.parametrize("d_count", ALL_D)
    def test_each_term_appears_once(self, d_count: int) -> None:
        """A dict cannot hold a duplicate key, but a rename could merge two terms.

        If two distinct blocks were ever keyed identically, the later would
        silently overwrite the earlier and the microstate count would drop --
        this asserts the key count directly so the cause is named, not just the
        symptom.
        """
        states = solved(d_count)
        assert len(states) == len({TermKey(k) for k in states})
