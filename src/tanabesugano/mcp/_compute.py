"""Numerics shared between the MCP tools layer and the plotting helper.

Wraps the existing tanabesugano.matrices solvers with light coercion so the
MCP layer never imports matplotlib (kept in plotting.py) or pydantic just to
crunch numbers.
"""

from __future__ import annotations

import numpy as np

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
