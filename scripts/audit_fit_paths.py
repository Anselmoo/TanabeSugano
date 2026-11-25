"""Fit-path audit of the three (Dq, B, C) fit paths for tanabesugano 2.1.0.

Question: does each fit path return the correct ligand-field parameters for
d2-d8, and when it does not, does it at least warn pertinently?  Paths graded:

* ``fit_spectrum`` (``tanabesugano.mcp._compute``), called directly with
  C = truth, with C = None (the per-configuration default) and, for d3/d8
  spin-allowed points, with a displaced closed-form seed (``seed-displaced``:
  ``_initial_seed`` patched to return 0.7 x Dq_cf, 1.4 x B_cf); and again at
  both C values with ``band_labels`` set to each band's term keys
  (``labelled-truth``, ``labelled-default``);
* ``ts_reverse_fit_app`` and ``ts_ratio_fit_app``, called through the in-memory
  FastMCP server the way ``test_reverse_fit_contract.py`` does it
  (``create_server()`` + ``run_loop_free``).  The reverse app's numbers come
  from ``structured_content``; the ratio app returns no structured content, so
  its Dq and B are parsed from the chart title ``Custom TS dN: Dq=..., B=...``.

Ground truth.  Synthetic band energies come ONLY from
``tanabesugano.test._determinant_oracle.relative_term_levels``, an independent
determinant-basis oracle that imports nothing from the package.  Building the
input with the package's own ``compute_point`` would grade the fitter with
itself.  The ground key is the block that holds the 0.0 level.  At start-up the
oracle's key spelling is checked against ``TermKey``; an unknown key is fatal.
Package functions are used only to evaluate a point (assignment, ground term,
objective value) -- that is grading, not input.

Band rule.  All excited levels of the ground multiplicity are first merged
(levels within 50 cm^-1 chain into one band at their mean energy, every label
kept), and the lowest k <= 3 merged bands are the spin-allowed set.  The
spin-forbidden variant adds the lowest 3 merged bands of multiplicity
(2S+1) +/- 2 (|dS| = 1; low-spin d5-d7 have only the manifold above).
Merging BEFORE truncating keeps degenerate partners together
(d5 4A1/4E at 10B + 5C).  A band additionally carries the label of any other
excited level within 50 cm^-1 of one of its members, since such a level is
observationally indistinguishable.  A label is ``<term>#<index>`` with a
0-based index into the term's ascending levels, the identity of ``Level.uid``.
Self-test: at every synthetic truth point, with the truth C, each band's
nearest predicted level must carry one of its labels, or the run aborts.

Truth points are fixed (no RNG): B in {0.45, 0.75, 1.15, 1.6} x default B,
skipped when outside fit_spectrum's default b_bounds (200, 1500); C/B in
{4.0, 4.8}, +0.2 when within 0.05 of the default C/B; Dq at 0.5 x (high-spin)
or 1.6 x (low-spin) the oracle spin crossover for d4-d7, and two fixed values
for d2/d3/d8.  One extra near-crossover point per d4-d7 cell sits at 0.95 x
(HS) or 1.05 x (LS) the crossover.

The JCE 2023 rows grade the same paths against published (Dq, Dq/B, C/B),
using the ``_reported`` columns only.  d5 and d6 rows are R1-tainted (the
published d5/d6 diagrams carry a propagated error, Hormann & Shaw 1987) and
are reported for comparison, never counted as pass or fail.

Outputs: ``audit/2.1.0/fit_audit.csv`` and ``AUDIT-2.1.0.md``, both byte
deterministic on one platform (floats at 1 decimal, no timings, no paths).

Usage::

    python scripts/audit_fit_paths.py           # write both outputs
    python scripts/audit_fit_paths.py --check   # exit 1 if either drifted

Exit codes: 0 success / no drift; 1 drift or a missing output under
``--check``; ``SystemExit`` with a message if the oracle's spelling, the
truth self-test, an app's grid constants or a JCE fixture is not understood.
"""

from __future__ import annotations

import argparse
import csv
import inspect
import io
import json
import math
import multiprocessing
import os
import re
import statistics
import sys

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

import numpy as np

from fastmcp.tools.function_tool import FunctionTool

import tanabesugano.mcp._compute as compute_module

from tanabesugano.levels import LevelSet
from tanabesugano.mcp._compute import _initial_seed
from tanabesugano.mcp._compute import assign_bands
from tanabesugano.mcp._compute import closed_form_dq_b
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import default_dq_bounds
from tanabesugano.mcp._compute import excited_levels
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import ground_term
from tanabesugano.mcp._compute import peak_rmse
from tanabesugano.mcp._compute import transition_candidates
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp.server import create_server
from tanabesugano.terms import TermKey
from tanabesugano.test._determinant_oracle import relative_term_levels
from tanabesugano.test._loop import run_loop_free


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    from tanabesugano.mcp._compute import SpectrumFit
    from tanabesugano.mcp._compute import SpinState


REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "audit" / "2.1.0" / "fit_audit.csv"
MD_PATH = REPO_ROOT / "AUDIT-2.1.0.md"
JCE_DIR = REPO_ROOT / "audit" / "jce2023"

DQ_TOL_PCT = 2.0
B_TOL_PCT = 5.0
THRESHOLD_REASON = (
    "the oracle is exact (eigenvalues of the full determinant Hamiltonian), so a "
    "correct continuous optimiser recovers Dq and B to well under 0.1 %; the slack "
    "exists only for the two grid paths, whose cells are several percent wide"
)
MERGE_CM1 = 50.0
MAX_ALLOWED = 3
MAX_FORBIDDEN = 3
B_FACTORS = (0.45, 0.75, 1.15, 1.6)
NEAR_B_FACTOR = 0.75
FIT_B_BOUNDS = (200.0, 1500.0)
CB_RATIOS = (4.0, 4.8)
CB_COLLISION = 0.05
CB_SHIFT = 0.2
HS_FACTOR = 0.5
LS_FACTOR = 1.6
NEAR_FRACTION = 0.05
FIXED_DQ: dict[int, tuple[float, float]] = {
    2: (900.0, 1800.0),
    3: (1200.0, 2000.0),
    8: (700.0, 1200.0),
}
CROSSOVER_CONFIGS = (4, 5, 6, 7)
CLOSED_FORM_CONFIGS = (3, 8)
ORACLE_WEAK_DQ = 50.0
ORACLE_STRONG_DQ = 6000.0
BISECT_HI_DQ = 12000.0
BISECT_TOL_CM1 = 0.5
RMSE_EPS_CM1 = 1.0
SEED_SPAN = (0.8, 1.25)
SEED_DQ_FACTOR = 0.7
SEED_B_FACTOR = 1.4
MIN_ENERGY_CM1 = 1.0
APP_GRID: dict[str, dict[str, float]] = {
    "reverse_app": {"grid_steps": 25, "b_min": 400.0, "b_max": 1600.0},
    "ratio_app": {"grid_steps": 30, "b_min": 400.0, "b_max": 1600.0},
}
APP_DQ_MAX_FACTOR = 0.3
APP_ROUNDING_CM1 = 0.051
CLOSED_FORM_BANDS = 3
RATIO_MIN_BANDS = 2
RATIO_MAX_BANDS = 3
SPEARMAN_MIN_N = 3
EXACT_BANDS = 2  # two bands fix (Dq, B) exactly, so any estimator reproduces them

SEVERITY = (
    "N/A",
    "OK",
    "RAISED-EXPECTED",
    "OK-B-UNIDENTIFIED",
    "RAISED",
    "WRONG-WARNED",
    "WRONG-SILENT",
)
FAILURES = frozenset({"RAISED", "WRONG-WARNED", "WRONG-SILENT"})
MATRIX_COLUMNS = (
    ("fit_spectrum", "truth", "fit C=truth"),
    ("fit_spectrum", "default", "fit C=default"),
    ("fit_spectrum", "seed-displaced", "fit seed-displaced"),
    ("fit_spectrum", "labelled-truth", "fit labelled C=truth"),
    ("fit_spectrum", "labelled-default", "fit labelled C=default"),
    ("reverse_app", "app-default", "reverse app"),
    ("ratio_app", "app-default", "ratio app"),
)
CSV_COLUMNS = (
    "source",
    "system",
    "d",
    "spin",
    "sf",
    "path",
    "c_mode",
    "truth_Dq",
    "truth_B",
    "truth_C",
    "fit_Dq",
    "fit_B",
    "fit_C",
    "dDq_pct",
    "dB_pct",
    "dC_pct",
    "rmse",
    "r2",
    "rmse_at_reported",
    "rmse_at_fit",
    "ground_reached",
    "n_bands",
    "warnings",
    "warning_kinds",
    "pertinent_warning",
    "raised",
    "assignment_ok",
    "infeasible_at_c",
    "verdict",
    "approx",
    "R1_tainted",
    "geometry",
    "failure_classes",
)
WARNING_KINDS = (
    ("large residual", "residual"),
    ("B pinned", "b-pinned"),
    ("only one spin-allowed transition", "single-transition"),
    ("free parameters", "too-few-bands"),
    ("was not constrained", "c-note"),
)
NON_PERTINENT_KINDS = frozenset({"c-note"})

FIX_CLASSES = {
    "a": "generic seed obs[0]/10 (_initial_seed)",
    "bounds-exclude-truth": "default dq_bounds (default_dq_bounds) exclude the truth",
    "b": "the start set misses the truth basin (_search_starts)",
    "c": "a band's nearest level at the returned point does not carry its label",
    "d": "regime penalty / crossover proximity (fit_spectrum objective)",
    "e": "C-misspecification bias: C never fitted",
    "f": "no ambiguity check",
    "app-hs": "app hard-codes the high-spin reference and default C",
    "app-sf": "app has no include_spin_forbidden and fits forbidden bands as allowed",
    "app-lattice": (
        "ratio app: the Dq grid has no node at nu1/10 for d3/d8, so the returned Dq is the "
        "node nearest nu1/10, not nu1/10 itself"
    ),
    "app-grid": (
        "app grid resolution: Dq grid 0..3 x obs[0]/10, B grid 400..1600 "
        "(25 steps reverse, 30 ratio)"
    ),
    "single-band": "one observed band for two free parameters: B is not identifiable",
    "estimator-disagreement": (
        "published values are not the minimum of this objective (reverse app; fit_spectrum "
        "is covered by (f))"
    ),
    "unclassified": "matches no rule",
}
CLASS_RULES = {
    "a": (
        "fit_spectrum only, not seed-displaced: generic seed (not d3/d8, <3 bands, or "
        "spin-forbidden bands included) and seed Dq / truth Dq outside the local-start "
        "span [0.8, 1.25]"
    ),
    "bounds-exclude-truth": (
        "fit_spectrum only, not seed-displaced: the truth Dq lies outside "
        "default_dq_bounds(bands, seed), the seed being _initial_seed's"
    ),
    "b": (
        "fit_spectrum only: objective (C used) at the returned point exceeds the objective "
        "(same C) at the truth (Dq, B) by > 1 cm^-1, or 'did not converge'"
    ),
    "c": "assignment_ok is False",
    "d": (
        "ground_reached is False, the row is a near-crossover point, or the raise names the "
        "crossover / penalty region"
    ),
    "e": (
        "fit_spectrum only: C = default (labelled or not) and the same case at C = truth, "
        "with the same labelling, is OK"
    ),
    "f": (
        "fit_spectrum only: WRONG-SILENT and the objective at the returned point (C used) "
        "is within 1 cm^-1 of, or below, the objective at the full truth (Dq, B, C)"
    ),
    "app-hs": "app row with spin=low",
    "app-sf": "reverse-app row with spin-forbidden bands in its input",
    "app-lattice": (
        "ratio-app row, d3 or d8 (nu1 = 10Dq), no Dq grid node within rounding of nu1/10, "
        "and the returned Dq is the node nearest nu1/10"
    ),
    "app-grid": (
        "app row whose returned (Dq, B) is the grid node nearest the truth on both axes, "
        "i.e. the error is pure grid resolution"
    ),
    "single-band": "n_bands == 1",
    "estimator-disagreement": (
        "JCE, sf=False, reverse app, every band assigned, more than two bands, reported C "
        "given: RMSE at the returned point < RMSE at the reported (Dq, B, C)"
    ),
    "unclassified": "a failing row no rule above matched",
}

