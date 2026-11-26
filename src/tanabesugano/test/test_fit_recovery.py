"""T2 recovery tests for ``fit_spectrum``, graded against the determinant oracle.

Provenance: every expected (Dq, B, C) is the input handed to
``_determinant_oracle.relative_term_levels``, which imports nothing from the
package. No expected value comes from ``fit_spectrum`` or ``compute_point``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import numpy as np
import pytest

from tanabesugano.levels import LevelSet
from tanabesugano.mcp._compute import BAND_RESOLUTION_CM1
from tanabesugano.mcp._compute import NM_FATOL_CM1
from tanabesugano.mcp._compute import NM_XATOL_CM1
from tanabesugano.mcp._compute import _pick_minimum
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import excited_levels
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import nu1_floor
from tanabesugano.mcp._compute import term_multiplicity
from tanabesugano.mcp._compute import transition_candidates
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


BAND_RULE_MAX_DELTA_MULT = 2
"""The user's band rule (plan G, Task 1): a band is a level whose 2S+1 differs from the
ground's by at most 2 (Delta S = 0, +-1). Written here from the decision, not imported
from ``_compute``, so the generator cannot inherit a defect in the code under test."""


def oracle_bands(
    d: int, dq: float, b: float, c: float, *, spin_allowed_only: bool
) -> list[tuple[float, str]]:
    """Return ``(energy above ground, "<term>#<index>")`` for the excited oracle levels.

    ``spin_allowed_only`` keeps the ground's multiplicity; otherwise the band rule
    (``BAND_RULE_MAX_DELTA_MULT``) applies. The filter uses the oracle's own ground
    level, never the package's.
    """
    levels = sorted(
        (float(e), f"{key}#{i}")
        for key, values in relative_term_levels(d, dq, b, c).items()
        for i, e in enumerate(values)
    )
    ground_mult = int(levels[0][1].split("_", 1)[0])
    max_delta = 0 if spin_allowed_only else BAND_RULE_MAX_DELTA_MULT
    return [
        (e, uid)
        for e, uid in levels[1:]
        if abs(int(uid.split("_", 1)[0]) - ground_mult) <= max_delta
    ]


@pytest.mark.parametrize("d", [4, 5, 6])
def test_oracle_bands_follow_the_band_rule(d: int) -> None:
    """With spin-forbidden bands on, the generator yields only Delta S = 0, +-1 levels.

    The band rule (plan G, Task 1b; ``BAND_RULE_MAX_DELTA_MULT``) applies to every
    generator a fit is fed from, not only to ``merged_bands``. d4-d6 are the d-counts
    with levels two multiplicity steps from the ground (singlets for a quintet ground,
    doublets for a sextet).

    Observed red (b219f71, the generator unfiltered): d4 ``['1_T_2#0', ...]``, d5
    ``['2_T_2#0', ...]``, d6 (low-spin 1A1 ground at these parameters) ``['5_T_2#0', '5_E#0']``.
    """
    bands = oracle_bands(d, 1500.0, 700.0, 3000.0, spin_allowed_only=False)
    ground_mult = int(relative_term_ground(d, 1500.0, 700.0, 3000.0).split("_", 1)[0])
    beyond = [
        uid
        for _e, uid in bands
        if abs(int(uid.split("_", 1)[0]) - ground_mult) > BAND_RULE_MAX_DELTA_MULT
    ]
    assert beyond == []


def relative_term_ground(d: int, dq: float, b: float, c: float) -> str:
    """The oracle's ground term key, read from its lowest level."""
    levels = relative_term_levels(d, dq, b, c)
    return min(((min(v), k) for k, v in levels.items()), key=lambda x: x[0])[1]


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


BOUNDS_EXCLUDED_TRUTH = [
    (4, 1675.0, 723.8, 2895.2, "high", 4),
    (4, 1851.3, 723.8, 2895.2, "low", 6),
    (7, 1343.7, 728.2, 2912.8, "high", 6),
    (7, 1485.2, 728.2, 2912.8, "low", 6),
]
"""The four B1 cases whose truth lay outside the old default bounds (B6 idx 77, 91,
169, 183): (d, Dq, B, C, spin_state, n_bands), spin-forbidden bands included."""


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
    Observed red (e72032a): ``AssertionError: dDq -24.18 %``.
    """
    dq, b, c = 850.0, 907.0, 4850.0
    bands = oracle_bands(8, dq, b, c, spin_allowed_only=False)[:5]
    assert any(not uid.startswith("3_") for _e, uid in bands[:3])
    fit = fit_spectrum(8, [e for e, _u in bands], c, include_spin_forbidden=True)
    assert_recovered(fit, dq, b)


MERGE_CM1 = 50.0
"""Levels closer than this read as one band, as in the audit (``audit_fit_paths.MERGE_CM1``)."""


def merged_bands(d: int, dq: float, b: float, c: float, n_bands: int) -> list[float]:
    """Return the lowest ``n_bands`` oracle bands under the band rule, near-degenerate merged."""
    groups: list[list[float]] = []
    for e, _uid in oracle_bands(d, dq, b, c, spin_allowed_only=False):
        if groups and e - groups[-1][-1] <= MERGE_CM1:
            groups[-1].append(e)
        else:
            groups.append([e])
    return [sum(g) / len(g) for g in groups[:n_bands]]


SEARCH_MISSES = [
    (5, 963.6, 645.0, 3096.0, 3),
    (5, 1785.4, 1376.0, 5504.0, 3),
    (5, 2055.7, 1376.0, 6604.8, 3),
    (5, 1590.1, 645.0, 2580.0, 3),
    (3, 1200.0, 1468.8, 7050.2, 6),
    (5, 836.9, 645.0, 2580.0, 3),
    (5, 1283.3, 989.0, 3956.0, 3),
]
"""Synthetic rows that fail unlabelled at C = truth after the bounds fix (audit at
8135f29): the d5 high-spin spin-forbidden misses, and the d3 row that had been right
only by a closed-form seed built from 2E. (d, Dq, B, C, n_bands)

