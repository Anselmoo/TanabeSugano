"""Numerics shared between the MCP tools layer and the plotting helper.

Wraps the existing tanabesugano.matrices solvers with light coercion so the
MCP layer never imports matplotlib (kept in plotting.py) or pydantic just to
crunch numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from typing import TypedDict

import numpy as np

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


def fit_spectrum(
    d_count: int,
    observed_peaks_cm1: list[float],
    C: float | None = None,
    *,
    spin_state: SpinState = "high",
    include_spin_forbidden: bool = False,
    dq_bounds: tuple[float, float] | None = None,
    b_bounds: tuple[float, float] = (200.0, 1500.0),
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
        Defaults to ``(0.2 * dq_seed, 5 * dq_seed)``. The lower bound must stay
        strictly positive: the solver silently returns corrupted energies for
        Dq < 0 (the ground level stops being the zero point) with no error.

    """
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
    observed = np.asarray(sorted(float(p) for p in observed_peaks_cm1), dtype=float)
    warnings: list[str] = []

    # --- Seed ---------------------------------------------------------------
    # For d3/d8 the closed form gives BOTH parameters analytically, so the
    # optimizer starts on (or beside) the answer instead of hunting for it.
    b_default = float(DEFAULTS[d_count]["default_B"])
    dq_seed = float(observed[0]) / 10.0
    b_seed = b_default
    try:
        dq_seed, b_seed = closed_form_dq_b(d_count, observed.tolist())
    except ValueError:
        pass  # not d3/d8, or fewer than three bands -- generic seed stands
    if not b_bounds[0] <= b_seed <= b_bounds[1]:
        b_seed = min(max(b_seed, b_bounds[0]), b_bounds[1])

    if dq_bounds is None:
        dq_bounds = (0.2 * dq_seed, 5.0 * dq_seed)
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

    def objective(params: np.ndarray) -> float:
        dq, b = float(params[0]), float(params[1])
        excess = (_relu(dq_bounds[0] - dq) + _relu(dq - dq_bounds[1])) / dq_bounds[1] + (
            _relu(b_bounds[0] - b) + _relu(b - b_bounds[1])
        ) / b_bounds[1]
        if excess > 0 or dq <= 0 or b <= 0:
            return base * (2.0 + excess)
        try:
            terms = compute_point(d_count, dq, b, C)
            found_ground, candidates = transition_candidates(
                terms,
                spin_allowed_only=spin_allowed_only,
            )
        except (ValueError, KeyError, np.linalg.LinAlgError):
            return base * 3.0
        if found_ground != reference or not candidates:
            # Crossed the spin crossover. Refuse it: the low-spin manifolds are
            # far denser (d5: 31 lines vs 0), and a nearest-neighbour residual
            # is minimised by a dense forest of candidates, so an unconstrained
            # search is actively rewarded for ending up in the wrong regime.
            return base * 2.0
        return peak_rmse(observed, np.array([e for e, _a, _s in candidates]))

    starts = [
        (dq_seed, b_seed),
        (0.8 * dq_seed, b_seed),
        (1.25 * dq_seed, b_seed),
        (dq_seed, 0.7 * b_seed),
        (dq_seed, 1.2 * b_seed),
    ]
    best = None
    for start in starts:
        result = minimize(
            objective,
            np.array(start, dtype=float),
            method="Nelder-Mead",
            options={"maxiter": 800, "xatol": 1e-2, "fatol": 1e-2},
        )
        if best is None or result.fun < best.fun:
            best = result
    assert best is not None  # noqa: S101 - starts is non-empty by construction

    # --- Accept or refuse ---------------------------------------------------
    fitted_dq, fitted_b = float(best.x[0]), float(best.x[1])
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

    fitted_terms = compute_point(d_count, fitted_dq, fitted_b, C)
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
    predicted = np.array([e for e, _a, _s in fitted_candidates])
    residuals = [float(predicted[int(np.argmin(np.abs(predicted - o)))] - o) for o in observed]
    rmse = peak_rmse(observed, predicted)

    pinned_tol = 0.01
    if abs(fitted_b - b_bounds[0]) / b_bounds[0] < pinned_tol or (
        abs(fitted_b - b_bounds[1]) / b_bounds[1] < pinned_tol
    ):
        warnings.append(f"B pinned at its search bound ({fitted_b:.0f} cm^-1); result suspect")
    free_parameters = 2  # Dq and B; C is held fixed
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
        C,
        spin_allowed_only=spin_allowed_only,
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
        C=C,
        rmse_cm1=rmse,
        ground_term=found_ground,
        spin_state=spin_state,
        transitions=all_transitions,
        residuals_cm1=residuals,
        warnings=warnings,
        c_is_default=c_is_default,
        c_constrained=c_constrained,
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
