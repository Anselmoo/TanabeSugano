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
DIAGRAM_URI = "ui://tanabesugano/diagram.html"
SPECTRUM_URI = "ui://tanabesugano/spectrum.html"

# ── Optional Prefab / FastMCP apps API ───────────────────────────────────
try:
    from fastmcp.apps import AppConfig
    from fastmcp.apps import ResourceCSP
    from fastmcp.tools import ToolResult
    from mcp import types as _mcp_types
    from mcp.types import ToolAnnotations
    from prefab_ui import components as pf
    from prefab_ui.actions import CallTool
    from prefab_ui.app import PrefabApp
    from prefab_ui.components.charts import ChartSeries
    from prefab_ui.components.charts import LineChart
    from prefab_ui.components.charts import Sparkline

    from tanabesugano import __version__ as _pkg_version
    from tanabesugano.mcp._inputs import CM1_TO_EV

    _HAVE_APPS = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAVE_APPS = False


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_apps(mcp: FastMCP) -> None:
    """Register every Prefab-native ts_*_app tool plus the Chart.js resources."""
    if not _HAVE_APPS:
        log.debug("prefab_ui / fastmcp.apps not available; skipping all *_app tools.")
        return

    _register_explore(mcp)
    _register_plot_view(mcp)
    _register_diagram_app(mcp)
    _register_dashboard(mcp)
    _register_compare(mcp)
    _register_heatmap(mcp)
    _register_overlay(mcp)
    _register_reverse_fit(mcp)
    _register_ratio_fit(mcp)
    _register_spectrum(mcp)


# ─────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────

_READONLY_ANNOTATIONS = (
    ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
    if _HAVE_APPS
    else None
)
_TS_META: dict[str, object] = {"domain": "tanabesugano", "surface": "mcp", "interactive": True}


def _convert_energy(e_cm: float, unit: str) -> float:
    """Convert a cm^-1 value to the requested display unit.

    Args:
        e_cm: Energy in wavenumbers (cm^-1).
        unit: One of "cm1", "eV", "nm".  "nm" inverts the axis
            (shorter wavelength = higher energy).

    """
    if unit == "eV":
        return e_cm * CM1_TO_EV
    if unit == "nm":
        return 1e7 / e_cm if e_cm else float("nan")
    return e_cm  # "cm1" — no conversion


_Y_LABEL: dict[str, str] = {
    "cm1": "E (cm⁻¹)",
    "eV": "E (eV)",
    "nm": "E (nm)",
}


