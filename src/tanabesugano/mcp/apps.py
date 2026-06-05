"""FastMCP `app=True` tools for the TanabeSugano server.

Each tool here renders as an in-chat Prefab UI (Card, LineChart, DataTable,
Form, ...) in app-capable MCP clients (Claude Desktop, VS Code Copilot,
Cursor). All tools also work as plain JSON for non-app clients because
PrefabApp serialises to a structured representation.

Imports happen at module level so Pydantic's TypeAdapter can resolve the
PrefabApp / Form forward refs against this module's globalns when FastMCP
builds its tool schemas. When the [mcp] extra is missing the whole module
no-ops via the _HAVE_APPS guard.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING


log = logging.getLogger(__name__)

HEATMAP_URI = "ui://tanabesugano/heatmap.html"

# ── Optional Prefab / FastMCP apps API ───────────────────────────────────
try:
    from fastmcp.apps import AppConfig
    from fastmcp.apps import ResourceCSP
    from mcp.types import ToolAnnotations
    from prefab_ui import components as pf
    from prefab_ui.actions import CallTool
    from prefab_ui.app import PrefabApp
    from prefab_ui.components.charts import ChartSeries
    from prefab_ui.components.charts import LineChart
    from prefab_ui.components.charts import Sparkline

    from tanabesugano import __version__ as _pkg_version

    _HAVE_APPS = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAVE_APPS = False


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_apps(mcp: FastMCP) -> None:
    """Register every Prefab-native ts_*_app tool plus the Chart.js heatmap resource."""
    if not _HAVE_APPS:
        log.debug("prefab_ui / fastmcp.apps not available; skipping all *_app tools.")
        return

    _register_explore(mcp)
    _register_plot_view(mcp)
    _register_diagram_app(mcp)
    _register_dashboard(mcp)
    _register_compare(mcp)
    _register_heatmap(mcp)


# ─────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────

_READONLY_ANNOTATIONS = (
    ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
    if _HAVE_APPS
    else None
)
_TS_META: dict[str, object] = {"domain": "tanabesugano", "surface": "mcp", "interactive": True}


def _sweep_payload(
    d_count: int,
    dq_min: float,
    dq_max: float,
    steps: int,
    b_val: float,
    c_val: float,
    *,
    normalize: bool,
) -> tuple[list[dict], list[ChartSeries], str, str, str, str, float]:
    """Compute one sweep and return Prefab-shaped data: rows + ChartSeries list.

    Returns:
        (rows, series, title, x_axis_key, x_label, y_label, ground_y) — `rows`
        is a list of dicts keyed by x-axis value and one column per term-level
        (suitable as `LineChart.data`); `series` is one `ChartSeries` per
        term-level pointing at those columns; `ground_y` is the lowest
        y-value of the ground term over the sweep (used for Metric cards).

    """
    from tanabesugano.mcp._compute import sweep_dq
    from tanabesugano.plot_style import color_for
    from tanabesugano.plot_style import term_to_unicode

    dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, b_val, c_val)
    if not points:
        return [], [], "", "x", "x", "y", 0.0

    ground_term = min(
        points[0],
        key=lambda t: min(points[0][t]) if points[0][t] else float("inf"),
    )

    x_key = "x"
    rows: list[dict] = []
    series_specs: list[tuple[str, str]] = []  # (column_key, unicode_label)
    series_colors: dict[str, str] = {}
    # One series per unique term (level-0 only).  With 42+ states in d6,
    # including every eigenvalue collapses Prefab's LineChart height to zero.
    # The full multi-level diagram is available via ts_plot_png (matplotlib PNG).
    seen_terms: set[str] = set()

    for i, dq in enumerate(dq_values):
        row: dict[str, float] = {
            x_key: float(dq * 10.0 / b_val) if normalize else float(dq * 10.0),
        }
        for term, energies in points[i].items():
            if not energies:
                continue
            key = f"{term}_0"
            row[key] = float(energies[0] / b_val) if normalize else float(energies[0])
            if term not in seen_terms:
                seen_terms.add(term)
                series_specs.append((key, term_to_unicode(term)))
                series_colors[key] = color_for(term)
        rows.append(row)

    series = [
        ChartSeries(data_key=key, label=label, color=series_colors[key])
        for key, label in series_specs
    ]

    title = f"Tanabe-Sugano d{d_count} (B={b_val:g}, C={c_val:g} cm⁻¹)"
    x_label = "10Dq/B" if normalize else "10Dq (cm⁻¹)"
    y_label = "E/B" if normalize else "E (cm⁻¹)"
    ground_y = min(row.get(f"{ground_term}_0", float("inf")) for row in rows)
    return rows, series, title, x_key, x_label, y_label, ground_y


# ─────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────


def _register_explore(mcp: FastMCP) -> None:
    """Primary discovery surface: a form that dispatches into ts_diagram_app."""

    @mcp.tool(
        name="ts_explore_app",
        title="Explore Tanabe-Sugano diagrams",
        version=_pkg_version,
        tags={"tanabesugano", "form", "discovery"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_explore_app() -> PrefabApp:
        """Open an interactive form to pick d_count, Dq range, B, C, and render a diagram.

        Submitting the form calls `ts_diagram_app` with the chosen parameters,
        which renders the in-chat LineChart + DataTable. Use this as the
        entry point for non-expert users — they don't need to know tool names.
        """
        from tanabesugano.mcp._inputs import TSInput

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(content="Tanabe-Sugano explorer", level=2)
            pf.Muted(
                content=(
                    "Pick a d-electron count (d² – d⁸), set the crystal-field "
                    "and Racah parameters, then submit to render an interactive "
                    "Tanabe-Sugano diagram in this chat."
                ),
            )
            pf.Form.from_model(
                TSInput,
                submit_label="Render diagram",
                on_submit=CallTool(tool="ts_diagram_app"),
            )
        return app


def _register_plot_view(mcp: FastMCP) -> None:
    """Register the 'chart in the chat' tool (single LineChart of the sweep)."""

    @mcp.tool(
        name="ts_plot_view",
        title="Tanabe-Sugano chart (in-chat)",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_plot_view(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
    ) -> PrefabApp:
        """Render a single Prefab LineChart of the Tanabe-Sugano sweep in the chat.

        Lighter than `ts_diagram_app` — just the curve, no table. Use this
        when the user has already settled on parameters and just wants the
        visual update.
        """
        from tanabesugano.mcp.tools._shared import resolve_bc

        b_val, c_val = resolve_bc(d_count, B, C)
        rows, series, title, x_key, x_label, y_label, _ = _sweep_payload(
            d_count,
            dq_min,
            dq_max,
            steps,
            b_val,
            c_val,
            normalize=normalize,
        )

        with PrefabApp() as app, pf.Column(gap=3, css_class="p-6"):
            pf.Heading(content=title, level=3)
            LineChart(
                data=rows,
                series=series,
                x_axis=x_key,
                show_legend=True,
                show_tooltip=True,
                show_grid=True,
                show_dots=False,
                height=420,
            )
            pf.Muted(content=f"{x_label}  /  {y_label}")
        return app


def _register_diagram_app(mcp: FastMCP) -> None:
    """Full diagram: LineChart + DataTable + Metric cards."""

    @mcp.tool(
        name="ts_diagram_app",
        title="Tanabe-Sugano diagram (chart + table)",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "interactive", "table"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_diagram_app(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
    ) -> PrefabApp:
        """Render the LineChart plus a sorted DataTable of term energies at dq_max.

        This is the richer companion to `ts_plot_view`: same chart but the
        bottom half is a sortable / searchable table of every eigenvalue at
        the high end of the Dq sweep, plus Metric cards summarising the run.
        """
        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc
        from tanabesugano.plot_style import term_to_unicode

        b_val, c_val = resolve_bc(d_count, B, C)
        rows, series, title, x_key, x_label, y_label, _ground_y = _sweep_payload(
            d_count,
            dq_min,
            dq_max,
            steps,
            b_val,
            c_val,
            normalize=normalize,
        )

        # Build table rows for terms at the end of the sweep (Dq = dq_max).
        terms_at_end = compute_point(d_count, dq_max, b_val, c_val)
        table_rows: list[dict] = []
        for term, energies in terms_at_end.items():
            unicode_label = term_to_unicode(term)
            for n, e in enumerate(energies):
                table_rows.append(
                    {
                        "term": unicode_label,
                        "level": n,
                        "energy_cm": round(float(e), 1),
                        "energy_over_B": round(float(e / b_val), 3) if b_val else 0.0,
                        "spin_family": pf.Badge(
                            label=str(_multiplicity_of(term)),
                            variant=_badge_variant(term),
                        ),
                    },
                )
        table_rows.sort(key=lambda r: r["energy_cm"])

        ground_term = DEFAULTS[d_count]["ground_term"]

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(content=title, level=3)
            with pf.Grid(columns=3, gap=4):
                pf.Metric(label="Ground term", value=ground_term)
                pf.Metric(
                    label="Dq range",
                    value=f"{dq_min:g} – {dq_max:g} cm⁻¹",
                    description=f"{steps} points",
                )
                pf.Metric(
                    label="Racah B / C",
                    value=f"{b_val:g} / {c_val:g} cm⁻¹",
                )
            LineChart(
                data=rows,
                series=series,
                x_axis=x_key,
                show_legend=True,
                show_tooltip=True,
                show_grid=True,
                show_dots=False,
                height=380,
            )
            pf.Muted(content=f"{x_label}  /  {y_label}")
            pf.Separator()
            pf.Heading(content=f"Term energies at Dq = {dq_max:g} cm⁻¹", level=4)
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="term", header="Term", sortable=True),
                    pf.DataTableColumn(key="level", header="Level", sortable=True),
                    pf.DataTableColumn(key="energy_cm", header="E (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="energy_over_B", header="E/B", sortable=True),
                    pf.DataTableColumn(key="spin_family", header="2S+1"),
                ],
                rows=table_rows,
                search=True,
            )
        return app


def _register_dashboard(mcp: FastMCP) -> None:
    """Overview: a Card grid showing each d-count's ground term + Sparkline."""

    @mcp.tool(
        name="ts_dashboard_app",
        title="d² – d⁸ overview dashboard",
        version=_pkg_version,
        tags={"tanabesugano", "dashboard", "overview"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_dashboard_app() -> PrefabApp:
        """Single-call overview of every supported d-configuration.

        For each d-count: shows the ground term, the matrix size, the default
        Racah parameters, and a Sparkline of the lowest-eigenvalue energy
        across the default Dq sweep. Useful as a 'home page' before drilling
        into one configuration with `ts_diagram_app`.
        """
        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
        from tanabesugano.mcp._compute import sweep_dq
        from tanabesugano.mcp._defaults import DEFAULTS

        cards: list[dict] = []
        for d in SUPPORTED_D_COUNTS:
            cfg = DEFAULTS[d]
            b = cfg["default_B"]
            c = cfg["default_C"]
            _, points = sweep_dq(d, 0.0, 1500.0, 30, b, c)
            ground = min(
                points[0],
                key=lambda t, p=points: min(p[0][t]) if p[0][t] else float("inf"),
            )
            spark = [float(min(p[ground])) if p[ground] else 0.0 for p in points]
            cards.append({"d": d, "cfg": cfg, "spark": spark, "ground": ground})

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(content="Tanabe-Sugano: d² – d⁸ overview", level=2)
            pf.Muted(
                content=(
                    "Default Racah parameters and a sparkline of the ground-term "
                    "energy across 0 – 1500 cm⁻¹ Dq. Click a configuration for "
                    "the full diagram via ts_diagram_app."
                ),
            )
            with pf.Grid(columns=4, gap=4):
                for c_data in cards:
                    with pf.Card(css_class="p-4"):
                        pf.Heading(content=f"d{c_data['d']}", level=4)
                        pf.Metric(
                            label="Ground term",
                            value=c_data["cfg"]["ground_term"],
                        )
                        pf.Muted(
                            content=(
                                f"B = {c_data['cfg']['default_B']:g} cm⁻¹  "
                                f"C = {c_data['cfg']['default_C']:g} cm⁻¹"
                            ),
                        )
                        Sparkline(
                            data=c_data["spark"],
                            height=48,
                            variant="default",
                            fill=True,
                        )
        return app


def _register_compare(mcp: FastMCP) -> None:
    """Small-multiples grid of LineCharts for chosen d_counts."""

    @mcp.tool(
        name="ts_compare_app",
        title="Compare Tanabe-Sugano diagrams",
        version=_pkg_version,
        tags={"tanabesugano", "compare", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_compare_app(
        d_counts: list[int],
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 40,
        normalize: bool = True,
    ) -> PrefabApp:
        """Render a Grid of LineCharts (small multiples) for the given d_counts.

        Defaults to comparing the configurations the user picks. Use this to
        teach the d²/d⁸, d³/d⁷, d⁴/d⁶ "hole-particle" symmetries on one screen.
        """
        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        valid = [d for d in d_counts if d in SUPPORTED_D_COUNTS]
        if not valid:
            valid = [3, 5, 8]

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(
                content=f"Compare: {', '.join(f'd{d}' for d in valid)}",
                level=3,
            )
            cols = 2 if len(valid) <= 4 else 3  # noqa: PLR2004
            with pf.Grid(columns=cols, gap=4):
                for d in valid:
                    cfg = DEFAULTS[d]
                    b_val, c_val = resolve_bc(d, None, None)
                    rows, series, _title, x_key, _, _, _ = _sweep_payload(
                        d,
                        dq_min,
                        dq_max,
                        steps,
                        b_val,
                        c_val,
                        normalize=normalize,
                    )
                    with pf.Card(css_class="p-3"):
                        pf.Heading(
                            content=f"d{d}  ({cfg['ground_term']})",
                            level=4,
                        )
                        LineChart(
                            data=rows,
                            series=series,
                            x_axis=x_key,
                            show_legend=False,
                            show_tooltip=True,
                            show_grid=True,
                            show_dots=False,
                            height=240,
                        )
        return app


def _register_heatmap(mcp: FastMCP) -> None:
    """Energy-vs-(B,C) heatmap for one term at fixed Dq, via Chart.js iframe."""

    @mcp.tool(
        name="ts_parameter_heatmap_app",
        title="Energy heatmap over Racah (B, C)",
        version=_pkg_version,
        tags={"tanabesugano", "heatmap", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=HEATMAP_URI),
    )
    def ts_parameter_heatmap_app(
        d_count: int,
        term: str,
        Dq: float = 900.0,
        level: int = 0,
        b_min: float = 600.0,
        b_max: float = 1200.0,
        c_min: float = 3000.0,
        c_max: float = 5500.0,
        steps: int = 12,
    ) -> PrefabApp:
        """Sweep Racah B × C at fixed Dq and render a Chart.js heatmap of energies.

        Picks `level`-th eigenvalue of *term* at every (B, C) grid cell. The
        Chart.js + chartjs-chart-matrix view is hosted as the HTML resource
        at `ui://tanabesugano/heatmap.html`; non-app clients see the raw data
        table inside a Card.
        """
        import json as _json

        from tanabesugano.mcp._compute import compute_point

        b_vals = [b_min + (b_max - b_min) * i / max(steps - 1, 1) for i in range(steps)]
        c_vals = [c_min + (c_max - c_min) * j / max(steps - 1, 1) for j in range(steps)]
        cells: list[dict] = []
        table_rows: list[dict] = []
        for b in b_vals:
            for c in c_vals:
                try:
                    terms = compute_point(d_count, Dq, b, c)
                    energies = terms.get(term, [])
                    v = float(energies[level]) if level < len(energies) else float("nan")
                except (ValueError, RuntimeError):
                    v = float("nan")
                cells.append({"x": round(b, 1), "y": round(c, 1), "v": round(v, 1)})
                table_rows.append({"B": round(b, 1), "C": round(c, 1), "energy_cm": round(v, 1)})

        payload = {
            "title": f"d{d_count} {term} (level {level}) at Dq={Dq:g}",
            "cells": cells,
            "x_label": "Racah B (cm⁻¹)",
            "y_label": "Racah C (cm⁻¹)",
            "x_values": [round(b, 1) for b in b_vals],
            "y_values": [round(c, 1) for c in c_vals],
        }
        meta_json = _json.dumps(payload)

        with PrefabApp() as app, pf.Column(gap=3, css_class="p-6"):
            pf.Heading(content=payload["title"], level=3)
            pf.Muted(
                content=(
                    "Chart.js heatmap (chartjs-chart-matrix) renders in app-capable "
                    "clients via the linked resource. The fallback table below "
                    "always works."
                ),
            )
            # Stash the heatmap payload in a hidden Text so a client iframe
            # consuming ui://tanabesugano/heatmap.html can read it via the
            # MCP resource. Falls back to the DataTable for non-app clients.
            pf.Text(content=meta_json, css_class="hidden")
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="B", header="B (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="C", header="C (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="energy_cm", header="Energy (cm⁻¹)", sortable=True),
                ],
                rows=table_rows,
                search=True,
            )
        return app

    @mcp.resource(
        HEATMAP_URI,
        mime_type="text/html",
        title="Tanabe-Sugano parameter heatmap (Chart.js)",
        app=AppConfig(
            csp=ResourceCSP(
                resource_domains=[
                    "https://cdn.jsdelivr.net",
                    "https://unpkg.com",
                ],
            ),
        ),
    )
    def heatmap_view() -> str:
        """Chart.js + chartjs-chart-matrix renderer for ts_parameter_heatmap_app."""
        return _HEATMAP_HTML


# ─────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────


_BADGE_VARIANT_BY_MULT: dict[int, str] = {
    1: "secondary",
    2: "default",
    3: "default",
    4: "success",
    5: "warning",
    6: "destructive",
    7: "secondary",
}


def _multiplicity_of(term: str) -> int:
    head = term.split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return 0


def _badge_variant(term: str) -> str:
    return _BADGE_VARIANT_BY_MULT.get(_multiplicity_of(term), "secondary")


# Chart.js + chartjs-chart-matrix heatmap renderer.  No Plotly anywhere.
_HEATMAP_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="light dark">
  <title>Tanabe-Sugano heatmap</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-chart-matrix@2.0.1/dist/chartjs-chart-matrix.min.js"></script>
  <style>
    html, body { margin: 0; padding: 0; background: transparent; }
    #wrap { padding: 10px; }
    canvas { max-height: 460px; }
    .hint { font-family: -apple-system, system-ui, sans-serif; color: #888;
            padding: 12px; font-size: 13px; }
  </style>
</head>
<body>
  <div id="wrap">
    <canvas id="hm"></canvas>
    <div id="hint" class="hint">Waiting for ts_parameter_heatmap_app result…</div>
  </div>
  <script type="module">
    import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";
    const app = new App({ name: "TS Heatmap", version: "1.0.0" });
    let chart = null;
    app.ontoolresult = ({ content }) => {
      // The Prefab Column emits a hidden Text with the heatmap JSON payload.
      const txt = (content || []).find(c => c.type === 'text');
      if (!txt) return;
      let payload;
      try { payload = JSON.parse(txt.text); }
      catch (e) {
        document.getElementById('hint').textContent = 'Invalid payload: ' + e.message;
        return;
      }
      document.getElementById('hint').style.display = 'none';
      const vs = payload.cells.map(c => c.v).filter(v => Number.isFinite(v));
      const vmin = Math.min(...vs);
      const vmax = Math.max(...vs);
      const colorAt = (v) => {
        if (!Number.isFinite(v)) return 'rgba(0,0,0,0.05)';
        const t = (v - vmin) / (vmax - vmin || 1);
        // viridis-ish: dark purple -> teal -> yellow
        const r = Math.round(68 + (253 - 68) * t);
        const g = Math.round(1  + (231 - 1)  * t);
        const b = Math.round(84 + (37  - 84) * t);
        return `rgb(${r},${g},${b})`;
      };
      const ctx = document.getElementById('hm').getContext('2d');
      if (chart) chart.destroy();
      const xWidth = payload.x_values.length > 1
        ? (payload.x_values[1] - payload.x_values[0]) : 1;
      const yHeight = payload.y_values.length > 1
        ? (payload.y_values[1] - payload.y_values[0]) : 1;
      chart = new Chart(ctx, {
        type: 'matrix',
        data: {
          datasets: [{
            label: payload.title,
            data: payload.cells,
            backgroundColor: (ctx) => colorAt(ctx.raw.v),
            width: ({chart}) =>
              (chart.chartArea?.width || 1) / payload.x_values.length - 1,
            height: ({chart}) =>
              (chart.chartArea?.height || 1) / payload.y_values.length - 1,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (i) =>
              `B=${i.raw.x}, C=${i.raw.y}: ${i.raw.v} cm⁻¹` } },
            title: { display: true, text: payload.title },
          },
          scales: {
            x: { type: 'linear', title: { display: true, text: payload.x_label } },
            y: { type: 'linear', title: { display: true, text: payload.y_label } },
          },
        },
      });
    };
    await app.connect();
  </script>
</body>
</html>
"""
