"""T2 recovery tests for ``fit_spectrum``, graded against the determinant oracle.

Provenance: every expected (Dq, B, C) is the input handed to
``_determinant_oracle.relative_term_levels``, which imports nothing from the
package. No expected value comes from ``fit_spectrum`` or ``compute_point``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.test._determinant_oracle import relative_term_levels


if TYPE_CHECKING:
    from tanabesugano.mcp._compute import SpectrumFit

DQ_TOL_PCT = 2.0
"""Copied from ``scripts/audit_fit_paths.py`` ``DQ_TOL_PCT``: test and audit agree."""
B_TOL_PCT = 5.0
"""Copied from ``scripts/audit_fit_paths.py`` ``B_TOL_PCT``."""
C_TOL_PCT = 5.0
"""B7's criterion for a fitted C; the audit grades no C."""


def oracle_bands(
    d: int, dq: float, b: float, c: float, *, spin_allowed_only: bool
) -> list[tuple[float, str]]:
    """Return ``(energy above ground, "<term>#<index>")`` for every excited oracle level.

    The multiplicity filter uses the oracle's own ground level, never the package's.
    """
    levels = sorted(
        (float(e), f"{key}#{i}")
        for key, values in relative_term_levels(d, dq, b, c).items()
        for i, e in enumerate(values)
    )
    ground_mult = levels[0][1].split("_", 1)[0]
    return [
        (e, uid)
        for e, uid in levels[1:]
        if not spin_allowed_only or uid.split("_", 1)[0] == ground_mult
    ]


def term_labels(bands: list[tuple[float, str]]) -> list[str]:
    """Return the term key of each band (``4_T_1#2`` -> ``4_T_1``): the label a user can supply."""
    return [uid.split("#", 1)[0] for _e, uid in bands]


def assert_recovered(fit: SpectrumFit, dq: float, b: float, c: float | None = None) -> None:
    """Assert the fit is within the recovery tolerances of the oracle truth."""
    d_dq = 100.0 * (fit.Dq - dq) / dq
    d_b = 100.0 * (fit.B - b) / b
    assert abs(d_dq) <= DQ_TOL_PCT, f"dDq {d_dq:+.2f} %"
    assert abs(d_b) <= B_TOL_PCT, f"dB {d_b:+.2f} %"
    if c is not None:
        d_c = 100.0 * (fit.C - c) / c
        assert abs(d_c) <= C_TOL_PCT, f"dC {d_c:+.2f} %"


def test_oracle_bands_d8_nu1_is_ten_dq() -> None:
    """T1a self-check of the harness: d8 nu1 = 10 Dq exactly.

    Observed red: ``NameError: name 'oracle_bands' is not defined``.
    """
    bands = oracle_bands(8, 850.0, 907.0, 4850.0, spin_allowed_only=True)
    assert len(bands) == 3
    assert abs(bands[0][0] - 8500.0) < 1e-6
    assert term_labels(bands) == ["3_T_2", "3_T_1", "3_T_1"]


# The four B1 cases whose truth lay outside the old default bounds (B6 idx 77, 91,
# 169, 183): (d, Dq, B, C, spin_state, n_bands), spin-forbidden bands included.
BOUNDS_EXCLUDED_TRUTH = [
    (4, 1675.0, 723.8, 2895.2, "high", 4),
    (4, 1851.3, 723.8, 2895.2, "low", 6),
    (7, 1343.7, 728.2, 2912.8, "high", 6),
    (7, 1485.2, 728.2, 2912.8, "low", 6),
]


@pytest.mark.parametrize(("d", "dq", "b", "c", "_spin", "n_bands"), BOUNDS_EXCLUDED_TRUTH)
def test_default_dq_bounds_contain_truth(
    d: int, dq: float, b: float, c: float, _spin: str, n_bands: int
) -> None:
    """The default Dq bounds contain the truth, reading only the observed bands.

    Containment only: B6 widen/nn/truth recovers just 2 of these 4, so recovery is
    asserted under the grid search (C2), not here.

    Observed red: ``ImportError: cannot import name 'default_dq_bounds'``; on the old
    formula ``(0.2, 5) * min(obs) / 10`` the upper bound is 420 against a truth of 1675.
    """
    from tanabesugano.mcp._compute import default_dq_bounds

    observed = [e for e, _uid in oracle_bands(d, dq, b, c, spin_allowed_only=False)[:n_bands]]
    lo, hi = default_dq_bounds(observed, observed[0] / 10.0)
    assert lo < dq < hi


def test_closed_form_seed_skipped_with_spin_forbidden() -> None:
    """d8 with a singlet among the lowest three bands still recovers (Dq, B).

    The closed form reads the lowest three bands as nu1..nu3; with spin-forbidden
    bands included, one of them is 1_E, and the seed is built from the wrong level.
    """
    dq, b, c = 850.0, 907.0, 4850.0
    bands = oracle_bands(8, dq, b, c, spin_allowed_only=False)[:5]
    assert any(not uid.startswith("3_") for _e, uid in bands[:3])
    fit = fit_spectrum(8, [e for e, _u in bands], c, include_spin_forbidden=True)
    assert_recovered(fit, dq, b)
