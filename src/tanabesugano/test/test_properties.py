"""Property-based tests over the (Dq, B, C) parameter space.

Scope is deliberately narrow: **Tier 1 invariants only** -- statements that must
hold for EVERY parameter combination, not fitter behaviour. The existing
parametrized tests pin a handful of hand-chosen points; these search the space
between them, which is where a sign error that only bites at large C/B, or a
degeneracy that only appears near a crossover, would hide.

Honest scoping note: this would NOT have caught either mutation that survived
the campaign (a symmetric edit across a conjugate pair, and a global constant
shift). Both preserve every property asserted here, at every point in the space.
Property testing is a complement to the absolute-oracle inventory in
test_oracle_coverage.py, not a substitute for it.

`derandomize=True` keeps CI reproducible: the same examples run every time, so a
failure is always replayable and the suite cannot flake. `max_examples` is kept
low because each example diagonalises up to a 42x42 matrix.
"""

from __future__ import annotations

import numpy as np
import pytest

from hypothesis import HealthCheck
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from tanabesugano import matrices
from tanabesugano.terms import TermKey
from tanabesugano.terms import parse_term_key


SOLVERS = {d: getattr(matrices, f"d{d}") for d in range(2, 9)}
ALL_D = tuple(range(2, 9))

# Physically meaningful ranges. Dq excludes negatives deliberately: the solver
# subtracts a hardcoded ground expression that stops being the true minimum
# below zero (see test_matrices_invariants.test_negative_dq_breaks_the_zero_point).
dq_values = st.floats(min_value=0.0, max_value=6000.0, allow_nan=False, allow_infinity=False)
b_values = st.floats(min_value=300.0, max_value=1500.0, allow_nan=False, allow_infinity=False)
c_over_b = st.floats(min_value=2.0, max_value=8.0, allow_nan=False, allow_infinity=False)
d_counts = st.sampled_from(ALL_D)

SETTINGS = settings(
    max_examples=40,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def levels(d_count: int, dq: float, b: float, c: float) -> np.ndarray:
    states = SOLVERS[d_count](Dq=dq, B=b, C=c).solver().as_dict()
    return np.array([float(e) for v in states.values() for e in np.asarray(v).flatten()])


class TestParameterSpaceInvariants:
    @SETTINGS
    @given(d_count=d_counts, dq=dq_values, b=b_values, ratio=c_over_b)
    def test_ground_state_is_always_exactly_zero(
        self,
        d_count: int,
        dq: float,
        b: float,
        ratio: float,
    ) -> None:
        """The zero point must hold everywhere, not just at sampled points."""
        assert levels(d_count, dq, b, b * ratio).min() == pytest.approx(0.0, abs=1e-9)

    @SETTINGS
    @given(d_count=d_counts, dq=dq_values, b=b_values, ratio=c_over_b)
    def test_all_levels_are_finite(
        self,
        d_count: int,
        dq: float,
        b: float,
        ratio: float,
    ) -> None:
        assert np.all(np.isfinite(levels(d_count, dq, b, b * ratio)))

    @SETTINGS
    @given(d_count=d_counts, dq=dq_values, b=b_values, ratio=c_over_b)
    def test_level_count_never_varies(
        self,
        d_count: int,
        dq: float,
        b: float,
        ratio: float,
    ) -> None:
        """Degeneracies must not collapse or split as parameters move."""
        expected = {2: 11, 3: 20, 4: 43, 5: 43, 6: 43, 7: 20, 8: 11}
        assert len(levels(d_count, dq, b, b * ratio)) == expected[d_count]

    @SETTINGS
    @given(d_count=d_counts, dq=dq_values, b=b_values, ratio=c_over_b)
    def test_term_keys_are_always_valid(
        self,
        d_count: int,
        dq: float,
        b: float,
        ratio: float,
    ) -> None:
        """No parameter combination may produce a key outside the closed set."""
        states = SOLVERS[d_count](Dq=dq, B=b, C=b * ratio).solver().as_dict()
        for key in states:
            assert parse_term_key(str(key)) is not None, f"invalid key {key!r}"
            assert str(key) in {k.value for k in TermKey}


class TestScalingProperties:
    """Relations that must hold between two points in the space."""

    @SETTINGS
    @given(dq=st.floats(min_value=1.0, max_value=5000.0), b=b_values, ratio=c_over_b)
    def test_nu1_is_10dq_for_d3_and_d8_everywhere(
        self,
        dq: float,
        b: float,
        ratio: float,
    ) -> None:
        """The identity is exact and B-, C-independent across the whole space."""
        for d_count, excited in ((3, "4_T_2"), (8, "3_T_2")):
            states = SOLVERS[d_count](Dq=dq, B=b, C=b * ratio).solver().as_dict()
            ground = min(float(e) for v in states.values() for e in np.asarray(v).flatten())
            value = float(np.asarray(states[TermKey(excited)]).flatten()[0])
            assert value - ground == pytest.approx(10 * dq, rel=1e-9, abs=1e-6)

    @SETTINGS
    @given(dq=dq_values, b=b_values, ratio=c_over_b)
    def test_hole_conjugation_holds_everywhere(
        self,
        dq: float,
        b: float,
        ratio: float,
    ) -> None:
        """d^n(+Dq) == d^(10-n)(-Dq) after re-referencing each to its own minimum.

        NOTE this is a RELATIVE invariant: it cannot see a symmetric edit made to
        both members of a conjugate pair. See test_oracle_coverage.py.
        """
        c = b * ratio
        for d_a, d_b in ((2, 8), (3, 7), (4, 6)):
            a = np.sort(levels(d_a, dq, b, c))
            z = np.sort(levels(d_b, -dq, b, c))
            assert a - a.min() == pytest.approx(z - z.min(), abs=1e-6)
