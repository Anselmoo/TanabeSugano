"""Numerics shared between the MCP tools layer and the plotting helper.

Wraps the existing tanabesugano.matrices solvers with light coercion so the
MCP layer never imports matplotlib (kept in plotting.py) or pydantic just to
crunch numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from typing import Literal
from typing import TypedDict

import numpy as np

from scipy.optimize import OptimizeResult
from scipy.optimize import linear_sum_assignment
from scipy.optimize import minimize

from tanabesugano.batch import ELECTRON_CONFIG_SOLVERS
from tanabesugano.constants import ElectronConfiguration
from tanabesugano.levels import LevelSet
from tanabesugano.plot_style import _TERM_RE


SUPPORTED_D_COUNTS: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8)


def _resolve_config(d_count: int) -> ElectronConfiguration:
    try:
        return ElectronConfiguration(d_count)
    except ValueError as exc:
        msg = f"d_count must be one of {SUPPORTED_D_COUNTS}; got {d_count}"
        raise ValueError(msg) from exc


def compute_point(d_count: int, Dq: float, B: float, C: float) -> dict[str, list[float]]:
    """Return term-symbol -> eigenvalues (in cm^-1) for a single (Dq, B, C) point."""
    cfg = _resolve_config(d_count)
    solver_class = ELECTRON_CONFIG_SOLVERS[cfg]
    states = solver_class(Dq=Dq, B=B, C=C).solver().as_dict()
    return {term: np.asarray(values).flatten().tolist() for term, values in states.items()}


def sweep_dq(
    d_count: int,
    dq_min: float,
    dq_max: float,
    steps: int,
    B: float,
    C: float,
) -> tuple[np.ndarray, list[dict[str, list[float]]]]:
    """Return (dq_values, list-of-term-dicts) sweeping Dq from dq_min to dq_max."""
    min_steps = 2
    if steps < min_steps:
        msg = "steps must be >= 2"
        raise ValueError(msg)
    cfg = _resolve_config(d_count)
    solver_class = ELECTRON_CONFIG_SOLVERS[cfg]
    dq_values = np.linspace(dq_min, dq_max, steps)
    points: list[dict[str, list[float]]] = []
    for dq in dq_values:
        states = solver_class(Dq=float(dq), B=B, C=C).solver().as_dict()
        points.append(
            {term: np.asarray(values).flatten().tolist() for term, values in states.items()},
        )
    return dq_values, points


# --- Shared ligand-field helpers -------------------------------------------------
#
# These exist because the ground term, the spin-allowed transition set and the
# residual metric were previously reimplemented (and diverged) in four places.
# Every fitting surface must go through these, not roll its own.

WEAK_FIELD_DQ_CM1: float = 10.0
"""Dq used to evaluate the high-spin (weak-field) reference ground term.

Not zero: at exactly Dq = 0 the octahedral splitting vanishes and several terms
are degenerate, so the argmin is ambiguous. A small positive Dq lifts the
degeneracy while staying deep in the weak-field regime. The resulting ground
term is independent of B (verified across B = 400..1400 for d2..d8).
"""

STRONG_FIELD_DQ_CM1: float = 6000.0
"""Dq used to evaluate the low-spin (strong-field) reference ground term."""

CROSSOVER_TOL_DQ_CM1: float = 0.05
"""Bisection half-width for the reported spin-crossover Dq, in cm^-1.

Set from the *display* precision, not measured from the solver: the critical
field is reported as delta = 10 * Dq rounded to whole cm^-1, so 0.05 in Dq
pins the last displayed digit. Costs ~16 extra solves (log2(3000 / 0.05)),
against the 100 the surrounding sweep already pays to draw the curves.
"""

SpinState = Literal["high", "low", "auto"]
ParameterProvenance = Literal["fitted", "given", "default", "undetermined"]
"""Where a reported Dq, B or C comes from.

``fitted``: determined by the bands. ``given``: the caller's value, held.
``default``: the per-configuration default, held. ``undetermined``: free in the fit,
but minima that fit the bands equally well (:data:`BAND_RESOLUTION_CM1`) disagree on
it beyond :data:`MINIMA_DISTINCT`; the reported value is one of them, for display.
Same rule as free-ion parentage: where the data cannot decide, nothing guesses.
"""


def term_multiplicity(term_key: str) -> int:
    """Return the spin multiplicity (2S+1) of an octahedral solver key.

    ``"3_T_1" -> 3``, ``"5_E" -> 5``.

    Raises
    ------
    ValueError
        If ``term_key`` is not an octahedral solver key -- in particular for
        free-ion notation such as ``"3F"`` or ``"6S"``. This is deliberate: an
        earlier version returned 0 on failure, and because free-ion strings were
        being passed in from ``DEFAULTS[d]["ground_term"]`` the resulting
        multiplicity comparison was silently never true. That disabled
        spin-allowed filtering in four separate tools without any error. Zero is
        not a valid multiplicity, so it can only ever mean a bug is being hidden.

    """
    match = _TERM_RE.match(term_key)
    if match is None:
        msg = (
            f"{term_key!r} is not an octahedral term key (expected e.g. '3_T_1'). "
            "Free-ion notation such as '3F' has no octahedral multiplicity; "
            "use reference_ground_term() to obtain a solver key instead."
        )
        raise ValueError(msg)
    return int(match.group("mult"))


def ground_term(term_energies: dict[str, list[float]]) -> tuple[str, float]:
    """Return ``(term_key, energy)`` of the lowest-lying level.

    The ground term is derived per point, never looked up from a table: it is
    genuinely Dq-dependent for d4/d6/d7 (d6 flips 5_T_2 -> 1_A_1 across the spin
    crossover), so any static per-d_count answer would be wrong physics.

    Never use ``next(iter(term_energies))`` for this -- dict insertion order is
    not energy order, and it names the wrong term for all seven configurations.
    """
    best_key: str | None = None
    best_energy = float("inf")
    for term_key in sorted(term_energies):  # sorted() makes ties deterministic
        for energy in term_energies[term_key]:
            value = float(energy)
            if value < best_energy:
                best_key, best_energy = term_key, value
    if best_key is None:
        msg = "term_energies is empty; cannot determine a ground term"
        raise ValueError(msg)
    return best_key, best_energy


def reference_ground_term(
    d_count: int,
    B: float,
    C: float,
    spin_state: SpinState = "high",
    Dq: float | None = None,
) -> str:
    """Return the ground-term key of the requested spin regime.

    ``"high"`` evaluates at :data:`WEAK_FIELD_DQ_CM1`, ``"low"`` at
    :data:`STRONG_FIELD_DQ_CM1`, and ``"auto"`` at the supplied ``Dq``.

    A fit pins itself to this reference so the optimizer cannot wander across a
    spin crossover. That matters because the low-spin manifolds are far denser
    than the high-spin ones (d5: 31 spin-allowed transitions vs 0), and a
    nearest-neighbour residual is minimised by a dense forest of candidate
    lines -- so an unconstrained search is actively rewarded for crossing over.
    """
    if spin_state == "auto":
        if Dq is None:
            msg = "spin_state='auto' requires an explicit Dq"
            raise ValueError(msg)
        probe_dq = float(Dq)
    elif spin_state == "high":
        probe_dq = WEAK_FIELD_DQ_CM1
    elif spin_state == "low":
        probe_dq = STRONG_FIELD_DQ_CM1
    else:
        msg = f"spin_state must be 'high', 'low' or 'auto'; got {spin_state!r}"
        raise ValueError(msg)
    return ground_term(compute_point(d_count, probe_dq, B, C))[0]


def transition_candidates(
    term_energies: dict[str, list[float]],
    *,
    spin_allowed_only: bool = True,
    min_energy_cm1: float = 1.0,
) -> tuple[str, list[tuple[float, str, bool]]]:
    """Return ``(ground_term_key, [(delta_E, assignment, spin_allowed), ...])``.

    Energies are measured from the lowest-lying level, and the assignment string
    names the real ground term -- both previously taken from whichever key
    happened to be first in the solver's dict.

    Assignments are per-LEVEL, not per-term. A term that contributes several
    levels contributes several bands, and they used to come back under one
    shared string: d8 nu2 and nu3 both read ``3_A_2→3_T_1``, so the two most
    commonly reported bands in the whole package were indistinguishable. The
    :class:`~tanabesugano.levels.LevelSet` supplies the multiplet ordinal, and
    suppresses it for terms holding a single level.

    Built with :meth:`LevelSet.from_states`, which does no extra solving:
    this runs inside the fitting objective, thousands of times per fit.
    """
    ground_key, _ground_energy = ground_term(term_energies)
    ground_mult = term_multiplicity(ground_key)
    manifold = LevelSet.from_states(term_energies)

    candidates: list[tuple[float, str, bool]] = []
    for level in manifold.levels:
        allowed = level.multiplicity == ground_mult
        if spin_allowed_only and not allowed:
            continue
        if level.energy_cm1 > min_energy_cm1:
            candidates.append(
                (level.energy_cm1, manifold.transition_label(level), allowed),
            )
    return ground_key, sorted(candidates)


SPIN_ALLOWED_INTENSITY = 1.0
SPIN_FORBIDDEN_INTENSITY = 0.05
"""Relative oscillator strength of a spin-forbidden vs a spin-allowed d-d band.

