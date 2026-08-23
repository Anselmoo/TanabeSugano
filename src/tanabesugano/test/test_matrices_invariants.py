"""Exact analytic invariants for the d2..d8 solver core.

These tests need **no external reference data**. Every assertion is an identity
that follows from the ligand-field algebra itself, so unlike a literature
fixture it can never go stale, be mis-transcribed, or inherit someone else's
convention error. That matters especially for d5 and d6, whose published
Tanabe-Sugano diagrams are known to contain a propagated error
(Hormann & Shaw, J. Chem. Educ. 1987, 64, 918) -- validating those two against
a textbook diagram would validate against the error.

Before these existed the numerical content of matrices.py was untested:
test_matrices.py never instantiated d2..d8, and test_num.py asserted only the
number of dict keys.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from tanabesugano import matrices
from tanabesugano.free_ion import free_ion_levels
from tanabesugano.terms import TermKey


SOLVERS = {d: getattr(matrices, f"d{d}") for d in range(2, 9)}
ALL_D = sorted(SOLVERS)

# Hole-conjugate pairs: d^n in a field of +Dq mirrors d^(10-n) at -Dq.
CONJUGATE_PAIRS = [(2, 8), (3, 7), (4, 6)]

# Total number of levels (eigenvalues, degenerate roots repeated) per config.
EXPECTED_LEVEL_COUNT = {2: 11, 3: 20, 4: 43, 5: 43, 6: 43, 7: 20, 8: 11}

B_REF = 900.0
C_REF = 4000.0


def levels(d_count: int, dq: float, b: float = B_REF, c: float = C_REF) -> np.ndarray:
    """All eigenvalues for one (Dq, B, C) point, ascending."""
    states = SOLVERS[d_count](Dq=dq, B=b, C=c).solver().as_dict()
    return np.sort(
        np.array([float(e) for v in states.values() for e in np.asarray(v).flatten()]),
    )


def level_of(states: dict, key: str, index: int = 0) -> float:
    return float(np.asarray(states[key]).flatten()[index])


class TestGroundStateConvention:
    """The lowest level must sit at exactly 0.0 -- the whole diagram hangs on it."""

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_ground_state_is_exactly_zero(self, d_count: int) -> None:
        for dq, b, c_over_b in itertools.product(
            (0.0, 10.0, 850.0, 2500.0, 6000.0),
            (400.0, 900.0, 1400.0),
            (2.0, 4.5, 8.0),
        ):
            lowest = levels(d_count, dq, b, b * c_over_b).min()
            assert lowest == pytest.approx(0.0, abs=1e-9), (
                f"d{d_count} at Dq={dq}, B={b}, C={b * c_over_b}: min={lowest}"
            )

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_negative_dq_no_longer_breaks_the_zero_point(self, d_count: int) -> None:
        """Dq < 0 used to corrupt the energy zero silently; it no longer can.

        The old solvers subtracted a hardcoded ground expression that stopped
        being the true minimum once Dq went negative -- d3/d8 returned a minimum
        of -9239.0 with no error, so a fitter wandering below zero got
        meaningless energies. Referencing to the actual minimum removed the
        whole failure mode as a side effect; this pins that it stays removed.
        """
        assert levels(d_count, -500.0).min() == pytest.approx(0.0, abs=1e-9)


class TestHoleConjugation:
    """d^n and d^(10-n) are related by Dq -> -Dq. Catches one-sided edits."""

    @pytest.mark.parametrize(("d_a", "d_b"), CONJUGATE_PAIRS)
    @pytest.mark.parametrize("dq", [300.0, 850.0, 1500.0])
    def test_conjugate_pairs_have_identical_spectra(
        self,
        d_a: int,
        d_b: int,
        dq: float,
    ) -> None:
        """Compared after re-referencing each to its OWN minimum.

        solver() subtracts a hardcoded ground expression that is wrong at
        negative Dq (see test_negative_dq_breaks_the_zero_point), so the raw
        outputs differ by a constant offset. Re-referencing removes it and
        leaves the physical statement: the observable spectra are identical.
        """
        a = levels(d_a, dq)
        b = levels(d_b, -dq)
        a -= a.min()
        b -= b.min()
        assert a == pytest.approx(b, abs=1e-6)

    @pytest.mark.parametrize("dq", [300.0, 850.0, 1500.0])
    def test_d5_is_self_conjugate(self, dq: float) -> None:
        assert levels(5, dq) == pytest.approx(levels(5, -dq), abs=1e-6)


class TestFreeIonLimit:
    """At Dq = 0 the octahedral field vanishes and the Racah closed forms hold."""

    def test_d2_free_ion_levels(self) -> None:
        expected = sorted(
            {
                0.0,  # 3F
                5 * B_REF + 2 * C_REF,  # 1D
                15 * B_REF,  # 3P
                12 * B_REF + 2 * C_REF,  # 1G
                22 * B_REF + 7 * C_REF,  # 1S
            },
        )
        found = sorted({round(float(e), 3) for e in levels(2, 0.0)})
        assert found == pytest.approx(expected, abs=1e-3)

    def test_d5_quartet_free_ion_levels(self) -> None:
        """The quartets are a subset -- d5 also carries a doublet manifold."""
        expected = {
            10 * B_REF + 5 * C_REF,  # 4G
            7 * B_REF + 7 * C_REF,  # 4P
            17 * B_REF + 5 * C_REF,  # 4D
            22 * B_REF + 7 * C_REF,  # 4F
        }
        found = {round(float(e), 3) for e in levels(5, 0.0)}
        missing = {e for e in expected if not any(abs(e - f) < 1e-3 for f in found)}
        assert not missing, f"missing quartet levels: {missing}"

    @pytest.mark.parametrize("d_count", [2, 8])
    def test_p_minus_f_gap_is_15b(self, d_count: int) -> None:
        """E(3P) - E(3F) = 15B at zero field, for d2 and d8 alike."""
        found = {round(float(e), 3) for e in levels(d_count, 0.0)}
        assert any(abs(e - 15 * B_REF) < 1e-3 for e in found), (
            f"d{d_count}: no level at 15B = {15 * B_REF}; got {sorted(found)}"
        )


# ---------------------------------------------------------------------------
# Racah's free-ion closed forms
# ---------------------------------------------------------------------------
# The expressions now live in tanabesugano.free_ion, because Level needs the
# free-ion TERM SYMBOL to label a multiplet 3T_1g(F) / 3T_1g(P) rather than
# (a) / (b). They are imported rather than duplicated: the same closed form
# asserted in two places at two tolerances lets the looser one mask what the
# tighter one catches.
#
# Their oracle status is unchanged by the move. Independence comes from the two
# sides being derived differently -- a transcription of Racah's published table
# on one side, a numerical diagonalisation of the Coulomb matrices on the other
# -- not from which directory the transcription sits in. This module is still
# the only place that asserts the solver against them.
#
# WHERE THESE COME FROM. They are Racah's published free-ion term energies.
# They were NOT read off this package -- a value measured from the code and then
# asserted against the code proves nothing. Two mutually independent sources
# agree on every expression below:
#
#   1. LITERATURE. G. Racah, Phys. Rev. 62 (1942) 438. The table is reproduced
#      verbatim in teaching notes, e.g.
#      https://www.chm.uri.edu/weuler/chm501/lectures/lecture14.html
#      which prints the d3/d7 and d4/d6 blocks in full.
#   2. FIRST PRINCIPLES. A re-derivation carried out for this commit: the
#      two-electron Coulomb Hamiltonian of the d shell, built in the Slater
#      determinant basis from Gaunt coefficients (Wigner 3j via the Racah
#      formula), diagonalised, and every eigenvalue assigned an (S, L) label by
#      the standard microstate-counting subtraction. It touches nothing in this
#      package. It reproduces the literature table term by term, and reproduces
#      the d2 values already asserted in TestFreeIonLimit -- so it is calibrated
#      against expressions that predate it.
#
# Racah A shifts every term of a configuration by the same amount, so it cancels
# once energies are referred to the ground term, which is what solver() reports.
# The values below are therefore E(term) - E(ground term).
#
# The third element of each entry is how many eigenvalues the solver must place
# at that energy: the number of Oh irreps the free-ion term L reduces to. That
# is pure group theory, not measurement:
#
#     S -> A1                        1 irrep
#     P -> T1                        1
#     D -> E + T2                    2
#     F -> A2 + T1 + T2              3
#     G -> A1 + E + T1 + T2          4
#     H -> E + 2 T1 + T2             4
#     I -> A1 + A2 + E + T1 + 2 T2   6
#
# Summed over a whole manifold this independently reproduces EXPECTED_LEVEL_COUNT
# (d4 -> 43, d7 -> 20), which was obtained by measuring the solver. Two routes to
# the same number, only one of which has ever touched the code under test.


def racah_table(d_count: int, b: float, c: float) -> list[tuple[str, float, int]]:
    """Adapter: (symbol, energy, irrep-count) triples, the shape these tests use.

    The irrep count comes from the length of the Oh reduction, so it is derived
    from the same group theory the comment block above spells out rather than
    re-entered as a literal.
    """
    return [(t.symbol, t.energy_cm1, len(t.oh_irreps)) for t in free_ion_levels(d_count, b, c)]


# d2 and d8 joined this oracle when the table moved: they were previously
# covered only by TestFreeIonLimit's relative checks (15B splitting), never by
# a full absolute pin of every zero-field level.
RACAH_D_COUNTS = [2, 3, 4, 5, 6, 7, 8]

FREE_ION_TOL = 1e-6


def merged_terms(table: list[tuple[str, float, int]]) -> list[tuple[str, float, int]]:
    """Collapse terms that are exactly degenerate (d3/d7: 2H and 2P coincide)."""
    merged: list[list] = []
    for name, energy, count in sorted(table, key=lambda t: t[1]):
        if merged and abs(energy - merged[-1][1]) <= FREE_ION_TOL:
            merged[-1][0] += f"+{name}"
            merged[-1][2] += count
        else:
            merged.append([name, energy, count])
    return [(str(n), float(e), int(k)) for n, e, k in merged]


class TestFreeIonRacahClosedForms:
    """ABSOLUTE oracle for every configuration with a Racah table: values, not relationships.

    The gap this closes is recorded in test_oracle_coverage.py. Hole conjugation
    says d^n(+Dq) == d^(10-n)(-Dq); it is structurally blind to an edit applied
    to BOTH members of a conjugate pair, and to a global constant shifted by a
    few tenths of a percent. Neither survives a test that fixes a number.

    Every assertion here is at Dq = 0, where the octahedral field vanishes and
    each solver block must land on the free-ion term it descends from.
    """

    @pytest.mark.parametrize("d_count", RACAH_D_COUNTS)
    @pytest.mark.parametrize(
        ("b", "c"),
        [(900.0, 4000.0), (650.0, 2600.0), (1250.0, 6100.0)],
    )
    def test_zero_field_levels_are_the_racah_free_ion_terms(
        self,
        d_count: int,
        b: float,
        c: float,
    ) -> None:
        """Exact values AND exact multiplicities, in both directions."""
        expected = merged_terms(racah_table(d_count, b, c))
        found = levels(d_count, 0.0, b, c)

        for name, energy, count in expected:
            hits = int(np.sum(np.abs(found - energy) <= FREE_ION_TOL))
            assert hits == count, (
                f"d{d_count} at B={b}, C={c}: free-ion term {name} sits at "
                f"{energy}; expected {count} solver level(s) there, found {hits}"
            )

        unexplained = [
            float(e) for e in found if all(abs(float(e) - t[1]) > FREE_ION_TOL for t in expected)
        ]
        assert not unexplained, (
            f"d{d_count} at B={b}, C={c}: levels on no Racah free-ion term: {unexplained}"
        )

    @pytest.mark.parametrize("d_count", RACAH_D_COUNTS)
    def test_every_block_lands_on_a_free_ion_term(self, d_count: int) -> None:
        """Per-block, so each entry in ABSOLUTE_ORACLE is individually earned.

        The pooled check above could in principle be satisfied by a mutation
        that slid one level onto another term's energy. This one names the
        block, so a numeric edit anywhere in it has somewhere to show up.
        """
        b, c = B_REF, C_REF
        expected = [t[1] for t in racah_table(d_count, b, c)]
        states = SOLVERS[d_count](Dq=0.0, B=b, C=c).solver().as_dict()
        for key, values in states.items():
            for energy in np.asarray(values).flatten():
                assert any(abs(float(energy) - e) <= FREE_ION_TOL for e in expected), (
                    f"d{d_count} block {key}: level {float(energy)} at Dq=0 is "
                    "not any Racah free-ion term energy"
                )

    @pytest.mark.parametrize("d_count", RACAH_D_COUNTS)
    def test_irrep_counts_reproduce_the_level_count(self, d_count: int) -> None:
        """The group-theory reduction and EXPECTED_LEVEL_COUNT must agree.

        EXPECTED_LEVEL_COUNT was obtained by measuring the solver. The Oh
        reduction of the free-ion terms is arithmetic over a character table.
        Two routes, one number -- and if they ever disagree, the measured one
        is the suspect.
        """
        predicted = sum(t[2] for t in racah_table(d_count, B_REF, C_REF))
        assert predicted == EXPECTED_LEVEL_COUNT[d_count]


class TestExactTransitionIdentities:
    """Identities that probe the Racah content, not just the field splitting."""

    @pytest.mark.parametrize(
        ("d_count", "excited"),
        [(3, "4_T_2"), (8, "3_T_2"), (4, "5_T_2"), (6, "5_E")],
    )
    @pytest.mark.parametrize("b", [400.0, 900.0, 1400.0])
    def test_nu1_is_exactly_10dq(self, d_count: int, excited: str, b: float) -> None:
        """Independent of B and C: the Racah terms cancel identically.

        d3/d8 are the classic pair. d4/d6 hold for a different reason and were
        added when the dashboard began *displaying* the identity: 5D is the only
        quintet in either configuration, so its Eg/T2g components have nothing to
        mix with and their separation is exactly Delta_o. Group theory, not a
        measurement of this solver -- which is what lets it police the
        "= 10Dq exactly" badge ``ts_dashboard_app`` prints on d3/d4/d6/d8.

        This is the ONLY place nu1 == 10Dq is asserted against the solver. The
        dashboard tests deliberately do not re-assert it at a second tolerance;
        they assert their own contract (one transition per curve) instead.
        """
        dq = 777.0
        states = SOLVERS[d_count](Dq=dq, B=b, C=C_REF).solver().as_dict()
        ground = min(float(e) for v in states.values() for e in np.asarray(v).flatten())
        assert level_of(states, excited) - ground == pytest.approx(10 * dq, abs=1e-6)

    def test_d2_a2_minus_t2_is_10dq(self) -> None:
        """For d2 the 10Dq gap is 3T2g -> 3A2g, NOT a transition from the ground term."""
        dq = 777.0
        states = SOLVERS[2](Dq=dq, B=B_REF, C=C_REF).solver().as_dict()
        gap = level_of(states, "3_A_2") - level_of(states, "3_T_2")
        assert gap == pytest.approx(10 * dq, abs=1e-6)

    def test_d3_doublet_gap_is_20b(self) -> None:
        states = SOLVERS[3](Dq=777.0, B=B_REF, C=C_REF).solver().as_dict()
        gap = level_of(states, "2_A_2") - level_of(states, "2_A_1")
        assert gap == pytest.approx(20 * B_REF, abs=1e-6)

    def test_d3_a1_minus_t2_is_4b_plus_3c(self) -> None:
        states = SOLVERS[3](Dq=777.0, B=B_REF, C=C_REF).solver().as_dict()
        gap = level_of(states, "2_A_1") - level_of(states, "4_T_2")
        assert gap == pytest.approx(4 * B_REF + 3 * C_REF, abs=1e-6)

    @pytest.mark.parametrize("d_count", [2, 8])
    def test_singlet_triplet_gap_is_12b_plus_2c(self, d_count: int) -> None:
        """Identical for d2 and d8 -- a direct hole-conjugate consistency check."""
        states = SOLVERS[d_count](Dq=777.0, B=B_REF, C=C_REF).solver().as_dict()
        gap = level_of(states, "1_T_1") - level_of(states, "3_T_2")
        assert gap == pytest.approx(12 * B_REF + 2 * C_REF, abs=1e-6)


class TestStructuralInvariants:
    """Shape guarantees a fitter is entitled to rely on."""

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_level_count(self, d_count: int) -> None:
        assert len(levels(d_count, 850.0)) == EXPECTED_LEVEL_COUNT[d_count]

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_key_set_is_independent_of_parameters(self, d_count: int) -> None:
        """Safe to precompute: the term keys never depend on (Dq, B, C)."""
        first = set(SOLVERS[d_count](Dq=0.0, B=400.0, C=2000.0).solver().as_dict())
        for dq, b in ((850.0, 900.0), (6000.0, 1400.0)):
            assert set(SOLVERS[d_count](Dq=dq, B=b, C=C_REF).solver().as_dict()) == first

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_eigenvalues_are_sorted_and_finite(self, d_count: int) -> None:
        states = SOLVERS[d_count](Dq=850.0, B=B_REF, C=C_REF).solver().as_dict()
        for key, values in states.items():
            arr = np.asarray(values).flatten().astype(float)
            assert np.all(np.isfinite(arr)), f"d{d_count} {key} has non-finite entries"
            assert np.all(np.diff(arr) >= -1e-9), f"d{d_count} {key} is not ascending"

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_solver_is_deterministic(self, d_count: int) -> None:
        assert np.array_equal(levels(d_count, 850.0), levels(d_count, 850.0))

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_spectrum_is_continuous_across_the_crossover(self, d_count: int) -> None:
        """No discontinuity as Dq sweeps through a spin crossover.

        A jump here would mean a mis-signed shift in one of the crossover
        correction blocks, which a single-point test cannot see.
        """
        grid = np.arange(1500.0, 2600.0, 25.0)
        previous = levels(d_count, float(grid[0]))
        for dq in grid[1:]:
            current = levels(d_count, float(dq))
            assert np.abs(current - previous).max() < 2000.0, f"d{d_count} jumps at Dq={dq}"
            previous = current


class TestGroundBlockNormalisation:
    """The block carrying the ground state is offset by ONE constant, whole.

    Six configurations write ``BLOCK = self.BLOCK_states() - GS``, which is
    size-agnostic. d7 instead assigned ``T_4_1[0] = 0.0`` and subtracted from
    ``T_4_1[1]`` by hand, so anything past the second element was silently left
    unshifted. ``T_4_1`` is 2x2 today, so no absolute-value assertion can see
    the difference -- the defect is only observable when the block grows.

    Injecting an oversized block makes it observable. The expected result comes
    from the INJECTED values, never from the solver: offsetting an array by a
    single scalar cannot change the gaps inside it, so
    ``diff(out) == diff(injected)`` is an algebraic identity, not a measurement.

    d2 is the control -- it already uses the whole-array form, so it must pass
    both before and after the d7 fix.
    """

    INJECTED = (100.0, 500.0, 900.0)

    # (d_count, states-method to oversize, term key it lands under)
    GROUND_BLOCKS = [
        (2, "T_3_1_states", TermKey.TRIPLET_T_1),
        (7, "T_4_1_states", TermKey.QUARTET_T_1),
    ]

    @pytest.mark.parametrize(("d_count", "method", "key"), GROUND_BLOCKS)
    def test_whole_ground_block_is_offset_by_one_constant(
        self,
        d_count: int,
        method: str,
        key: TermKey,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        instance = SOLVERS[d_count](Dq=850.0, B=B_REF, C=C_REF)
        monkeypatch.setattr(
            instance,
            method,
            lambda: np.array(self.INJECTED, dtype=float),
        )
        out = np.asarray(instance.solver().as_dict()[key], dtype=float)

        assert out.shape == (len(self.INJECTED),), f"d{d_count} {key} changed shape: {out}"
        np.testing.assert_allclose(
            np.diff(out),
            np.diff(np.array(self.INJECTED)),
            err_msg=f"d{d_count} {key} was not offset by a single constant: {out}",
        )


class TestCrossoverRebasing:
    """The spin-crossover shift must reach EVERY term, not a hand-written list.

    d4/d5/d6/d7 previously carried 43 individual subtraction lines -- twelve,
    eleven, twelve and eight -- each naming one term. They were complete, but
    only by vigilance: adding a term meant remembering to add a line. The tests
    below fail if any term is left unshifted, which is the failure the old shape
    permitted and LevelSet, which references to its own minimum, cannot express.
    """

    # (d_count, a Dq comfortably BELOW that configuration's spin crossover)
    CROSSOVER_CONFIGS = [(4, 2500.0), (5, 2500.0), (6, 3000.0), (7, 2500.0)]

    @pytest.mark.parametrize(("d_count", "dq"), CROSSOVER_CONFIGS)
    def test_every_term_is_shifted_past_the_crossover(
        self,
        d_count: int,
        dq: float,
    ) -> None:
        """No term may be left negative -- that is what an omitted line looked like."""
        states = SOLVERS[d_count](Dq=dq, B=B_REF, C=C_REF).solver().as_dict()
        negative = {
            str(term): float(np.asarray(values).flatten().min())
            for term, values in states.items()
            if float(np.asarray(values).flatten().min()) < -1e-9
        }
        assert not negative, f"d{d_count} left terms below zero: {negative}"

    @pytest.mark.parametrize(("d_count", "dq"), CROSSOVER_CONFIGS)
    def test_exactly_one_level_sits_at_zero(self, d_count: int, dq: float) -> None:
        """Shifting by too much, or twice, would move the ground off zero."""
        assert levels(d_count, dq).min() == pytest.approx(0.0, abs=1e-9)

    def test_the_shift_is_rigid_and_reaches_every_term(self) -> None:
        """A rigid shift, applied to ALL terms -- the assertion the old shape could not make.

        With 43 individual subtraction lines the only way to check completeness
        was to read them. LevelSet references to its own minimum, so a term
        added to the manifold is shifted by construction, and a non-rigid shift
        would change the gaps.
        """
        from tanabesugano.levels import LevelSet

        raw = {"3_T_1": [-500.0, 250.0], "1_A_1": [100.0], "5_E": [0.0]}
        before = np.sort(np.array([e for v in raw.values() for e in v]))
        out = LevelSet.from_states(raw)
        after = np.sort(np.array([lv.energy_cm1 for lv in out.levels]))

        assert len(out.levels) == before.size, "a level went missing"
        assert after.min() == pytest.approx(0.0), "ground not referenced to zero"
        assert np.diff(after) == pytest.approx(np.diff(before)), "shift was not rigid"