The d5 bands follow the band rule (plan G, Task 1b: Delta S = 0, +-1 only). Under the
earlier all-multiplicity bands, 836.9 and 1283.3 passed at 8135f29 and were left out;
under the rule they miss there too, so they joined the table (the last two rows)."""


@pytest.mark.parametrize(("d", "dq", "b", "c", "n_bands"), SEARCH_MISSES)
def test_grid_search_recovers_unlabelled(
    d: int, dq: float, b: float, c: float, n_bands: int
) -> None:
    """High-spin, spin-forbidden bands, C = truth, no labels: the grid search finds the truth.

    Observed red at 8135f29 (five local starts around one seed), in table order:
    ``AssertionError: dDq +125.56 %``, ``+64.33 %``, ``-10.50 %``, ``-15.56 %``, ``+4.83 %``
    on the all-multiplicity bands. Re-run at 8135f29 on the band-rule bands (plan G,
    Task 1b, throwaway worktree), in table order: dDq ``+125.85 %``, ``-7.87 %``,
    ``-10.65 %``, ``-19.41 %``, ``+4.83 %``, ``+113.62 %``, ``+71.93 %`` -- every row
    still beyond DQ_TOL_PCT, so each still fails on the defect it defends.
    """
    fit = fit_spectrum(d, merged_bands(d, dq, b, c, n_bands), c, include_spin_forbidden=True)
    assert_recovered(fit, dq, b)


TWO_BAND_TIES = [
    (7, 1267.0, 791.0, 4499.0),
    (2, 1800.0, 700.0, 3801.0),
]
"""Two spin-allowed bands, two parameters: several assignments fit exactly. The truth
is the exact minimum nearest the generic seed (obs[0] / 10, default B) in log
distance; the alternatives sit about three times farther. (d, Dq, B, C)"""


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
    Observed red (886f1b9): ``TypeError: fit_spectrum() got an unexpected keyword
    argument 'band_labels'``.
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
    """Labels travel with their band when the bands are given out of order.

    Observed red (886f1b9): ``TypeError: ... unexpected keyword argument 'band_labels'``.
    """
    dq, b, c = 1000.0, 750.0, 3450.0
    bands = [
        x
        for x in oracle_bands(7, dq, b, c, spin_allowed_only=True)
        if x[1] in {"4_T_2#0", "4_T_1#1"}
    ][::-1]
    fit = fit_spectrum(7, [e for e, _u in bands], c, band_labels=term_labels(bands))
    assert_recovered(fit, dq, b)


def test_assign_bands_is_injective() -> None:
    """Two bands 50 cm^-1 apart around one isolated level map to two levels.

    Observed red (886f1b9): ``ImportError: cannot import name 'assign_bands'``.
    """
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
    Observed red (886f1b9): ``TypeError: ... unexpected keyword argument 'band_labels'``.
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
"""The nine synthetic d5 high-spin spin-forbidden points of the audit: (Dq, B, C)."""


@pytest.mark.parametrize(("dq", "b", "c"), D5_HS_POINTS)
def test_labelled_hs_d5_recovers_c(dq: float, b: float, c: float) -> None:
    """Three labelled bands, C not given: C is fitted and Dq, B, C all recovered.

    Before free C, eight of the nine come back wrong at the default C (audit at
    eef709b, labelled-default): the default C misplaces every level, and no (Dq, B)
    can compensate. The ninth (1283.3 / 989 / 3956) sits next to the default C/B.
    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'c_fitted'``
    on all nine. The eight-of-nine count was measured on all-multiplicity bands.
    Bands follow the band rule since plan G, Task 1b. The red is not re-run: it is the
    absence of ``c_fitted``, which fails the same way for any bands.
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
    A guard, green before C4.
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
    Bands follow the band rule since plan G, Task 1b. The red is not re-run: it is the
    absence of the ``fit_c`` keyword, which fails the same way for any bands.
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
    assert any(
        abs(m[0] / dq - 1) * 100 < DQ_TOL_PCT and abs(m[1] / b - 1) * 100 < B_TOL_PCT for m in exact
    )