A crude single number for a real selection rule, but the right order of
magnitude and the one this package already drew with: spin-forbidden bands run
one to two orders of magnitude weaker, which is why high-spin d5 -- whose every
d-d transition is forbidden, there being exactly one sextet in the whole
configuration -- gives Mn(II) its famously pale pink.

Named here rather than inline so the spectrum and landscape surfaces cannot
drift apart on what "weak" means.
"""

C_PROBE_FRACTION = 0.05
"""How far Racah C is nudged either way when testing whether it matters."""

C_SENSITIVITY_TOL_CM1 = 1.0
"""Band shift below which a C perturbation counts as having done nothing.

Far above float noise (the solver reproduces a level to ~1e-9 cm^-1) and far
below any real dependence, which runs to hundreds of cm^-1.
"""


def c_constrains_manifold(
    d_count: int,
    Dq: float,
    B: float,
    C: float,
    *,
    spin_allowed_only: bool = True,
) -> bool:
    """Whether the fitted band set actually moves when Racah C moves.

    Answered by measurement rather than by a per-configuration table, because
    the honest answer is not a property of the configuration alone. Sweeping C
    over 3000-5200 at Dq in {400 .. 2600} and B in {700 .. 1300}: d2, d3 and d8
    are C-independent *everywhere*, while d4, d5, d6 and d7 acquire
    C-dependence only past their spin crossover -- where the spin-allowed set
    becomes the low-spin manifold, whose matrix elements do carry C. A lookup
    keyed on ``d_count`` would therefore be wrong on one side of the crossover
    whichever value it stored, which is the same trap the hand-maintained
    ground-term table fell into.

    A change in the *number* of candidate bands counts as dependence too: it
    means the perturbation moved the ground term, which is as C-sensitive as an
    outcome gets.
    """

    def band_energies(c_value: float) -> list[float]:
        _ground, candidates = transition_candidates(
            compute_point(d_count, Dq, B, c_value),
            spin_allowed_only=spin_allowed_only,
        )
        return [energy for energy, _label, _allowed in candidates]

    baseline = band_energies(C)
    for probe in (C * (1.0 - C_PROBE_FRACTION), C * (1.0 + C_PROBE_FRACTION)):
        shifted = band_energies(probe)
        if len(shifted) != len(baseline):
            return True
        if any(abs(a - b) > C_SENSITIVITY_TOL_CM1 for a, b in zip(baseline, shifted, strict=True)):
            return True
    return False


def peak_rmse(observed: np.ndarray, predicted: np.ndarray) -> float:
    """RMSE of every observed peak against its nearest predicted line.

    There is deliberately no tolerance gate. The previous implementation only
    accumulated error for peaks within 500 cm^-1 of a prediction *and* divided
    by that matched count, so unmatched peaks left both the numerator and the
    denominator -- making "match one peak perfectly and ignore the rest" score
    an unbeatable 0.0. Every observed peak must contribute to both.
    """
    if observed.size == 0:
        msg = "observed must contain at least one peak"
        raise ValueError(msg)
    if predicted.size == 0:
        msg = "predicted must contain at least one transition"
        raise ValueError(msg)
    deltas = np.abs(predicted[None, :] - observed[:, None]).min(axis=1)
    return float(np.sqrt(np.mean(deltas**2)))


def closed_form_dq_b(d_count: int, observed_peaks_cm1: list[float]) -> tuple[float, float]:
    """Exact analytic (Dq, B) from three spin-allowed bands, for d3 and d8 only.

    ``Dq = nu1 / 10`` and ``B = (nu3 + nu2 - 3*nu1) / 15``.

    This is how the published values are actually derived: it reproduces the
    literature pairs for [Ni(H2O)6]2+ (850, 907), [Cr(H2O)6]3+ (1700, 667) and
    [Ni(NH3)6]2+ (1075, 897) exactly. It is used as the optimizer seed, and is
    worth reporting alongside the least-squares answer because the two differ
    whenever the observed bands are not mutually consistent with a single
    (Dq, B) -- the closed form honours nu1 exactly and pushes all residual into
    nu2/nu3, while least-squares redistributes it.

    Restricted to d3 and d8 because both have an orbitally non-degenerate
    ground term (4A2g / 3A2g) for which nu1 = 10Dq holds exactly. d2 and d7
    have T1g ground terms where nu1 != 10Dq, so the formula does not apply.
    """
    closed_form_configs = (3, 8)
    required_peaks = 3
    if d_count not in closed_form_configs:
        msg = (
            f"closed_form_dq_b is only valid for d3 and d8 (got d{d_count}). "
            "Other configurations have orbitally degenerate ground terms where "
            "nu1 != 10Dq."
        )
        raise ValueError(msg)
    if len(observed_peaks_cm1) < required_peaks:
        msg = f"closed form needs {required_peaks} bands; got {len(observed_peaks_cm1)}"
        raise ValueError(msg)
    nu1, nu2, nu3 = sorted(float(p) for p in observed_peaks_cm1)[:required_peaks]
    return nu1 / 10.0, (nu3 + nu2 - 3.0 * nu1) / 15.0


DQ_BOUNDS_SEED_SPAN = (0.2, 5.0)
"""Default Dq bounds as multiples of the seed, the historical window."""

DQ_BOUNDS_BAND_SPAN = (0.005, 0.25)
"""Default Dq bounds as fractions of the highest observed band.

