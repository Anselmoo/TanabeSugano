"""Global minimum of a band set's RMSE, searched with the determinant oracle alone.

A local search is a weaker check than the fitter it would judge (the fitter
already starts from a grid and several seeds), so this one is brute force: every
node of a grid over the fit's own (Dq, B) box, each scored with the optimal
(Hungarian) assignment of bands to the oracle's levels, then ``least_squares``
polish from the best nodes. It imports only the oracle, numpy and scipy -- no
package code -- so the audit script may import it as well.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scipy.optimize import least_squares
from scipy.optimize import linear_sum_assignment

from tanabesugano.test._determinant_oracle import IRREP_DIM
from tanabesugano.test._determinant_oracle import blocks


GRID_STEPS = 101
"""Nodes per axis: a step of 1 % of each range."""
POLISH_STARTS = 5
CHUNK = 2048
"""Grid nodes diagonalised per batch, to bound memory."""


@dataclass(frozen=True, slots=True)
class OracleMinimum:
    """The lowest RMSE found, where, and with which levels."""

    rmse_cm1: float
    Dq: float
    B: float
    levels: tuple[tuple[str, int], ...]


def _levels(n: int, dq: np.ndarray, b: np.ndarray, c: float) -> list[tuple[int, str, np.ndarray]]:
    """Per block: (multiplicity, key, levels of shape (nodes, k)), absolute energies."""
    out = []
    for blk in blocks(n):
        h = dq[:, None, None] * blk.dq + b[:, None, None] * blk.b + c * blk.c
        ev = np.linalg.eigvalsh(h)
        out.append(
            (blk.multiplicity, blk.key, ev.reshape(len(dq), -1, IRREP_DIM[blk.irrep]).mean(axis=2))
        )
    return out


def _candidates(
    per_block: list[tuple[int, str, np.ndarray]],
    node: int,
    multiplicity: int,
    *,
    spin_forbidden: bool = False,
) -> tuple[np.ndarray, list[tuple[str, int]]] | None:
    """Levels above the ground at one node, or None off the ``multiplicity`` regime.

    Only levels of the ground multiplicity, unless ``spin_forbidden``: then every level.
    """
    ground_e, ground_mult, ground_key = min(
        (float(lv[node].min()), mult, key) for mult, key, lv in per_block
    )
    if ground_mult != multiplicity:
        return None
    energies: list[float] = []
    ids: list[tuple[str, int]] = []
    for mult, key, lv in per_block:
        if mult != multiplicity and not spin_forbidden:
            continue
        for index, energy in enumerate(np.sort(lv[node])):
            if key == ground_key and index == 0:
                continue
            energies.append(float(energy) - ground_e)
            ids.append((key, index))
    return np.array(energies), ids


def _assign(observed: np.ndarray, energies: np.ndarray) -> tuple[float, np.ndarray]:
    """Optimal assignment of bands to levels: (rmse, level column per band)."""
    if len(energies) < len(observed):
        return float("inf"), np.array([], dtype=int)
    cost = (observed[:, None] - energies[None, :]) ** 2
    rows, cols = linear_sum_assignment(cost)
    return float(np.sqrt(cost[rows, cols].mean())), cols


def oracle_rmse(
    n: int,
    observed: list[float],
    dq: float,
    b: float,
    c: float,
    multiplicity: int,
    *,
    spin_forbidden: bool = False,
) -> float:
    """RMSE at one point under the optimal assignment; inf outside the regime."""
    per_block = _levels(n, np.array([dq]), np.array([b]), c)
    found = _candidates(per_block, 0, multiplicity, spin_forbidden=spin_forbidden)
    if found is None:
        return float("inf")
    return _assign(np.asarray(observed, dtype=float), found[0])[0]


def oracle_global_min(
    n: int,
    observed: list[float],
    c: float,
    dq_bounds: tuple[float, float],
    b_bounds: tuple[float, float],
    multiplicity: int,
    *,
    spin_forbidden: bool = False,
) -> OracleMinimum:
    """The lowest band RMSE over the box, at fixed C, in the ``multiplicity`` regime."""
    obs = np.asarray(observed, dtype=float)
    dq_axis = np.linspace(*dq_bounds, GRID_STEPS)
    b_axis = np.linspace(*b_bounds, GRID_STEPS)
    dq_grid, b_grid = (g.ravel() for g in np.meshgrid(dq_axis, b_axis, indexing="ij"))
    scored: list[tuple[float, float, float, tuple[tuple[str, int], ...]]] = []
    for start in range(0, len(dq_grid), CHUNK):
        dq_chunk, b_chunk = dq_grid[start : start + CHUNK], b_grid[start : start + CHUNK]
        per_block = _levels(n, dq_chunk, b_chunk, c)
        for node in range(len(dq_chunk)):
            found = _candidates(per_block, node, multiplicity, spin_forbidden=spin_forbidden)
            if found is None:
                continue
            rmse, cols = _assign(obs, found[0])
            if np.isfinite(rmse):
                ids = tuple(found[1][j] for j in cols)
                scored.append((rmse, float(dq_chunk[node]), float(b_chunk[node]), ids))
    if not scored:
        msg = f"d{n}: no grid node lies in the multiplicity-{multiplicity} regime"
        raise ValueError(msg)
    scored.sort(key=lambda s: s[0])
    best = OracleMinimum(scored[0][0], scored[0][1], scored[0][2], scored[0][3])
    for _rmse, dq0, b0, ids in scored[:POLISH_STARTS]:

        def residual(x: np.ndarray, ids: tuple[tuple[str, int], ...] = ids) -> np.ndarray:
            per_block = _levels(n, np.array([x[0]]), np.array([x[1]]), c)
            ground = min(float(lv[0].min()) for _m, _k, lv in per_block)
            table = {key: np.sort(lv[0]) - ground for _m, key, lv in per_block}
            return np.array([table[key][index] for key, index in ids]) - obs

        fit = least_squares(
            residual, [dq0, b0], bounds=([dq_bounds[0], b_bounds[0]], [dq_bounds[1], b_bounds[1]])
        )
        polished = oracle_rmse(
            n,
            observed,
            float(fit.x[0]),
            float(fit.x[1]),
            c,
            multiplicity,
            spin_forbidden=spin_forbidden,
        )
        if polished < best.rmse_cm1:
            best = OracleMinimum(polished, float(fit.x[0]), float(fit.x[1]), ids)
    return best
