"""Documentation-style tool: explain a d-configuration in plain English."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tanabesugano import __version__
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._defaults import GROUND_STATE_NOTES
from tanabesugano.mcp._defaults import WHY_TANABE_SUGANO
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.tools._shared import READONLY
from tanabesugano.mcp.tools._shared import TS_META


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the ts_explain tool."""

    @mcp.tool(
        name="ts_explain",
        title="Explain a d-configuration",
        version=__version__,
        tags={"tanabesugano", "docs"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_explain(d_count: D_COUNT_LITERAL) -> str:  # type: ignore[valid-type]
        """Multi-paragraph explanation of a d^n configuration in plain English.

        Combines the universal "why use a Tanabe-Sugano diagram" rationale
        with per-d_count ground-state notes from the chemistry literature.
        Call once per configuration; static across sessions.
        """
        cfg = DEFAULTS[d_count]
        note = GROUND_STATE_NOTES[d_count]
        return (
            f"d{d_count} configuration -- ground term {cfg['ground_term']}, "
            f"matrix sum dim {cfg['matrix_size']}, "
            f"default Racah B = {cfg['default_B']:g} cm^-1, "
            f"C = {cfg['default_C']:g} cm^-1. "
            f"Library version {__version__}.\n\n"
            f"{note}\n\n"
            f"{WHY_TANABE_SUGANO}"
        )
