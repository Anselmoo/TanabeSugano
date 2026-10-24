"""matrices.py against an independent determinant-basis oracle (T1a).

The package writes one small matrix per (S, Gamma) block by hand. The oracle in
:mod:`tanabesugano.test._determinant_oracle` builds the full d^n Hamiltonian in all
``C(10, n)`` Slater determinants instead and sorts the eigenvalues by symmetry
afterwards. It imports nothing from ``tanabesugano`` and copies no expression
from ``free_ion.py``, so agreement is evidence about ``matrices.py``.

The existing invariants in ``test_matrices_invariants.py`` (free-ion levels at
Dq = 0, hole conjugation, nu1 = 10Dq, the 15B and 12B + 2C gaps, comb(10, n)
counts) pin both field limits but not every off-diagonal element at
intermediate field, and conjugation cannot see an error made consistently in d4
and d6; d5 is self-conjugate. This module closes that gap.

Two groups of tests, in this order:

1. ``TestOracle*`` validate the oracle itself against sources that touch
   neither the oracle nor the package (definition of Dq, the character table
   of O, Racah's d2 term energies, counting). Each was observed red against a
   deliberately broken oracle; the observed text is in its docstring.
2. ``TestPackageAgainstOracle`` compares every level of every (S, Gamma) block.
   The mutation test is the valid red for that comparison.

Tolerance: 1e-6 cm^-1, fixed before the first comparison. ``eigh`` is backward
stable, so the error is O(dim * eps * ||H||) ~ 252 * 2.2e-16 * 1e5 ~ 6e-9 cm^-1;
the tolerance is two orders above that and was not read off the implementation.
"""

from __future__ import annotations

import math

from collections import Counter

import numpy as np
import pytest

from tanabesugano.test import _determinant_oracle as orc


TOL_CM1 = 1e-6
D_COUNTS = (2, 3, 4, 5, 6, 7, 8)


def _points() -> list[tuple[float, float, float]]:
    """Dq = 0; an 81-point Dq sweep 0..4000 cm^-1; 30 random (Dq, B, C).

    The sweep (step 50 cm^-1, B = 900, C = 4000) puts every high-spin/low-spin
    crossover of d4-d7 between two grid points without calling the package's own
    crossover routine. Random points: Dq in [0, 4000], B in [400, 1200],
    C/B in [3, 6], seed 20261024.
    """
    pts = [(0.0, 900.0, 4000.0)]
    pts += [(float(dq), 900.0, 4000.0) for dq in np.arange(0.0, 4000.0 + 1e-9, 50.0)]
    rng = np.random.default_rng(20261024)
    for _ in range(30):
        dq = float(rng.uniform(0.0, 4000.0))
        b = float(rng.uniform(400.0, 1200.0))
        pts.append((dq, b, b * float(rng.uniform(3.0, 6.0))))
    return pts


POINTS = _points()


# --------------------------------------------------------------------------
# 1. The oracle itself
# --------------------------------------------------------------------------


class TestOracleOneElectron:
    def test_octahedral_field_splits_eg_and_t2g_by_10dq(self) -> None:
        """Eg at +6Dq (x2), t2g at -4Dq (x3). Source: the definition of Dq.

        Observed red with <2|V|-2> = 3Dq:
        ``Arrays are not almost equal ... [2]: -2.0 (ACTUAL), -4.0 (DESIRED)``
        """
        ev = np.linalg.eigvalsh(orc.crystal_field_matrix())
        np.testing.assert_array_almost_equal(ev, [-4.0, -4.0, -4.0, 6.0, 6.0], decimal=12)