def _sweep_payload(
    d_count: int,
    dq_min: float,
    dq_max: float,
    steps: int,
    b_val: float,
    c_val: float,
    *,
    normalize: bool,
    energy_unit: str = "cm1",
) -> tuple[list[dict], list[ChartSeries], str, str, str, str, float]:
    """Compute one sweep and return Prefab-shaped data: rows + ChartSeries list.

    Returns:
        (rows, series, title, x_axis_key, x_label, y_label, ground_y) where
        `rows` is a list of dicts keyed by x-axis value and one column per
        unique term (level-0 only, so Prefab LineChart doesn't collapse).
        `ground_y` is in the requested energy unit.

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
            # Round x to 3 dp — shows "0.716" not "0.7161613750298401".
            x_key: round(float(dq * 10.0 / b_val), 3) if normalize else round(float(dq * 10.0), 1),
        }
        for term, energies in points[i].items():
            if not energies:
                continue
            key = f"{term}_0"
            e_raw = float(energies[0]) if energies else 0.0
            if normalize and b_val:
                y_val = round(e_raw / b_val, 3)
            elif energy_unit == "cm1":
                y_val = round(e_raw, 1)
            else:
                y_val = round(_convert_energy(e_raw, energy_unit), 4)
            row[key] = y_val
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
    y_label = "E/B" if normalize else _Y_LABEL.get(energy_unit, "E (cm⁻¹)")
    ground_y = min(row.get(f"{ground_term}_0", float("inf")) for row in rows)
    return rows, series, title, x_key, x_label, y_label, ground_y


def _chartjs_series_payload(
    rows: list[dict],
    series: list[ChartSeries],
    x_key: str,
    *,
    title: str,
    x_label: str,
    y_label: str,
) -> str:
    """Build the JSON payload for the Chart.js diagram / overlay HTML views.

    Args:
        rows: list of dicts (x + per-term y values).
        series: list of ChartSeries with data_key, label, color.
        x_key: the dict key for x values.
        title, x_label, y_label: display strings.

    Returns:
        JSON string with ``{title, x_label, y_label, series}`` where each
        series entry is ``{label, color, data: [{x, y}]}``.

    """
    import json as _json

    chart_series = []
    for s in series:
        data = [{"x": row[x_key], "y": row.get(s.data_key)} for row in rows]
        chart_series.append(
            {"label": s.label or s.data_key, "color": s.color or "#888", "data": data}
        )
    return _json.dumps(
        {"title": title, "x_label": x_label, "y_label": y_label, "series": chart_series}
    )


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
    """Register ts_plot_view with Chart.js rendering for proper axis labels."""

    @mcp.tool(
        name="ts_plot_view",
        title="Tanabe-Sugano chart (in-chat)",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_plot_view(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
        energy_unit: str = "cm1",
    ) -> ToolResult:
        """Render a Tanabe-Sugano sweep as an interactive Chart.js chart with proper axis labels.

        Lighter than `ts_diagram_app` — just the curve, no table. The Chart.js
        view at ui://tanabesugano/diagram.html renders with labelled x/y axes.
        Supports energy_unit = "cm1" | "eV" | "nm" for the y-axis.
        Note: "nm" inverts the energy axis (shorter wavelength = higher energy).
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
            energy_unit=energy_unit,
        )
        payload = _chartjs_series_payload(
            rows, series, x_key, title=title, x_label=x_label, y_label=y_label
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])

    @mcp.resource(
        DIAGRAM_URI,
        mime_type="text/html",
        title="Tanabe-Sugano Chart.js line chart",
        app=AppConfig(
            csp=ResourceCSP(resource_domains=["https://cdn.jsdelivr.net", "https://unpkg.com"]),
        ),
    )
    def diagram_view() -> str:
        """Chart.js line chart with proper x/y axis titles for ts_plot_view et al."""
        return _DIAGRAM_HTML


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
        energy_unit: str = "cm1",
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
            energy_unit=energy_unit,
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
            pf.Text(content=f"↑ {y_label}", css_class="text-xs text-muted-foreground font-mono")
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
            pf.Text(
                content=f"→ {x_label}",
                css_class="text-xs text-muted-foreground font-mono text-right",
            )
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
        energy_unit: str = "cm1",
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
            cols = 2 if len(valid) <= 4 else 3
            with pf.Grid(columns=cols, gap=4):
                for d in valid:
                    cfg = DEFAULTS[d]
                    b_val, c_val = resolve_bc(d, None, None)
                    rows, series, _title, x_key, x_label, y_label, _ = _sweep_payload(
                        d,
                        dq_min,
                        dq_max,
                        steps,
                        b_val,
                        c_val,
                        normalize=normalize,
                        energy_unit=energy_unit,
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
                        pf.Muted(content=f"{x_label}  /  {y_label}")
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
                except Exception:
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
# New innovative tools
# ─────────────────────────────────────────────────────────────────────────


def _register_overlay(mcp: FastMCP) -> None:
    """Overlay multiple d-configurations on one Chart.js chart."""

    @mcp.tool(
        name="ts_overlay_app",
        title="Overlay Tanabe-Sugano diagrams",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "overlay", "compare"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_overlay_app(
        d_counts: list[int],
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        normalize: bool = True,
        energy_unit: str = "cm1",
    ) -> ToolResult:
        """Overlay multiple d-configurations on one Chart.js chart with proper axis labels.

        Shows partially-overlapping Tanabe-Sugano diagrams on shared axes, making
        the hole-particle symmetry pairs (d2/d8, d3/d7, d4/d6) directly comparable.
        Each d-count gets a distinct color tint; terms are distinguishable by line style.
        Use `energy_unit` to switch between cm1 / eV / nm on the y-axis.
        """
        import json as _json

        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
        from tanabesugano.mcp.tools._shared import resolve_bc
        from tanabesugano.plot_style import color_for
        from tanabesugano.plot_style import term_to_unicode

        valid = [d for d in d_counts if d in SUPPORTED_D_COUNTS]
        if not valid:
            valid = [3, 7]

        # Assign a distinct base tint per d-count, then use term color within.
        # Each series label is prefixed by "d{N}" to disambiguate across overlaid configs.
        all_series: list[dict] = []
        x_label = y_label = title = ""

        for d in valid:
            b_val, c_val = resolve_bc(d, None, None)
            rows, series, title, x_key, x_label, y_label, _ = _sweep_payload(
                d,
                dq_min,
                dq_max,
                steps,
                b_val,
                c_val,
                normalize=normalize,
                energy_unit=energy_unit,
            )
            for s in series:
                data = [{"x": row[x_key], "y": row.get(s.data_key)} for row in rows]
                all_series.append(
                    {
                        "label": f"d{d} {term_to_unicode(s.data_key.rsplit('_', 1)[0])}",
                        "color": s.color or color_for(s.data_key.rsplit("_", 1)[0]),
                        "data": data,
                        "d_count": d,
                    }
                )

        title_overlay = f"Overlay: {', '.join(f'd{d}' for d in valid)}"
        payload = _json.dumps(
            {
                "title": title_overlay,
                "x_label": x_label,
                "y_label": y_label,
                "series": all_series,
            }
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


def _register_reverse_fit(mcp: FastMCP) -> None:
    """Fit Dq/B from observed absorption peak positions."""

    @mcp.tool(
        name="ts_reverse_fit_app",
        title="Fit Dq/B from observed peaks",
        version=_pkg_version,
        tags={"tanabesugano", "fitting", "reverse"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_reverse_fit_app(
        d_count: int,
        observed_peaks: list[float],
        energy_unit: str = "cm1",
        dq_max_search: float = 2500.0,
        b_min: float = 400.0,
        b_max: float = 1600.0,
        grid_steps: int = 25,
    ) -> PrefabApp:
        """Grid-search Dq and Racah B to best-fit observed absorption peak positions.

        Performs a coarse grid search over (Dq, B) space, comparing computed
        spin-allowed transitions (same ground-state multiplicity) against the
        observed peak positions. Returns best-fit parameters plus a residuals table.

        Args:
            d_count: d-electron count (2–8).
            observed_peaks: Measured absorption maxima in the chosen energy_unit.
            energy_unit: Unit of observed_peaks: "cm1" (default), "eV", or "nm".
            dq_max_search: Upper Dq search limit in cm^-1.
            b_min, b_max: Racah B search range (cm^-1).
            grid_steps: Grid resolution per axis (total grid_steps² evaluations).

        """
        import math

        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        # Convert observed peaks to cm^-1.
        def to_cm1(e: float) -> float:
            if energy_unit == "eV":
                return e / CM1_TO_EV
            if energy_unit == "nm":
                return 1e7 / e if e else float("nan")
            return e

        peaks_cm = sorted(to_cm1(p) for p in observed_peaks if p > 0)
        if not peaks_cm:
            with PrefabApp() as app, pf.Column(gap=3, css_class="p-6"):
                pf.Heading(content="No valid peaks provided", level=3)
            return app

        default_B = DEFAULTS[d_count]["default_B"]
        default_C = DEFAULTS[d_count]["default_C"]
        ground_mult = _multiplicity_of(DEFAULTS[d_count]["ground_term"])

        best_dq = best_b = best_rms = float("inf")
        results: list[dict] = []

        dq_grid = [dq_max_search * i / max(grid_steps - 1, 1) for i in range(grid_steps)]
        b_grid = [b_min + (b_max - b_min) * j / max(grid_steps - 1, 1) for j in range(grid_steps)]

        for dq in dq_grid:
            for b in b_grid:
                try:
                    terms = compute_point(d_count, dq, b, default_C)
                except Exception:
                    continue
                # Collect spin-allowed transitions from the ground term.
                allowed: list[float] = []
                for term_key, energies in terms.items():
                    if _multiplicity_of(term_key) == ground_mult:
                        allowed.extend(float(e) for e in energies if e > 0)
                if not allowed:
                    continue
                allowed.sort()
                # Match each observed peak to the closest computed transition.
                rms = 0.0
                for pk in peaks_cm:
                    closest = min(allowed, key=lambda e, pk=pk: abs(e - pk))
                    rms += (closest - pk) ** 2
                rms = math.sqrt(rms / len(peaks_cm))
                results.append({"Dq": round(dq, 1), "B": round(b, 1), "RMS": round(rms, 1)})
                if rms < best_rms:
                    best_rms, best_dq, best_b = rms, dq, b

        best_c = default_C
        _, best_c = resolve_bc(d_count, best_b, None)

        # Build best-fit terms table.
        try:
            best_terms = compute_point(d_count, best_dq, best_b, best_c)
        except (ValueError, RuntimeError):
            best_terms = {}
        table_rows: list[dict] = []
        for term_key, energies in best_terms.items():
            for n, e in enumerate(energies):
                table_rows.append(
                    {
                        "term": term_key,
                        "level": n,
                        "energy_cm": round(float(e), 1),
                        "spin_allowed": _multiplicity_of(term_key) == ground_mult,
                    }
                )
        table_rows.sort(key=lambda r: r["energy_cm"])

        results.sort(key=lambda r: r["RMS"])
        top_results = results[:20]

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(content=f"Reverse fit: d{d_count}", level=3)
            with pf.Grid(columns=3, gap=4):
                pf.Metric(label="Best Dq", value=f"{best_dq:.1f} cm⁻¹")
                pf.Metric(label="Best B", value=f"{best_b:.1f} cm⁻¹")
                pf.Metric(label="RMS residual", value=f"{best_rms:.1f} cm⁻¹")
            pf.Text(
                content=f"Observed peaks ({energy_unit}): {', '.join(str(p) for p in observed_peaks)}",
                css_class="text-sm text-muted-foreground",
            )
            pf.Separator()
            pf.Heading(content="Top 20 grid candidates", level=4)
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="Dq", header="Dq (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="B", header="B (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="RMS", header="RMS (cm⁻¹)", sortable=True),
                ],
                rows=top_results,
                search=False,
            )
            pf.Separator()
            pf.Heading(content="Term energies at best-fit Dq", level=4)
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="term", header="Term", sortable=True),
                    pf.DataTableColumn(key="level", header="Level", sortable=True),
                    pf.DataTableColumn(key="energy_cm", header="E (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="spin_allowed", header="Spin-allowed"),
                ],
                rows=table_rows,
                search=True,
            )
        return app


def _register_ratio_fit(mcp: FastMCP) -> None:
    """Custom TS diagram derived from two/three measured absorption bands."""

    @mcp.tool(
        name="ts_ratio_fit_app",
        title="Custom TS diagram from band positions",
        version=_pkg_version,
        tags={"tanabesugano", "fitting", "ratios"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_ratio_fit_app(
        d_count: int,
        v1: float,
        v2: float,
        v3: float | None = None,
        energy_unit: str = "cm1",
        b_min: float = 400.0,
        b_max: float = 1600.0,
        grid_steps: int = 30,
    ) -> ToolResult:
        """Derive Dq and Racah B from two or three measured band positions.

        Uses the two-ratio method: finds the (Dq, B) grid point where the
        computed spin-allowed transitions best reproduce the observed band ratios
        nu2/nu1 (and nu3/nu1 when v3 is provided). Returns a Chart.js TS diagram
        with the fitted Dq/B region highlighted.

        Args:
            d_count: d-electron count (2–8).
            v1, v2: First and second spin-allowed band positions.
            v3: Optional third band position.
            energy_unit: Unit of v1/v2/v3 (cm1, eV, nm).
            b_min, b_max: Racah B search range (cm^-1).
            grid_steps: Grid resolution.

        """
        import json as _json
        import math

        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        def to_cm1(e: float) -> float:
            if energy_unit == "eV":
                return e / CM1_TO_EV
            if energy_unit == "nm":
                return 1e7 / e if e else float("nan")
            return e

        obs = sorted(to_cm1(x) for x in ([v1, v2] + ([v3] if v3 else [])) if x > 0)
        if len(obs) < 2:
            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text='{"title":"Error","x_label":"","y_label":"","series":[],"error":"Need at least 2 peaks."}',
                    )
                ]
            )

        obs_ratios = [obs[i] / obs[0] for i in range(1, len(obs))]
        ground_mult = _multiplicity_of(DEFAULTS[d_count]["ground_term"])
        default_C = DEFAULTS[d_count]["default_C"]
        dq_max_search = obs[0] * 2.0  # sensible upper bound

        best_dq = best_b = float("inf")
        best_score = float("inf")

        dq_grid = [dq_max_search * i / max(grid_steps - 1, 1) for i in range(grid_steps)]
        b_grid = [b_min + (b_max - b_min) * j / max(grid_steps - 1, 1) for j in range(grid_steps)]

        for dq in dq_grid:
            for b in b_grid:
                try:
                    terms = compute_point(d_count, dq, b, default_C)
                except Exception:
                    continue
                allowed = sorted(
                    float(e)
                    for term_key, energies in terms.items()
                    if _multiplicity_of(term_key) == ground_mult
                    for e in energies
                    if e > 0
                )
                if len(allowed) < 2:
                    continue
                comp_ratios = [
                    allowed[i] / allowed[0] for i in range(1, min(len(obs), len(allowed)))
                ]
                if not comp_ratios:
                    continue
                # Score: RMS of ratio differences + magnitude match of v1.
                ratio_err = math.sqrt(
                    sum((cr - or_) ** 2 for cr, or_ in zip(comp_ratios, obs_ratios))
                    / len(comp_ratios)
                )
                mag_err = abs(allowed[0] - obs[0]) / obs[0]
                score = ratio_err + 0.3 * mag_err
                if score < best_score:
                    best_score, best_dq, best_b = score, dq, b

        if not (0 < best_dq < 1e7) or not (0 < best_b < 1e7):
            # Grid search found nothing valid; return an error payload.
            import json as _json

            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text=_json.dumps(
                            {
                                "title": f"No fit found for d{d_count}",
                                "x_label": "",
                                "y_label": "",
                                "series": [],
                                "error": "Could not converge: try different peak values or a wider B range.",
                            }
                        ),
                    )
                ]
            )

        b_fit, c_fit = resolve_bc(d_count, best_b, None)
        dq_lo = max(0.0, best_dq * 0.6)
        dq_hi = best_dq * 1.6

        try:
            rows, series, title, x_key, x_label, y_label, _ = _sweep_payload(
                d_count,
                dq_lo,
                dq_hi,
                grid_steps,
                b_fit,
                c_fit,
                normalize=True,
            )
        except Exception:
            rows, series, title, x_key, x_label, y_label = (
                [],
                [],
                f"d{d_count} fit",
                "x",
                "10Dq/B",
                "E/B",
            )

        # Mark the fitted Dq/B location as a vertical annotation dataset.
        x_fit_norm = round(best_dq * 10.0 / b_fit, 3) if b_fit else 0.0
        all_series: list[dict] = []
        for s in series:
            data = [{"x": row[x_key], "y": row.get(s.data_key)} for row in rows]
            all_series.append(
                {"label": s.label or s.data_key, "color": s.color or "#888", "data": data}
            )
        # Add vertical marker series at the fitted Dq.
        all_series.append(
            {
                "label": f"Fitted 10Dq/B = {x_fit_norm:g}",
                "color": "#FF0000",
                "data": [{"x": x_fit_norm, "y": 0}, {"x": x_fit_norm, "y": 150}],
                "borderDash": [6, 3],
            }
        )

        title_custom = f"Custom TS d{d_count}: Dq={best_dq:.1f}, B={b_fit:.1f} cm⁻¹"
        payload = _json.dumps(
            {"title": title_custom, "x_label": x_label, "y_label": y_label, "series": all_series}
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


def _register_spectrum(mcp: FastMCP) -> None:
    """Simulated UV-Vis absorption spectrum with Lorentzian broadening."""

    @mcp.tool(
        name="ts_spectrum_app",
        title="Simulated UV-Vis absorption spectrum",
        version=_pkg_version,
        tags={"tanabesugano", "spectrum", "simulation"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=SPECTRUM_URI),
    )
    def ts_spectrum_app(
        d_count: int,
        Dq: float = 900.0,
        B: float | None = None,
        C: float | None = None,
        energy_unit: str = "cm1",
        broadening: float = 500.0,
        n_points: int = 500,
    ) -> ToolResult:
        """Simulate a Lorentzian-broadened UV-Vis absorption spectrum.

        Computes all term energies from the ground state; spin-allowed transitions
        (same 2S+1 as the ground term) appear at full height while spin-forbidden
        ones appear at 5% height. Returns a Chart.js line chart with the energy
        axis in the requested unit (cm1 / eV / nm).

        Args:
            d_count: d-electron count (2–8).
            Dq: Crystal-field strength (cm^-1).
            B, C: Racah parameters (cm^-1); defaults to per-configuration values.
            energy_unit: x-axis unit (cm1, eV, nm). Note nm inverts the axis.
            broadening: Lorentzian FWHM in cm^-1.
            n_points: Number of points in the spectrum curve.

        """
        import json as _json
        import math

        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        b_val, c_val = resolve_bc(d_count, B, C)
        terms = compute_point(d_count, Dq, b_val, c_val)
        ground_mult = _multiplicity_of(DEFAULTS[d_count]["ground_term"])

        # Collect stick transitions (energy_cm, relative_intensity).
        sticks: list[tuple[float, float]] = []
        for term_key, energies in terms.items():
            mult = _multiplicity_of(term_key)
            intensity = 1.0 if mult == ground_mult else 0.05
            for e in energies:
                e_f = float(e)
                if e_f > 1e-3:  # skip ground state (≈ 0)
                    sticks.append((e_f, intensity))

        if not sticks:
            payload = _json.dumps(
                {
                    "title": f"d{d_count} spectrum — no transitions",
                    "x_label": "",
                    "y_label": "Abs.",
                    "series": [],
                }
            )
            return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])

        e_min_cm = max(0.0, min(e for e, _ in sticks) - 3 * broadening)
        e_max_cm = max(e for e, _ in sticks) + 3 * broadening
        gamma = broadening / 2.0  # half-width

        e_axis_cm = [
            e_min_cm + (e_max_cm - e_min_cm) * i / max(n_points - 1, 1) for i in range(n_points)
        ]

        # Lorentzian broadening: sum of I * (γ/π) / ((ε - ε₀)² + γ²)
        spectrum = [
            sum(inten * (gamma / math.pi) / ((e_axis - e0) ** 2 + gamma**2) for e0, inten in sticks)
            for e_axis in e_axis_cm
        ]
        # Normalise to max = 1.
        s_max = max(spectrum) if spectrum else 1.0
        spectrum = [round(s / s_max, 4) if s_max else 0.0 for s in spectrum]

        # Convert x-axis to requested unit.
        x_axis = [round(_convert_energy(e, energy_unit), 4) for e in e_axis_cm]
        x_label_map = {"cm1": "E (cm⁻¹)", "eV": "E (eV)", "nm": "λ (nm)"}
        x_label = x_label_map.get(energy_unit, "E (cm⁻¹)")

        data = [{"x": x, "y": y} for x, y in zip(x_axis, spectrum)]
        title_spectrum = f"Simulated spectrum d{d_count} (Dq={Dq:g}, B={b_val:g} cm⁻¹)"
        payload = _json.dumps(
            {
                "title": title_spectrum,
                "x_label": x_label,
                "y_label": "Absorbance (arb. units)",
                "series": [{"label": "Simulated spectrum", "color": "#0072B2", "data": data}],
            }
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])

    @mcp.resource(
        SPECTRUM_URI,
        mime_type="text/html",
        title="TanabeSugano simulated spectrum (Chart.js)",
        app=AppConfig(
            csp=ResourceCSP(resource_domains=["https://cdn.jsdelivr.net", "https://unpkg.com"]),
        ),
    )
    def spectrum_view() -> str:
        """Chart.js line chart renderer for ts_spectrum_app — same schema as diagram.html."""
        return _DIAGRAM_HTML  # spectrum uses same Chart.js view as line diagrams


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