The seed span alone fails whenever the lowest band is a weak low-lying
spin-forbidden level: ``min(obs) / 10`` then sits far below the real Dq, and the
fit-path audit found four cases whose truth lay above ``5 * dq_seed``. The band
span reads only the observed bands, never a reference value. It is the span the
B6 ablation widened to: it contains every audited truth, and a lone d3/d8 nu1
(Dq = nu1 / 10) sits well inside it. It is an empirical window, not a bound
derived from the Hamiltonian.
"""


def default_dq_bounds(observed_peaks_cm1: Sequence[float], dq_seed: float) -> tuple[float, float]:
    """Return the default ``dq_bounds``: the seed window widened by the band span."""
    top = max(observed_peaks_cm1)
    return (
        min(DQ_BOUNDS_SEED_SPAN[0] * dq_seed, DQ_BOUNDS_BAND_SPAN[0] * top),
        max(DQ_BOUNDS_SEED_SPAN[1] * dq_seed, DQ_BOUNDS_BAND_SPAN[1] * top),
    )


@dataclass(frozen=True)
class SpectrumFit:
    """Result of fitting observed absorption bands to (Dq, B).

    ``transitions`` carries every term (not only the fitted spin-allowed ones)
    with an ``spin_allowed`` flag, so the assignment table loses no information.
    ``warnings`` collects soft signals -- a pinned parameter, a large residual,
    an unidentifiable B -- that are worth surfacing but must not fail the fit.

    ``C`` is reported beside ``Dq`` and ``B`` but is never optimised, so on its
    own it is indistinguishable from a fitted quantity: two unrelated complexes
    come back with byte-identical C and nothing says why. Two flags separate
    the questions that conflation hides. ``c_is_default`` is bookkeeping --
    whether the value came from the per-configuration defaults or from the
    caller. ``c_constrained`` is the physical one -- whether the observed bands
    could have pinned C at all, measured per fit by
    :func:`c_constrains_manifold` rather than assumed from ``d_count``.
    ``c_fitted`` says whether C was a free parameter of this fit (see the
    ``fit_c`` argument of :func:`fit_spectrum`); when it is True, ``C`` is a
    result, not an input.

    ``minima`` lists every distinct minimum the search converged to, as
    ``(Dq, B, C, objective)``: the returned point first, then the others by
    objective (cm^-1, label penalties included). It lists what the search reached,
    not necessarily every minimum that exists.

    ``dq_provenance``, ``b_provenance`` and ``c_provenance`` say where each value
    comes from (:data:`ParameterProvenance`). A parameter is ``undetermined`` when
    the minima within :data:`BAND_RESOLUTION_CM1` of the best objective disagree on
    it by more than :data:`MINIMA_DISTINCT`. ``c_candidates`` then holds those tied
    minima and ``c_range`` their (lowest, highest) C; when C is undetermined the
    reported point is the best-objective one, a display value, not a result.

    ``assignment`` is the pairing the fit made, one ``(observed, computed, level_uid)``
    per band in the caller's order: the injective :func:`assign_bands` result at the
    returned point. Anything that names the level a band was fitted to reads it
    here; a nearest-line search would disagree whenever two bands crowd one level.
    """

    Dq: float
    B: float
    C: float
    rmse_cm1: float
    ground_term: str
    spin_state: SpinState
    transitions: list[tuple[float, str, bool]]
    residuals_cm1: list[float]
    warnings: list[str]
    c_is_default: bool
    c_constrained: bool
    c_fitted: bool = False
    minima: tuple[tuple[float, float, float, float], ...] = ()
    dq_provenance: ParameterProvenance = "fitted"
    b_provenance: ParameterProvenance = "fitted"
    c_provenance: ParameterProvenance = "default"
    c_candidates: tuple[tuple[float, float, float, float], ...] = ()
    c_range: tuple[float, float] | None = None
    assignment: tuple[tuple[float, float, str], ...] = ()


def crossover_dq(
    d_count: int,
    B: float,
    C: float,
    reference: str,
    *,
    hi: float = STRONG_FIELD_DQ_CM1,
    tol: float = 1.0,
) -> float:
    """Lowest Dq at which ``reference`` is the ground term, by bisection.

    Two consumers: seeding a low-spin fit above the spin crossover (seeding
    below it would start the optimizer where the spin-regime constraint rejects
    every step), and reporting the critical Dq in ``ts_spin_crossover_app``.

    ``reference`` must be the *strong-field* ground term, obtained at a Dq where
    the field is large. Anchoring instead on "the ground term has changed since
    Dq = 0" does not work: at Dq = 0 the ligand field vanishes, so every
    crystal-field component of the free-ion ground term is exactly degenerate
    and :func:`ground_term`'s ``sorted()`` tie-break names an arbitrary one of
    them (d6 reports ``5_E``, not the weak-field ``5_T_2``). Such a predicate
    fires at the first step above zero and returns a crossover of ~0.

    Returns ``hi`` unchanged when ``reference`` is not the ground term there,
    i.e. when there is no crossover at or below ``hi``.
    """
    lo = 0.0
    if ground_term(compute_point(d_count, hi, B, C))[0] != reference:
        return hi
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if ground_term(compute_point(d_count, mid, B, C))[0] == reference:
            hi = mid
        else:
            lo = mid
    return hi


SEARCH_GRID_NODES = (12, 4)
"""Dq x B nodes of the start grid, log-spaced over ``dq_bounds`` and ``b_bounds``.

Every node is refined, none is ranked away. Measured on the 208-case synthetic
audit matrix at the true C (plan C0m, private prototype): 186 recovered with no
previously recovered case lost; 185 in the shipped fit, whose nearest-seed
tie-break returns the seed's B on one single-band case. Keeping only the six best of a finer 24 x 6 grid recovered
174 and lost 7, because a coarse node's objective does not predict which basin
holds the truth.
"""

CROSSOVER_START_FACTORS = (0.9, 1.1)
"""Extra Dq starts either side of the spin crossover at the seed's B."""


TIE_RMSE_CM1 = 1.0
"""Minima whose objective is within this of the best count as tied.

The scale of ``C_SENSITIVITY_TOL_CM1``: far above the optimizer's ``fatol`` and far
below any band-position difference a spectrum can resolve.
"""


def _pick_minimum(
    results: Sequence[OptimizeResult], seed: tuple[float, float], *, determined: bool
) -> OptimizeResult:
    """Return the lowest minimum; if the data cannot choose, the tied one nearest the seed.

    ``determined`` is True when there are more bands than free parameters. Then the
    lowest objective wins outright: on oracle d4 low-spin three bands the truth fits
    to 0.001 cm^-1 and a seed-nearer point to 0.09, both inside ``TIE_RMSE_CM1``,
    and the bands do discriminate. With as many bands as free parameters or fewer,
    several assignments fit exactly and the data cannot choose. Nearest-to-seed (log distance in Dq and B) is a convention
    chosen by the maintainer: it restores the textbook answer the old local-start
    fit returned by accident (two-band [Co(H2O)6]2+), and it keeps the choice
    deterministic. It is not a physical argument.
    """
    # A run that did not converge must not win over a converged one at a similar
    # objective, which would make the fit raise although a converged run got there.
    results = [r for r in results if r.success] or list(results)
    lowest = min(float(r.fun) for r in results)
    if determined:
        return min(results, key=lambda r: float(r.fun))
    tied = [r for r in results if float(r.fun) <= lowest + TIE_RMSE_CM1]
    log_seed = np.log(np.asarray(seed, dtype=float))

    def distance(result: OptimizeResult) -> float:
        point = np.asarray(result.x[:2], dtype=float)
        if np.any(point <= 0):
            return float("inf")
        return float(np.linalg.norm(np.log(point) - log_seed))

    # min() keeps the first of equal distances, i.e. start order, so ties stay stable.
    return min(tied, key=distance)