class TestOracleGroup:
    def test_rotation_group_is_o(self) -> None:
        """24 rotations in classes 1/8/3/6/6, unitary, commuting with the Oh field.

        Source: the character table of O. Observed red with C4(y) generated at
        pi/3 instead of pi/2: ``generated 29 rotations, expected 24`` (closure is
        bounded so a non-symmetry fails instead of looping).
        """
        group = orc.rotation_group()
        assert len(group) == 24
        assert Counter(cls for cls, _ in group) == {"E": 1, "C3": 8, "C2": 3, "C4": 6, "C2'": 6}
        v = orc.crystal_field_matrix()
        for _, g in group:
            np.testing.assert_allclose(g.conj().T @ g, np.eye(5), atol=1e-12)
            np.testing.assert_allclose(g @ v, v @ g, atol=1e-12)

    def test_d_orbitals_span_e_plus_t2(self) -> None:
        """chi(D^2(g)) per class equals chi(E) + chi(T_2) = (5, -1, 1, -1, 1).

        Source: character table of O; l = 2 reduces to E + T_2 in O.
        Observed red with T_1/T_2 characters swapped in CHARACTERS:
        ``assert {'E': 5.0, ... 'C3': -1.0, ...} == {'E': 5, ... 'C4': 1, ...}``
        """
        expected = {
            cls: e + t
            for cls, e, t in zip(
                orc.CLASSES, orc.CHARACTERS["E"], orc.CHARACTERS["T_2"], strict=True
            )
        }
        got: dict[str, float] = {}
        for cls, g in orc.rotation_group():
            got.setdefault(cls, round(float(np.trace(g).real), 9))
            assert float(np.trace(g).real) == pytest.approx(got[cls])
        assert got == {"E": 5, "C3": -1, "C2": 1, "C4": -1, "C2'": 1}
        assert got == expected


class TestOracleFreeIon:
    # Racah's d2 terms above 3F, textbook values (not free_ion.py).
    D2_TERMS = {  # term: ((B, C) coefficients, Oh irreps)
        "3F": ((0, 0), ("A_2", "T_1", "T_2")),
        "3P": ((15, 0), ("T_1",)),
        "1D": ((5, 2), ("E", "T_2")),
        "1G": ((12, 2), ("A_1", "E", "T_1", "T_2")),
        "1S": ((22, 7), ("A_1",)),
    }

    def test_d2_free_ion_terms_and_their_oh_labels(self) -> None:
        """At Dq = 0 every d2 block level sits on a Racah term, labelled by its Oh reduction.

        Source: Racah's d2 energies (3F = -8B, 3P = +7B, 1D = -3B + 2C,
        1G = +4B + 2C, 1S = +14B + 7C), shifted to 3F = 0. B and C are not
        round numbers so no coefficient can match by accident.
        Observed red with F^4 = 63C/7:
        ``3_T_1 ... [1]: 16130.05102040817 (ACTUAL), 13759.5 (DESIRED)``.
        """
        b, c = 917.3, 3871.9
        expected: dict[str, list[float]] = {}
        for term, ((kb, kc), irreps) in self.D2_TERMS.items():
            mult = term[0]
            for irrep in irreps:
                expected.setdefault(f"{mult}_{irrep}", []).append(kb * b + kc * c)
        got = orc.relative_term_levels(2, 0.0, b, c)
        assert set(got) == set(expected)
        for key, levels in expected.items():
            np.testing.assert_allclose(got[key], sorted(levels), atol=1e-8, err_msg=key)


class TestOracleLimits:
    @pytest.mark.parametrize("n", D_COUNTS)
    def test_strong_field_slopes_are_t2g_eg_counts(self, n: int) -> None:
        """With B = C = 0 the spectrum is -4p + 6q, C(6, p) * C(4, q) states each.

        Source: counting t2g^p eg^q configurations, p + q = n.
        Observed red with the m = 0 diagonal of V set to 5Dq: the multiset of
        slopes no longer matches: ``{2.0: 12} != {2.0: 24}`` and ``{12.0: 1} != {12.0: 6}`` (d2).
        """
        spec = orc.full_spectrum(n, 1.0, 0.0, 0.0)
        got = Counter(round(float(e), 9) for e in spec)
        expected: Counter[float] = Counter()
        for p in range(max(0, n - 4), min(6, n) + 1):
            q = n - p
            expected[float(-4 * p + 6 * q)] += math.comb(6, p) * math.comb(4, q)
        assert got == expected

    @pytest.mark.parametrize("n", D_COUNTS)
    def test_hole_equivalence(self, n: int) -> None:
        """d^n(+Dq) == d^(10-n)(-Dq), block by block; d5 maps onto itself.

        Source: particle-hole conjugation of the d shell.
        Observed red with the field scaled by 1.01 for n < 5 only:
        ``d4 vs d6 5_T_2 at (300.0, 900.0, 4000.0) ... [0]: 3030.000000000022 (ACTUAL),
        3000.0000000000437 (DESIRED)``.
        """
        for dq, b, c in POINTS[::7]:
            a = orc.relative_term_levels(n, dq, b, c)
            h = orc.relative_term_levels(10 - n, -dq, b, c)
            assert set(a) == set(h)
            for key in a:
                np.testing.assert_allclose(
                    a[key], h[key], atol=1e-8, err_msg=f"d{n} vs d{10 - n} {key} at {dq, b, c}"
                )


