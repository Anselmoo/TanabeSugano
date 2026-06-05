"""Optional FastMCP `apps` integrations.

The `fastmcp[apps]` extra installs Generative / Prefab / low-level app helpers
that enable interactive UIs in capable clients (Claude Desktop, etc.). Each
helper is loaded lazily and skipped silently when unavailable so the server
still boots on stripped-down installs.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from fastmcp import FastMCP

log = logging.getLogger(__name__)


def register_apps(mcp: FastMCP) -> None:
    """Wire optional FastMCP apps providers onto *mcp*.

    Quietly no-ops for any provider whose extra isn't installed.
    """
    _register_generative(mcp)
    _register_prefab(mcp)


def _register_generative(mcp: FastMCP) -> None:
    try:
        from fastmcp.apps.generative import GenerativeUI
    except ImportError:
        log.debug("fastmcp.apps.generative not available; skipping GenerativeUI.")
        return
    try:
        mcp.add_provider(GenerativeUI())
    except (AttributeError, TypeError) as exc:
        log.debug("GenerativeUI registration failed: %s", exc)


def _register_prefab(mcp: FastMCP) -> None:
    """Register a Prefab LinePlot view that wraps ts_diagram for interactive clients."""
    try:
        from fastmcp.apps.prefab import LinePlot
    except ImportError:
        log.debug("fastmcp.apps.prefab not available; skipping LinePlot view.")
        return

    from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
    from tanabesugano.mcp._compute import sweep_dq
    from tanabesugano.mcp._defaults import DEFAULTS

    @mcp.tool(
        name="ts_plot_view",
        title="Interactive Tanabe-Sugano line plot",
        tags={"tanabesugano", "plot", "interactive"},
        app=True,
        meta={"domain": "tanabesugano", "surface": "mcp", "interactive": True},
    )
    def ts_plot_view(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 50,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
    ) -> LinePlot:
        """Prefab LinePlot of a Tanabe-Sugano diagram for interactive MCP clients.

        Prefer ts_plot_png for non-interactive contexts to keep token cost low.
        """
        if d_count not in SUPPORTED_D_COUNTS:
            return LinePlot(title=f"unsupported d_count: {d_count}", series=[])
        cfg = DEFAULTS[d_count]
        b_val = B if B is not None else cfg["default_B"]
        c_val = C if C is not None else cfg["default_C"]
        dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, b_val, c_val)
        x = [float(v * 10.0 / b_val) if normalize else float(v * 10.0) for v in dq_values]

        # Flatten each term's eigenvalue ladder into separate series so the
        # client can pick / hide individual states.
        series: list[dict] = []
        for term in points[0]:
            max_n = max(len(pt[term]) for pt in points)
            for n in range(max_n):
                y = [
                    (pt[term][n] / b_val if normalize else pt[term][n])
                    if n < len(pt[term])
                    else None
                    for pt in points
                ]
                series.append({"name": f"{term}[{n}]", "x": x, "y": y})

        return LinePlot(
            title=f"Tanabe-Sugano d{d_count} (B={b_val:g}, C={c_val:g})",
            x_label="10Dq/B" if normalize else "10Dq (cm^-1)",
            y_label="E/B" if normalize else "E (cm^-1)",
            series=series,
        )
