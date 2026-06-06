"""Shared constants and helpers used across the ts_* tool submodules."""

from __future__ import annotations

from mcp.types import ToolAnnotations


# Every ts_* tool is read-only and idempotent; computations are pure functions
# of (d_count, Dq, B, C). openWorldHint=False signals "no external state".
READONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

# Surface tag attached to every tool so consumers can filter / theme by domain.
TS_META: dict[str, object] = {"domain": "tanabesugano", "surface": "mcp"}


def resolve_bc(d_count: int, b: float | None, c: float | None) -> tuple[float, float]:
    """Fill in the per-d_count default Racah parameters when not provided."""
    from tanabesugano.mcp._defaults import DEFAULTS

    cfg = DEFAULTS[d_count]
    return (
        b if b is not None else cfg["default_B"],
        c if c is not None else cfg["default_C"],
    )