SYSTEM_ION: dict[str, tuple[str, int]] = {
    "ZnO:Ni2+": ("Ni2+", 8),
    "Al2O3:V3+": ("V3+", 2),
    "[V(H2O)6]3+": ("V3+", 2),
    "[V(H2O)6]2+": ("V2+", 3),
    "[Cr(H2O)6]3+": ("Cr3+", 3),
    "KZnClSO4·3H2O:Cr3+": ("Cr3+", 3),
    "[Cr(oxalate)3]3-": ("Cr3+", 3),
    "Al2O3:Cr3+": ("Cr3+", 3),
    "[Cr(NH3)6]3+": ("Cr3+", 3),
    "K3Cr(CN)6": ("Cr3+", 3),
    "[Mn(CN)6]3-": ("Mn3+", 4),
    "MnI2": ("Mn2+", 5),
    "MnBr2": ("Mn2+", 5),
    "MnCl2": ("Mn2+", 5),
    "MnF2": ("Mn2+", 5),
    "[Mn(H2O)6]2+": ("Mn2+", 5),
    "LiGa5O8:Fe3+": ("Fe3+", 5),
    "[Co(oxalate)3]3-": ("Co3+", 6),
    "[Co(H2O)6]3+": ("Co3+", 6),
    "[Co(NH3)6]3+": ("Co3+", 6),
    "[Co(NO2)6]3-": ("Co3+", 6),
    "AgCl:Co2+": ("Co2+", 7),
    "CoCl2": ("Co2+", 7),
    "KCoF3": ("Co2+", 7),
    "[Co(H2O)6]2+": ("Co2+", 7),
    "CoSiF6·6H2O": ("Co2+", 7),
    "Co(bipy)3Br2·6H2O": ("Co2+", 7),
    "AgCl:Ni2+": ("Ni2+", 8),
    "[NiF6]4-": ("Ni2+", 8),
    "MgO:Ni2+": ("Ni2+", 8),
    "[Ni(H2O)6]2+": ("Ni2+", 8),
    "LiGa5O8:Ni2+": ("Ni2+", 8),
    "[Ni(NH3)6]2+": ("Ni2+", 8),
}
LOW_SPIN_SYSTEMS = frozenset(
    {"[Mn(CN)6]3-", "[Co(oxalate)3]3-", "[Co(H2O)6]3+", "[Co(NH3)6]3+", "[Co(NO2)6]3-"},
)
JCE_IRREPS = {"A1": "A_1", "A2": "A_2", "E": "E", "T1": "T_1", "T2": "T_2"}
R1_CONFIGS = (5, 6)
JCE_CITATION = (
    "García Rojas & Pérez Torres, J. Chem. Educ. 2023, 100, 251-258, "
    "doi:10.1021/acs.jchemed.2c00885"
)

KNOWN_DEFECT_BANDS = (19070.0, 22710.0, 24500.0)
KNOWN_DEFECT_DQ = 760.0
KNOWN_DEFECT_DQ_OVER_B = 0.918
KNOWN_DEFECT_C_OVER_B = 3.917
COUNTERFACTUAL_SEED = (650.0, 750.0)
COUNTERFACTUAL_DQ_BOUNDS = (130.0, 3250.0)
MULTISTART_DQ_SEEDS = 25
MULTISTART_B_SEEDS = 5

FINDINGS_STATIC = {
    "M": (
        "**M. The d5 mechanism.** High-spin d5 with spin-forbidden bands fails for two "
        "separable reasons (Section 1). With C right, the minimum exists: on the Mn bands a "
        "start grid over Dq and B chosen without the reference reaches it, and since the "
        "fit-path fix so does fit_spectrum's own Dq x B start grid (one system, and "
        "R1-tainted as a comparator). With C at the default, the published point is not a "
        "minimum of the objective at all, so no seed can fix it; that needs C fitted as "
        "well, and whether three bands determine C is not measured here. Noisy bands are "
        "not measured either."
    ),
    "S1": (
        "**S1. WRONG-WARNED should not be read as 'flagged'.** The C-not-constrained note "
        "fires on most OK runs too, so it carries no information about a wrong answer; only "
        "residual, B-pinned, single-transition and too-few-bands warnings count as pertinent."
    ),
    "S2": (
        "**S2. Estimator disagreement does not explain the JCE misses.** The tag applies "
        "only where the reverse app's answer beats the published (Dq, B, C) on the app's own "
        "objective with every band assigned, more than two bands and a reported C. Even so "
        "narrowed it holds on OK rows about as often as on failing ones (Section 6), so it "
        "marks a disagreement between estimators, not the cause of a miss. A looser rule "
        "fires on most OK rows, and for fit_spectrum it would only repeat class (f)."
    ),
    "S3": (
        "**S3. C-misspecification is a continuous bias.** Holding C at the default shifts Dq "
        "in a direction set by the sign of the C error; passing low-spin default-C runs are "
        "still off by 1-2 % in the predicted direction."
    ),
    "S4": (
        "**S4. Infeasible-at-C runs come mostly from the low-B truth points, not from the "
        "near-crossover ones.** At the default C their truth Dq lies in the other spin "
        "regime, so no fit pinned to the requested regime can reach it. The tag explains "
        "the failure; it does not excuse it, so the run stays a failure."
    ),
    "design": (
        "**Design note for the fix.** Scope by ablation -- {grid multistart vs current seed} "
        "x {labelled vs unlabelled matching} x {C truth / default / free} -- rather than by "
        "row tags alone. This is a recommendation, not done here."
    ),
}


@dataclass(frozen=True)
class Band:
    """One observed band: mean energy of the merged levels and their truth labels."""

    energy: float
    labels: tuple[str, ...]
    spin_allowed: bool


@dataclass(frozen=True)
class Case:
    """One band set to be fitted, with its truth and the flags it is reported under."""

    source: str
    system: str
    d: int
    spin: SpinState
    sf: bool
    truth_dq: float
    truth_b: float | None
    truth_c: float | None
    ground_key: str
    bands: tuple[Band, ...]
    expect_raise: bool = False
    near_crossover: bool = False
    approx: bool = False
    r1: bool = False
    geometry: str = "Oh"


@dataclass
class Run:
    """What one path returned for one case."""

    path: str
    c_mode: str
    c_used: float
    fit_dq: float | None = None
    fit_b: float | None = None
    fit_c: float | None = None
    rmse: float | None = None
    warnings: list[str] = field(default_factory=list)
    raised: str = ""


@dataclass
class Row:
    """A graded run: the CSV record plus the numbers the classifier needs."""

    case: Case
    run: Run
    values: dict[str, str]
    verdict: str
    d_dq: float | None = None
    d_b: float | None = None
    d_c: float | None = None
    obj_fit: float | None = None
    obj_truth_c_used: float | None = None
    obj_truth: float | None = None
    kinds: tuple[str, ...] = ()
    classes: tuple[str, ...] = ()


def check_oracle_spelling() -> None:
    """Fail unless every oracle block key is a ``TermKey`` value, for d2..d8.

    Raises:
        SystemExit: if any key is unknown; no silent mapping is attempted.

    """
    known = {k.value for k in TermKey}
    for n in range(2, 9):
        unknown = set(relative_term_levels(n, 1000.0, 800.0, 3500.0)) - known
        if unknown:
            raise SystemExit(f"oracle d{n} emits keys unknown to TermKey: {sorted(unknown)}")


def multiplicity(key: str) -> int:
    """Return 2S+1 from a ``<mult>_<irrep>`` key or ``<mult>_<irrep>#<i>`` label."""
    return int(key.split("_", 1)[0])


def oracle_levels(n: int, dq: float, b: float, c: float) -> list[tuple[float, str]]:
    """Return every oracle level as ``(energy, "<term>#<index>")``, ascending."""
    levels = relative_term_levels(n, dq, b, c)
    out = [(float(e), f"{key}#{i}") for key, values in levels.items() for i, e in enumerate(values)]
    return sorted(out)


def oracle_ground(n: int, dq: float, b: float, c: float) -> str:
    """Return the oracle block key holding the 0.0 level."""
    return oracle_levels(n, dq, b, c)[0][1].split("#")[0]


def oracle_crossover(n: int, b: float, c: float) -> float:
    """Bisect the oracle for the Dq at which the ground multiplicity flips.

    Compares multiplicities, not keys, because every Oh component of the
    free-ion ground term is degenerate at Dq = 0.

    Raises:
        SystemExit: if the bracket does not contain a spin crossover.

    """
    lo, hi = ORACLE_WEAK_DQ, BISECT_HI_DQ
    hs = multiplicity(oracle_ground(n, lo, b, c))
    ls = multiplicity(oracle_ground(n, hi, b, c))
    if hs == ls:
        raise SystemExit(f"d{n} B={b} C={c}: no crossover in [{lo}, {hi}]")
    while hi - lo > BISECT_TOL_CM1:
        mid = 0.5 * (lo + hi)
        if multiplicity(oracle_ground(n, mid, b, c)) == ls:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def cluster_levels(levels: list[tuple[float, str]]) -> list[list[tuple[float, str]]]:
    """Chain levels closer than ``MERGE_CM1`` into clusters, ascending."""
    clusters: list[list[tuple[float, str]]] = []
    for level in sorted(levels):
        if clusters and level[0] - clusters[-1][-1][0] <= MERGE_CM1:
            clusters[-1].append(level)
        else:
            clusters.append([level])
    return clusters


def band_from(
    members: list[tuple[float, str]], ground_mult: int, partners: list[tuple[float, str]]
) -> Band:
    """Build a band at the members' mean energy, labelled with members and near partners."""
    labels = {lab for _e, lab in members}
    labels.update(lab for e, lab in partners if any(abs(e - m) <= MERGE_CM1 for m, _l in members))
    return Band(
        energy=sum(e for e, _l in members) / len(members),
        labels=tuple(sorted(labels)),
        spin_allowed=any(multiplicity(lab) == ground_mult for _e, lab in members),
    )