class TestOracleCompleteness:
    @pytest.mark.parametrize("n", D_COUNTS)
    def test_blocks_reproduce_the_full_spectrum(self, n: int) -> None:
        """Block levels x (2S+1) x d_Gamma == all C(10, n) eigenvalues; [H, S^2] = 0.

        Source: math.comb(10, n) and the unprojected Hamiltonian.
        Observed red with the S^2 eigenvalue window shifted so no state matched:
        ``assert 0 == 45``.
        """
        dq, b, c = 1234.5, 811.0, 3507.0
        ops = orc.operators(n)
        h = dq * ops.dq + b * ops.b + c * ops.c
        np.testing.assert_allclose(h @ ops.s2, ops.s2 @ h, atol=1e-8)

        rebuilt: list[float] = []
        for blk in orc.blocks(n):
            for e in blk.levels(dq, b, c):
                rebuilt += [float(e)] * (blk.multiplicity * orc.IRREP_DIM[blk.irrep])
        assert len(rebuilt) == math.comb(10, n)
        np.testing.assert_allclose(sorted(rebuilt), orc.full_spectrum(n, dq, b, c), atol=1e-7)


class TestOracleSecondOpinion:
    @pytest.mark.parametrize("n", D_COUNTS)
    def test_zero_field_matches_free_ion_tables(self, n: int) -> None:
        """At Dq = 0 the oracle's distinct levels per multiplicity equal free_ion.py.

        This validates the ORACLE, not the solver: the solver's free-ion
        assertions stay in test_matrices_invariants.py (one claim, one place).
        free_ion.py was read only after the textbook d2 check above passed.
        Observed red with F^4 = 63C/7: ``AssertionError: ('1_E', '1D')`` with a nearest
        level 1422.3 cm^-1 away (d2).
        """
        from tanabesugano.free_ion import free_ion_levels

        b, c = 917.3, 3871.9
        got = orc.relative_term_levels(n, 0.0, b, c)
        for level in free_ion_levels(n, b, c):
            for irrep in level.oh_irreps:
                key = f"{level.multiplicity}_{irrep}"
                assert np.min(np.abs(got[key] - level.energy_cm1)) < 1e-7, (key, level.symbol)


# --------------------------------------------------------------------------
# 2. matrices.py against the oracle
# --------------------------------------------------------------------------


def _package_levels(cls: type, dq: float, b: float, c: float) -> dict[str, np.ndarray]:
    states = cls(Dq=dq, B=b, C=c).solver().as_dict()
    return {str(k): np.sort(np.asarray(v, dtype=float).ravel()) for k, v in states.items()}


def _mismatches(
    d_count: int, cls: type, points: list[tuple[float, float, float]]
) -> dict[str, float]:
    """``{term: max |package - oracle|}`` over ``points``, only where it exceeds TOL_CM1.

    A term present on one side only, or with a different level count, is ``inf``.
    """
    worst: dict[str, float] = {}
    for dq, b, c in points:
        ref = orc.relative_term_levels(d_count, dq, b, c)
        pkg = _package_levels(cls, dq, b, c)
        for key in set(ref) | set(pkg):
            if key not in ref or key not in pkg or len(ref[key]) != len(pkg[key]):
                dev = math.inf
            else:
                dev = float(np.max(np.abs(ref[key] - pkg[key])))
            if dev > TOL_CM1:
                worst[key] = max(worst.get(key, 0.0), dev)
    return worst


