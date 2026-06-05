"""Matplotlib PNG fallback for non-app MCP clients."""

from __future__ import annotations

import base64

from typing import TYPE_CHECKING

from fastmcp.tools import ToolResult
from mcp import types

from tanabesugano import __version__
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.plotting import render_diagram_png
from tanabesugano.mcp.tools._shared import READONLY
from tanabesugano.mcp.tools._shared import TS_META
from tanabesugano.mcp.tools._shared import resolve_bc


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the ts_plot_png matplotlib PNG fallback tool."""

    @mcp.tool(
        name="ts_plot_png",
        title="Render a Tanabe-Sugano diagram (PNG)",
        version=__version__,
        tags={"tanabesugano", "plot"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_plot_png(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
        dpi: int = 144,
    ) -> ToolResult:
        """Render a publication-style matplotlib PNG of a Tanabe-Sugano diagram.

        Use this in non-app MCP clients (or when token cost is a concern). In
        app-capable clients prefer `ts_plot_view` / `ts_diagram_app`, which
        render an in-chat Prefab LineChart with per-term legend toggling.
        """
        b_val, c_val = resolve_bc(d_count, B, C)
        png = render_diagram_png(
            d_count=d_count,
            dq_min=dq_min,
            dq_max=dq_max,
            steps=steps,
            B=b_val,
            C=c_val,
            normalize=normalize,
            dpi=dpi,
        )
        b64 = base64.b64encode(png).decode()
        return ToolResult(
            content=[types.ImageContent(type="image", data=b64, mimeType="image/png")],
        )