MINIMA_DISTINCT = (0.02, 0.05, 0.05)
"""Relative Dq, B, C differences above which two minima count as distinct.

The audit's recovery tolerances: two minima closer than this in every parameter
would grade as the same answer.
"""


def _distinct_minima(
    results: Sequence[OptimizeResult],
    best: OptimizeResult,
    C: float,
    *,
    ceiling: float,
) -> tuple[tuple[float, float, float, float], ...]:
    """Return ``(Dq, B, C, objective)`` of each distinct converged minimum.

    A run counts if it converged and escaped the penalty region (objective below
    ``ceiling``). ``best``, the point actually returned, comes first, so a
    near-duplicate never displaces it; the others follow by objective.
    """

    def point(r: OptimizeResult) -> tuple[float, float, float, float]:
        c = float(r.x[2]) if len(r.x) > 2 else C
        return (float(r.x[0]), float(r.x[1]), c, float(r.fun))

    converged = sorted(
        (r for r in results if r.success and float(r.fun) < ceiling), key=lambda r: float(r.fun)
    )
    kept = [point(best)]
    for candidate in map(point, converged):
        if all(
            any(abs(a / b - 1) > tol for a, b, tol in zip(candidate[:3], k[:3], MINIMA_DISTINCT))
            for k in kept
        ):
            kept.append(candidate)
    return (kept[0], *sorted(kept[1:], key=lambda m: m[3]))


def _undetermined(
    minima: Sequence[tuple[float, float, float, float]],
) -> tuple[list[tuple[float, float, float, float]], tuple[bool, bool, bool]]:
    """Return the minima tied with the best, and per (Dq, B, C) whether they disagree.

    Tied: objective within :data:`BAND_RESOLUTION_CM1` of the lowest, i.e. no
    spectrum could tell them apart. Disagree: spread (max / min - 1) above
    :data:`MINIMA_DISTINCT`.
    """
    lowest = min(m[3] for m in minima)
    tied = [m for m in minima if m[3] <= lowest + BAND_RESOLUTION_CM1]
    open_ = tuple(
        max(m[k] for m in tied) / min(m[k] for m in tied) - 1 > MINIMA_DISTINCT[k] for k in range(3)
    )
    return tied, (open_[0], open_[1], open_[2])


def _local_starts(dq_seed: float, b_seed: float) -> list[tuple[float, float]]:
    """Return the five starts around the seed: itself, Dq x 0.8 / 1.25, B x 0.7 / 1.2."""
    return [
        (dq_seed, b_seed),
        (0.8 * dq_seed, b_seed),
        (1.25 * dq_seed, b_seed),
        (dq_seed, 0.7 * b_seed),
        (dq_seed, 1.2 * b_seed),
    ]


def _search_starts(
    d_count: int,
    C: float,
    dq_seed: float,
    b_seed: float,
    dq_bounds: tuple[float, float],
    b_bounds: tuple[float, float],
) -> list[tuple[float, float]]:
    """Return every Nelder-Mead start: the grid, the five local starts, the crossover pair."""
    n_dq, n_b = SEARCH_GRID_NODES
    starts = [
        (float(dq), float(b))
        for dq in np.geomspace(*dq_bounds, n_dq)
        for b in np.geomspace(*b_bounds, n_b)
    ]
    starts += _local_starts(dq_seed, b_seed)
    # The order C0m measured with. With the tie-break in _pick_minimum it matters
    # only between runs tied at the same distance from the seed.
    low_spin_ground = reference_ground_term(d_count, b_seed, C, "low")
    crossover = crossover_dq(d_count, b_seed, C, low_spin_ground)
    if crossover < STRONG_FIELD_DQ_CM1:
        starts += [(f * crossover, b_seed) for f in CROSSOVER_START_FACTORS]
    return starts


C_OVER_B_WINDOW = (3.0, 6.0)
"""Admissible Racah C/B while C is fitted; outside it the objective is penalised.

The per-configuration defaults in ``_defaults.py`` (free-ion C and B from
Tanabe & Sugano's original parametrisation) put C/B at 4.42-4.81 for every d2-d8,
and the window brackets that by a factor of about 1.5 either side. It was not
tuned on the audit. Widening it is not free: at (2, 8) a labelled d5 high-spin
spectrum near the crossover admits a second exact minimum at C/B 2.25 (plan B7,
objection O2(iii)). A fit that lands on an edge is warned about, because there C
was stopped by the window, not by the bands.
"""

FREE_C_GRID_NODES = (24, 6)
"""Dq x B nodes of the free-C scan grid, log-spaced over the bounds."""

FREE_C_GRID_RATIOS = (3.5, 4.5, 5.5)
"""C/B values of the free-C scan grid: C = ratio * B at each (Dq, B) node."""

FREE_C_GRID_KEEP = 6
"""How many scan nodes are refined when C is free.

Refining every node, as at held C, costs 3 x 151 Nelder-Mead runs in three
dimensions (17.5 s worst case in plan C0m). Keeping the six best nodes pairwise
more than one (Dq, B) step apart recovered 186 of the 208 audit cases with C free
and labels given in the C0m prototype (184 in the shipped fit), lost none recovered
at held C, and took at most 2.0 s. This is
measured only for labelled fits, which is the only case that frees C by default.
"""