def _report(d_count: int, worst: dict[str, float]) -> str:
    items = sorted(worst.items(), key=lambda kv: -kv[1])
    return "; ".join(f"d{d_count} {k}: max deviation {v:.3g} cm^-1" for k, v in items)


class TestPackageAgainstOracle:
    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_all_levels_match_at_every_point(self, d_count: int) -> None:
        """Every level of every (S, Gamma) block, at all 112 points, within 1e-6 cm^-1.

        Also pins the label set and the level count per term: a missing,
        extra or mislabelled block is an ``inf`` deviation.
        Valid red: ``test_a_flipped_element_is_caught_and_named`` below.
        """
        from tanabesugano import matrices

        worst = _mismatches(d_count, getattr(matrices, f"d{d_count}"), POINTS)
        assert not worst, _report(d_count, worst)

    @pytest.mark.parametrize(
        ("d_count", "block", "element", "term"),
        [
            (4, "T_3_1_states", (0, 1), "3_T_1"),
            (5, "T_2_2_states", (0, 1), "2_T_2"),
            (6, "T_1_2_states", (1, 2), "1_T_2"),
        ],
    )
    def test_a_flipped_element_is_caught_and_named(
        self, monkeypatch, d_count: int, block: str, element: tuple[int, int], term: str
    ) -> None:
        """Valid red for the comparison itself: one sign flip must be caught and named.

        One off-diagonal element that is a pure multiple of B is negated in one
        block of the solver class; the comparison must then fail and name that
        block as the worst term. The class is patched for this test only.

        Observed failure text (the report the comparison produces, worst first;
        other terms move only where the flipped block takes over the ground
        state and drags the zero point with it):

        * d4 3_T_1 (0, 1) = -sqrt6 B:
          ``d4 3_T_1: max deviation 2.06e+03 cm^-1; d4 1_E: max deviation 270 cm^-1; ...``
          (12 terms move)
        * d5 2_T_2 (0, 1) = 3 sqrt6 B:
          ``d5 2_T_2: max deviation 5.79e+03 cm^-1; d5 2_T_1: max deviation 619 cm^-1; ...``
          (11 terms move)
        * d6 1_T_2 (1, 2) = -5 sqrt3 B: ``d6 1_T_2: max deviation 9.51e+03 cm^-1``
        """
        from tanabesugano import matrices

        cls = getattr(matrices, f"d{d_count}")
        original_block = getattr(cls, block)
        original_construct = cls.construct_matrix

        def flipped(self):
            def construct(diag, off):
                off = dict(off)
                off[element] = -off[element]
                return original_construct(self, diag, off)

            self.construct_matrix = construct
            try:
                return original_block(self)
            finally:
                del self.construct_matrix

        # The element must be a non-zero multiple of B alone, else the mutation is vacuous.
        probe: dict[tuple[int, int], float] = {}

        def capture(self, diag, off):
            probe.update(off)
            return original_construct(self, diag, off)

        with monkeypatch.context() as m:
            m.setattr(cls, "construct_matrix", capture)
            getattr(cls(Dq=0.0, B=1.0, C=0.0), block)()
            unit_b = float(probe[element])
            getattr(cls(Dq=7.0, B=1.0, C=13.0), block)()
            assert float(probe[element]) == pytest.approx(unit_b)  # independent of Dq, C
            getattr(cls(Dq=7.0, B=2.0, C=13.0), block)()
            assert float(probe[element]) == pytest.approx(2 * unit_b)  # linear in B
            assert unit_b != 0.0

        monkeypatch.setattr(cls, block, flipped)
        worst = _mismatches(d_count, cls, POINTS)
        assert term in worst, f"mutation in d{d_count} {term} went undetected: {worst}"
        assert max(worst, key=lambda k: worst[k]) == term, _report(d_count, worst)
