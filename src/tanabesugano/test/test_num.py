"""Tests for numerical calculations.

Term-key counts per configuration, checked across the whole Dq sweep.

Historical note: ``state_check`` used to carry ``return len(states)`` *inside*
its ``for i in np.linspace(0, 1500, 30)`` loop, so 29 of the 30 Dq values were
dead code and only Dq = 0 was ever exercised -- and d8 had no test at all.
"""

from __future__ import annotations

import numpy as np
import pytest

from tanabesugano import matrices


STATE_FUNCTIONS = {
    2: matrices.d2,
    3: matrices.d3,
    4: matrices.d4,
    5: matrices.d5,
    6: matrices.d6,
    7: matrices.d7,
    8: matrices.d8,
}

# Number of distinct octahedral term keys returned by each solver.
EXPECTED_TERM_KEYS = {2: 7, 3: 8, 4: 12, 5: 11, 6: 12, 7: 8, 8: 7}


def state_check(x: int) -> int | None:
    """Number of term keys for configuration ``x``, verified constant over Dq.

    Returns None for an unsupported d-count, and raises if the key count is not
    stable across the sweep (it must be: the key set is fixed per configuration).
    """
    if x not in STATE_FUNCTIONS:
        return None

    counts = {
        len(STATE_FUNCTIONS[x](Dq=float(dq)).solver().as_dict()) for dq in np.linspace(0, 1500, 30)
    }
    if len(counts) != 1:
        msg = f"d{x} term-key count varies across the Dq sweep: {sorted(counts)}"
        raise AssertionError(msg)
    return counts.pop()


@pytest.mark.parametrize(("d_count", "expected"), sorted(EXPECTED_TERM_KEYS.items()))
def test_term_key_count(d_count: int, expected: int) -> None:
    assert state_check(d_count) == expected


def test_unsupported_d_count_returns_none() -> None:
    assert state_check(9) is None
