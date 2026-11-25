"""T2 recovery tests for ``fit_spectrum``, graded against the determinant oracle.

Provenance: every expected (Dq, B, C) is the input handed to
``_determinant_oracle.relative_term_levels``, which imports nothing from the
package. No expected value comes from ``fit_spectrum`` or ``compute_point``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._defaults import DEFAULTS
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


MERGE_CM1 = 50.0
"""Levels closer than this read as one band, as in the audit (``audit_fit_paths.MERGE_CM1``)."""


def merged_bands(d: int, dq: float, b: float, c: float, n_bands: int) -> list[float]:
    """Return the lowest ``n_bands`` oracle bands, all multiplicities, near-degenerate merged."""
    groups: list[list[float]] = []
    for e, _uid in oracle_bands(d, dq, b, c, spin_allowed_only=False):
        if groups and e - groups[-1][-1] <= MERGE_CM1:
            groups[-1].append(e)
        else:
            groups.append([e])
    return [sum(g) / len(g) for g in groups[:n_bands]]


# Synthetic rows that fail unlabelled at C = truth after the bounds fix (audit at
# 8135f29): the six d5 high-spin spin-forbidden misses, and the d3 row that had been
# right only by a closed-form seed built from 2E. (d, Dq, B, C, n_bands)
# Two further audit misses (d5 Dq 836.9 and 1283.3) already pass on these oracle
# bands before the grid exists, so they are not red tests and are left out.
SEARCH_MISSES = [
    (5, 963.6, 645.0, 3096.0, 3),
    (5, 1785.4, 1376.0, 5504.0, 3),
    (5, 2055.7, 1376.0, 6604.8, 3),
    (5, 1590.1, 645.0, 2580.0, 3),
    (3, 1200.0, 1468.8, 7050.2, 6),
]


@pytest.mark.parametrize(("d", "dq", "b", "c", "n_bands"), SEARCH_MISSES)
def test_grid_search_recovers_unlabelled(
    d: int, dq: float, b: float, c: float, n_bands: int
) -> None:
    """High-spin, spin-forbidden bands, C = truth, no labels: the grid search finds the truth.

    Observed red at 8135f29 (five local starts around one seed), in table order:
    ``AssertionError: dDq +125.56 %``, ``+64.33 %``, ``-10.50 %``, ``-15.56 %``, ``+4.83 %``.
    """
    fit = fit_spectrum(d, merged_bands(d, dq, b, c, n_bands), c, include_spin_forbidden=True)
    assert_recovered(fit, dq, b)


# Two spin-allowed bands, two parameters: several assignments fit exactly. The truth
# is the exact minimum nearest the generic seed (obs[0] / 10, default B) in log
# distance; the alternatives sit about three times farther. (d, Dq, B, C)
TWO_BAND_TIES = [
    (7, 1267.0, 791.0, 4499.0),
    (2, 1800.0, 700.0, 3801.0),
]


@pytest.mark.parametrize(("d", "dq", "b", "c"), TWO_BAND_TIES)
def test_exact_tie_prefers_minimum_nearest_seed(d: int, dq: float, b: float, c: float) -> None:
    """Among equally exact minima, the fit returns the one nearest the seed.

    A convention, not physics (the user's call, 2026-11-25): with two bands the data
    cannot choose, and the pre-grid fit returned the seed-near minimum by accident.

    Observed red at 107f967: ``AssertionError: dDq -51.35 %`` (d7, fit 616 / 1179) and
    ``dDq -50.32 %`` (d2, fit 894 / 1289), both at RMSE 0.01 cm^-1.
    """
    bands = oracle_bands(d, dq, b, c, spin_allowed_only=True)[:2]
    fit = fit_spectrum(d, [e for e, _u in bands], c)
    assert_recovered(fit, dq, b)


def test_labels_pick_the_assigned_level() -> None:
    """d7 high-spin with the weak 4A2 band unobserved: labels pin nu3 to 4T1(P).

    Unlabelled, 19015 cm^-1 is free to read as 4A2 and the fit returns 1013 / 953.
    """
    dq, b, c = 1000.0, 750.0, 3450.0
    bands = [
        x
        for x in oracle_bands(7, dq, b, c, spin_allowed_only=True)
        if x[1] in {"4_T_2#0", "4_T_1#1"}
    ]
    fit = fit_spectrum(7, [e for e, _u in bands], c, band_labels=term_labels(bands))
    assert_recovered(fit, dq, b)


def test_labelled_band_list_is_sorted_with_its_labels() -> None:
    """Labels travel with their band when the bands are given out of order."""
    dq, b, c = 1000.0, 750.0, 3450.0
    bands = [
        x
        for x in oracle_bands(7, dq, b, c, spin_allowed_only=True)
        if x[1] in {"4_T_2#0", "4_T_1#1"}
    ][::-1]
    fit = fit_spectrum(7, [e for e, _u in bands], c, band_labels=term_labels(bands))
    assert_recovered(fit, dq, b)


def test_assign_bands_is_injective() -> None:
    """Two bands 50 cm^-1 apart around one isolated level map to two levels."""
    from tanabesugano.mcp._compute import assign_bands

    observed = np.array([10000.0, 10050.0])
    levels = [(10025.0, "4_T_2#0"), (12000.0, "4_T_1#1")]
    columns, _rmse = assign_bands(observed, levels, None, penalty=1.0e4)
    assert sorted(columns.tolist()) == [0, 1]


@pytest.mark.parametrize(
    ("bands", "labels", "needle"),
    [
        ([8500.0, 13800.0, 25300.0], ["3_T_2", "3_T_1"], "one label per band"),
        ([8500.0, 13800.0, 25300.0], ["3_T_2", "9_X_9", "3_T_1"], "9_X_9"),
        ([8500.0, 13800.0, 25300.0], ["3_T_2", "1_A_1", "3_T_1"], "1_A_1"),
    ],
)
def test_band_labels_are_validated(bands: list[float], labels: list[str], needle: str) -> None:
    """A wrong count, an unknown term, or a term the fitted manifold lacks raises.

    1_A_1 is a real d8 term but spin-forbidden; without include_spin_forbidden it is
    not a candidate. C0m: unvalidated, three such bands returned Dq -18 % with only
    generic warnings.
    """
    with pytest.raises(ValueError, match=needle):
        fit_spectrum(8, bands, band_labels=labels)


def test_merged_band_label_needs_only_one_known_term() -> None:
    """A band covering a quartet and a near-degenerate doublet keeps both terms.

    With spin-allowed bands only, 2_E is no candidate, but 4_T_1 is: a label tuple is
    an either-or, so it must not raise.

    Observed red at the first C3 draft: ``ValueError: band label '2_E' names no
    spin-allowed level of d3`` on audit row d3 high-spin Dq 2000, B 1055.7.
    """
    dq, b, c = 1000.0, 750.0, 3450.0
    bands = oracle_bands(3, dq, b, c, spin_allowed_only=True)[:3]
    labels: list[str | tuple[str, ...]] = list(term_labels(bands))
    labels[1] = (labels[1], "2_E")
    fit = fit_spectrum(3, [e for e, _u in bands], c, band_labels=labels)
    assert_recovered(fit, dq, b)


def merged_labelled_bands(
    d: int, dq: float, b: float, c: float, n_bands: int
) -> tuple[list[float], list[tuple[str, ...]]]:
    """As :func:`merged_bands`, with each band's term keys (all merged levels' terms)."""
    groups: list[list[tuple[float, str]]] = []
    for e, uid in oracle_bands(d, dq, b, c, spin_allowed_only=False):
        if groups and e - groups[-1][-1][0] <= MERGE_CM1:
            groups[-1].append((e, uid))
        else:
            groups.append([(e, uid)])
    chosen = groups[:n_bands]
    energies = [sum(e for e, _u in g) / len(g) for g in chosen]
    labels = [tuple(sorted({uid.split("#", 1)[0] for _e, uid in g})) for g in chosen]
    return energies, labels


# The nine synthetic d5 high-spin spin-forbidden points of the audit: (Dq, B, C).
D5_HS_POINTS = [
    (502.1, 387.0, 1548.0),
    (578.1, 387.0, 1857.6),
    (836.9, 645.0, 2580.0),
    (963.6, 645.0, 3096.0),
    (1283.3, 989.0, 3956.0),
    (1477.4, 989.0, 4747.2),
    (1785.4, 1376.0, 5504.0),
    (2055.7, 1376.0, 6604.8),
    (1590.1, 645.0, 2580.0),
]


@pytest.mark.parametrize(("dq", "b", "c"), D5_HS_POINTS)
def test_labelled_hs_d5_recovers_c(dq: float, b: float, c: float) -> None:
    """Three labelled bands, C not given: C is fitted and Dq, B, C all recovered.

    Before free C, eight of the nine come back wrong at the default C (audit at
    eef709b, labelled-default): the default C misplaces every level, and no (Dq, B)
    can compensate. The ninth (1283.3 / 989 / 3956) sits next to the default C/B.
    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'c_fitted'``
    on all nine.
    """
    energies, labels = merged_labelled_bands(5, dq, b, c, 3)
    fit = fit_spectrum(5, energies, include_spin_forbidden=True, band_labels=labels)
    assert fit.c_fitted
    assert_recovered(fit, dq, b, c)


def test_three_unlabelled_bands_keep_c_held() -> None:
    """Guard, green before C4: three unlabelled bands do not free C.

    C0m: unlabelled, the d5 high-spin manifold has 37-60 exact minima in (Dq, B, C).
    The plan also asked for the "not constrained" warning here; it never fires,
    because the d5 high-spin bands do move with C. That assertion was dropped.
    """
    dq, b, c = D5_HS_POINTS[3]
    fit = fit_spectrum(5, merged_bands(5, dq, b, c, 3), include_spin_forbidden=True)
    assert not getattr(fit, "c_fitted", False)
    assert DEFAULTS[5]["default_C"] == fit.C


def test_two_labelled_bands_keep_c_held() -> None:
    """Guard: two labelled bands cannot fix three parameters (C0m: 19 exact minima)."""
    dq, b, c = 2500.0, 700.0, 3080.0
    bands = oracle_bands(6, dq, b, c, spin_allowed_only=True)[:2]
    fit = fit_spectrum(6, [e for e, _u in bands], spin_state="low", band_labels=term_labels(bands))
    assert not getattr(fit, "c_fitted", False)


def test_explicit_c_or_fit_c_false_holds_c() -> None:
    """An explicit C, or fit_c=False, keeps C fixed even with every band labelled.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'fit_c'``.
    """
    dq, b, c = D5_HS_POINTS[3]
    energies, labels = merged_labelled_bands(5, dq, b, c, 3)
    held = fit_spectrum(5, energies, 3500.0, include_spin_forbidden=True, band_labels=labels)
    off = fit_spectrum(5, energies, include_spin_forbidden=True, band_labels=labels, fit_c=False)
    assert not held.c_fitted
    assert held.C == 3500.0
    assert not off.c_fitted


def test_c_over_b_outside_window_warns() -> None:
    """Truth C/B = 7, outside the (3, 6) window: the fit pins on the edge and says so.

    C0m: 18 of 18 such labelled fits pinned at the window edge with no warning.
    Observed red: ``assert False`` -- no warning names the C/B window.
    """
    dq, b = D5_HS_POINTS[3][:2]
    energies, labels = merged_labelled_bands(5, dq, b, 7.0 * b, 3)
    fit = fit_spectrum(5, energies, include_spin_forbidden=True, band_labels=labels)
    assert any("C/B" in w and "window" in w for w in fit.warnings)


def test_missing_band_lists_both_exact_minima() -> None:
    """d5 high-spin, middle (4T2) band dropped: two exact minima, both listed.

    C0m check 4 (oracle, C held at truth): with the 4T2 band gone, a second
    (Dq, B) reproduces the two remaining bands exactly and honours the term labels,
    by putting the top band on 4E from 4D. Labels cannot tell them apart, so the
    fit must list both rather than return one silently. The held-C search reaches
    both in 7 of the 9 audit points (not 502.1 / 387 or 1590.1 / 645): ``minima``
    lists what the search found, not every minimum that exists.
    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'minima'``.
    """
    dq, b, c = D5_HS_POINTS[1]
    energies, labels = merged_labelled_bands(5, dq, b, c, 3)
    del energies[1], labels[1]
    fit = fit_spectrum(5, energies, c, include_spin_forbidden=True, band_labels=labels)
    exact = [m for m in fit.minima if m[3] < 1.0]
    assert len(exact) == 2
    assert any(abs(m[0] / dq - 1) < 0.02 and abs(m[1] / b - 1) < 0.05 for m in exact)


def test_minima_are_distinct_and_sorted() -> None:
    """``minima`` holds each converged minimum once, best first, returned one included."""
    dq, b, c = 1200.0, 750.0, 3450.0
    fit = fit_spectrum(7, [e for e, _u in oracle_bands(7, dq, b, c, spin_allowed_only=True)], c)
    objectives = [m[3] for m in fit.minima]
    assert objectives == sorted(objectives)
    assert any(m[0] == fit.Dq and m[1] == fit.B for m in fit.minima)
    for i, m in enumerate(fit.minima):
        for n in fit.minima[:i]:
            assert (
                abs(m[0] / n[0] - 1) > 0.02
                or abs(m[1] / n[1] - 1) > 0.05
                or abs(m[2] / n[2] - 1) > 0.05
            )


def test_bounds_excluding_minimum_warns() -> None:
    """Review Focus 4: dq_bounds below the truth pin Dq on the edge, and the fit says so.

    d8 oracle (850, 907, 4850), bounds (300, 700): the best the fit can do is Dq = 700.
    Observed red: ``assert False`` -- Dq came back at 700 with no warning naming it.
    """
    bands = [e for e, _u in oracle_bands(8, 850.0, 907.0, 4850.0, spin_allowed_only=True)]
    fit = fit_spectrum(8, bands, 4850.0, dq_bounds=(300.0, 700.0))
    assert fit.Dq == pytest.approx(700.0, rel=0.01)
    assert any("Dq pinned" in w for w in fit.warnings)


# Audit near-crossover points (1.1 x crossover, spin-allowed bands) that the other
# spin regime reproduces too (C5 scan): d6 one band, exactly; d7 three bands, to 10 cm^-1.
OTHER_REGIME_CASES = [
    (6, 1292.5, 798.8, 3195.2, "low"),
    (7, 1343.7, 728.2, 2912.8, "low"),
]


@pytest.mark.parametrize(("d", "dq", "b", "c", "other"), OTHER_REGIME_CASES)
def test_near_crossover_names_other_regime(
    d: int, dq: float, b: float, c: float, other: str
) -> None:
    """Unlabelled high-spin bands near the crossover: say the low-spin regime fits them too.

    Observed red (against 32a91a0): ``assert False`` on both -- no warning names the
    other regime, and the high-spin answer is returned as if it were the only one.
    """
    bands = [e for e, _u in oracle_bands(d, dq, b, c, spin_allowed_only=True)]
    fit = fit_spectrum(d, bands, c)
    assert abs(fit.Dq / dq - 1) * 100 <= DQ_TOL_PCT  # one d6 band leaves B open
    assert any(f"{other}-spin regime also fits" in w for w in fit.warnings)


def test_labels_settle_the_regime() -> None:
    """With term labels the other regime cannot carry the bands, so nothing is said."""
    d, dq, b, c, _other = OTHER_REGIME_CASES[1]
    bands = oracle_bands(d, dq, b, c, spin_allowed_only=True)
    fit = fit_spectrum(d, [e for e, _u in bands], c, band_labels=term_labels(bands))
    assert not any("regime also fits" in w for w in fit.warnings)