def synthetic_bands(
    n: int, dq: float, b: float, c: float, *, sf: bool
) -> tuple[str, tuple[Band, ...], tuple[Band, ...]]:
    """Apply the band rule (merge first, then truncate) at one truth point.

    Returns:
        ``(ground_key, bands, forbidden_only_bands)``; the last is what a
        high-spin d5 spin-allowed-only run is handed.

    """
    levels = oracle_levels(n, dq, b, c)
    ground_label, excited = levels[0][1], levels[1:]
    gm = multiplicity(ground_label)
    allowed = cluster_levels([lv for lv in excited if multiplicity(lv[1]) == gm])[:MAX_ALLOWED]
    # Spin-forbidden = |dS| = 1: HS grounds see the manifold below, LS (d5-d7) mainly above.
    forbidden = cluster_levels([lv for lv in excited if multiplicity(lv[1]) in (gm - 2, gm + 2)])
    forbidden = forbidden[:MAX_FORBIDDEN]

    def to_bands(clusters: list[list[tuple[float, str]]]) -> tuple[Band, ...]:
        """Re-merge the chosen clusters (cross-spin) and label each band."""
        members = [lv for cl in clusters for lv in cl]
        return tuple(band_from(cl, gm, excited) for cl in cluster_levels(members))

    chosen = allowed + (forbidden if sf else [])
    return ground_label.split("#")[0], to_bands(chosen), to_bands(forbidden)


def displaced_cb(d: int, ratio: float) -> float:
    """Return ``ratio``, shifted by ``CB_SHIFT`` if it sits on the default C/B."""
    default = DEFAULTS[d]["default_C"] / DEFAULTS[d]["default_B"]
    return ratio + CB_SHIFT if abs(ratio - default) < CB_COLLISION else ratio


def truth_b_values(d: int) -> list[float]:
    """Return the truth B values of one configuration inside fit_spectrum's b_bounds."""
    values = [round(f * DEFAULTS[d]["default_B"], 1) for f in B_FACTORS]
    return [b for b in values if FIT_B_BOUNDS[0] <= b <= FIT_B_BOUNDS[1]]


def skipped_b_values() -> list[str]:
    """Describe every (d, B factor) dropped for falling outside fit_spectrum's b_bounds."""
    out: list[str] = []
    for d in range(2, 9):
        for f in B_FACTORS:
            b = round(f * DEFAULTS[d]["default_B"], 1)
            if not FIT_B_BOUNDS[0] <= b <= FIT_B_BOUNDS[1]:
                out.append(f"d{d} {f:g} x {DEFAULTS[d]['default_B']:g} = {fmt(b)}")
    return out


def truth_points(d: int, spin: SpinState) -> list[tuple[float, float, float, bool]]:
    """Return the fixed ``(Dq, B, C, near_crossover)`` grid for one cell."""
    points: list[tuple[float, float, float, bool]] = []
    for b in truth_b_values(d):
        for ratio in CB_RATIOS:
            c = round(displaced_cb(d, ratio) * b, 1)
            if d in CROSSOVER_CONFIGS:
                factor = HS_FACTOR if spin == "high" else LS_FACTOR
                points.append((round(factor * oracle_crossover(d, b, c), 1), b, c, False))
            else:
                points.extend((dq, b, c, False) for dq in FIXED_DQ[d])
    if d in CROSSOVER_CONFIGS:
        b = round(NEAR_B_FACTOR * DEFAULTS[d]["default_B"], 1)
        c = round(displaced_cb(d, CB_RATIOS[0]) * b, 1)
        near = 1.0 - NEAR_FRACTION if spin == "high" else 1.0 + NEAR_FRACTION
        points.append((round(near * oracle_crossover(d, b, c), 1), b, c, True))
    return points


def expected_ground_mult(d: int, spin: SpinState) -> int:
    """Return the oracle's ground multiplicity of a regime at the default (B, C)."""
    dq = ORACLE_WEAK_DQ if spin == "high" else ORACLE_STRONG_DQ
    return multiplicity(oracle_ground(d, dq, DEFAULTS[d]["default_B"], DEFAULTS[d]["default_C"]))


def has_forbidden_manifold(d: int, spin: SpinState, gm: int) -> bool:
    """Return whether d^n has any level of multiplicity ``gm +/- 2`` (|dS| = 1)."""
    dq = ORACLE_WEAK_DQ if spin == "high" else ORACLE_STRONG_DQ
    levels = oracle_levels(d, dq, DEFAULTS[d]["default_B"], DEFAULTS[d]["default_C"])
    return any(multiplicity(lab) in (gm - 2, gm + 2) for _e, lab in levels)


def synthetic_cases() -> tuple[list[Case], list[str]]:
    """Build every synthetic case, and the reasons for cells left N/A.

    Raises:
        SystemExit: if a truth point does not sit in the regime of its cell.

    """
    cases: list[Case] = []
    na_cells: list[str] = []
    spins: tuple[SpinState, ...] = ("high", "low")
    for d in range(2, 9):
        for spin in spins:
            if spin == "low" and d not in CROSSOVER_CONFIGS:
                continue
            gm = expected_ground_mult(d, spin)
            for sf in (False, True):
                if sf and not has_forbidden_manifold(d, spin, gm):
                    na_cells.append(
                        f"d{d} {spin}-spin sf=True: ground multiplicity {gm} has no "
                        "(2S+1) +/- 2 manifold, so the band set equals sf=False",
                    )
                    continue
                for dq, b, c, near in truth_points(d, spin):
                    ground, bands, forbidden = synthetic_bands(d, dq, b, c, sf=sf)
                    if multiplicity(ground) != gm:
                        raise SystemExit(f"d{d} {spin} Dq={dq}: oracle ground {ground} off-regime")
                    expect = not bands and not sf
                    cases.append(
                        Case(
                            source="synthetic",
                            system=f"d{d}-{spin}",
                            d=d,
                            spin=spin,
                            sf=sf,
                            truth_dq=dq,
                            truth_b=b,
                            truth_c=c,
                            ground_key=ground,
                            bands=forbidden if expect else bands,
                            expect_raise=expect,
                            near_crossover=near,
                        ),
                    )
    return cases, na_cells


def load_app_tools() -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Fetch the two app tool functions from an in-memory server, once.

    Also checks the apps' grid defaults against ``APP_GRID``, which the
    app-grid classifier mirrors.

    Raises:
        SystemExit: if either tool is not a plain function tool, or a grid
            default differs from ``APP_GRID``.

    """

    async def go() -> tuple[object, object]:
        """Create the server and resolve both tools inside a loop-free worker."""
        server = create_server()
        return (
            await server.get_tool("ts_reverse_fit_app"),
            await server.get_tool("ts_ratio_fit_app"),
        )

    reverse, ratio = run_loop_free(go)
    if not isinstance(reverse, FunctionTool) or not isinstance(ratio, FunctionTool):
        raise SystemExit("ts_reverse_fit_app / ts_ratio_fit_app are no longer FunctionTools")
    for path, tool in (("reverse_app", reverse), ("ratio_app", ratio)):
        params = inspect.signature(tool.fn).parameters
        actual = {name: params[name].default for name in APP_GRID[path]}
        if actual != APP_GRID[path]:
            raise SystemExit(f"{path} grid defaults {actual} != mirrored {APP_GRID[path]}")
    return reverse.fn, ratio.fn


def run_fit_spectrum(case: Case, c_mode: str) -> Run:
    """Call ``fit_spectrum`` for one case with C = truth or C = None, labelled or not."""
    c_arg = case.truth_c if c_mode in {"truth", "seed-displaced", "labelled-truth"} else None
    run = Run(
        path="fit_spectrum",
        c_mode=c_mode,
        c_used=c_arg if c_arg is not None else DEFAULTS[case.d]["default_C"],
    )
    try:
        fit = fit_spectrum(
            case.d,
            [band.energy for band in case.bands],
            c_arg,
            spin_state=case.spin,
            include_spin_forbidden=case.sf,
            band_labels=run_labels(case, c_mode),
        )
    except ValueError as exc:
        run.raised = str(exc)
        return run
    run.fit_dq, run.fit_b, run.fit_c = fit.Dq, fit.B, fit.C
    run.rmse = fit.rmse_cm1
    run.warnings = list(fit.warnings)
    return run


LABELLED_MODES = frozenset({"labelled-truth", "labelled-default"})


def run_labels(case: Case, c_mode: str) -> list[tuple[str, ...]] | None:
    """Return the term-key labels a labelled run passes, one tuple per band, else None.

    Term keys only (``4_T_1``), never the oracle's ``#index``: a user can name the
    term a band belongs to but not which of several same-term levels it is (B7 O1).
    """
    if c_mode not in LABELLED_MODES:
        return None
    return [tuple(sorted({lab.split("#", 1)[0] for lab in band.labels})) for band in case.bands]


def run_seed_displaced(case: Case) -> Run:
    """Call ``fit_spectrum`` with C = truth and the closed-form seed displaced."""
    dq_cf, b_cf = closed_form_dq_b(case.d, [band.energy for band in case.bands])
    seed = (SEED_DQ_FACTOR * dq_cf, SEED_B_FACTOR * b_cf)
    with mock.patch.object(compute_module, "_initial_seed", return_value=seed):
        return run_fit_spectrum(case, "seed-displaced")


def run_reverse(case: Case, tool: Callable[..., Any]) -> Run:
    """Call ``ts_reverse_fit_app`` and read its structured content."""
    run = Run(path="reverse_app", c_mode="app-default", c_used=DEFAULTS[case.d]["default_C"])
    result = tool(d_count=case.d, observed_peaks=[band.energy for band in case.bands])
    data = result.structured_content
    if not data or "error" in data:
        run.raised = str((data or {}).get("error", "no structured content"))
        return run
    run.fit_dq, run.fit_b, run.fit_c = float(data["Dq"]), float(data["B"]), float(data["C"])
    run.rmse = float(data["rmse_cm1"])
    return run


def ratio_inputs(case: Case) -> list[float]:
    """Return the band energies the ratio app is given: the lowest three."""
    return sorted(band.energy for band in case.bands)[:RATIO_MAX_BANDS]


def run_ratio(case: Case, tool: Callable[..., Any]) -> Run:
    """Call ``ts_ratio_fit_app`` with the lowest three bands and parse the title."""
    run = Run(path="ratio_app", c_mode="app-default", c_used=DEFAULTS[case.d]["default_C"])
    energies = ratio_inputs(case)
    kwargs: dict[str, float] = {"v1": energies[0], "v2": energies[1]}
    if len(energies) == RATIO_MAX_BANDS:
        kwargs["v3"] = energies[2]
    result = tool(d_count=case.d, **kwargs)
    payload = json.loads(result.content[0].text)
    if "error" in payload:
        run.raised = str(payload["error"])
        return run
    match = re.search(r"Dq=([\d.]+), B=([\d.]+)", payload.get("title", ""))
    if match is None:
        run.raised = f"unparseable title: {payload.get('title')!r}"
        return run
    run.fit_dq, run.fit_b = float(match.group(1)), float(match.group(2))
    return run


def fmt(value: float | None) -> str:
    """Format a float at 1 decimal, ``n/a`` for None, without a negative zero."""
    if value is None or not math.isfinite(value):
        return "n/a"
    text = f"{value:.1f}"
    return "0.0" if text == "-0.0" else text


def pct(fit: float | None, truth: float | None) -> float | None:
    """Return the signed percent deviation, or None when either side is missing."""
    if fit is None or truth is None or truth == 0:
        return None
    return (fit - truth) / truth * 100.0


def label_matches(uid: str, labels: tuple[str, ...]) -> bool:
    """Return whether ``uid`` equals a truth label; ``term#*`` matches any index."""
    term = uid.split("#", maxsplit=1)[0]
    return any(uid == lab or (lab.endswith("#*") and lab.split("#")[0] == term) for lab in labels)