# Chart.js line chart with proper axis titles. Used by ts_plot_view, ts_overlay_app,
# ts_ratio_fit_app, and ts_spectrum_app. Payload schema:
#   { title, x_label, y_label, series: [{label, color, data: [{x, y}], borderDash?}] }
_DIAGRAM_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="light dark">
  <title>Tanabe-Sugano diagram</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    html, body { margin: 0; padding: 0; background: transparent; }
    #wrap { padding: 8px; }
    canvas { max-height: 460px; }
    .hint { font-family: -apple-system, system-ui, sans-serif; color: #888; padding: 12px; font-size: 13px; }
  </style>
</head>
<body>
  <div id="wrap"><canvas id="chart"></canvas></div>
  <div id="hint" class="hint">Waiting for result…</div>
  <script type="module">
    import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";
    const app = new App({ name: "TS Chart", version: "1.0.0" });
    let chart = null;
    app.ontoolresult = ({ content }) => {
      const txt = (content || []).find(c => c.type === 'text');
      if (!txt) return;
      let p;
      try { p = JSON.parse(txt.text); } catch(e) {
        document.getElementById('hint').textContent = 'Parse error: ' + e.message;
        return;
      }
      document.getElementById('hint').style.display = 'none';
      if (chart) chart.destroy();
      const ctx = document.getElementById('chart').getContext('2d');
      const datasets = (p.series || []).map(s => ({
        label: s.label || '',
        data: s.data || [],
        borderColor: s.color || '#888',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        borderDash: s.borderDash || [],
        tension: 0.3,
      }));
      chart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
          responsive: true,
          animation: false,
          parsing: false,
          plugins: {
            title: { display: !!p.title, text: p.title || '', font: { size: 14 } },
            legend: { display: true, labels: { boxWidth: 18, font: { size: 10 } } },
            tooltip: { mode: 'index', intersect: false },
          },
          scales: {
            x: {
              type: 'linear',
              title: { display: true, text: p.x_label || '', font: { size: 12 } },
              ticks: { maxTicksLimit: 10 },
            },
            y: {
              title: { display: true, text: p.y_label || '', font: { size: 12 } },
              ticks: { maxTicksLimit: 8 },
            },
          },
        },
      });
    };
    await app.connect();
  </script>
</body>
</html>
"""


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
