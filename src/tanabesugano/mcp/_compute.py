"""Numerics shared between the MCP tools layer and the plotting helper.

Wraps the existing tanabesugano.matrices solvers with light coercion so the
MCP layer never imports matplotlib (kept in plotting.py) or pydantic just to
crunch numbers.
"""

from __future__ import annotations

import numpy as np

from scipy.optimize import minimize

from tanabesugano.batch import ELECTRON_CONFIG_SOLVERS
from tanabesugano.constants import ElectronConfiguration


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
    states = solver_class(Dq=Dq, B=B, C=C).solver()
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
        states = solver_class(Dq=float(dq), B=B, C=C).solver()
        points.append(
            {term: np.asarray(values).flatten().tolist() for term, values in states.items()},
        )
    return dq_values, points


def _extract_transition_energies(
    term_energies: dict[str, list[float]],
) -> list[tuple[float, str]]:
    """Extract transition energies from ground state to all excited states.

    Returns list of (energy_cm1, assignment_string) tuples sorted by energy.
    """
    transitions: list[tuple[float, str]] = []
    all_energies = [e for energies in term_energies.values() for e in energies]
    ground_energy = min(all_energies) if all_energies else 0.0
    first_term = next(iter(term_energies.keys()))

    for term, energies in term_energies.items():
        for energy in energies:
            trans_energy = energy - ground_energy
            if trans_energy > 1.0:
                transitions.append((trans_energy, f"{first_term}→{term}"))

    return sorted(transitions)


def _match_peaks(
    observed: np.ndarray,
    predicted: np.ndarray,
    tolerance_cm1: float = 500.0,
) -> float:
    """Calculate goodness-of-fit between observed and predicted peaks.

    Uses a simple nearest-neighbor matching with a distance metric.
    Returns RMSE (lower is better).
    """
    if len(observed) == 0 or len(predicted) == 0:
        return 1e6

    rmse = 0.0
    matched_count = 0
    for obs_peak in observed:
        distances = np.abs(predicted - obs_peak)
        min_dist = np.min(distances)
        if min_dist < tolerance_cm1:
            rmse += min_dist**2
            matched_count += 1

    if matched_count == 0:
        return 1e6
    return np.sqrt(rmse / matched_count)


def fit_spectrum(
    d_count: int,
    observed_peaks_cm1: list[float],
    C: float | None = None,
    dq_bounds: tuple[float, float] = (500.0, 30000.0),
    b_bounds: tuple[float, float] = (200.0, 1200.0),
) -> tuple[float, float, float, float, list[tuple[float, str]]]:
    """Fit observed absorption peaks to find optimal Dq and B parameters.

    Parameters
    ----------
    d_count : int
        Number of d electrons (2-8).
    observed_peaks_cm1 : list[float]
        Observed transition energies in cm^-1 (typically 10000-40000).
    C : float, optional
        Racah C parameter. If None, uses default for the d_count.
    dq_bounds : tuple, optional
        Search bounds for Dq in cm^-1.
    b_bounds : tuple, optional
        Search bounds for B in cm^-1.

    Returns
    -------
    tuple[float, float, float, float, list]
        (fitted_Dq, fitted_B, fitted_C, rmse_cm1, predicted_transitions)

    """
    from tanabesugano.mcp._defaults import DEFAULTS

    if C is None:
        C = float(DEFAULTS[d_count]["default_C"])

    observed = np.asarray(observed_peaks_cm1, dtype=float)

    def objective(params: np.ndarray) -> float:
        dq, b = params
        if dq < dq_bounds[0] or dq > dq_bounds[1]:
            return 1e6
        if b < b_bounds[0] or b > b_bounds[1]:
            return 1e6

        try:
            terms = compute_point(d_count, dq, b, C)
            transitions = _extract_transition_energies(terms)
            predicted = np.array([t[0] for t in transitions])
            return _match_peaks(observed, predicted)
        except Exception:  # noqa: BLE001
            return 1e6

    initial_guess = np.array([5000.0, 600.0])
    result = minimize(
        objective,
        initial_guess,
        method="Nelder-Mead",
        options={"maxiter": 500, "xatol": 1e-2, "fatol": 1.0},
    )

    if not result.success:
        msg = f"Fitting failed to converge: {result.message}"
        raise ValueError(msg)

    fitted_dq, fitted_b = result.x
    fitted_terms = compute_point(d_count, fitted_dq, fitted_b, C)
    predicted_transitions = _extract_transition_energies(fitted_terms)
    final_rmse = _match_peaks(observed, np.array([t[0] for t in predicted_transitions]))

    return fitted_dq, fitted_b, C, final_rmse, predicted_transitions