def matches_every_level(case: Case, path: str) -> bool:
    """Return whether this path matches every multiplicity (fit_spectrum with sf)."""
    return path == "fit_spectrum" and case.sf


def predicted_levels(
    case: Case, path: str, dq: float, b: float, c: float
) -> tuple[str, list[tuple[float, str]]]:
    """Return the package ground key and the levels this path matches against.

    Raises:
        SystemExit: if a solver term list is not ascending (the uid index
            would not mean the oracle's index).

    """
    states = compute_point(case.d, dq, b, c)
    for key, values in states.items():
        if list(values) != sorted(values):
            raise SystemExit(f"solver term {key} is not ascending; uid index is not an ordinal")
    ground_key, _ = ground_term(states)
    gm = multiplicity(ground_key)
    every = matches_every_level(case, path)
    levels = [
        (lv.energy_cm1, lv.uid)
        for lv in LevelSet.from_states(states).levels
        if lv.energy_cm1 > MIN_ENERGY_CM1 and (every or lv.multiplicity == gm)
    ]
    return ground_key, levels


def r_squared(energies: list[float], residuals: list[float]) -> float | None:
    """Return 1 - SS_res / SS_tot of nearest-line residuals, None when SS_tot is 0."""
    if len(energies) < 2:  # noqa: PLR2004  one band has no variance to explain
        return None
    mean = sum(energies) / len(energies)
    ss_tot = sum((e - mean) ** 2 for e in energies)
    if ss_tot == 0:
        return None
    return 1.0 - sum(r * r for r in residuals) / ss_tot


def nearest_residuals(bands: tuple[Band, ...], levels: list[tuple[float, str]]) -> list[float]:
    """Return each band's energy minus its nearest predicted level's energy."""
    return [
        band.energy - min(levels, key=lambda lv, e=band.energy: abs(lv[0] - e))[0] for band in bands
    ]


def assignment_ok(bands: tuple[Band, ...], levels: list[tuple[float, str]]) -> bool:
    """Return whether every band's nearest predicted level carries one of its labels."""
    return all(
        label_matches(min(levels, key=lambda lv, e=band.energy: abs(lv[0] - e))[1], band.labels)
        for band in bands
    )


def truth_self_test(cases: list[Case]) -> int:
    """Hard-fail unless every synthetic case assigns correctly at its own truth.

    Returns:
        The number of cases checked.

    Raises:
        SystemExit: listing the first failing cases.

    """
    failures: list[str] = []
    checked = 0
    for case in cases:
        if case.expect_raise or case.truth_b is None or case.truth_c is None:
            continue
        _, levels = predicted_levels(
            case, "fit_spectrum", case.truth_dq, case.truth_b, case.truth_c
        )
        checked += 1
        if not assignment_ok(case.bands, levels):
            failures.append(f"d{case.d} {case.spin} sf={case.sf} Dq={case.truth_dq}")
    if failures:
        raise SystemExit(f"truth self-test failed for {len(failures)} cases: {failures[:5]}")
    return checked


def jce_label_check(cases: list[Case]) -> list[str]:
    """Report JCE bands whose table label is not the nearest level at the reported point."""
    out: list[str] = []
    for case in cases:
        if case.truth_b is None or case.truth_c is None:
            continue
        _, levels = predicted_levels(
            case, "fit_spectrum", case.truth_dq, case.truth_b, case.truth_c
        )
        for band in case.bands:
            nearest = min(levels, key=lambda lv, e=band.energy: abs(lv[0] - e))[1]
            if not label_matches(nearest, band.labels):
                out.append(
                    f"{case.system} sf={case.sf} {fmt(band.energy)}: "
                    f"{'/'.join(band.labels)} -> {nearest}",
                )
    return out


def objective_at(
    case: Case, path: str, dq: float, b: float, c: float, c_mode: str = ""
) -> float | None:
    """Return the path's objective at ``(dq, b, c)``, None if undefined.

    fit_spectrum: its own injective assignment (with this run's labels); the apps:
    nearest-line RMSE.
    """
    if path == "fit_spectrum":
        try:
            _, levels = excited_levels(
                compute_point(case.d, dq, b, c),
                spin_allowed_only=not matches_every_level(case, path),
            )
        except (ValueError, KeyError):
            return None
        observed = np.asarray([band.energy for band in case.bands])
        if len(levels) < observed.size:
            return None
        labels = run_labels(case, c_mode)
        order = np.argsort(observed)
        sorted_labels = None if labels is None else [labels[i] for i in order]
        base = float(np.sqrt(np.mean(observed**2)))
        return assign_bands(observed[order], levels, sorted_labels, penalty=base)[1]
    try:
        _, candidates = transition_candidates(
            compute_point(case.d, dq, b, c),
            spin_allowed_only=not matches_every_level(case, path),
        )
    except (ValueError, KeyError):
        return None
    if not candidates:
        return None
    observed = [band.energy for band in case.bands]
    if path == "ratio_app":
        observed = ratio_inputs(case)
    return peak_rmse(np.asarray(observed), np.asarray([e for e, _a, _s in candidates]))


def warning_kinds(warnings: list[str]) -> tuple[str, ...]:
    """Map each warning to a kind from ``WARNING_KINDS``; unknown text becomes ``other``."""
    kinds: list[str] = []
    for text in warnings:
        kind = next((k for needle, k in WARNING_KINDS if needle in text), "other")
        kinds.append(kind)
    return tuple(kinds)


def infeasible_at_c(case: Case, run: Run) -> bool:
    """Return whether the truth Dq is in the other spin regime at the C the run used."""
    if case.truth_b is None:
        return False
    regime = multiplicity(oracle_ground(case.d, case.truth_dq, case.truth_b, run.c_used))
    return regime != multiplicity(case.ground_key)


def decide_verdict(
    case: Case, run: Run, d_dq: float | None, d_b: float | None, kinds: tuple[str, ...]
) -> str:
    """Apply the verdict rules of section 2 to one run."""
    if run.raised:
        expected = (
            case.expect_raise and run.path == "fit_spectrum" and "no spin-allowed" in run.raised
        )
        verdict = "RAISED-EXPECTED" if expected else "RAISED"
    else:
        dq_ok = d_dq is not None and abs(d_dq) <= DQ_TOL_PCT
        b_ok = d_b is None or abs(d_b) <= B_TOL_PCT
        pertinent = any(k not in NON_PERTINENT_KINDS for k in kinds)
        if dq_ok and b_ok:
            verdict = "OK"
        elif dq_ok and "single-transition" in kinds:
            verdict = "OK-B-UNIDENTIFIED"
        else:
            verdict = "WRONG-WARNED" if pertinent else "WRONG-SILENT"
    return verdict


def grade(case: Case, run: Run) -> Row:
    """Grade one run against its case and build the CSV record."""
    d_dq = pct(run.fit_dq, case.truth_dq)
    d_b = pct(run.fit_b, case.truth_b)
    d_c = pct(run.fit_c, case.truth_c)
    kinds = warning_kinds(run.warnings)
    ground_reached = "n/a"
    assignment = "n/a"
    obj_fit = obj_truth_c_used = obj_truth = None
    r2: float | None = None
    if run.fit_dq is not None and run.fit_b is not None:
        ground_key, levels = predicted_levels(case, run.path, run.fit_dq, run.fit_b, run.c_used)
        ground_reached = str(ground_key == case.ground_key)
        if levels:
            assignment = str(assignment_ok(case.bands, levels))
            r2 = r_squared(
                [band.energy for band in case.bands], nearest_residuals(case.bands, levels)
            )
        obj_fit = objective_at(case, run.path, run.fit_dq, run.fit_b, run.c_used, run.c_mode)
    if case.truth_b is not None:
        obj_truth_c_used = objective_at(
            case, run.path, case.truth_dq, case.truth_b, run.c_used, run.c_mode
        )
        if case.truth_c is not None:
            obj_truth = objective_at(
                case, run.path, case.truth_dq, case.truth_b, case.truth_c, run.c_mode
            )
    verdict = decide_verdict(case, run, d_dq, d_b, kinds)
    if case.r1:
        verdict = f"{verdict}-R1"
    jce = case.source == "jce2023"
    values = {
        "source": case.source,
        "system": case.system,
        "d": str(case.d),
        "spin": case.spin,
        "sf": str(case.sf),
        "path": run.path,
        "c_mode": run.c_mode,
        "truth_Dq": fmt(case.truth_dq),
        "truth_B": fmt(case.truth_b),
        "truth_C": fmt(case.truth_c),
        "fit_Dq": fmt(run.fit_dq),
        "fit_B": fmt(run.fit_b),
        "fit_C": fmt(run.fit_c),
        "dDq_pct": fmt(d_dq),
        "dB_pct": fmt(d_b),
        "dC_pct": fmt(d_c),
        "rmse": fmt(run.rmse),
        "r2": "n/a" if r2 is None else f"{r2:.4f}",
        "rmse_at_reported": fmt(obj_truth if obj_truth is not None else obj_truth_c_used)
        if jce
        else "n/a",
        "rmse_at_fit": fmt(obj_fit) if jce else "n/a",
        "ground_reached": ground_reached,
        "n_bands": str(len(case.bands)),
        "warnings": " | ".join(run.warnings),
        "warning_kinds": ";".join(kinds),
        "pertinent_warning": str(any(k not in NON_PERTINENT_KINDS for k in kinds)),
        "raised": run.raised,
        "assignment_ok": assignment,
        "infeasible_at_c": str(infeasible_at_c(case, run)),
        "verdict": verdict,
        "approx": str(case.approx),
        "R1_tainted": str(case.r1),
        "geometry": case.geometry,
        "failure_classes": "",
    }
    return Row(
        case=case,
        run=run,
        values=values,
        verdict=verdict,
        d_dq=d_dq,
        d_b=d_b,
        d_c=d_c,
        obj_fit=obj_fit,
        obj_truth_c_used=obj_truth_c_used,
        obj_truth=obj_truth,
        kinds=kinds,
    )


def base_verdict(row: Row) -> str:
    """Return the verdict without its ``-R1`` suffix."""
    return row.verdict.removesuffix("-R1")


def is_failure(row: Row) -> bool:
    """Return whether a row counts as a failure for the failure classification."""
    return base_verdict(row) in FAILURES


def shared_classes(row: Row) -> list[str]:
    """Return classes (c), (d), single-band and estimator-disagreement."""
    case, values = row.case, row.values
    message = row.run.raised.lower()
    found: list[str] = []
    if values["assignment_ok"] == "False":
        found.append("c")
    if (
        values["ground_reached"] == "False"
        or case.near_crossover
        or "crossover" in message
        or "penalty region" in message
    ):
        found.append("d")
    if len(case.bands) == 1:
        found.append("single-band")
    if estimator_disagrees(row):
        found.append("estimator-disagreement")
    return found


def estimator_disagrees(row: Row) -> bool:
    """Return whether a JCE reverse-app row beats the published point on its own objective."""
    case = row.case
    return (
        case.source == "jce2023"
        and not case.sf
        and row.run.path == "reverse_app"
        and row.values["assignment_ok"] == "True"
        and len(case.bands) > EXACT_BANDS
        and case.truth_c is not None
        and row.obj_fit is not None
        and row.obj_truth is not None
        and row.obj_fit < row.obj_truth
    )


