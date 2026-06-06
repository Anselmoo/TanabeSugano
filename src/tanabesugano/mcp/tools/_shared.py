"""Shared constants and helpers used across the ts_* tool submodules."""

from __future__ import annotations

from mcp.types import ToolAnnotations


# Every ts_* tool is read-only and idempotent; computations are pure functions
# of (d_count, Dq, B, C). openWorldHint=False signals "no external state".
READONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

# Surface tag attached to every tool so consumers can filter / theme by domain.
TS_META: dict[str, object] = {"domain": "tanabesugano", "surface": "mcp"}


def resolve_term_key(d_count: int, term: str) -> str:
    """Map a user-supplied term symbol to the solver's octahedral key.

    The dashboard surfaces free-ion ground-term notation (``"3F"``, ``"6S"``)
    because that's how spectroscopists read it, but the d-N solvers in
    ``matrices.py`` emit octahedral keys (``"3_T_1"``, ``"6_A_1"``). Without
    this helper, a user who reads ``"6S"`` from the dashboard and pastes it
    into ``ts_parameter_heatmap_app`` gets a silent ``NaN`` heatmap because
    ``terms.get("6S", [])`` returns ``[]`` at every grid cell.

    Accepts either form. Returns the solver key untouched if it already looks
    octahedral (contains an underscore).
    """
    if "_" in term:
        return term
    from tanabesugano.mcp._defaults import DEFAULTS
    from tanabesugano.mcp._defaults import GROUND_TERM_OCTAHEDRAL

    if d_count in DEFAULTS and term == DEFAULTS[d_count]["ground_term"]:
        return GROUND_TERM_OCTAHEDRAL.get(d_count, term)
    return term


def resolve_bc(d_count: int, b: float | None, c: float | None) -> tuple[float, float]:
    """Fill in the per-d_count default Racah parameters when not provided.

    Raises ValueError with a clear message when d_count is outside d2..d8, so
    every ts_*_app tool that uses this helper bubbles up a structured error
    instead of a raw KeyError stack trace.
    """
    from tanabesugano.mcp._defaults import DEFAULTS

    if d_count not in DEFAULTS:
        msg = f"d_count must be one of {sorted(DEFAULTS)}, got {d_count!r}"
        raise ValueError(msg)
    cfg = DEFAULTS[d_count]
    return (
        b if b is not None else cfg["default_B"],
        c if c is not None else cfg["default_C"],
    )
