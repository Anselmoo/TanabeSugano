"""Oracles for the Racah free-ion term tables.

These tables previously lived in ``test_matrices_invariants.py`` as an absolute
oracle for the solver. They moved into ``src`` because ``Level`` now needs the
free-ion *term symbol* to label a multiplet as 3T_1g(F) / 3T_1g(P) rather than
(a) / (b). Their oracle status is unaffected: independence comes from the two
sides being derived differently -- a transcription of Racah's published closed
forms versus a numerical diagonalisation of the Coulomb matrices -- not from
which directory the transcription sits in. ``test_matrices_invariants.py`` still
asserts the solver against them and is the only place that does.

Every check below is arithmetic the package cannot influence:

* ``sum over terms of (2S+1)(2L+1) == C(10, n)`` -- the free-ion completeness
  identity, and a strictly stronger statement than the irrep-count sum already
  asserted elsewhere, because it uses 2L+1 directly rather than a reduction.
* ``sum of dim(irrep) over the Oh reduction of L == 2L+1`` -- character-table
  arithmetic.
* the tabulated ground term equals ``DEFAULTS[d]["ground_term"]``, which was
  entered independently for the MCP layer.
"""

from __future__ import annotations

import math

import pytest


D_COUNTS = [2, 3, 4, 5, 6, 7, 8]
B_REF, C_REF = 900.0, 4000.0

IRREP_DIMENSION = {"A_1": 1, "A_2": 1, "E": 2, "T_1": 3, "T_2": 3}


class TestOctahedralReduction:
    """The L -> Oh reduction, checked by dimension counting."""

    def test_every_orbital_letter_has_a_reduction(self) -> None:
        from tanabesugano.free_ion import OH_REDUCTION
        from tanabesugano.terms import FreeIonTerm

        assert set(OH_REDUCTION) == set(FreeIonTerm)

    @pytest.mark.parametrize("letter", ["S", "P", "D", "F", "G", "H", "I"])
    def test_reduction_dimensions_sum_to_2l_plus_1(self, letter: str) -> None:
        """A reduction that dropped or duplicated an irrep fails here.

        Provenance: dim(Gamma) values are the Oh character table; 2L+1 is the
        orbital degeneracy. Neither is computed by this package.
        """
        from tanabesugano.free_ion import OH_REDUCTION
        from tanabesugano.terms import FreeIonTerm

        term = FreeIonTerm(letter)
        total = sum(IRREP_DIMENSION[irrep] for irrep in OH_REDUCTION[term])
        assert total == 2 * term.orbital_L + 1


class TestFreeIonCompleteness:
    """C(10, n) again -- the oracle the package cannot influence."""

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_spin_orbit_degeneracies_sum_to_the_microstate_count(self, d_count: int) -> None:
        """Sum (2S+1)(2L+1) over free-ion terms == C(10, n).

        Catches a dropped term, a duplicated term, and a wrong multiplicity --
        by arithmetic rather than by spelling.
        """
        from tanabesugano.free_ion import free_ion_levels

        terms = free_ion_levels(d_count, B_REF, C_REF)
        total = sum(t.degeneracy for t in terms)
        assert total == math.comb(10, d_count)

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_ground_term_matches_the_independently_entered_default(self, d_count: int) -> None:
        """DEFAULTS[d]['ground_term'] was typed in for the MCP layer, separately."""
        from tanabesugano.free_ion import free_ion_levels
        from tanabesugano.mcp._defaults import DEFAULTS

        lowest = min(free_ion_levels(d_count, B_REF, C_REF), key=lambda t: t.energy_cm1)
        assert lowest.symbol == DEFAULTS[d_count]["ground_term"]

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_ground_term_energy_is_the_zero_point(self, d_count: int) -> None:
        """Energies are relative to the ground term, matching solver() output."""
        from tanabesugano.free_ion import free_ion_levels

        assert min(t.energy_cm1 for t in free_ion_levels(d_count, B_REF, C_REF)) == 0.0


class TestAgreementWithTheSolver:
    """Both directions: no free-ion term without a level, no level without a term."""

    @pytest.mark.parametrize("d_count", D_COUNTS)
    @pytest.mark.parametrize(("b", "c"), [(900.0, 4000.0), (650.0, 2600.0), (1250.0, 6100.0)])
    def test_every_solver_level_sits_on_a_tabulated_term(
        self,
        d_count: int,
        b: float,
        c: float,
    ) -> None:
        from tanabesugano.free_ion import free_ion_levels
        from tanabesugano.mcp._compute import compute_point

        energies = [t.energy_cm1 for t in free_ion_levels(d_count, b, c)]
        zero = compute_point(d_count, 0.0, b, c)
        for key, values in zero.items():
            for level in values:
                assert any(abs(float(level) - e) <= 1e-6 for e in energies), (
                    f"d{d_count} block {key}: zero-field level {float(level)} "
                    f"is on no tabulated free-ion term"
                )

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_each_term_gets_exactly_the_levels_its_reduction_predicts(self, d_count: int) -> None:
        """Term by term: the Oh reduction says how many solver levels sit there.

        Degenerate terms are pooled first (d3/d7: 2H and 2P are both at 9B+3C),
        because energy cannot separate them and this test asserts by energy.
        """
        from tanabesugano.free_ion import free_ion_levels
        from tanabesugano.mcp._compute import compute_point

        terms = free_ion_levels(d_count, B_REF, C_REF)
        found = [float(e) for v in compute_point(d_count, 0.0, B_REF, C_REF).values() for e in v]

        pooled: dict[float, int] = {}
        for t in terms:
            match = next((e for e in pooled if abs(e - t.energy_cm1) <= 1e-6), t.energy_cm1)
            pooled[match] = pooled.get(match, 0) + len(t.oh_irreps)

        for energy, expected in pooled.items():
            hits = sum(1 for e in found if abs(e - energy) <= 1e-6)
            assert hits == expected, (
                f"d{d_count}: {expected} level(s) predicted at {energy:.3f} cm^-1, found {hits}"
            )


class TestDegenerateTermsAreNotSilentlyMerged:
    """d3/d7's 2H and 2P coincide exactly. The table must still list both."""

    @pytest.mark.parametrize("d_count", [3, 7])
    def test_2h_and_2p_are_separate_entries_at_the_same_energy(self, d_count: int) -> None:
        """Provenance: Racah's table gives both as 9B + 3C. Their coincidence is
        exact and parameter-independent, not an artefact of a particular (B, C).
        """
        from tanabesugano.free_ion import free_ion_levels

        terms = free_ion_levels(d_count, B_REF, C_REF)
        doublet_h = [t for t in terms if t.multiplicity == 2 and t.orbital.value == "H"]
        doublet_p = [t for t in terms if t.multiplicity == 2 and t.orbital.value == "P"]
        assert len(doublet_h) == 1
        assert len(doublet_p) == 1
        assert doublet_h[0].energy_cm1 == pytest.approx(doublet_p[0].energy_cm1, abs=1e-9)
        assert doublet_h[0].energy_cm1 == pytest.approx(9 * B_REF + 3 * C_REF, abs=1e-9)