def fit_classes(row: Row, paired_truth_ok: bool) -> list[str]:
    """Return classes (a), (b), (e), (f) for a ``fit_spectrum`` row."""
    case, run = row.case, row.run
    found: list[str] = []
    energies = sorted(band.energy for band in case.bands)
    closed_form = (
        case.d in CLOSED_FORM_CONFIGS and len(energies) >= CLOSED_FORM_BANDS and not case.sf
    )
    seed_ratio = energies[0] / 10.0 / case.truth_dq
    generic_off = not closed_form and not SEED_SPAN[0] <= seed_ratio <= SEED_SPAN[1]
    if run.c_mode != "seed-displaced" and generic_off:
        found.append("a")
    lo, hi = default_dq_bounds(energies, seed_dq(case))
    if run.c_mode != "seed-displaced" and not lo < case.truth_dq < hi:
        found.append("bounds-exclude-truth")
    fit, at_truth = row.obj_fit, row.obj_truth_c_used
    better_exists = fit is not None and at_truth is not None and fit > at_truth + RMSE_EPS_CM1
    if better_exists or "converge" in run.raised.lower():
        found.append("b")
    if run.c_mode in {"default", "labelled-default"} and paired_truth_ok:
        found.append("e")
    as_good = fit is not None and row.obj_truth is not None and fit <= row.obj_truth + RMSE_EPS_CM1
    if base_verdict(row) == "WRONG-SILENT" and as_good:
        found.append("f")
    return found


def seed_dq(case: Case) -> float:
    """Return the Dq seed ``fit_spectrum`` derives its default ``dq_bounds`` from."""
    energies = sorted(band.energy for band in case.bands)
    return _initial_seed(case.d, energies, include_spin_forbidden=case.sf)[0]


def app_grids(case: Case, path: str) -> tuple[list[float], list[float]]:
    """Rebuild an app's (Dq, B) grid from the mirrored constants for this case."""
    spec = APP_GRID[path]
    steps = int(spec["grid_steps"])
    energies = ratio_inputs(case) if path == "ratio_app" else sorted(b.energy for b in case.bands)
    dq_max = energies[0] * APP_DQ_MAX_FACTOR
    dq_grid = [dq_max * i / (steps - 1) for i in range(steps)]
    b_grid = [
        spec["b_min"] + (spec["b_max"] - spec["b_min"]) * j / (steps - 1) for j in range(steps)
    ]
    return dq_grid, b_grid


def app_classes(row: Row) -> list[str]:
    """Return the app-specific classes for a reverse- or ratio-app row."""
    case, run = row.case, row.run
    found: list[str] = []
    if case.spin == "low":
        found.append("app-hs")
    if run.path == "reverse_app" and any(not band.spin_allowed for band in case.bands):
        found.append("app-sf")
    if run.path == "ratio_app" and case.d in CLOSED_FORM_CONFIGS:
        dq_nodes, _ = app_grids(case, run.path)
        nu1 = ratio_inputs(case)[0]
        nearest = min(dq_nodes, key=lambda g: abs(g - nu1 / 10.0))
        if (
            abs(nearest - nu1 / 10.0) > APP_ROUNDING_CM1
            and run.fit_dq is not None
            and abs(run.fit_dq - nearest) <= APP_ROUNDING_CM1
        ):
            found.append("app-lattice")
    if run.fit_dq is not None and run.fit_b is not None and case.truth_b is not None:
        dq_grid, b_grid = app_grids(case, run.path)
        truth_b = case.truth_b
        nearest_dq = min(dq_grid, key=lambda g: abs(g - case.truth_dq))
        nearest_b = min(b_grid, key=lambda g: abs(g - truth_b))
        if (
            abs(run.fit_dq - nearest_dq) <= APP_ROUNDING_CM1
            and abs(run.fit_b - nearest_b) <= APP_ROUNDING_CM1
        ):
            found.append("app-grid")
    return found


def classify(row: Row, paired_truth_ok: bool) -> tuple[str, ...]:
    """Apply ``CLASS_RULES`` to one failing row; a row may carry several classes."""
    if row.run.path == "fit_spectrum":
        found = fit_classes(row, paired_truth_ok)
    else:
        found = app_classes(row)
    found.extend(shared_classes(row))
    return tuple(sorted(found)) or ("unclassified",)


def attach_classes(rows: list[Row]) -> None:
    """Classify every failing row in place, pairing C=default with its C=truth run.

    A labelled run pairs with the labelled run of the same case, an unlabelled one
    with the unlabelled.
    """
    truth_ok: dict[tuple[Case, bool], bool] = {}
    for row in rows:
        if row.run.path == "fit_spectrum" and row.run.c_mode in {"truth", "labelled-truth"}:
            labelled = row.run.c_mode in LABELLED_MODES
            truth_ok[row.case, labelled] = base_verdict(row) == "OK"
    for row in rows:
        labelled = row.run.c_mode in LABELLED_MODES
        row.classes = classify(row, truth_ok.get((row.case, labelled), False))
        if is_failure(row):
            row.values["failure_classes"] = ";".join(row.classes)


def jce_d_count(block: str) -> int:
    """Return the Oh d-count from a Table 1/2 block like ``d6(Oh)/d4(Td)``.

    Raises:
        SystemExit: if the block is not of that shape.

    """
    match = re.match(r"d(\d)\(Oh", block)
    if match is None:
        raise SystemExit(f"unrecognised JCE block {block!r}")
    return int(match.group(1))


def jce_geometry(system: str, oh_count: int) -> str:
    """Decide Oh vs Td-equivalent from the metal ion's actual d-count.

    Raises:
        SystemExit: for a system missing from ``SYSTEM_ION`` or a d-count that
            fits neither reading of its block.

    """
    if system not in SYSTEM_ION:
        raise SystemExit(f"JCE system {system!r} has no entry in SYSTEM_ION")
    actual = SYSTEM_ION[system][1]
    if actual == oh_count:
        return "Oh"
    if actual == 10 - oh_count:
        return "Td-equivalent"
    raise SystemExit(f"{system}: ion d{actual} fits neither d{oh_count}(Oh) nor d{10 - oh_count}")


def jce_label(row: dict[str, str]) -> str:
    """Return the truth label of a Table 1 band; a blank ordinal matches any index.

    Raises:
        SystemExit: on an irrep spelling not in ``JCE_IRREPS``.

    """
    irrep = row["irrep"]
    if irrep not in JCE_IRREPS:
        raise SystemExit(f"unknown JCE irrep {irrep!r} in {row['system']}")
    index = str(int(row["ordinal"]) - 1) if row["ordinal"] else "*"
    return f"{row['multiplicity']}_{JCE_IRREPS[irrep]}#{index}"


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV into a list of row dicts."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def jce_partners(
    levels: list[tuple[float, str]], d: int, dq: float, b: float | None, c: float | None
) -> list[tuple[float, str]]:
    """Return oracle levels degenerate (within ``MERGE_CM1``) with each table-labelled level.

    Each table label is located in the oracle at the reported (Dq, B, C) -- the
    level of that term nearest the band -- and every other excited oracle level
    within the merge window of it is returned, re-anchored at the band's energy
    so ``band_from`` attaches it to that band.  Without B and C there is no
    reported point, so no partners are added.
    """
    if b is None or c is None:
        return []
    excited = oracle_levels(d, dq, b, c)[1:]
    partners: list[tuple[float, str]] = []
    for energy, label in levels:
        own = [lv for lv in excited if label_matches(lv[1], (label,))]
        if not own:
            continue
        anchor = min(own, key=lambda lv, e=energy: abs(lv[0] - e))[0]
        partners.extend(
            (energy, lab) for e, lab in excited if abs(e - anchor) <= MERGE_CM1 and lab != label
        )
    return partners


def jce_bands(
    levels: list[tuple[float, str]], gm: int, partners: list[tuple[float, str]]
) -> tuple[Band, ...]:
    """Merge JCE bands within ``MERGE_CM1``; table labels plus their oracle-degenerate partners."""
    return tuple(band_from(cl, gm, partners) for cl in cluster_levels(levels))


def jce_cases() -> list[Case]:
    """Build the JCE 2023 cases: a spin-allowed-only case and, if any, a mixed one.

    Raises:
        SystemExit: if a Table 2 system has no bands in Table 1.

    """
    bands_by_system: dict[str, list[dict[str, str]]] = defaultdict(list)
    for band in read_csv(JCE_DIR / "jce2023_table1_bands.csv"):
        bands_by_system[band["system"]].append(band)
    cases: list[Case] = []
    for params in read_csv(JCE_DIR / "jce2023_table2_parameters.csv"):
        system = params["system"]
        if system not in bands_by_system:
            raise SystemExit(f"{system} has parameters but no bands")
        d = jce_d_count(params["block"])
        spin: SpinState = "low" if system in LOW_SPIN_SYSTEMS else "high"
        gm = expected_ground_mult(d, spin)
        dq = float(params["Dq_cm1"])
        b = dq / float(params["Dq_over_B_reported"]) if params["Dq_over_B_reported"] else None
        c = float(params["C_over_B_reported"]) * b if params["C_over_B_reported"] and b else None
        dq_ref = ORACLE_WEAK_DQ if spin == "high" else ORACLE_STRONG_DQ
        ground = oracle_ground(d, dq_ref, DEFAULTS[d]["default_B"], DEFAULTS[d]["default_C"])
        rows = bands_by_system[system]
        levels = [(float(r["wavenumber_cm1"]), jce_label(r)) for r in rows]
        allowed = [lv for lv in levels if multiplicity(lv[1]) == gm]
        variants: list[tuple[bool, list[tuple[float, str]]]] = []
        if allowed:
            variants.append((False, allowed))
        if len(allowed) < len(levels):
            variants.append((True, levels))
        cases.extend(
            Case(
                source="jce2023",
                system=system,
                d=d,
                spin=spin,
                sf=sf,
                truth_dq=dq,
                truth_b=b,
                truth_c=c,
                ground_key=ground,
                bands=jce_bands(chosen, gm, jce_partners(chosen, d, dq, b, c)),
                approx=any(r["approx"] == "True" for r in rows),
                r1=d in R1_CONFIGS,
                geometry=jce_geometry(system, d),
            )
            for sf, chosen in variants
        )
    return cases


def run_case(case: Case, reverse: Callable[..., Any], ratio: Callable[..., Any]) -> list[Row]:
    """Run every applicable path on one case and grade each run."""
    runs: list[Run] = []
    if case.truth_c is not None:
        runs.append(run_fit_spectrum(case, "truth"))
    runs.append(run_fit_spectrum(case, "default"))
    if case.truth_c is not None:
        runs.append(run_fit_spectrum(case, "labelled-truth"))
    runs.append(run_fit_spectrum(case, "labelled-default"))
    if (
        case.source == "synthetic"
        and case.d in CLOSED_FORM_CONFIGS
        and not case.sf
        and len(case.bands) >= CLOSED_FORM_BANDS
    ):
        runs.append(run_seed_displaced(case))
    if not case.expect_raise:
        runs.append(run_reverse(case, reverse))
        if not case.sf and len(case.bands) >= RATIO_MIN_BANDS:
            runs.append(run_ratio(case, ratio))
    return [grade(case, run) for run in runs]


MAX_WORKERS = 8
"""Process-pool ceiling. Rows are collected in case order, so the output does not
depend on the worker count; only the wall time does."""

_WORKER_TOOLS: tuple[Callable[..., Any], Callable[..., Any]] | None = None