def _free_c_starts(
    objective: Callable[[np.ndarray], float],
    dq_bounds: tuple[float, float],
    b_bounds: tuple[float, float],
    local: Sequence[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Return the free-C starts: the best spread-out scan nodes, then the local starts."""
    n_dq, n_b = FREE_C_GRID_NODES
    nodes = {
        (i, j, k): (float(dq), float(b), float(ratio * b))
        for i, dq in enumerate(np.geomspace(*dq_bounds, n_dq))
        for j, b in enumerate(np.geomspace(*b_bounds, n_b))
        for k, ratio in enumerate(FREE_C_GRID_RATIOS)
    }
    values = {key: objective(np.asarray(x)) for key, x in nodes.items()}
    kept: list[tuple[int, int, int]] = []
    # Separation is measured in (Dq, B) steps only: two ratios at one node are one start.
    for key in sorted(nodes, key=lambda k: (values[k], k)):
        if all(max(abs(key[0] - q[0]), abs(key[1] - q[1])) > 1 for q in kept):
            kept.append(key)
        if len(kept) == FREE_C_GRID_KEEP:
            break
    return [nodes[key] for key in kept] + list(local)


def _initial_seed(
    d_count: int, observed_sorted: list[float], *, include_spin_forbidden: bool
) -> tuple[float, float]:
    """Return the (Dq, B) seed: the d3/d8 closed form where it applies, else (obs[0]/10, B0).

    The closed form reads the lowest three bands as nu1..nu3. With spin-forbidden
    bands in the list one of those can be a doublet or singlet (d8: 1_E sits
    between nu2 and nu3), and the seed is then built from the wrong level, so it
    is used only for spin-allowed fits. One function, so the audit can displace
    the seed on every path by patching a single name.
    """
    from tanabesugano.mcp._defaults import DEFAULTS

    if not include_spin_forbidden:
        try:
            return closed_form_dq_b(d_count, observed_sorted)
        except ValueError:
            pass  # not d3/d8, or fewer than three bands -- generic seed stands
    return observed_sorted[0] / 10.0, float(DEFAULTS[d_count]["default_B"])


BandLabel = str | Sequence[str] | None
"""One band's label: a term key (``4_T_1``, any level of that term), a level uid
(``4_T_1#1``), several of either (a band covering near-degenerate levels, e.g.
``("4_E", "4_A_1")``), or ``None`` for an unlabelled band."""


def excited_levels(
    term_energies: dict[str, list[float]], *, spin_allowed_only: bool
) -> tuple[str, list[tuple[float, str]]]:
    """Return ``(ground_key, [(energy, uid), ...])`` for the levels a band can land on.

    The same filter as :func:`transition_candidates` (multiplicity of the ground
    term unless ``spin_allowed_only`` is False, energy above 1 cm^-1), keyed by
    :attr:`Level.uid` so a label can be checked against it.
    """
    ground_key, _ground_energy = ground_term(term_energies)
    ground_mult = term_multiplicity(ground_key)
    levels = [
        (level.energy_cm1, level.uid)
        for level in LevelSet.from_states(term_energies).levels
        if (not spin_allowed_only or level.multiplicity == ground_mult) and level.energy_cm1 > 1.0
    ]
    return ground_key, sorted(levels)


def _score_point(
    d_count: int,
    observed: np.ndarray,
    labels: Sequence[tuple[str, ...] | None] | None,
    point: tuple[float, float, float],
    *,
    reference: str,
    spin_allowed_only: bool,
    penalty: float,
) -> float | None:
    """The fit objective at one (Dq, B, C): band RMSE under the injective assignment.

    ``observed`` is sorted and ``labels`` normalised and in the same order. Returns
    None when the point is outside the regime the fit is pinned to -- the ground
    term is not ``reference``, or there are fewer levels than bands. Refusing those
    matters: the low-spin manifolds are far denser (d5: 31 lines vs 0), and a dense
    forest of candidates fits any band list, so a search that scored them would be
    rewarded for ending up in the wrong regime. Solver errors propagate.
    """
    dq, b, c = point
    found_ground, levels = excited_levels(
        compute_point(d_count, dq, b, c), spin_allowed_only=spin_allowed_only
    )
    if found_ground != reference or len(levels) < observed.size:
        return None
    return assign_bands(observed, levels, labels, penalty=penalty)[1]


def fit_objective(
    d_count: int,
    observed_peaks_cm1: Sequence[float],
    Dq: float,
    B: float,
    C: float,
    *,
    spin_state: SpinState = "high",
    include_spin_forbidden: bool = False,
    band_labels: Sequence[BandLabel] | None = None,
) -> float | None:
    """Score one (Dq, B, C) exactly as :func:`fit_spectrum` scores it (cm^-1).

    For a landscape or a diagnostic grid: the same assignment, label penalty and
    regime pin as the fit, so a grid drawn from it cannot rank points differently
    from the fit. Returns None for a point outside the requested spin regime or one
    the solver cannot evaluate. Not a fit: nothing here searches.
    """
    order = sorted(range(len(observed_peaks_cm1)), key=lambda i: float(observed_peaks_cm1[i]))
    observed = np.asarray([float(observed_peaks_cm1[i]) for i in order], dtype=float)
    labels = None
    if band_labels is not None:
        normalised = _normalise_labels(band_labels, len(observed_peaks_cm1))
        labels = [normalised[i] for i in order]
    if Dq <= 0 or B <= 0 or C <= 0:
        return None
    try:
        return _score_point(
            d_count,
            observed,
            labels,
            (Dq, B, C),
            reference=reference_ground_term(d_count, B, C, spin_state),
            spin_allowed_only=not include_spin_forbidden,
            penalty=float(np.sqrt(np.mean(observed**2))),
        )
    except (ValueError, KeyError, np.linalg.LinAlgError):
        return None


def _label_matches(uid: str, label: tuple[str, ...]) -> bool:
    """Whether a level uid satisfies one band's label (term key or exact uid)."""
    term = uid.split("#", maxsplit=1)[0]
    return any(lab in {uid, term} for lab in label)


def assign_bands(
    observed: np.ndarray,
    levels: Sequence[tuple[float, str]],
    labels: Sequence[tuple[str, ...] | None] | None,
    *,
    penalty: float,
) -> tuple[np.ndarray, float]:
    """Assign each observed band to a distinct level; return the level indices and the cost.

    Injective: two bands can no longer share one level, which nearest-line matching
    allowed and which let a dense manifold absorb several bands at once. A band
    whose label the level does not satisfy pays ``penalty**2`` on top of its squared
    distance, so a label steers the assignment without making the objective
    discontinuous. The cost is an RMSE over bands, penalties included.
    """
    predicted = np.asarray([e for e, _uid in levels], dtype=float)
    cost = (observed[:, None] - predicted[None, :]) ** 2
    if labels is not None:
        mismatch = np.array(
            [
                [label is not None and not _label_matches(uid, label) for _e, uid in levels]
                for label in labels
            ],
            dtype=bool,
        )
        cost = cost + np.where(mismatch, penalty**2, 0.0)
    rows, columns = linear_sum_assignment(cost)
    return columns[np.argsort(rows)], float(np.sqrt(cost[rows, columns].mean()))


def _normalise_labels(
    band_labels: Sequence[BandLabel], n_bands: int
) -> list[tuple[str, ...] | None]:
    """Return one tuple of label strings (or None) per band; raise on a count mismatch."""
    if len(band_labels) != n_bands:
        msg = f"band_labels needs one label per band: {len(band_labels)} for {n_bands} bands"
        raise ValueError(msg)
    out: list[tuple[str, ...] | None] = []
    for label in band_labels:
        if label is None:
            out.append(None)
        elif isinstance(label, str):
            out.append((label,))
        else:
            out.append(tuple(label))
    return out


def fit_spectrum(
    d_count: int,
    observed_peaks_cm1: list[float],
    C: float | None = None,
    *,
    spin_state: SpinState = "high",
    include_spin_forbidden: bool = False,
    dq_bounds: tuple[float, float] | None = None,
    b_bounds: tuple[float, float] = (200.0, 1500.0),
    band_labels: Sequence[BandLabel] | None = None,
    fit_c: bool | None = None,
) -> SpectrumFit:
    """Fit observed absorption peaks to determine Dq and Racah B.

    Raises ``ValueError`` rather than returning a sentinel when the problem is
    ill-posed or the optimizer fails to reach a physically valid minimum; the
    MCP layer converts that into a structured ``ComputeError``.

    Parameters
    ----------
    d_count:
        d-electron count, 2..8.
    observed_peaks_cm1:
        Measured band maxima in cm^-1. All must be positive.
    C:
        Racah C. Defaults to the per-configuration value. Note the spin-allowed
        manifold of d2 and d8 is independent of C, so it has no effect there.
    spin_state:
        Which side of the spin crossover to fit on. The fit is pinned to this
        regime; see :func:`reference_ground_term`.
    include_spin_forbidden:
        Fit against spin-forbidden transitions too. Required for high-spin d5,
        whose d-d bands are *all* spin-forbidden.
    dq_bounds:
        Defaults to :func:`default_dq_bounds`: the seed window
        ``(0.2, 5) * dq_seed`` widened to ``(0.005, 0.25) * max(observed)``. The lower bound must stay
        strictly positive: the solver silently returns corrupted energies for
        Dq < 0 (the ground level stops being the zero point) with no error.
    band_labels:
        One :data:`BandLabel` per observed band, in the order given.
    fit_c:
        Whether Racah C is fitted alongside Dq and B, inside
        :data:`C_OVER_B_WINDOW`. An explicit ``C`` is always held. ``None`` (the
        default) frees C when at least three bands are given and every one is
        labelled: unlabelled, a high-spin d5 spectrum has 37-60 exact (Dq, B, C)
        minima, and two labelled bands still leave a one-parameter family.
        ``True`` frees C regardless and warns when that gate is not met. If C
        turns out not to move the fitted bands, the fit is redone with C held at
        its default and says so.

    """
    fit = _fit_one_regime(
        d_count,
        observed_peaks_cm1,
        C,
        spin_state=spin_state,
        include_spin_forbidden=include_spin_forbidden,
        dq_bounds=dq_bounds,
        b_bounds=b_bounds,
        band_labels=band_labels,
        fit_c=fit_c,
    )
    other = _other_regime_fit(
        d_count,
        observed_peaks_cm1,
        C,
        spin_state=spin_state,
        include_spin_forbidden=include_spin_forbidden,
        b_bounds=b_bounds,
        band_labels=band_labels,
        fit_c=fit_c,
    )
    if other is not None and other.rmse_cm1 <= max(fit.rmse_cm1, BAND_RESOLUTION_CM1):
        note = (
            f"the {other.spin_state}-spin regime also fits these bands: Dq = {other.Dq:.0f}, "
            f"B = {other.B:.0f} cm^-1, ground term {other.ground_term}, RMSE "
            f"{other.rmse_cm1:.0f} cm^-1 (this fit: {fit.rmse_cm1:.0f}); the bands alone do "
            "not decide the spin state"
        )
        return replace(fit, warnings=[*fit.warnings, note])
    return fit


BAND_RESOLUTION_CM1 = 100.0
"""How well a broad d-d band maximum is located; RMSE differences below it are not evidence.

Two uses: minima within it of the best count as tied when deciding whether a
parameter is undetermined (:data:`ParameterProvenance`), and the other spin regime
counts as also fitting when it comes within it. On the 134 audit fits that free C,
it marks C undetermined on 10, including both whose C is off by more than 5 %;
1 cm^-1 marks 4.

d-d bands run 2000-4000 cm^-1 wide, and their maxima are rarely quoted better
than about +-100 cm^-1. A fit in the other spin regime whose RMSE is within this
(or within this fit's own RMSE, if larger) fits as well as any spectrum can tell.
Set by that physical scale, not on the audit: on its oracle (noise-free) d4-d7
cases the other regime comes within 50 cm^-1 on 11 of 111 unlabelled cases and
on none labelled, where the labels themselves decide the regime.
"""


def _other_regime_fit(
    d_count: int,
    observed_peaks_cm1: list[float],
    C: float | None,
    *,
    spin_state: SpinState,
    include_spin_forbidden: bool,
    b_bounds: tuple[float, float],
    band_labels: Sequence[BandLabel] | None,
    fit_c: bool | None,
) -> SpectrumFit | None:
    """Fit the same bands in the other spin regime, or return None where there is none.

    Only d4-d7 have two regimes, and only where the crossover lies below
    ``STRONG_FIELD_DQ_CM1`` at the default B (and the caller's C, else the default)
    is the other one reachable.
    The default ``dq_bounds`` are used, since the caller's were chosen for one regime.
    """
    from tanabesugano.mcp._defaults import DEFAULTS

    if d_count not in {4, 5, 6, 7}:
        return None
    b0 = float(DEFAULTS[d_count]["default_B"])
    c0 = float(DEFAULTS[d_count]["default_C"]) if C is None else C
    if crossover_dq(d_count, b0, c0, reference_ground_term(d_count, b0, c0, "low")) >= (
        STRONG_FIELD_DQ_CM1
    ):
        return None
    other: SpinState = "low" if spin_state == "high" else "high"
    try:
        return _fit_one_regime(
            d_count,
            observed_peaks_cm1,
            C,
            spin_state=other,
            include_spin_forbidden=include_spin_forbidden,
            b_bounds=b_bounds,
            band_labels=band_labels,
            fit_c=fit_c,
        )
    except ValueError:
        return None  # the other regime cannot carry these bands (or labels) at all


def _fit_one_regime(
    d_count: int,
    observed_peaks_cm1: list[float],
    C: float | None = None,
    *,
    spin_state: SpinState = "high",
    include_spin_forbidden: bool = False,
    dq_bounds: tuple[float, float] | None = None,
    b_bounds: tuple[float, float] = (200.0, 1500.0),
    band_labels: Sequence[BandLabel] | None = None,
    fit_c: bool | None = None,
) -> SpectrumFit:
    """Fit in the requested spin regime only; :func:`fit_spectrum` adds the regime check."""
    from tanabesugano.mcp._defaults import DEFAULTS

    if not observed_peaks_cm1:
        msg = "at least one observed peak is required"
        raise ValueError(msg)
    if any(p <= 0 for p in observed_peaks_cm1):
        msg = f"observed peaks must all be positive; got {observed_peaks_cm1}"
        raise ValueError(msg)

    c_is_default = C is None
    if C is None:
        C = float(DEFAULTS[d_count]["default_C"])
    labels = (
        None if band_labels is None else _normalise_labels(band_labels, len(observed_peaks_cm1))
    )
    identified = (
        len(observed_peaks_cm1) >= 3
        and labels is not None
        and all(label is not None for label in labels)
    )
    free_c = c_is_default and (identified if fit_c is None else fit_c)
    order = sorted(range(len(observed_peaks_cm1)), key=lambda i: float(observed_peaks_cm1[i]))
    observed = np.asarray([float(observed_peaks_cm1[i]) for i in order], dtype=float)
    if labels is not None:
        labels = [labels[i] for i in order]
    warnings: list[str] = []
    if free_c and not identified:
        warnings.append(
            "C is fitted (fit_c=True) without three or more labelled bands: such a "
            "spectrum is matched exactly by many (Dq, B, C), so the returned C is one "
            "of them, not a determination",
        )

    # --- Seed ---------------------------------------------------------------
    # The seed adds local starts beside the grid. For d3/d8 spin-allowed fits it
    # is the closed form, which gives both parameters analytically.
    dq_seed, b_seed = _initial_seed(
        d_count, observed.tolist(), include_spin_forbidden=include_spin_forbidden
    )
    if not b_bounds[0] <= b_seed <= b_bounds[1]:
        b_seed = min(max(b_seed, b_bounds[0]), b_bounds[1])

    if dq_bounds is None:
        dq_bounds = default_dq_bounds(observed.tolist(), dq_seed)
    if dq_bounds[0] <= 0:
        msg = f"dq_bounds lower limit must be > 0 (Dq <= 0 corrupts the solver); got {dq_bounds}"
        raise ValueError(msg)

    # --- Feasibility --------------------------------------------------------
    reference = reference_ground_term(d_count, b_seed, C, spin_state)
    spin_allowed_only = not include_spin_forbidden

    # Probe feasibility at a Dq where the requested regime actually holds, NOT
    # at the seed. For low-spin the seed (min(obs)/10) can fall below the spin
    # crossover -- e.g. [Co(NH3)6]3+ seeds at Dq ~ 2110 where d6 is still
    # high-spin with a single band, so a perfectly valid low-spin fit was
    # refused while the message quoted the low-spin term's name.
    probe_dq = dq_seed
    if ground_term(compute_point(d_count, probe_dq, b_seed, C))[0] != reference:
        probe_dq = STRONG_FIELD_DQ_CM1 if spin_state == "low" else WEAK_FIELD_DQ_CM1
        # Seed the search inside the requested regime too, otherwise the
        # optimizer starts where the spin-regime constraint rejects every step.
        if spin_state == "low":
            dq_seed = max(dq_seed, crossover_dq(d_count, b_seed, C, reference))
    _, seed_candidates = transition_candidates(
        compute_point(d_count, probe_dq, b_seed, C),
        spin_allowed_only=spin_allowed_only,
    )
    if not seed_candidates:
        msg = (
            f"d{d_count} has no spin-allowed d-d transitions from its {reference} "
            f"ground term in the {spin_state}-spin regime, so it cannot be fitted "
            "from spin-allowed bands. Pass include_spin_forbidden=True (high-spin "
            "d5 bands are all spin-forbidden) or spin_state='low'."
        )
        raise ValueError(msg)
    if len(seed_candidates) < observed.size:
        msg = (
            f"d{d_count} offers only {len(seed_candidates)} spin-allowed transition(s) "
            f"from {reference} but {observed.size} peaks were supplied; the fit is "
            "under-determined. Supply fewer peaks, or pass include_spin_forbidden=True."
        )
        raise ValueError(msg)
    if labels is not None:
        _, probe_levels = excited_levels(
            compute_point(d_count, probe_dq, b_seed, C), spin_allowed_only=spin_allowed_only
        )
        # A label tuple is an either-or (a band over near-degenerate levels), so it
        # fails only when none of its terms names a candidate level.
        for label in labels:
            if label is not None and not any(
                _label_matches(uid, label) for _e, uid in probe_levels
            ):
                kind = "spin-allowed " if spin_allowed_only else ""
                named = " / ".join(repr(lab) for lab in label)
                msg = (
                    f"band label {named} names no {kind}level of d{d_count} from the "
                    f"{reference} ground term in the {spin_state}-spin regime"
                )
                raise ValueError(msg)
    if len(seed_candidates) == 1:
        warnings.append(
            "only one spin-allowed transition (= 10Dq) exists for this configuration, "
            "so B is not determined by the data",
        )

    # --- Objective ----------------------------------------------------------
    # The penalty is finite, scale-aware and sloped back toward the feasible
    # box. A constant sentinel made the objective perfectly flat wherever
    # nothing matched, and Nelder-Mead reports success on a flat plateau -- so
    # the old convergence guard never fired and the sentinel leaked out as a
    # "result".
    base = float(np.sqrt(np.mean(observed**2)))

    def _relu(x: float) -> float:
        return x if x > 0 else 0.0

    c_lo, c_hi = C_OVER_B_WINDOW

    def objective(params: np.ndarray) -> float:
        dq, b = float(params[0]), float(params[1])
        c = float(params[2]) if free_c else C
        excess = (_relu(dq_bounds[0] - dq) + _relu(dq - dq_bounds[1])) / dq_bounds[1] + (
            _relu(b_bounds[0] - b) + _relu(b - b_bounds[1])
        ) / b_bounds[1]
        if free_c and b > 0:
            excess += (_relu(c_lo - c / b) + _relu(c / b - c_hi)) / c_hi
        if excess > 0 or dq <= 0 or b <= 0 or c <= 0:
            return base * (2.0 + excess)
        try:
            score = _score_point(
                d_count,
                observed,
                labels,
                (dq, b, c),
                reference=reference,
                spin_allowed_only=spin_allowed_only,
                penalty=base,
            )
        except (ValueError, KeyError, np.linalg.LinAlgError):
            return base * 3.0
        # None: crossed the spin crossover, or too few levels for every band.
        return base * 2.0 if score is None else score

    starts: Sequence[tuple[float, ...]]
    if free_c:
        local = [(dq, b, C) for dq, b in _local_starts(dq_seed, b_seed)]
        starts = _free_c_starts(objective, dq_bounds, b_bounds, local)
    else:
        starts = _search_starts(d_count, C, dq_seed, b_seed, dq_bounds, b_bounds)
    results = [
        minimize(
            objective,
            np.array(start, dtype=float),
            method="Nelder-Mead",
            options={"maxiter": 2000 if free_c else 800, "xatol": 1e-2, "fatol": 1e-2},
        )
        for start in starts
    ]
    free_parameters = 3 if free_c else 2
    best = _pick_minimum(results, (dq_seed, b_seed), determined=observed.size > free_parameters)
    minima = _distinct_minima(results, best, C, ceiling=base)
    tied, (dq_open, b_open, c_open) = (
        _undetermined(minima) if minima else ([], (False, False, False))
    )
    c_open = c_open and free_c
    if c_open:
        # C is not decided by the bands: report the best-objective minimum, whole, as a
        # display value, rather than the seed-nearest one the tie-break would pick.
        best = min((r for r in results if r.success), key=lambda r: float(r.fun))
        minima = _distinct_minima(results, best, C, ceiling=base)

    # --- Accept or refuse ---------------------------------------------------
    fitted_dq, fitted_b = float(best.x[0]), float(best.x[1])
    fitted_c = float(best.x[2]) if free_c else C
    if not best.success:
        msg = f"fit did not converge: {best.message}"
        raise ValueError(msg)
    if best.fun >= base:
        msg = (
            "fit never escaped the penalty region -- no (Dq, B) in bounds reproduced "
            f"the observed bands for d{d_count}. Check the peak list, the d-count, "
            "or try spin_state='low'."
        )
        raise ValueError(msg)
    if fitted_dq <= 0 or fitted_b <= 0:
        msg = f"fit returned non-physical parameters Dq={fitted_dq}, B={fitted_b}"
        raise ValueError(msg)

    fitted_terms = compute_point(d_count, fitted_dq, fitted_b, fitted_c)
    found_ground, fitted_candidates = transition_candidates(
        fitted_terms,
        spin_allowed_only=spin_allowed_only,
    )
    if found_ground != reference:
        msg = (
            f"fit converged on ground term {found_ground} but the {spin_state}-spin "
            f"reference is {reference}; refusing a cross-crossover solution."
        )
        raise ValueError(msg)

    _, all_transitions = transition_candidates(fitted_terms, spin_allowed_only=False)
    _, fitted_levels = excited_levels(fitted_terms, spin_allowed_only=spin_allowed_only)
    columns, _cost = assign_bands(observed, fitted_levels, labels, penalty=base)
    predicted = np.asarray([fitted_levels[j][0] for j in columns], dtype=float)
    residuals = [float(p - o) for p, o in zip(predicted, observed, strict=True)]
    by_caller: list[tuple[float, float, str]] = [(0.0, 0.0, "")] * observed.size
    for k, i in enumerate(order):
        energy, uid = fitted_levels[columns[k]]
        by_caller[i] = (float(observed_peaks_cm1[i]), float(energy), uid)
    rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))

    pinned_tol = 0.01
    if abs(fitted_b - b_bounds[0]) / b_bounds[0] < pinned_tol or (
        abs(fitted_b - b_bounds[1]) / b_bounds[1] < pinned_tol
    ):
        warnings.append(f"B pinned at its search bound ({fitted_b:.0f} cm^-1); result suspect")
    if min(abs(fitted_dq - edge) / edge for edge in dq_bounds) < pinned_tol:
        warnings.append(
            f"Dq pinned at its search bound ({fitted_dq:.0f} cm^-1, dq_bounds {dq_bounds}); "
            "the best fit may lie outside the bounds",
        )
    if observed.size <= free_parameters:
        warnings.append(
            f"only {observed.size} band(s) for {free_parameters} free parameters: the fit is "
            "exactly determined or under-determined, so rmse carries no information "
            "about fit quality (degrees of freedom = "
            f"{max(observed.size - free_parameters, 0)})",
        )
    rmse_frac = 0.05
    if rmse > rmse_frac * float(np.mean(observed)):
        warnings.append(
            f"large residual: RMSE {rmse:.0f} cm^-1 is over {rmse_frac:.0%} of the mean "
            "band energy; the single-(Dq, B) model may not describe this spectrum",
        )

    c_constrained = c_constrains_manifold(
        d_count,
        fitted_dq,
        fitted_b,
        fitted_c,
        spin_allowed_only=spin_allowed_only,
    )
    if free_c and not c_constrained:
        # C was free but the fitted bands do not depend on it, so the returned C
        # is arbitrary. Refit with it held, and say why.
        held = _fit_one_regime(
            d_count,
            observed_peaks_cm1,
            C,
            spin_state=spin_state,
            include_spin_forbidden=include_spin_forbidden,
            dq_bounds=dq_bounds,
            b_bounds=b_bounds,
            band_labels=band_labels,
        )
        note = (
            "C was to be fitted, but the fitted bands do not move with C, so it was "
            f"held at its default {C:.0f} cm^-1 and the fit redone"
        )
        return replace(
            held, c_is_default=True, c_provenance="default", warnings=[note, *held.warnings]
        )
    if free_c:
        ratio = fitted_c / fitted_b
        if min(abs(ratio - edge) / edge for edge in C_OVER_B_WINDOW) < pinned_tol:
            warnings.append(
                f"C/B pinned at the edge of its window {C_OVER_B_WINDOW} "
                f"(C/B = {ratio:.2f}); C was stopped by the window, not by the bands, "
                "so C and B are suspect",
            )
    names = [n for n, o in (("Dq", dq_open), ("B", b_open), ("C", c_open)) if o]
    if names:
        spans = ", ".join(
            f"{n} {min(m[k] for m in tied):.0f}-{max(m[k] for m in tied):.0f}"
            for k, n in enumerate(("Dq", "B", "C"))
            if n in names
        )
        warnings.append(
            f"{' and '.join(names)} undetermined: {len(tied)} minima fit these bands to within "
            f"{BAND_RESOLUTION_CM1:.0f} cm^-1 of each other (the band resolution) but disagree "
            f"({spans} cm^-1); the reported value is one of them, for display",
        )
    if not c_constrained:
        warnings.append(
            f"C = {C:.0f} cm^-1 is reported but was not constrained by these bands: "
            f"the fitted manifold of d{d_count} at Dq = {fitted_dq:.0f} cm^-1 is "
            "unchanged by a 5% change in C, so this value is an assumption carried "
            "through the fit, not a result of it",
        )

    return SpectrumFit(
        Dq=fitted_dq,
        B=fitted_b,
        C=fitted_c,
        rmse_cm1=rmse,
        ground_term=found_ground,
        spin_state=spin_state,
        transitions=all_transitions,
        residuals_cm1=residuals,
        warnings=warnings,
        c_is_default=c_is_default and not free_c,
        c_constrained=c_constrained,
        c_fitted=free_c,
        minima=minima,
        dq_provenance="undetermined" if dq_open else "fitted",
        b_provenance="undetermined" if b_open else "fitted",
        c_provenance=(
            ("undetermined" if c_open else "fitted")
            if free_c
            else ("default" if c_is_default else "given")
        ),
        c_candidates=tuple(tied) if c_open else (),
        c_range=(min(m[2] for m in tied), max(m[2] for m in tied)) if c_open else None,
        assignment=tuple(by_caller),
    )


