"""FastMCP `apps` integrations for the TanabeSugano server.

Wires:
- GenerativeUI (auto-generated Prefab UI tools `generate_prefab_ui` and
  `search_prefab_components`) for clients that can host interactive UI.
- An interactive `ts_plot_view` tool backed by a low-level HTML resource
  view that renders the Tanabe-Sugano series with Plotly.js. This is the
  primary interactive surface — non-app clients should use `ts_plot_png`.

Imports happen at module level (not inside the registration functions) so
Pydantic can resolve the tool/resource return-type annotations from this
module's globalns when fastmcp builds its schemas. Missing optional pieces
log and no-op rather than crashing the server boot.
"""

from __future__ import annotations

import json
import logging

from typing import TYPE_CHECKING


log = logging.getLogger(__name__)

VIEW_URI = "ui://tanabesugano/diagram.html"

# ── Optional low-level apps API ──────────────────────────────────────────
# Imported at module level so Pydantic's TypeAdapter can resolve forward
# refs (`-> ToolResult`) against this module's globals.
try:
    from fastmcp.apps import AppConfig
    from fastmcp.apps import ResourceCSP
    from fastmcp.tools import ToolResult
    from mcp import types as _mcp_types
    from mcp.types import ToolAnnotations

    from tanabesugano import __version__ as _pkg_version

    _HAVE_APPS = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAVE_APPS = False


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_apps(mcp: FastMCP) -> None:
    """Wire optional FastMCP apps providers and the interactive plot view."""
    _register_generative(mcp)
    if _HAVE_APPS:
        _register_interactive_view(mcp)
    else:
        log.debug("fastmcp.apps low-level API not available; skipping ts_plot_view.")


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


def _register_interactive_view(mcp: FastMCP) -> None:
    """Register an interactive Plotly.js view of the Tanabe-Sugano diagram."""
    from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
    from tanabesugano.mcp._compute import sweep_dq
    from tanabesugano.mcp._defaults import DEFAULTS

    @mcp.tool(
        name="ts_plot_view",
        title="Interactive Tanabe-Sugano diagram",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "interactive"},
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={"domain": "tanabesugano", "surface": "mcp", "interactive": True},
        app=AppConfig(resource_uri=VIEW_URI),
    )
    def ts_plot_view(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 50,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
    ) -> ToolResult:
        """Compute a Tanabe-Sugano sweep and emit data for the interactive view.

        The accompanying HTML resource (registered below) consumes the JSON
        payload via `App.ontoolresult` and renders an interactive Plotly chart.
        Non-app clients can still parse the JSON text content directly.
        """
        if d_count not in SUPPORTED_D_COUNTS:
            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text=f"d_count must be one of {SUPPORTED_D_COUNTS}; got {d_count}",
                    ),
                ],
            )
        cfg = DEFAULTS[d_count]
        b_val = B if B is not None else cfg["default_B"]
        c_val = C if C is not None else cfg["default_C"]
        dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, b_val, c_val)
        x = [float(v * 10.0 / b_val) if normalize else float(v * 10.0) for v in dq_values]
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
        payload = {
            "title": f"Tanabe-Sugano d{d_count} (B={b_val:g}, C={c_val:g})",
            "x_label": "10Dq/B" if normalize else "10Dq (cm^-1)",
            "y_label": "E/B" if normalize else "E (cm^-1)",
            "d_count": d_count,
            "B": b_val,
            "C": c_val,
            "series": series,
        }
        return ToolResult(
            content=[_mcp_types.TextContent(type="text", text=json.dumps(payload))],
        )

    @mcp.resource(
        VIEW_URI,
        mime_type="text/html",
        title="Tanabe-Sugano interactive plot",
        app=AppConfig(
            csp=ResourceCSP(
                resource_domains=["https://cdn.plot.ly", "https://unpkg.com"],
            ),
        ),
    )
    def diagram_view() -> str:
        """Plotly.js-powered interactive line plot bound to ts_plot_view results."""
        return _VIEW_HTML


_VIEW_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="light dark">
  <title>Tanabe-Sugano diagram</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    html, body { margin: 0; padding: 0; background: transparent; }
    #plot { width: 100%; height: 480px; }
    .hint { font-family: -apple-system, system-ui, sans-serif; color: #888;
            padding: 12px; font-size: 13px; }
  </style>
</head>
<body>
  <div id="plot"></div>
  <div id="hint" class="hint">Waiting for ts_plot_view result…</div>
  <script type="module">
    import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";
    const app = new App({ name: "TS Diagram", version: "1.0.0" });
    app.ontoolresult = ({ content }) => {
      const txt = (content || []).find(c => c.type === 'text');
      if (!txt) return;
      let payload;
      try { payload = JSON.parse(txt.text); }
      catch (e) {
        document.getElementById('hint').textContent = 'Invalid payload: ' + e.message;
        return;
      }
      document.getElementById('hint').style.display = 'none';
      const data = payload.series.map(s => ({
        x: s.x, y: s.y, name: s.name, type: 'scatter', mode: 'lines',
        line: { width: 1.4 },
      }));
      const layout = {
        title: { text: payload.title, font: { size: 14 } },
        xaxis: { title: { text: payload.x_label } },
        yaxis: { title: { text: payload.y_label } },
        showlegend: true,
        legend: { font: { size: 9 }, orientation: 'v' },
        margin: { l: 55, r: 10, t: 40, b: 45 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
      };
      Plotly.newPlot('plot', data, layout, { responsive: true, displaylogo: false });
    };
    await app.connect();
  </script>
</body>
</html>
"""