def pool_size() -> int:
    """Return the worker count: the CPU count, capped at ``MAX_WORKERS``."""
    return max(1, min(MAX_WORKERS, os.cpu_count() or 1))


def init_worker() -> None:
    """Load the two app tools once per worker process."""
    global _WORKER_TOOLS  # noqa: PLW0603 - one in-memory server per process
    _WORKER_TOOLS = load_app_tools()


def run_case_in_worker(case: Case) -> list[Row]:
    """Run one case with this worker's app tools."""
    if _WORKER_TOOLS is None:
        raise SystemExit("worker tools not loaded")
    return run_case(case, *_WORKER_TOOLS)


def known_defect() -> list[tuple[str, str, str, str, str, str, str]]:
    """Regenerate the [Mn(H2O)6]2+ known-defect rows, hand-picked illustration included."""
    b = KNOWN_DEFECT_DQ / KNOWN_DEFECT_DQ_OVER_B
    c = KNOWN_DEFECT_C_OVER_B * b
    bands = list(KNOWN_DEFECT_BANDS)
    results: list[tuple[str, str, str, str, str, str, str]] = []

    def record(name: str, call: Callable[[], Any]) -> None:
        """Run one fit and append its formatted row, or the raise message."""
        try:
            fit = call()
        except ValueError as exc:
            results.append((name, "raised", "", "", "", "", str(exc)))
            return
        results.append(
            (
                name,
                fmt(fit.Dq),
                fmt(fit.B),
                fmt(fit.C),
                fmt(fit.rmse_cm1),
                "n/a" if (r2 := r_squared(bands, fit.residuals_cm1)) is None else f"{r2:.4f}",
                " | ".join(fit.warnings) or "none",
            ),
        )

    record("C = default", lambda: fit_spectrum(5, bands, None, include_spin_forbidden=True))
    record("C = reference", lambda: fit_spectrum(5, bands, c, include_spin_forbidden=True))
    record(
        "reference-blind 25 x 5 start grid (Dq x B), C = reference",
        lambda: reference_blind_fit(bands, c),
    )
    record(
        "reference-blind 25 x 5 start grid (Dq x B), C = default",
        lambda: reference_blind_fit(bands, None),
    )
    with mock.patch.object(compute_module, "_initial_seed", return_value=COUNTERFACTUAL_SEED):
        record(
            "illustration (hand-picked): seed (650, 750), dq_bounds (130, 3250), C = reference",
            lambda: fit_spectrum(
                5, bands, c, include_spin_forbidden=True, dq_bounds=COUNTERFACTUAL_DQ_BOUNDS
            ),
        )
    return results


def reference_blind_fit(bands: list[float], c: float | None) -> SpectrumFit:
    """Fit high-spin d5 from a Dq x B start grid chosen without the reference; keep the best.

    Dq seeds span the default bounds (0.2, 5) x obs[0]/10 geometrically, B seeds span
    ``FIT_B_BOUNDS``. Each start patches the seed ``fit_spectrum`` would derive.
    """
    lo, hi = 0.2 * bands[0] / 10.0, 5.0 * bands[0] / 10.0
    jobs = [
        (bands, c, (float(dq), float(b0)), (lo, hi))
        for dq in np.geomspace(lo, hi, MULTISTART_DQ_SEEDS)
        for b0 in np.geomspace(*FIT_B_BOUNDS, MULTISTART_B_SEEDS)
    ]
    with multiprocessing.Pool(pool_size()) as pool:
        fits = pool.map(blind_start, jobs)
    best: SpectrumFit | None = None
    for fit in fits:  # in start order, so ties resolve as the serial loop did
        if fit is not None and (best is None or fit.rmse_cm1 < best.rmse_cm1):
            best = fit
    if best is None:
        msg = "every start raised"
        raise ValueError(msg)
    return best


def blind_start(
    job: tuple[list[float], float | None, tuple[float, float], tuple[float, float]],
) -> SpectrumFit | None:
    """Run one reference-blind start: patch the seed, fit, or return None if it raises."""
    bands, c, seed, dq_bounds = job
    with mock.patch.object(compute_module, "_initial_seed", return_value=seed):
        try:
            return fit_spectrum(5, bands, c, include_spin_forbidden=True, dq_bounds=dq_bounds)
        except ValueError:
            return None


def nearest_line_rmse(d: int, bands: Sequence[float], dq: float, b: float, c: float) -> float:
    """Return fit_spectrum's spin-forbidden nearest-line RMSE at one (Dq, B, C)."""
    _, candidates = transition_candidates(compute_point(d, dq, b, c), spin_allowed_only=False)
    predicted = np.asarray([e for e, _a, _s in candidates])
    return peak_rmse(np.asarray(list(bands)), predicted)


def render_csv(rows: list[Row]) -> str:
    """Render the CSV with LF line endings."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([row.values[col] for col in CSV_COLUMNS])
    return buffer.getvalue()


def md_table(header: Sequence[str], body: Sequence[Sequence[str]]) -> list[str]:
    """Render a Markdown table, escaping pipes in cells."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines.extend(
        "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |" for cells in body
    )
    return lines


def worst(verdicts: list[str]) -> str:
    """Return ``"<worst> <count>/<total>"`` under ``SEVERITY``."""
    if not verdicts:
        return "N/A"
    top = max(verdicts, key=SEVERITY.index)
    return f"{top} {verdicts.count(top)}/{len(verdicts)}"


def d5_minimum_evidence(rows: list[Row]) -> tuple[int, int, float]:
    """Count synthetic d5 HS sf C=truth runs whose returned objective exceeds the truth's.

    Returns:
        ``(runs, runs_with_better_truth, max_objective_at_truth)``.

    """
    picked = [
        r
        for r in rows
        if r.case.source == "synthetic"
        and r.case.d == 5  # noqa: PLR2004  d5 is the configuration section 1 is about
        and r.case.spin == "high"
        and r.case.sf
        and r.run.path == "fit_spectrum"
        and r.run.c_mode == "truth"
        and r.obj_truth is not None
    ]
    better = [
        r for r in picked if r.obj_fit is None or r.obj_fit > (r.obj_truth or 0.0) + RMSE_EPS_CM1
    ]
    worst_truth = max((r.obj_truth or 0.0 for r in picked), default=0.0)
    return len(picked), len(better), worst_truth


def section_known_defect(
    defect: list[tuple[str, str, str, str, str, str, str]], rows: list[Row]
) -> list[str]:
    """Render section 1."""
    b = KNOWN_DEFECT_DQ / KNOWN_DEFECT_DQ_OVER_B
    ref_c = KNOWN_DEFECT_C_OVER_B * b
    default_c = float(DEFAULTS[5]["default_C"])
    n, better, at_truth = d5_minimum_evidence(rows)
    lines = [
        "## 1. Known defect: [Mn(H2O)6]2+ (d5 high-spin, all bands spin-forbidden)",
        "",
        (
            f"Bands {', '.join(fmt(e) for e in KNOWN_DEFECT_BANDS)} cm^-1, "
            f"`include_spin_forbidden=True`. Reference ({JCE_CITATION}, Table 2, reported): "
            f"Dq {fmt(KNOWN_DEFECT_DQ)}, B {fmt(b)}, C {fmt(KNOWN_DEFECT_C_OVER_B * b)} cm^-1. "
            "This reference is d5 and therefore R1-tainted "
            "(Hormann & Shaw, J. Chem. Educ. 1987, 64, 918): the table is a comparison, not a "
            "grade. Regenerated live. The start-grid rows and the hand-picked illustration "
            "monkeypatch `tanabesugano.mcp._compute._initial_seed` inside this process "
            "only; the start grid never sees the reference."
        ),
        "",
    ]
    lines.extend(
        md_table(
            ("run", "Dq", "B", "C", "rmse", "r2", "warnings / raised"), [tuple(r) for r in defect]
        )
    )
    lines.extend(
        [
            "",
            (
                "The claim that the right minimum exists rests on the oracle, not on this "
                f"reference: over the {n} synthetic d5 high-spin spin-forbidden fit_spectrum "
                f"runs with C = truth, the objective at the truth is at most {fmt(at_truth)} "
                f"cm^-1, and in {better} of them fit_spectrum returns a point whose objective "
                "is more than 1 cm^-1 higher (or raises). "
                + (
                    "The minimum is there and the start strategy does not reach it."
                    if better
                    else "The minimum is there and fit_spectrum reaches it in every run."
                )
            ),
            "",
            (
                "At the default C the reference (Dq, B) is not a minimum of this objective: "
                "the nearest-line RMSE there is "
                f"{fmt(nearest_line_rmse(5, KNOWN_DEFECT_BANDS, KNOWN_DEFECT_DQ, b, default_c))} "
                "cm^-1, against "
                f"{fmt(nearest_line_rmse(5, KNOWN_DEFECT_BANDS, KNOWN_DEFECT_DQ, b, ref_c))} "
                "cm^-1 at the reference C. No choice of seed can recover it at the default C."
            ),
            "",
        ],
    )
    return lines