def _classify_covalency(beta: float) -> str:
    """Map a nephelauxetic ratio to a qualitative bond-covalency label."""
    if beta >= 0.95:
        return "essentially ionic"
    if beta >= 0.85:
        return "weakly covalent"
    if beta >= 0.70:
        return "moderately covalent"
    if beta >= 0.55:
        return "strongly covalent"
    return "very strongly covalent"


def _suggest_ligands(beta: float, ion: str) -> list[str]:
    """Suggest ligands whose nephelauxetic cloud expansion matches the observed beta.

    Uses Jorgensen's (1 - beta) = h(ligand) * k(metal) relation. We solve for the
    h(ligand) implied by the fit and return the nearest entries in the series.
    """
    from tanabesugano.mcp._defaults import NEPHELAUXETIC_METAL_K
    from tanabesugano.mcp._defaults import NEPHELAUXETIC_SERIES

    k_metal = NEPHELAUXETIC_METAL_K.get(ion)
    if not k_metal or k_metal <= 0:
        return []

    implied_h = (1.0 - beta) / k_metal
    ranked = sorted(
        NEPHELAUXETIC_SERIES,
        key=lambda entry: abs(entry[1] - implied_h),
    )
    return [name for name, _h in ranked[:3]]


class NephelauxeticDict(TypedDict):
    """Shape of `nephelauxetic_analysis`'s return value.

    `dict[str, object]` was technically satisfied by every field but told a
    caller nothing about which key holds a `str` versus a `float` versus a
    `list[str]` -- the same uninformative-but-satisfied shape the package
    already fixed once for `solver()`. This mirrors `NephelauxeticResult` in
    `mcp/models.py`, minus `complex_B` (the caller already has `fitted_B`).
    """

    ion: str
    free_ion_B: float
    beta: float
    covalency: str
    suggested_ligands: list[str]
    interpretation: str