def test_minima_are_distinct_and_sorted() -> None:
    """``minima`` holds each converged minimum once: the returned point first, then by objective.

    Observed red (31e352e, on the two-band tie): ``minima[0]`` was (616.4, 1179.2), not
    the returned (1267.0, 791.0) -- the list was sorted by objective alone (Fable O4).
    """
    for d, dq, b, c in ((7, 1200.0, 750.0, 3450.0), *TWO_BAND_TIES):
        bands = [e for e, _u in oracle_bands(d, dq, b, c, spin_allowed_only=True)]
        fit = fit_spectrum(d, bands[:2] if (d, dq, b, c) in TWO_BAND_TIES else bands, c)
        assert fit.minima[0][:2] == (fit.Dq, fit.B)
        rest = [m[3] for m in fit.minima[1:]]
        assert rest == sorted(rest)
        for i, m in enumerate(fit.minima):
            for n in fit.minima[:i]:
                assert (
                    abs(m[0] / n[0] - 1) * 100 > DQ_TOL_PCT
                    or abs(m[1] / n[1] - 1) * 100 > B_TOL_PCT
                    or abs(m[2] / n[2] - 1) * 100 > C_TOL_PCT
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


OTHER_REGIME_CASES = [
    (6, 1292.5, 798.8, 3195.2, "low"),
    (7, 1343.7, 728.2, 2912.8, "low"),
]
"""Audit near-crossover points (0.95 x crossover, high-spin side, spin-allowed bands) that
the other spin regime reproduces too (C5 scan): d6 one band exactly, d7 three to 10 cm^-1."""


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
    """With term labels the other regime cannot carry the bands, so nothing is said.

    A guard, green at 32a91a0 (before the regime check): labels already make the other regime raise.
    """
    d, dq, b, c, _other = OTHER_REGIME_CASES[1]
    bands = oracle_bands(d, dq, b, c, spin_allowed_only=True)
    fit = fit_spectrum(d, [e for e, _u in bands], c, band_labels=term_labels(bands))
    assert not any("regime also fits" in w for w in fit.warnings)


def test_c_valley_is_undetermined() -> None:
    """d6 low-spin, three labelled spin-allowed bands: tied minima disagree on C, so C is
    reported as undetermined, with the candidates and their range, not as fitted.

    Fable review of plan C: truth (4069.1, 1224.8, 6124.0) has exact minima at
    C 5451 and 4948, and the fit returned C 19 % off with ``c_fitted`` True and no
    warning that C is open.
    Observed red (31e352e): ``AttributeError: ... no attribute 'c_provenance'``;
    numerically the fit returned C 4948 (-19.2 %) with no undetermined warning.
    """
    dq, b, c = 4069.1, 1224.8, 6124.0
    bands = oracle_bands(6, dq, b, c, spin_allowed_only=True)[:3]
    fit = fit_spectrum(6, [e for e, _u in bands], spin_state="low", band_labels=term_labels(bands))
    assert fit.c_provenance == "undetermined"
    assert len(fit.c_candidates) >= 2
    lo, hi = fit.c_range
    assert hi / lo - 1 > C_TOL_PCT / 100
    assert lo <= fit.C <= hi
    assert any("undetermined" in w for w in fit.warnings)


def test_unique_free_c_is_fitted() -> None:
    """d5 high-spin, three labelled bands: one tied minimum, C fitted (unchanged)."""
    dq, b, c = D5_HS_POINTS[3]
    energies, labels = merged_labelled_bands(5, dq, b, c, 3)
    fit = fit_spectrum(5, energies, include_spin_forbidden=True, band_labels=labels)
    assert (fit.dq_provenance, fit.b_provenance, fit.c_provenance) == ("fitted",) * 3
    assert not fit.c_is_default


@pytest.mark.parametrize(("c_arg", "expected"), [(4850.0, "given"), (None, "default")])
def test_held_c_provenance(c_arg: float | None, expected: str) -> None:
    """A held C is 'given' when the caller passed it, 'default' when it came from defaults."""
    bands = [e for e, _u in oracle_bands(8, 850.0, 907.0, 4850.0, spin_allowed_only=True)]
    fit = fit_spectrum(8, bands, c_arg)
    assert fit.c_provenance == expected
    assert fit.c_is_default == (expected == "default")


def test_pick_minimum_prefers_a_converged_run() -> None:
    """Over-determined fits too: a non-converged run must not win on a slightly lower objective.

    Observed red (31e352e): ``_pick_minimum(..., determined=True)`` returned the
    ``success=False`` run, which then makes the fit raise "did not converge" (Fable O5).
    """
    stalled = SimpleNamespace(fun=0.001, success=False, x=np.array([1000.0, 700.0]))
    converged = SimpleNamespace(fun=0.002, success=True, x=np.array([1000.0, 700.0]))
    for determined in (True, False):
        picked = _pick_minimum([stalled, converged], (1000.0, 700.0), determined=determined)
        assert picked is converged


def test_fit_c_true_without_labels_warns() -> None:
    """fit_c=True on unlabelled bands frees C anyway, and says the result is one of many.

    Coverage for a branch no test reached; green at 31e352e, never red.
    """
    dq, b, c = D5_HS_POINTS[3]
    fit = fit_spectrum(5, merged_bands(5, dq, b, c, 3), include_spin_forbidden=True, fit_c=True)
    assert fit.c_fitted
    assert any("fit_c=True" in w for w in fit.warnings)


def test_c_free_but_irrelevant_is_held_at_default() -> None:
    """d8 spin-allowed bands do not move with C: a requested C fit falls back to the default.

    Observed red (31e352e): ``AttributeError: ... no attribute 'c_provenance'``;
    the fallback itself already held C (its warning was green).
    """
    bands = oracle_bands(8, 850.0, 907.0, 4850.0, spin_allowed_only=True)
    fit = fit_spectrum(8, [e for e, _u in bands], band_labels=term_labels(bands))
    assert not fit.c_fitted
    assert (fit.c_provenance, fit.c_is_default) == ("default", True)
    assert DEFAULTS[8]["default_C"] == fit.C
    assert any("do not move with C" in w for w in fit.warnings)


@pytest.mark.parametrize("c_over_b", [3.5, 5.5])
@pytest.mark.parametrize(("dq", "b"), [(963.6, 645.0), (1477.4, 989.0)])
def test_free_c_recovers_across_c_over_b(dq: float, b: float, c_over_b: float) -> None:
    """Free C away from C/B 4.0 and 4.8, the only ratios measured before (Fable O3, plan C).

    High-spin d5, three labelled bands: the configuration where C is fitted at all
    (d3 and d8 spin-allowed bands do not depend on C). 3.5 and 5.5 sit inside the
    (3, 6) window on either side. Green on arrival (33dcf7d): coverage, not a fix.
    """
    c = c_over_b * b
    energies, labels = merged_labelled_bands(5, dq, b, c, 3)
    fit = fit_spectrum(5, energies, include_spin_forbidden=True, band_labels=labels)
    assert fit.c_fitted
    assert_recovered(fit, dq, b, c)


# F1: holding the default C on unlabelled bands. Truths are oracle inputs (rows of the
# 29420b6 audit, F1-mechanism.md); bands come from the oracle, never from the package.
D6_LS_TIE = (2176.8, 798.8, 3195.2)
"""Audit row 971 (d6 low-spin, spin-allowed, default C): WRONG-SILENT at 29420b6."""
D2_HS_INCONSISTENT = (900.0, 989.0, 3956.0)
"""F1-evidence-3b row 1 (d2 high-spin, six merged bands with spin-forbidden)."""


def test_held_default_c_tie_is_undetermined() -> None:
    """Branch (i): a fitted C ties the held fit at a distinct (Dq, B), so Dq and B are open.

    Before the fix the held fit (2283, 819, RMSE 11) came back 'fitted' with no warning,
    4.9 % off in Dq; the oracle truth fits the same bands exactly at its own C.
    Observed red: ``assert ('fitted', 'fitted') == ('undetermined', 'undetermined')``.
    """
    bands = [e for e, _u in oracle_bands(6, *D6_LS_TIE, spin_allowed_only=True)[:3]]
    fit = fit_spectrum(6, bands, spin_state="low")
    assert (fit.dq_provenance, fit.b_provenance) == ("undetermined", "undetermined")
    assert fit.c_provenance == "default"
    assert fit.free_c_minima
    hits = [w for w in fit.warnings if "Dq and B undetermined: C is not determined" in w]
    assert len(hits) == 1, fit.warnings


def test_held_default_c_inconsistent_is_undetermined() -> None:
    """Branch (ii): a fitted C fits the bands far better than the default C can.

    The (Dq, B) assertion is a regression pin that the returned point did not move
    (the fix reports, it does not refit), not a truth claim. Truth fits at RMSE 0.
    Observed red: the pin held, then
    ``assert ('fitted', 'fitted', 'default') == ('undetermined', 'undetermined', 'default')``.
    """
    fit = fit_spectrum(2, merged_bands(2, *D2_HS_INCONSISTENT, 6), include_spin_forbidden=True)
    assert abs(fit.Dq - 898.2) <= 0.5
    assert abs(fit.B - 1008.4) <= 0.5
    assert (fit.dq_provenance, fit.b_provenance, fit.c_provenance) == (
        "undetermined",
        "undetermined",
        "default",
    )
    hits = [w for w in fit.warnings if "is inconsistent with these bands" in w]
    assert len(hits) == 1, fit.warnings
    assert "fits 159 cm^-1 better" in hits[0]
    assert min(m[3] for m in fit.free_c_minima) < 1.0


def test_exact_answer_at_the_default_c_stays_fitted() -> None:
    """Negative control: true C equals the default, the held fit is exact, so nothing fires.

    Look-back on the F1 fix (mechanism-first, 9474397): the tie branch marked 52 of
    130 such exact answers undetermined, because a free-C local minimum within
    100 cm^-1 of a held RMSE near 0 counted as a tie. d7 low-spin, truth
    (2263.2, 728.2, default C 4499): held RMSE 0.005, free-C alternative at 12.6.
    Observed red: ``assert 'undetermined' == 'fitted'``.
    """
    c0 = float(DEFAULTS[7]["default_C"])
    bands = [e for e, _u in oracle_bands(7, 2263.2, 728.2, c0, spin_allowed_only=True)[:3]]
    fit = fit_spectrum(7, bands, spin_state="low")
    assert fit.dq_provenance == "fitted"
    assert fit.free_c_minima == ()


FREE_C_AMBIGUOUS = [
    pytest.param(5, [7716.37, 9876.12, 11610.0], (1654.0, 200.0), id="683 d5 502.1/387/1548"),
    pytest.param(5, [8777.78, 10991.02, 13158.0], (1541.25, 200.0), id="689 d5 578.1/387/1857.6"),
    pytest.param(
        6, [5463.38, 9586.73, 12925.0, 16814.74], (1641.89, 200.0), id="941 d6 1292.5/798.8/3195.2"
    ),
]
"""Audit rows (29420b6 CSV index) where the free-C point the warning names fits at
RMSE <= 2 while 70-83 % off in Dq. Bands: the oracle levels at truth exactly as
``audit_fit_paths.synthetic_bands`` merged them (spin-forbidden, high-spin), copied
from the audit. The (Dq, B) pair is the held fit from the same CSV: a regression pin
that the note does not move the returned point, not a truth claim.

Re-pinned in plan G, Task 1f. The old held fits at 3824ce5 -- 1706.1/370.7 (RMSE 406.7),
1716.9/477.0 (537.5), 1725.0/574.6 (285.1) -- put the lowest band on 2_T_2 (d5) or 1_A_1
(d6), a Delta S = 2 level the fit no longer matches. Without it the default-C held fit
runs to the B floor (200): 1654.0 (RMSE 5574.3), 1541.25 (4684.1), 1641.89 (3463.5), all
'undetermined'. The "not unique" assertion is unchanged and still holds."""


@pytest.mark.parametrize(("d", "bands", "held"), FREE_C_AMBIGUOUS)
def test_ambiguous_free_c_point_is_said_to_be_ambiguous(
    d: int, bands: list[float], held: tuple[float, float]
) -> None:
    """The warning says when the free-C point it names is itself one of several.

    Look-back on the F1 fix (Q3): each row has 4-5 further free-C minima within
    100 cm^-1 of the named one at a distinct (Dq, B); the warning named one as if
    it were the answer, and minima flagged it lowest_rmse with no caveat.
    Observed red (all three): ``assert []`` -- no warning carries "not unique".
    """
    fit = fit_spectrum(d, bands, include_spin_forbidden=True)
    assert abs(fit.Dq - held[0]) <= 0.1
    assert abs(fit.B - held[1]) <= 0.1
    notes = [w for w in fit.warnings if w.startswith("Dq and B undetermined:")]
    assert len(notes) == 1, fit.warnings
    assert [w for w in notes if "the free-C fit is not unique either" in w]


def _off_trigger_cases() -> list[tuple[str, int, list[float], dict[str, object]]]:
    d6 = oracle_bands(6, *D6_LS_TIE, spin_allowed_only=True)[:3]
    energies = [e for e, _u in d6]
    d3 = [e for e, _u in oracle_bands(3, 1200.0, 688.5, 3200.0, spin_allowed_only=True)[:3]]
    return [
        ("C given", 6, energies, {"C": 3195.2, "spin_state": "low"}),
        (
            "labelled, C held",
            6,
            energies,
            {"spin_state": "low", "band_labels": term_labels(d6), "fit_c": False},
        ),
        ("two bands", 6, energies[:2], {"spin_state": "low"}),
        ("C does not move the levels", 3, d3, {}),
    ]


@pytest.mark.parametrize(
    ("d", "bands", "kwargs"),
    [case[1:] for case in _off_trigger_cases()],
    ids=[case[0] for case in _off_trigger_cases()],
)
def test_free_c_check_does_not_run_off_trigger(
    d: int, bands: list[float], kwargs: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Focus 1: no free-C refit and no new warning outside the trigger.

    The spy pins that the refit is not even run, which is what the C-moves and
    label conditions save; the later guards would hide a missing one otherwise.
    Valid red, one mutation per trigger condition deleted from ``fit_spectrum`` /
    ``_held_c_check``: [C given] and [two bands] failed on ``free_c_minima``;
    [labelled, C held] and [C does not move the levels] failed on the spy
    (``assert [True] == []``).
    """
    from tanabesugano.mcp import _compute

    real = _compute._fit_one_regime
    refits: list[bool] = []

    def spy(*args: object, **kw: object) -> object:
        if kw.get("fit_c") is True:
            refits.append(True)
        return real(*args, **kw)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(_compute, "_fit_one_regime", spy)
    fit = fit_spectrum(d, bands, **kwargs)  # ty: ignore[invalid-argument-type]
    assert refits == []
    assert fit.free_c_minima == ()
    assert not any(w.startswith("Dq and B undetermined: C is") for w in fit.warnings)
    assert not any(w.startswith("Dq and B undetermined: the default C") for w in fit.warnings)


def test_free_c_refit_failure_keeps_held_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review Focus 2: a free-C refit that raises leaves the held fit as it was.

    Valid red (mutation: ``except ValueError`` narrowed away):
    ``ValueError: fit never escaped`` propagated out of ``fit_spectrum``.
    """
    from tanabesugano.mcp import _compute

    real = _compute._fit_one_regime

    def failing(*args: object, **kwargs: object) -> object:
        if kwargs.get("fit_c"):
            msg = "fit never escaped"
            raise ValueError(msg)
        return real(*args, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(_compute, "_fit_one_regime", failing)
    bands = [e for e, _u in oracle_bands(6, *D6_LS_TIE, spin_allowed_only=True)[:3]]
    fit = fit_spectrum(6, bands, spin_state="low")
    assert fit.dq_provenance == "fitted"
    assert fit.free_c_minima == ()


# --- F3: both d3/d8 Dq estimators reported ------------------------------------------------

SPIN_ALLOWED_ASSUMPTION = (
    "all bands are treated as spin-allowed; a spin-forbidden line (e.g. 2E/1E) in the input "
    "would be misassigned; label the bands or pass include_spin_forbidden=True if one is present"
)
"""Copied verbatim from the maintainer's ruling (feedback on tasks 4-7), not from the code."""
LOWEST_BAND_NU1 = f"nu1 is the lowest band: {SPIN_ALLOWED_ASSUMPTION}"


@pytest.mark.parametrize(
    ("nu1", "floor"),
    [
        pytest.param(17400.0, 50.0, id="hundreds-printed"),
        pytest.param(17235.0, 1.0, id="units-printed-floored"),
        pytest.param(17234.56789, 1.0, id="oracle-float-floored"),
        pytest.param(8500.0, 50.0, id="d8-hundreds"),
        pytest.param(20000.0, BAND_RESOLUTION_CM1, id="trailing-zeros-capped"),
        pytest.param(10000.0, BAND_RESOLUTION_CM1, id="ten-thousand-capped"),
    ],
)
def test_nu1_floor(nu1: float, floor: float) -> None:
    """Half the last printed digit of nu1, never below ``TIE_RMSE_CM1``.

    The expected values are read off the digits as printed, not from the code: 17400 is
    printed to the hundred (half = 50), 17235 to the unit (half = 0.5, floored to the
    1 cm^-1 tie), and an oracle float carries no printing precision at all. Trailing
    zeros cannot say more than ``BAND_RESOLUTION_CM1`` (how well a band maximum is
    located): 20000 read as "known to the ten-thousand" would floor at 5000.

    Observed red: ``ImportError: cannot import name 'nu1_floor'``; the two capped
    cases (final review): ``assert 5000.0 == 100.0``.
    """
    assert nu1_floor(nu1) == floor


def test_dq_nu1_reported_for_d3_and_d8() -> None:
    """d8 [Ni(H2O)6]2+: nu1/10 is the lowest band over ten, reported beside the LS Dq.

    The expected 850.0 is the input band 8500 / 10 (T1a: nu1 = 10Dq for d8), not a fit value.
    The disagreement sentence appears exactly when ``|10 Dq - nu1|`` exceeds the threshold.

    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'dq_nu1'``.
    """
    fit = fit_spectrum(8, [8500.0, 13800.0, 25300.0])
    assert fit.dq_nu1 == 850.0
    differs = abs(10.0 * fit.Dq - 8500.0) > max(fit.rmse_cm1, nu1_floor(8500.0))
    if differs:
        assert fit.dq_nu1_reason == (
            f"{LOWEST_BAND_NU1}; Dq estimators differ: nu1/10 = 850, "
            f"least squares = {fit.Dq:.0f} cm^-1"
        )
    else:
        assert fit.dq_nu1_reason == LOWEST_BAND_NU1
    assert not any("estimators" in w for w in fit.warnings), "report-only: no warning"


def test_dq_nu1_labelled_takes_the_t2_band() -> None:
    """Labelled d3: nu1 is the band labelled 4_T_2, wherever it sits in the input order.

    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'dq_nu1'``.
    """
    bands = oracle_bands(3, 1750.0, 700.0, 2800.0, spin_allowed_only=True)
    t2 = next(e for e, uid in bands if uid.startswith("4_T_2"))
    reordered = list(reversed(bands))
    fit = fit_spectrum(3, [e for e, _u in reordered], band_labels=term_labels(reordered))
    assert fit.dq_nu1 == t2 / 10.0


def test_dq_nu1_labelled_ignores_a_lower_spin_forbidden_line() -> None:
    """Labelled d3 with 2E below 4T2: nu1 is the 4T2 band, not the lowest band.

    The oracle (Dq 1750, B 700, C 2800) places 2E below 4T2; a selection that took
    ``min(observed)`` would report 2E/10. Only the label can tell them apart.

    Observed red (labelled branch mutated to ``min(observed)``):
    ``AssertionError: assert 1354.9857537857831 == (17500.000000000004 / 10.0)``.
    ``test_dq_nu1_labelled_takes_the_t2_band`` stays green under that mutation (its 4T2
    is also its lowest band), which is why this test exists.
    """
    bands = oracle_bands(3, 1750.0, 700.0, 2800.0, spin_allowed_only=False)
    picked = [next(b for b in bands if b[1].startswith(key)) for key in ("2_E", "4_T_2", "4_T_1")]
    assert picked[0][0] < picked[1][0], "precondition: 2E lies below 4T2"
    fit = fit_spectrum(
        3,
        [e for e, _u in picked],
        include_spin_forbidden=True,
        band_labels=term_labels(picked),
    )
    assert fit.dq_nu1 == picked[1][0] / 10.0
    assert fit.dq_nu1_reason is None or "lowest band" not in fit.dq_nu1_reason


def test_unlabelled_spin_allowed_fit_states_its_assumption() -> None:
    """Unlabelled, spin-allowed only: the result says every band was taken as spin-allowed.

    KZnClSO4·3H2O:Cr3+ printed bands, 2E (11975) included: band positions alone cannot
    tell it from a spin-allowed band, so the assumption is stated, not warned about.

    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'assumptions'``.
    """
    fit = fit_spectrum(3, [17235.0, 24385.0, 11975.0])
    assert fit.assumptions == (SPIN_ALLOWED_ASSUMPTION,)
    assert SPIN_ALLOWED_ASSUMPTION not in fit.warnings


@pytest.mark.parametrize("labelled", [True, False], ids=["labelled", "spin-forbidden"])
def test_labelled_or_spin_forbidden_fit_states_no_assumption(labelled: bool) -> None:
    """The assumption is the unlabelled spin-allowed path's alone.

    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'assumptions'``.
    """
    bands = [17400.0, 24600.0, 37800.0]
    if labelled:
        fit = fit_spectrum(3, bands, band_labels=["4_T_2", "4_T_1", "4_T_1"])
    else:
        fit = fit_spectrum(3, bands, include_spin_forbidden=True)
    assert fit.assumptions == ()


@pytest.mark.parametrize(
    "labels",
    [[None, None, None], ["1_T_1", None, None]],
    ids=["all-null", "partial"],
)
def test_null_labels_count_as_unlabelled(
    labels: list[str | None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A band whose label is None is unlabelled: the held-C check runs, the assumption is stated.

    ``_fit_one_regime`` frees C only when every band is labelled, so a None entry leaves
    C held exactly as no labels do. Final review (Opus) and challenger (Fable) both found
    the gates tested ``band_labels is None`` instead.
    Observed red, both cases: ``AssertionError: assert () == ('all bands a... is present',)``.
    """
    from tanabesugano.mcp import _compute

    real = _compute._fit_one_regime
    refits: list[bool] = []

    def spy(*args: object, **kw: object) -> object:
        if kw.get("fit_c") is True:
            refits.append(True)
        return real(*args, **kw)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(_compute, "_fit_one_regime", spy)
    bands = [e for e, _u in oracle_bands(6, *D6_LS_TIE, spin_allowed_only=True)[:3]]
    fit = fit_spectrum(6, bands, spin_state="low", band_labels=labels)
    assert fit.assumptions == (SPIN_ALLOWED_ASSUMPTION,)
    assert refits == [True]


def test_dq_nu1_accepts_a_uid_label() -> None:
    """A band labelled by level uid (``4_T_2#0``, the form band_assignments returns) is nu1.

    Observed red: ``assert None == 1740.0`` (reason "no band is labelled 4_T_2").
    """
    fit = fit_spectrum(3, [17400.0, 24600.0, 37800.0], band_labels=["4_T_2#0", "4_T_1", "4_T_1"])
    assert fit.dq_nu1 == 17400.0 / 10.0


def test_all_null_labels_take_the_lowest_band_as_nu1() -> None:
    """All-None labels are the unlabelled path: nu1 is the lowest band, under the assumption.

    Observed red: ``assert None == 1740.0`` (reason "no band is labelled 4_T_2").
    """
    fit = fit_spectrum(3, [17400.0, 24600.0, 37800.0], band_labels=[None, None, None])
    assert fit.dq_nu1 == 17400.0 / 10.0


@pytest.mark.parametrize(
    ("d_count", "kwargs", "reason"),
    [
        pytest.param(
            3,
            {"include_spin_forbidden": True},
            "unlabelled spin-forbidden bands: the lowest band may be 2E/1E",
            id="d3-unlabelled-spin-forbidden",
        ),
        pytest.param(
            5,
            {"include_spin_forbidden": True},
            "nu1 = 10Dq holds only for d3 and d8",
            id="d5",
        ),
    ],
)
def test_dq_nu1_none_with_reason(d_count: int, kwargs: dict[str, bool], reason: str) -> None:
    """No nu1 where it is not a band: unlabelled spin-forbidden input, or a d-count without it.

    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'dq_nu1'``.
    """
    bands = oracle_bands(d_count, 1500.0, 700.0, 3000.0, spin_allowed_only=False)[:4]
    fit = fit_spectrum(d_count, [e for e, _u in bands], **kwargs)
    assert fit.dq_nu1 is None
    assert fit.dq_nu1_reason == reason


@pytest.mark.parametrize(
    ("d_count", "dq", "b", "c", "nu1_offset"),
    [
        pytest.param(3, 1200.0, 688.5, 688.5 * 4.0, 0.0, id="d3-exact"),
        pytest.param(8, 850.0, 907.0, 4850.0, 0.5, id="d8-nu1-half-unit-off"),
    ],
)
def test_oracle_bands_do_not_disagree(
    d_count: int, dq: float, b: float, c: float, nu1_offset: float
) -> None:
    """Oracle bands: no disagreement sentence fires on float round-off (Review Focus 5).

    nu1 is a float with many digits, so :func:`nu1_floor` must fall back to
    ``TIE_RMSE_CM1`` rather than to half a 1e-12 digit. On exact d3 bands the two
    estimators agree to the bit (|10 Dq - nu1| = 0.0), which no threshold can tell
    apart; the d8 case moves nu1 by half a unit, giving |10 Dq - nu1| = 0.30 above the
    RMSE 0.23 and below the 1 cm^-1 floor, so only the floor keeps it silent.

    Observed red: ``AttributeError: 'SpectrumFit' object has no attribute 'dq_nu1'``.
    Behavioural red (threshold mutated to ``max(rmse, 0.0)``): ``[d8-nu1-half-unit-off]``
    fails: the reason gains ``; Dq estimators differ: nu1/10 = 850, least squares =
    850 cm^-1``; ``[d3-exact]`` stays green (gap 0.0).
    """
    bands = [e for e, _u in oracle_bands(d_count, dq, b, c, spin_allowed_only=True)]
    bands[0] += nu1_offset
    fit = fit_spectrum(d_count, bands, C=c)
    assert fit.dq_nu1 == bands[0] / 10.0
    assert fit.dq_nu1_reason == LOWEST_BAND_NU1


# --- F2: geometry="Td" ---------------------------------------------------------------------

TD_REFUSAL = (
    "geometry='Td' is high-spin only: Dq_t is about 4/9 of Dq_o, below every spin crossover"
)
"""Copied from the plan (F-release Task 8), not from the code."""


@pytest.mark.parametrize("n", [6, 7, 8])
def test_td_fit_recovers_from_displaced_seed(n: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """T2: spin-allowed oracle Td bands give back Dq_t (and B where it is determined).

    Truth B is 0.8 x each n's default B, so the default B is not the answer; truth Dq_t
    is 0.5 x the default B. ``_initial_seed`` is displaced to (0.7 x, 1.4 x) its own
    answer as the audit's seed-displaced runs are, because for n = 7 (fitted as d3) the
    closed-form seed is exact on oracle bands and for n = 6 the one band is 10 Dq_t. n = 6
    has a single spin-allowed band, so B is reported undetermined rather than asserted.
    d5 is excluded: high-spin d5 has no spin-allowed band.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'geometry'``.
    Strengthened after the Fable challenge (the earlier version seeded at the truth for
    n = 6, 7 and never asserted B); green on arrival, the code was right.
    """
    from tanabesugano.mcp import _compute

    real_seed = _compute._initial_seed

    def displaced(*args: object, **kw: object) -> tuple[float, float]:
        dq, b = real_seed(*args, **kw)  # ty: ignore[invalid-argument-type]
        return 0.7 * dq, 1.4 * b

    monkeypatch.setattr(_compute, "_initial_seed", displaced)
    b = 0.8 * float(DEFAULTS[n]["default_B"])
    c = float(DEFAULTS[n]["default_C"])
    dq_t = 0.5 * float(DEFAULTS[n]["default_B"])
    bands = [e for e, _u in oracle_bands(n, -dq_t, b, c, spin_allowed_only=True)]
    fit = fit_spectrum(n, bands, geometry="Td")
    assert fit.dq_convention == "Td"
    assert fit.Dq == pytest.approx(dq_t, rel=0.005)
    if len(bands) >= 2:
        assert pytest.approx(b, rel=0.005) == fit.B
    else:
        assert fit.b_provenance == "undetermined"


def test_td_d5_spin_forbidden_with_given_c() -> None:
    """T2: high-spin Td d5 from its quartet bands, C given, spin-forbidden fitting on.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'geometry'``.
    """
    b, c = 700.0, 2800.0
    dq_t = 400.0
    quartets = [
        (e, uid)
        for e, uid in oracle_bands(5, -dq_t, b, c, spin_allowed_only=False)
        if uid[0] == "4"
    ][:4]
    fit = fit_spectrum(
        5,
        [e for e, _u in quartets],
        C=c,
        geometry="Td",
        include_spin_forbidden=True,
        band_labels=term_labels(quartets),
    )
    assert fit.dq_convention == "Td"
    assert fit.Dq == pytest.approx(dq_t, rel=0.005)


def test_td_uses_the_callers_defaults() -> None:
    """Td d8 is fitted on the d2 manifold but with Ni(II)'s default C, not V(III)'s.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'geometry'``.
    Behavioural red (defaults read from the partner, ``DEFAULTS[10 - n]``):
    ``AssertionError: assert 4850.0 == 3801.0``.
    """
    b = float(DEFAULTS[8]["default_B"])
    bands = [
        e
        for e, _u in oracle_bands(
            8, -450.0, b, float(DEFAULTS[8]["default_C"]), spin_allowed_only=True
        )
    ]
    fit = fit_spectrum(8, bands, geometry="Td", include_spin_forbidden=True)
    assert DEFAULTS[8]["default_C"] == fit.C
    assert fit.c_is_default


def test_td_low_spin_is_refused() -> None:
    """Review Focus 3: Td with spin_state='low' is refused by name, not silently fitted.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'geometry'``.
    """
    with pytest.raises(ValueError, match="high-spin only") as err:
        fit_spectrum(6, [4500.0], geometry="Td", spin_state="low")
    assert str(err.value) == TD_REFUSAL


def test_td_nu1_follows_the_fitted_manifold() -> None:
    """Td d7 has nu1 = 10 Dq_t (4A2 -> 4T2); Td d8 has none. Keyed on the manifold, not on n.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'geometry'``.
    """
    d7 = [e for e, _u in oracle_bands(7, -400.0, 750.0, 3400.0, spin_allowed_only=True)]
    fit = fit_spectrum(7, d7, geometry="Td")
    assert fit.dq_nu1 == min(d7) / 10.0
    assert fit.dq_nu1 == pytest.approx(400.0, abs=1e-6)
    fit8 = fit_spectrum(8, [4400.0, 15500.0], geometry="Td")
    assert fit8.dq_nu1 is None
    assert fit8.dq_nu1_reason == "nu1 = 10Dq_t holds only for d2 and d7 in Td"


def test_zno_td_fit_matches_oracle() -> None:
    """ZnO:Ni2+ (Td d8): the fit reaches the oracle's no-SO point (515.13, 790.09).

    The reference is ``test_zno_td_no_so_value`` (fsolve on the oracle alone); the
    published 405/795 assume spin-orbit stabilisation and are not the target.

    Observed red: ``TypeError: fit_spectrum() got an unexpected keyword argument 'geometry'``.
    """
    fit = fit_spectrum(8, [4400.0, 15500.0], geometry="Td")
    assert fit.Dq == pytest.approx(515.13, abs=0.5)
    assert pytest.approx(790.09, abs=0.5) == fit.B
    assert fit.dq_convention == "Td"


# ── Observed [Mn(H2O)6]2+ (plan G, Task 1) ────────────────────────────────────

MN_OBSERVED_BANDS = (18870.0, 23120.0, 24960.0)
"""Foster & Gill (1968) *observed* bands of [Mn(H2O)6]2+ (SOURCE-CHECK.md), not the
calculated column 19070/22710/24500 that the JCE 2023 tables print."""
MN_QUARTET_LABELS: list[str | list[str]] = ["4_T_1", "4_T_2", ["4_E", "4_A_1"]]
"""The standard assignment: 4T1(G), 4T2(G), 4E/4A1(G)."""
MN_REF_C_FIXED = (827.348, 882.564, 3243.0, 93.678)
"""(Dq, B, C, RMSE) with C held at 3243 under the standard assignment.

Provenance: ``least_squares`` on ``_determinant_oracle`` levels alone (which imports
nothing from the package), printed to three decimals; re-derived in
``test_observed_mn_reference_is_an_oracle_minimum``, never by fit code. An independent
determinant Hamiltonian outside the repository agrees to 0.1 cm^-1."""
MN_REF_C_FREE = (805.981, 956.800, 3078.400)
"""(Dq, B, C) with C free, RMSE 0 (three bands, three parameters). Same provenance."""


ROUNDING_3DP = 5e-4
"""Half-width of a value printed to three decimals."""


def test_observed_mn_reference_is_an_oracle_minimum() -> None:
    """The independent reference, re-derived with the package's oracle only (item 1a).

    ``least_squares`` on ``_determinant_oracle`` levels under the standard assignment.
    Measured: C fixed -> (827.348, 882.564), RMSE 93.678, the same from three starts;
    C free -> (805.981, 956.800, 3078.400), RMSE 0. The constants are those values
    printed to three decimals, so the bound is the rounding half-width, 5e-4 (plan G,
    Task 1c; it replaces a 0.1 bound held against values rounded to one decimal). A
    provenance check of the reference values, not a test of the fix.
    """
    from scipy.optimize import least_squares

    bands = np.asarray(MN_OBSERVED_BANDS)

    def residuals(dq: float, b: float, c: float) -> np.ndarray:
        levels = relative_term_levels(5, dq, b, c)
        lowest_4e_4a1 = min(levels["4_E"][0], levels["4_A_1"][0])
        return np.asarray((levels["4_T_1"][0], levels["4_T_2"][0], lowest_4e_4a1)) - bands

    dq, b, c, rmse = MN_REF_C_FIXED
    for start in ((dq, b), (700.0, 700.0), (950.0, 1000.0)):
        fixed = least_squares(lambda p: residuals(p[0], p[1], c), start, xtol=1e-12, ftol=1e-12)
        assert np.all(np.abs(fixed.x - (dq, b)) <= ROUNDING_3DP), (start, fixed.x)
        assert abs(float(np.sqrt(np.mean(fixed.fun**2))) - rmse) <= ROUNDING_3DP
    free = least_squares(lambda p: residuals(*p), MN_REF_C_FREE, xtol=1e-12, ftol=1e-12)
    assert np.all(np.abs(free.x - MN_REF_C_FREE) <= ROUNDING_3DP), free.x
    assert float(np.sqrt(np.mean(free.fun**2))) <= 1e-3
    assert float(np.sqrt(np.mean(residuals(1113.3, 1178.0, 3243.0) ** 2))) > 1000.0


def test_labelled_observed_mn_c_fixed() -> None:
    """Labelled quartets, C = 3243: the reference minimum (item 1d).

    Tolerance: the fit's own stopping criterion (NM_XATOL_CM1 on Dq and B, NM_FATOL_CM1
    on the RMSE), fixed before measuring (plan G, Task 1c). Green on arrival: 2.1.0 at
    3824ce5 already returns 827.35 / 882.56 / RMSE 93.68.
    """
    dq, b, c, rmse = MN_REF_C_FIXED
    fit = fit_spectrum(
        5, list(MN_OBSERVED_BANDS), C=c, band_labels=MN_QUARTET_LABELS, include_spin_forbidden=True
    )
    assert abs(fit.Dq - dq) <= NM_XATOL_CM1
    assert abs(fit.B - b) <= NM_XATOL_CM1
    assert abs(fit.rmse_cm1 - rmse) <= NM_FATOL_CM1
    assert (fit.dq_provenance, fit.b_provenance, fit.c_provenance) == ("fitted", "fitted", "given")


def test_labelled_observed_mn_c_free() -> None:
    """Labelled quartets, C free: the exact reference point (item 1d).

    Tolerance: NM_XATOL_CM1 on Dq, B and C, fixed before measuring (plan G, Task 1c).
    Green on arrival: 2.1.0 at 3824ce5 already returns 805.98 / 956.80 / 3078.40.
    """
    fit = fit_spectrum(
        5, list(MN_OBSERVED_BANDS), band_labels=MN_QUARTET_LABELS, include_spin_forbidden=True
    )
    for got, want in zip((fit.Dq, fit.B, fit.C), MN_REF_C_FREE, strict=True):
        assert abs(got - want) <= NM_XATOL_CM1
    assert fit.c_provenance == "fitted"
    assert any("degrees of freedom = 0" in w for w in fit.warnings)


def test_unlabelled_observed_mn_assigns_only_quartets() -> None:
    """Unlabelled, C = 3243: no band lands on a sextet -> doublet (Delta S = 2) level.

    The reference is MN_REF_C_FIXED: C is given and the assignment is the same quartets.
    Observed red at 3824ce5 (fit Dq 1113.3, B 1178.0):
    ``AssertionError: assert ['2_T_2#0'] == []``.
    """
    dq, b, c, _rmse = MN_REF_C_FIXED
    fit = fit_spectrum(5, list(MN_OBSERVED_BANDS), C=c, include_spin_forbidden=True)
    assert [uid for _o, _p, uid in fit.assignment if not uid.startswith("4_")] == []
    assert abs(fit.Dq - dq) <= NM_XATOL_CM1
    assert abs(fit.B - b) <= NM_XATOL_CM1


SPIN_CHANGE_POINTS = [
    pytest.param(d, spin, id=f"d{d}-{spin}")
    for d in range(2, 9)
    for spin in (("high", "low") if d in (4, 5, 6, 7) else ("high",))
]


def _regime_point(d: int, spin: str) -> tuple[float, float, float]:
    """A (Dq, B, C) well inside ``spin``'s regime at the default B and C."""
    b, c = DEFAULTS[d]["default_B"], DEFAULTS[d]["default_C"]
    return (500.0 if spin == "high" else 3500.0, b, c)


@pytest.mark.parametrize(("d", "spin"), SPIN_CHANGE_POINTS)
def test_spin_forbidden_levels_change_spin_by_one(d: int, spin: str) -> None:
    """The fit's spin-forbidden match set holds only Delta S = 0, +-1 levels.

    d2, d3, d7, d8 lose nothing: every multiplicity there is within +-2 of the ground's.
    Observed red at 3824ce5, five cases: d4-high ``['1_T_2#0', ...]`` (23 singlets),
    d5-high ``['2_T_2#0', ...]`` (32 doublets), d5-low ``['6_A_1#0']``, d6-high
    ``['1_A_1#0', ...]`` (23 singlets), d6-low ``['5_T_2#0', '5_E#0']``; the rest green.
    """
    terms = compute_point(d, *_regime_point(d, spin))
    ground, levels = excited_levels(terms, spin_allowed_only=False)
    ground_mult = term_multiplicity(ground)
    assert [uid for _e, uid in levels if abs(int(uid.split("_")[0]) - ground_mult) > 2] == []
    every = [lv for lv in LevelSet.from_states(terms).levels if lv.energy_cm1 > 1.0]
    if d in (2, 3, 7, 8):
        assert len(levels) == len(every)


def test_label_naming_a_delta_s_two_term_is_refused() -> None:
    """A label on a sextet -> doublet term is refused by name, not dropped.

    Observed red at 3824ce5: ``Failed: DID NOT RAISE ValueError`` (the fit ran).
    """
    with pytest.raises(ValueError, match=r"2_T_2.*changes spin by more than one"):
        fit_spectrum(
            5,
            list(MN_OBSERVED_BANDS),
            C=3243.0,
            band_labels=["4_T_1", "2_T_2", ["4_E", "4_A_1"]],
            include_spin_forbidden=True,
        )


MERGED_D5_BANDS = [14628.689639271004, 18328.010222150508, 21930.0]
"""Three oracle bands of high-spin d5 at (963.6, 645, 3096), the second merging 2_T_2
with 4_T_2 within MERGE_CM1. Read off the oracle generator before it adopted the band
rule (plan G, Task 1b), so a Delta S = 2 member sits in a label tuple."""


def test_merged_label_drops_delta_s_two_members() -> None:
    """A tuple with one Delta S = 2 member fits exactly as the tuple without it.

    User decision 1a: drop Delta S = +-2 members of a merged label; refuse only when no
    allowed member remains. The reference fit is the same call with the member removed,
    so the expected value is not computed by the path under test.

    Observed red (working tree on 3824ce5): ``ValueError: band label '2_T_2' changes spin
    by more than one from the 6_A_1 ground term``.
    """
    merged = fit_spectrum(
        5,
        MERGED_D5_BANDS,
        C=3096.0,
        band_labels=[("4_T_1",), ("2_T_2", "4_T_2"), ("4_A_1", "4_E")],
        include_spin_forbidden=True,
    )
    plain = fit_spectrum(
        5,
        MERGED_D5_BANDS,
        C=3096.0,
        band_labels=[("4_T_1",), ("4_T_2",), ("4_A_1", "4_E")],
        include_spin_forbidden=True,
    )
    assert (merged.Dq, merged.B) == (plain.Dq, plain.B)
    assert merged.assignment == plain.assignment


def test_label_naming_only_delta_s_two_terms_is_refused() -> None:
    """A tuple of Delta S = 2 terms only is refused, naming every term and the rule.

    Observed red (working tree on 3824ce5): ``AssertionError`` on '2_A_2' -- the message
    named only the first term, '2_T_2'.
    """
    with pytest.raises(ValueError, match=r"Delta S = 0, \+-1") as excinfo:
        fit_spectrum(
            5,
            list(MN_OBSERVED_BANDS),
            C=3243.0,
            band_labels=["4_T_1", ("2_T_2", "2_A_2"), ["4_E", "4_A_1"]],
            include_spin_forbidden=True,
        )
    assert "2_T_2" in str(excinfo.value)
    assert "2_A_2" in str(excinfo.value)


def test_d5_refusal_hint_names_the_spin_rule() -> None:
    """The high-spin d5 refusal says which levels include_spin_forbidden=True matches.

    Observed red (working tree on 3824ce5): ``AssertionError: Regex pattern did not match``
    -- the hint said only that the bands are all spin-forbidden.
    """
    with pytest.raises(ValueError, match=r"only Delta S = 0, \+-1 levels are matched"):
        fit_spectrum(5, list(MN_OBSERVED_BANDS))


DEFAULT_C_REFUSALS = [
    pytest.param(4, [4953.2, 5287.0, 9058.2, 9545.6], 1736.8, id="d4-high 528.7/434.2/1736.8"),
    pytest.param(6, [4080.0, 6674.5, 8363.7, 10072.8], 1916.8, id="d6-high 408/479.2/1916.8"),
]
"""Audit rows (synthetic, sf, default C) that refuse once Delta S = 2 levels are gone.
Bands: ``audit_fit_paths.synthetic_bands`` at the truth (oracle levels), to 0.1 cm^-1.
The third value is the truth C, at which both fit exactly (Task 1e probe)."""


@pytest.mark.parametrize(("d", "bands", "_truth_c"), DEFAULT_C_REFUSALS)
def test_default_c_refusal_names_the_held_c(d: int, bands: list[float], _truth_c: float) -> None:
    """A refusal at the held default C says so, and says to pass C or label the bands.

    Plan G, Task 1e: with C = truth both rows fit exactly, so the cause is the default C,
    and a message pointing at the peak list or the d-count sends the user the wrong way.
    Observed red (working tree on 3824ce5): ``AssertionError: Regex pattern did not
    match`` -- the message named the peak list, the d-count and spin_state only.
    """
    c0 = float(DEFAULTS[d]["default_C"])
    with pytest.raises(ValueError, match=rf"C was held at the d{d} default {c0:.0f}") as excinfo:
        fit_spectrum(d, bands, include_spin_forbidden=True)
    assert "pass C" in str(excinfo.value)


def test_transition_candidates_still_lists_every_multiplicity() -> None:
    """The term list for display keeps doublets: the Delta S rule belongs to fitting.

    Green on arrival: a guard that the fix does not reach the display tables.
    """
    _ground, candidates = transition_candidates(
        compute_point(5, 800.0, 860.0, 3850.0), spin_allowed_only=False
    )
    assert any("→2_" in assignment for _e, assignment, _s in candidates)