def section_method(na_cells: list[str], self_test: int, jce_labels: list[str]) -> list[str]:
    """Render section 2."""
    lines = [
        "## 2. Method",
        "",
        (
            "- **Oracle.** Synthetic bands come only from "
            "`tanabesugano.test._determinant_oracle.relative_term_levels` (full C(10, n) "
            "determinant basis, imports nothing from the package). Its keys were checked "
            "against `TermKey` at start-up: identical spelling, no map needed. Package "
            "functions are used only to grade a point."
        ),
        (
            f"- **Band rule.** Excited levels are merged first (chained within "
            f"{fmt(MERGE_CM1)} cm^-1, mean energy, all labels kept), then the lowest "
            f"{MAX_ALLOWED} merged ground-multiplicity bands are taken; the sf variant adds the "
            f"lowest {MAX_FORBIDDEN} merged bands of multiplicity (2S+1) +/- 2 (|dS| = 1: the "
            "manifold below for high-spin, mainly the one above for low-spin d5-d7). A band "
            "also carries the label of "
            "any other excited level within the merge window. JCE input is merged the same "
            "way (MgO:Ni2+ has 3T1 and 1E both at 13670); a JCE band keeps its table labels "
            "plus any oracle level within the merge window of the labelled level at the "
            "reported (Dq, B, C), e.g. 4A1 beside a tabulated d5 4E (exactly degenerate at "
            "10B + 5C). Without a reported B and C no partner is added."
        ),
        (
            f"- **Truth self-test.** All {self_test} synthetic cases assign every band "
            "correctly at their own truth (Dq, B, C) under fit_spectrum's matching rule; the "
            "script aborts otherwise. At the JCE reported points, "
            f"{len(jce_labels)} band(s) are not nearest to their table label (listed in "
            "section 5); those are properties of the published data, not of the grader."
        ),
        (
            f"- **Truth points.** B in {B_FACTORS} x default B, dropped when outside "
            f"fit_spectrum's b_bounds {FIT_B_BOUNDS}: {', '.join(skipped_b_values())}. "
            f"C/B in {CB_RATIOS}, +{CB_SHIFT} when within {CB_COLLISION} of the default C/B "
            f"(d6: 4.8 -> 5.0). Dq = {HS_FACTOR} x (HS) / {LS_FACTOR} x (LS) the oracle "
            f"crossover for d4-d7, fixed {FIXED_DQ} for d2/d3/d8; one near-crossover point per "
            f"d4-d7 cell at {1 - NEAR_FRACTION:g} x / {1 + NEAR_FRACTION:g} x the crossover "
            f"(B factor {NEAR_B_FACTOR}). Truth B below 400 (d2, d5 at 0.45 x) lies outside "
            "both apps' B grid."
        ),
        (
            "- **labelled.** Every fit_spectrum case runs again at C = truth and C = default "
            "with `band_labels`: each band's term keys (`4_T_1`, never the oracle's `#index`), "
            "the label a user can name. A merged band carries the terms of all its levels."
        ),
        (
            "- **seed-displaced.** For d3/d8 spin-allowed points the closed form is exact on "
            "oracle bands (nu1 = 10Dq, nu2 + nu3 = 15B + 3 nu1), so fit_spectrum starts AT the "
            "answer. Each such point gets an extra C = truth run with `_initial_seed` "
            f"patched to return ({SEED_DQ_FACTOR} x Dq_cf, {SEED_B_FACTOR} x B_cf). JCE d3/d8 "
            "reported Dq is nu1/10 by construction, equal to both the closed-form seed and "
            "reverse-app grid node 8 -- hence the many dDq = 0.0 rows."
        ),
        (
            f"- **Verdict.** OK if |dDq| <= {DQ_TOL_PCT:g} % and |dB| <= {B_TOL_PCT:g} %: "
            f"{THRESHOLD_REASON}. That tolerance was set for the exact oracle; on JCE rows it "
            "is applied only as a comparator. OK-B-UNIDENTIFIED: Dq within tolerance, B not, "
            "and the 'only one spin-allowed transition' warning fired. Otherwise WRONG-WARNED "
            "only if a pertinent warning fired (warning_kinds residual, b-pinned, "
            "single-transition, too-few-bands; the c-note alone does not count), else "
            "WRONG-SILENT; RAISED on an exception or error payload. A run whose truth Dq lies "
            "in the other spin regime at the C it used keeps its verdict and is tagged "
            "`infeasible_at_c=True`: the tag explains, it does not excuse. OK-B-UNIDENTIFIED "
            "is not a failure. "
            "RAISED-EXPECTED only for fit_spectrum on high-spin d5 spin-allowed-only, fed the "
            "quartet bands, when the message says `no spin-allowed`. Where no B reference "
            "exists (JCE [Ni(NH3)6]2+) the verdict uses dDq only. Severity for 'worst': "
            + " < ".join(SEVERITY)
            + "."
        ),
        (
            "- **assignment_ok.** At the returned point (with the C the path used), each "
            "band's nearest predicted level by `Level.uid` must carry one of its labels. "
            "fit_spectrum with `include_spin_forbidden` matches every level; all other runs "
            "only the ground multiplicity. A blank JCE ordinal matches any index of the term."
        ),
        (
            "- **r2.** Computed by this grader; no fit path returns it. Over the same levels "
            "as assignment_ok, r2 = 1 - sum(res^2) / sum((E - mean E)^2), where res is each "
            "band's distance to its nearest predicted line -- the measure the fitters "
            "minimise. A high r2 beside a wrong Dq is therefore the silent-failure signature, "
            "not evidence of a good fit. n/a with no fitted point or fewer than two bands."
        ),
        (
            "- **Apps.** Neither app accepts `spin_state`, `include_spin_forbidden` or C: both "
            "pin the high-spin reference at the default C, so their low-spin rows fail by "
            "construction; they are recorded as `c_mode=app-default`. The reverse app receives "
            "every band of the case; the ratio app the lowest three, spin-allowed cases only. "
            "The app-grid classifier rebuilds each app's grid from mirrored constants: "
            f"grid_steps/b_min/b_max {APP_GRID['reverse_app']} (reverse) and "
            f"{APP_GRID['ratio_app']} (ratio) are checked at start-up against the tool "
            "signatures (apps.py L1719-1721, L1959-1961); Dq max = 3 x obs[0]/10 was read off "
            "apps.py L1779 (reverse) and L2013 (ratio). The reverse app's Dq grid contains "
            "obs[0]/10 exactly at node 8; the ratio app's does not (obs[0]/10 falls at index "
            "(steps - 1)/3, a node only when steps - 1 is divisible by 3), hence app-lattice."
        ),
        "- **Not applicable cells.**",
    ]
    lines.extend(f"  - {reason}" for reason in na_cells)
    lines.append(
        "  - ratio app with sf=True; both apps on high-spin d5 sf=False (no spin-allowed "
        "band exists); seed-displaced outside d3/d8 sf=False.",
    )
    lines.append("")
    return lines