def nephelauxetic_analysis(
    d_count: int,
    fitted_B: float,
    ion: str | None = None,
) -> NephelauxeticDict:
    """Interpret a fitted Racah B as metal-ligand bond covalency.

    Computes the nephelauxetic ratio beta = B(complex) / B(free ion), classifies
    the bond covalency, and suggests the ligand class implied by the cloud
    expansion.

    Parameters
    ----------
    d_count : int
        Number of d electrons (2-8); used to validate / default the ion.
    fitted_B : float
        The Racah B parameter of the complex (cm^-1), e.g. from fit_spectrum.
    ion : str, optional
        Free-ion label such as "Ni2+". If None, the first ion tabulated for the
        given d_count is used.

    Returns
    -------
    NephelauxeticDict
        ion, free_ion_B, beta, covalency, suggested_ligands, interpretation.

    """
    from tanabesugano.mcp._defaults import FREE_ION_RACAH_B
    from tanabesugano.mcp._defaults import ION_BY_D_COUNT

    if fitted_B <= 0:
        msg = f"fitted_B must be positive, got {fitted_B}"
        raise ValueError(msg)

    candidates = ION_BY_D_COUNT.get(d_count)
    if not candidates:
        msg = f"No tabulated free ions for d_count={d_count}"
        raise ValueError(msg)

    if ion is None:
        ion = candidates[0]
    elif ion not in FREE_ION_RACAH_B:
        msg = f"Unknown ion {ion!r}; known ions: {sorted(FREE_ION_RACAH_B)}"
        raise ValueError(msg)

    free_ion_b = FREE_ION_RACAH_B[ion]
    beta = fitted_B / free_ion_b
    covalency = _classify_covalency(beta)
    suggested = _suggest_ligands(beta, ion)

    reduction_pct = (1.0 - beta) * 100.0
    interpretation = (
        f"beta = {beta:.3f}: the d-electron cloud of {ion} has expanded by "
        f"{reduction_pct:.0f}% relative to the free ion, indicating a(n) "
        f"{covalency} metal-ligand bond."
    )
    if suggested:
        interpretation += f" Consistent with ligands such as {', '.join(suggested)}."

    return {
        "ion": ion,
        "free_ion_B": free_ion_b,
        "beta": beta,
        "covalency": covalency,
        "suggested_ligands": suggested,
        "interpretation": interpretation,
    }