def section_matrix(rows: list[Row], na_cells: list[str]) -> list[str]:
    """Render section 3 and the headline counts."""
    synthetic = [r for r in rows if r.case.source == "synthetic"]
    cells: dict[tuple[int, str, bool], dict[tuple[str, str], list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in synthetic:
        cells[row.case.d, row.case.spin, row.case.sf][row.run.path, row.run.c_mode].append(
            row.verdict
        )
    body: list[tuple[str, ...]] = []
    for d in range(2, 9):
        for spin in ("high", "low"):
            for sf in (False, True):
                key = (d, spin, sf)
                if key not in cells:
                    if any(f"d{d} {spin}-spin sf={sf}" in reason for reason in na_cells):
                        body.append((f"d{d}", spin, str(sf), *("N/A",) * len(MATRIX_COLUMNS)))
                    continue
                body.append(
                    (
                        f"d{d}",
                        spin,
                        str(sf),
                        *(worst(cells[key][p, m]) for p, m, _t in MATRIX_COLUMNS),
                    ),
                )
    lines = [
        "## 3. Synthetic matrix",
        "",
        "Worst verdict per cell and how many of the cell's runs carry it.",
        "",
    ]
    lines.extend(md_table(("d", "spin", "sf", *(t for _p, _m, t in MATRIX_COLUMNS)), body))
    lines.extend(["", "Headline counts (synthetic runs):", ""])
    lines.extend(verdict_counts(synthetic))
    lines.append("")
    return lines


def verdict_counts(rows: list[Row]) -> list[str]:
    """Render a path x verdict count table."""
    by_path: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_path[f"{row.run.path} ({row.run.c_mode})"][base_verdict(row)] += 1
    header = ("path", *SEVERITY[1:], "total")
    body = [
        (path, *(str(counter[v]) for v in SEVERITY[1:]), str(sum(counter.values())))
        for path, counter in sorted(by_path.items())
    ]
    return md_table(header, body)


def row_cells(row: Row, columns: tuple[str, ...]) -> tuple[str, ...]:
    """Pick CSV values for a Markdown table row."""
    return tuple(row.values[col] for col in columns)


def section_failures(rows: list[Row]) -> list[str]:
    """Render section 4."""
    columns = (
        "d",
        "spin",
        "sf",
        "path",
        "c_mode",
        "truth_Dq",
        "truth_B",
        "truth_C",
        "fit_Dq",
        "fit_B",
        "dDq_pct",
        "dB_pct",
        "warning_kinds",
        "assignment_ok",
        "verdict",
        "failure_classes",
    )
    failing = [r for r in rows if r.case.source == "synthetic" and is_failure(r)]
    lines = ["## 4. Failing synthetic rows", "", f"{len(failing)} rows.", ""]
    lines.extend(md_table(columns, [row_cells(r, columns) for r in failing]))
    lines.append("")
    return lines


def section_jce(rows: list[Row], jce_labels: list[str]) -> list[str]:
    """Render section 5."""
    columns = (
        "system",
        "d",
        "spin",
        "sf",
        "geometry",
        "path",
        "c_mode",
        "truth_Dq",
        "truth_B",
        "truth_C",
        "fit_Dq",
        "fit_B",
        "dDq_pct",
        "dB_pct",
        "rmse_at_reported",
        "rmse_at_fit",
        "assignment_ok",
        "approx",
        "verdict",
        "failure_classes",
    )
    jce = [r for r in rows if r.case.source == "jce2023"]
    co_rows = sorted({r.case.system for r in jce if SYSTEM_ION[r.case.system][0] == "Co3+"})
    co_no_c = sorted(
        {r.case.system for r in jce if r.case.system in co_rows and not r.case.truth_c}
    )
    lines = [
        "## 5. JCE 2023 systems",
        "",
        (
            f"Source: {JCE_CITATION}. "
            "Reference = the `_reported` columns of Table 2 only (B = Dq / (Dq/B), "
            "C = (C/B) B). Rows ending in `-R1` are d5/d6 and R1-tainted: a comparison, never "
            "a pass or fail. [Mn(CN)6]3- is fitted low-spin, as are the Co(III) rows. "
            "`approx=True` marks a system with a band the paper flags as approximate. "
            "ZnO:Ni2+ is Ni2+ (d8) in Td, fitted on the d2(Oh) diagram (geometry="
            "Td-equivalent); d5 cannot be told apart by d-count and is recorded as Oh. "
            "rmse_at_reported is the path's nearest-line RMSE at the reported (Dq, B, C), "
            "falling back to the C the run used only where the paper reports no C/B; "
            "rmse_at_fit is the same RMSE at the returned (Dq, B) with the C the run used."
        ),
        "",
        (
            f"Co(III) rows without a reported C/B: {len(co_no_c)} of {len(co_rows)} "
            f"({', '.join(co_no_c)}); they have only the C=default run."
        ),
        "",
        "Bands not nearest to their table label at the reported point:",
        "",
    ]
    lines.extend(f"- {entry}" for entry in jce_labels or ["none"])
    lines.extend(["", "Counts (non-R1 rows):", ""])
    lines.extend(verdict_counts([r for r in jce if not r.case.r1]))
    lines.append("")
    lines.extend(md_table(columns, [row_cells(r, columns) for r in jce]))
    lines.append("")
    return lines


def class_applies(key: str, row: Row) -> bool:
    """Return whether rule ``key`` can fire on ``row`` at all (its eligible population)."""
    case, run = row.case, row.run
    fit = run.path == "fit_spectrum"
    eligible = {
        "a": fit and run.c_mode != "seed-displaced",
        "bounds-exclude-truth": fit and run.c_mode != "seed-displaced",
        "b": fit,
        "e": fit and run.c_mode in {"default", "labelled-default"},
        "f": fit,
        "app-hs": not fit,
        "app-grid": not fit,
        "app-sf": run.path == "reverse_app",
        "app-lattice": run.path == "ratio_app" and case.d in CLOSED_FORM_CONFIGS,
        "estimator-disagreement": case.source == "jce2023" and run.path == "reverse_app",
    }
    return eligible.get(key, True)


def discrimination(key: str, rows: list[Row]) -> str:
    """Compare a class's firing rate on eligible failing vs eligible OK rows (non-R1).

    A class counts as discriminating only if it fires on OK rows at under a quarter of its
    rate on failing rows (the B1 decision rule); otherwise it is a precondition.
    """
    if key == "unclassified":
        return "-"
    pools = {"failing": [0, 0], "OK": [0, 0]}
    for row in rows:
        status = "failing" if is_failure(row) else "OK" if base_verdict(row) == "OK" else ""
        if not status or row.case.r1 or not class_applies(key, row):
            continue
        pools[status][1] += 1
        pools[status][0] += key in row.classes
    (ff, nf), (fo, no) = pools["failing"], pools["OK"]
    rates = f"{ff}/{nf} vs {fo}/{no}"
    if nf == 0 or ff == 0:
        return f"{rates}: never fires on a failure"
    if no == 0:
        return f"{rates}: untested (no eligible OK row)"
    verdict = "discriminates" if fo / no < (ff / nf) / 4 else "precondition"
    return f"{rates}: {verdict}"


def section_scope(rows: list[Row]) -> list[str]:
    """Render section 6."""
    fires: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        status = "failing" if is_failure(row) else "OK" if base_verdict(row) == "OK" else ""
        if not status or row.case.r1:
            continue
        for cls in row.classes:
            fires[row.case.source, status, cls] += 1
    body = [
        (
            key,
            FIX_CLASSES[key],
            CLASS_RULES[key],
            *(
                "-" if key == "unclassified" and status == "OK" else str(fires[src, status, key])
                for src in ("synthetic", "jce2023")
                for status in ("failing", "OK")
            ),
            discrimination(key, rows),
        )
        for key in FIX_CLASSES
    ]
    tagged = sum(
        1 for r in rows if is_failure(r) and r.values["infeasible_at_c"] == "True" and not r.case.r1
    )
    excluded = Counter(
        base_verdict(r) for r in rows if not r.case.r1 and base_verdict(r) == "OK-B-UNIDENTIFIED"
    )
    lines = [
        "## 6. Follow-up scope",
        "",
        (
            "Every failing row (RAISED, WRONG-WARNED, WRONG-SILENT; R1 rows excluded) is "
            "tested against each rule independently, so a row may carry several classes and "
            "columns do not sum to the failure count; in particular (e) is assigned whether "
            "or not (a)/(b) also apply. Not failures, so not classified: "
            f"OK-B-UNIDENTIFIED {excluded['OK-B-UNIDENTIFIED']}. "
            f"{tagged} "
            "of the failing rows carry the infeasible_at_c tag (R1 rows excluded; Section 7 "
            "S4 counts them too). Classes (a), bounds-exclude-truth, (b) and (f) apply to "
            "fit_spectrum only, (e) to its C=default runs; app-hs and app-grid to app rows, "
            "app-sf to reverse-app rows, app-lattice to d3/d8 ratio-app rows; "
            "estimator-disagreement to JCE reverse-app rows; (c), (d) and single-band to "
            "every row. The OK columns apply the same rules to rows graded OK. The last "
            "column pools both sources over the rows each rule can fire on (failing vs OK) "
            "and calls a class discriminating only if its OK rate is under a quarter of its "
            "failing rate; a precondition co-occurs with failures but does not separate them "
            "from successes, so it alone does not size a fix."
        ),
        "",
        (
            "Class (e) measures the bias of holding C at the default. Whether a free C would "
            "be identifiable is NOT measured by this audit; a fix that fits C must "
            "establish that per configuration and band set."
        ),
        "",
    ]
    header = ("class", "proposed fix", "rule", "synthetic failing", "synthetic OK")
    lines.extend(md_table((*header, "JCE failing", "JCE OK", "failing vs OK rate"), body))
    lines.append("")
    return lines


def spearman(x: list[float], y: list[float]) -> float | None:
    """Return Spearman's rho with average ranks for ties, None for n < 3 or no spread."""
    if len(x) < SPEARMAN_MIN_N:
        return None

    def ranks(values: list[float]) -> list[float]:
        """Return 1-based average ranks."""
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2.0 + 1.0
            i = j + 1
        return out

    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def findings_s1(rows: list[Row]) -> str:
    """Live numbers for S1: pertinent-warning share and the c-note on OK runs."""
    fits = [
        r
        for r in rows
        if r.case.source == "synthetic" and r.run.path == "fit_spectrum" and not r.run.raised
    ]
    dq_wrong = [r for r in fits if r.d_dq is not None and abs(r.d_dq) > DQ_TOL_PCT]
    pertinent = [r for r in dq_wrong if any(k not in NON_PERTINENT_KINDS for k in r.kinds)]
    ok = [r for r in fits if base_verdict(r) == "OK"]
    noted = [r for r in ok if "c-note" in r.kinds]
    return (
        f"Live: {len(pertinent)} of {len(dq_wrong)} synthetic fit_spectrum runs with "
        f"|dDq| > {DQ_TOL_PCT:g} % carry a pertinent warning; the c-note fires on "
        f"{len(noted)} of {len(ok)} OK runs."
    )


def findings_s2(rows: list[Row]) -> str:
    """Live numbers for S2: estimator-disagreement on failing vs OK JCE reverse-app rows."""
    rev = [r for r in rows if r.case.source == "jce2023" and r.run.path == "reverse_app"]
    rev = [r for r in rev if not r.case.r1]
    failing = [r for r in rev if is_failure(r) and estimator_disagrees(r)]
    ok = [r for r in rev if base_verdict(r) == "OK"]
    ok_hits = sum(1 for r in ok if estimator_disagrees(r))
    systems = ", ".join(sorted({r.case.system for r in failing})) or "none"
    return (
        f"Live: {len(failing)} failing non-R1 JCE reverse-app rows qualify ({systems}); the "
        f"same rule holds on {ok_hits} of {len(ok)} OK ones."
    )


def findings_s3(rows: list[Row]) -> str:
    """Live numbers for S3: per-cell Spearman(dC, dDq) and OK-run bias, low-spin default C."""
    cells: dict[tuple[int, bool], list[Row]] = defaultdict(list)
    for r in rows:
        if (
            r.case.source == "synthetic"
            and r.case.spin == "low"
            and r.run.path == "fit_spectrum"
            and r.run.c_mode == "default"
            and r.d_dq is not None
            and r.d_c is not None
        ):
            cells[r.case.d, r.case.sf].append(r)
    parts: list[str] = []
    for (d, sf), members in sorted(cells.items()):
        rho = spearman([m.d_c or 0.0 for m in members], [m.d_dq or 0.0 for m in members])
        rho_text = "n/a" if rho is None else f"{rho:+.2f}"
        parts.append(f"d{d} sf={sf}: rho {rho_text} (n={len(members)})")
    ok = [m for ms in cells.values() for m in ms if base_verdict(m) == "OK"]
    mean_abs = statistics.fmean(abs(m.d_dq or 0.0) for m in ok) if ok else None
    concordant, pairs = within_b_concordance([m for ms in cells.values() for m in ms])
    return (
        "Live, low-spin fit_spectrum C=default, Spearman between signed dC and dDq: "
        + "; ".join(parts)
        + f". Among the {len(ok)} of those runs graded OK, mean |dDq| = {fmt(mean_abs)} %. "
        "dC is set by the B factor and C/B together, so the pooled rho alone could be a B "
        "effect; holding B fixed, the C/B change moves dDq the same way as dC in "
        f"{concordant} of {pairs} pairs."
    )


def within_b_concordance(members: list[Row]) -> tuple[int, int]:
    """Count (d, sf, truth B) pairs whose two C/B points move dC and dDq the same way."""
    groups: dict[tuple[int, bool, float | None], list[Row]] = defaultdict(list)
    for m in members:
        if not m.case.near_crossover:
            groups[m.case.d, m.case.sf, m.case.truth_b].append(m)
    concordant = pairs = 0
    for group in groups.values():
        if len(group) != len(CB_RATIOS):
            continue
        lo, hi = sorted(group, key=lambda m: m.case.truth_c or 0.0)
        step_c = (hi.d_c or 0.0) - (lo.d_c or 0.0)
        step_dq = (hi.d_dq or 0.0) - (lo.d_dq or 0.0)
        pairs += 1
        concordant += step_c * step_dq > 0
    return concordant, pairs


def findings_s4(rows: list[Row]) -> str:
    """Live numbers for S4: failing runs tagged infeasible_at_c, by origin."""
    tagged = [r for r in rows if is_failure(r) and r.values["infeasible_at_c"] == "True"]
    fit = [r for r in tagged if r.case.source == "synthetic" and r.run.path == "fit_spectrum"]
    near = sum(1 for r in fit if r.case.near_crossover)
    factors = Counter(
        round((r.case.truth_b or 0.0) / DEFAULTS[r.case.d]["default_B"], 2)
        for r in fit
        if not r.case.near_crossover
    )
    origin = ", ".join(f"{n} at {f:g} x default B" for f, n in sorted(factors.items()))
    jce = sorted({r.case.system for r in tagged if r.case.source == "jce2023"})
    return (
        f"Live: {len(tagged)} failing runs carry the tag, "
        f"{sum(1 for r in tagged if r.case.r1)} of them R1 rows that Section 6 leaves out "
        f"({len(fit)} synthetic fit_spectrum: "
        f"{origin}, {near} near-crossover). JCE systems with tagged runs: "
        f"{', '.join(jce) or 'none'}."
    )


def section_findings(rows: list[Row]) -> list[str]:
    """Render section 7: static interpretation plus the live numbers behind it."""
    return [
        "## 7. Findings",
        "",
        FINDINGS_STATIC["M"],
        "",
        FINDINGS_STATIC["S1"],
        findings_s1(rows),
        "",
        FINDINGS_STATIC["S2"],
        findings_s2(rows),
        "",
        FINDINGS_STATIC["S3"],
        findings_s3(rows),
        "",
        FINDINGS_STATIC["S4"],
        findings_s4(rows),
        "",
        FINDINGS_STATIC["design"],
        "",
    ]


def render_md(
    rows: list[Row],
    na_cells: list[str],
    defect: list[tuple[str, str, str, str, str, str, str]],
    self_test: int,
    jce_labels: list[str],
) -> str:
    """Assemble the whole report."""
    lines = [
        "# Fit-path audit, tanabesugano 2.1.0",
        "",
        (
            "Generated by `scripts/audit_fit_paths.py` (`poe audit-fit`); do not edit by "
            "hand. Per-run data: `audit/2.1.0/fit_audit.csv`."
        ),
        "",
    ]
    lines.extend(section_known_defect(defect, rows))
    lines.extend(section_method(na_cells, self_test, jce_labels))
    lines.extend(section_matrix(rows, na_cells))
    lines.extend(section_failures(rows))
    lines.extend(section_jce(rows, jce_labels))
    lines.extend(section_scope(rows))
    lines.extend(section_findings(rows))
    return "\n".join(lines)


def build() -> tuple[str, str]:
    """Run the whole audit and return ``(csv_text, md_text)``."""
    check_oracle_spelling()
    reverse, ratio = load_app_tools()
    defect = known_defect()
    synthetic, na_cells = synthetic_cases()
    self_test = truth_self_test(synthetic)
    jce = jce_cases()
    jce_labels = jce_label_check(jce)
    del reverse, ratio  # loaded once here for the grid check; each worker loads its own
    with multiprocessing.Pool(pool_size(), initializer=init_worker) as pool:
        per_case = pool.map(run_case_in_worker, [*synthetic, *jce], chunksize=4)
    rows: list[Row] = [row for case_rows in per_case for row in case_rows]
    attach_classes(rows)
    return render_csv(rows), render_md(rows, na_cells, defect, self_test, jce_labels)


def main() -> int:
    """Write the outputs, or with ``--check`` compare them and return 1 on drift."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the outputs drifted")
    args = parser.parse_args()
    csv_text, md_text = build()
    outputs = ((CSV_PATH, csv_text), (MD_PATH, md_text))
    if args.check:
        stale = [
            p for p, text in outputs if not p.exists() or p.read_text(encoding="utf-8") != text
        ]
        for path in stale:
            print(f"drift: {path.relative_to(REPO_ROOT)}")
        return 1 if stale else 0
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
