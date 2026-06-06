"""FastMCP tools for the TanabeSugano server (Prefab + Chart.js).

Two rendering pipelines coexist:

* **Chart.js iframes**: ts_diagram_app, ts_plot_view, ts_overlay_app,
  ts_compare_app, ts_spectrum_app, ts_oxidation_landscape_app,
  ts_parameter_heatmap_app, ts_reverse_fit_app, ts_ratio_fit_app. Each
  declares ``app=AppConfig(resource_uri=...)`` pointing at one of three
  hand-registered ``ui://tanabesugano/{diagram,heatmap,spectrum}.html``
  resources (MIME ``text/html;profile=mcp-app`` per the MCP Apps spec)
  and returns a ``ToolResult`` carrying a JSON Chart.js payload.
* **Prefab-native**: ts_compute_app and ts_dashboard_app declare ``app=True``
  and return a ``PrefabApp`` rendered via FastMCP's auto-generated
  ``ui://prefab/tool/<hash>/renderer.html`` resource.

Imports happen at module level so Pydantic's TypeAdapter can resolve the
PrefabApp forward refs against this module's globalns when FastMCP builds
its tool schemas. When the ``[mcp]`` extra is missing the whole module
no-ops via the ``_HAVE_APPS`` guard.
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
    from prefab_ui.app import PrefabApp
    from prefab_ui.components.charts import ChartSeries  # used by _sweep_payload
    from prefab_ui.components.charts import Sparkline  # used by ts_dashboard_app

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

    _register_plot_view(mcp)
    _register_diagram_app(mcp)
    _register_dashboard(mcp)
    _register_compare(mcp)
    _register_heatmap(mcp)
    _register_overlay(mcp)
    _register_reverse_fit(mcp)
    _register_ratio_fit(mcp)
    _register_spectrum(mcp)
    _register_oxidation_landscape(mcp)
    _register_compute_table(mcp)


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
            x_key: (round(float(dq * 10.0 / b_val), 3) if b_val else 0.0)
            if normalize
            else round(float(dq * 10.0), 1),
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
    ground_y = min((row.get(f"{ground_term}_0", float("inf")) for row in rows), default=0.0)
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
            {"label": s.label or s.data_key, "color": s.color or "#888", "data": data},
        )
    return _json.dumps(
        {"title": title, "x_label": x_label, "y_label": y_label, "series": chart_series},
    )


# ─────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────


# ts_explore_app was removed: the Prefab Form.from_model component renders
# as a frozen / unresponsive panel in current Claude Desktop builds, and
# its on_submit=CallTool(tool="ts_diagram_app") wiring became stale after
# ts_diagram_app moved to the Chart.js ToolResult path (it no longer
# consumes Prefab state). Discovery now goes through tanabesugano_why and
# tanabesugano_explain_complex prompts, or directly through
# ts_supported_configs + ts_diagram_app.


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
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        if d_count not in DEFAULTS:
            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text=f"d_count must be 2..8, got {d_count}",
                    ),
                ],
            )
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
            rows,
            series,
            x_key,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])

    @mcp.resource(
        DIAGRAM_URI,
        # MCP Apps spec — UI resources must use the profiled MIME type.
        # Claude Desktop advertises ``extensions.io.modelcontextprotocol/ui``
        # with ``mimeTypes: ["text/html;profile=mcp-app"]`` in initialize;
        # plain ``text/html`` is rejected with "Unsupported UI resource
        # content format". Reference:
        # https://modelcontextprotocol.io/extensions/apps/overview
        mime_type="text/html;profile=mcp-app",
        title="Tanabe-Sugano Chart.js line chart",
        app=AppConfig(
            csp=ResourceCSP(resource_domains=["https://cdn.jsdelivr.net", "https://unpkg.com"]),
        ),
    )
    def diagram_view() -> str:
        """Chart.js line chart with proper x/y axis titles for ts_plot_view et al."""
        return _DIAGRAM_HTML


def _register_diagram_app(mcp: FastMCP) -> None:
    """Full diagram rendered via Chart.js (DIAGRAM_URI).

    Previously this tool returned a Prefab native ``PrefabApp`` with a
    ``LineChart`` + slider + ``DataTable``. The Prefab ``LineChart`` renders
    as a black canvas in current Claude Desktop builds even when the data is
    valid (verified: 12 series with varying y-values still produced a blank
    panel). Switched to the same Chart.js HTML resource path used by
    ``ts_plot_view`` / ``ts_overlay_app`` / ``ts_spectrum_app``, which all
    render reliably. The slider+table view is now available via
    ``ts_compute_app`` (table at one Dq) and ``ts_terms_table_data`` (raw
    rows for any agent).
    """

    @mcp.tool(
        name="ts_diagram_app",
        title="Tanabe-Sugano diagram (Chart.js)",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
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
    ) -> ToolResult:
        """Render a Tanabe-Sugano diagram as a Chart.js line plot.

        Returns the same JSON payload as ``ts_plot_view`` but with the
        ground term and reference 10Dq highlighted in the title so the
        chart is immediately interpretable. For the sortable level table
        at one (Dq, B, C) point, use ``ts_compute_app``; for the
        machine-readable rows use ``ts_terms_table_data``.

        Args:
            d_count: d-electron count (2–8).
            dq_min, dq_max: Dq sweep bounds in cm⁻¹.
            steps: Number of Dq grid points.
            B, C: Racah parameters in cm⁻¹; defaults per d_count.
            normalize: Plot E/B on y, 10Dq/B on x (standard Tanabe-Sugano).
            energy_unit: Used only when ``normalize=False`` (cm1 / eV / nm).

        """
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        b_val, c_val = resolve_bc(d_count, B, C)
        rows, series, _title, x_key, x_label, y_label, _ground_y = _sweep_payload(
            d_count,
            dq_min,
            dq_max,
            steps,
            b_val,
            c_val,
            normalize=normalize,
            energy_unit=energy_unit,
        )
        ground_term = DEFAULTS[d_count]["ground_term"]
        title_with_context = (
            f"d{d_count} ({ground_term}) — B={b_val:g}, C={c_val:g} cm⁻¹  "
            f"[Dq {dq_min:g}–{dq_max:g}, {steps} pts]"
        )
        payload = _chartjs_series_payload(
            rows,
            series,
            x_key,
            title=title_with_context,
            x_label=x_label,
            y_label=y_label,
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


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

        For each d-count card: ground term symbol, matrix size, default Racah
        parameters, representative free ions, a one-line chemical note, and a
        Sparkline of the **first excited state energy** across a 0–1500 cm⁻¹
        Dq sweep — the band that an absorption spectrum would actually show.
        Useful as a 'home page' before drilling into one configuration with
        `ts_diagram_app`.
        """
        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
        from tanabesugano.mcp._compute import sweep_dq
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp._defaults import GROUND_STATE_NOTES
        from tanabesugano.mcp._defaults import ION_BY_D_COUNT
        from tanabesugano.plot_style import term_to_unicode

        # Energy threshold above which an eigenvalue counts as a real excited
        # state — solvers zero the ground manifold so anything ≤ this is noise.
        ground_eps = 1.0
        # Representative octahedral Dq for displaying a single absorption-band
        # number alongside the sparkline. 1000 cm⁻¹ is mid-range for the
        # transition metals we cover (Dq sits between 600 and 1800 for the
        # ions listed in ION_BY_D_COUNT).
        ref_dq = 1000.0

        cards: list[dict] = []
        for d in SUPPORTED_D_COUNTS:
            cfg = DEFAULTS[d]
            b = cfg["default_B"]
            c = cfg["default_C"]
            _, points = sweep_dq(d, 0.0, 1500.0, 30, b, c)
            # First excited state energy at each Dq step: the lowest eigenvalue
            # above the ground manifold across all term symbols. This gives a
            # curve that meaningfully tracks the lowest d-d absorption band as
            # crystal-field strength grows.
            spark: list[float] = []
            for p in points:
                all_e = sorted(float(e) for term in p.values() for e in term)
                first_excited = next((e for e in all_e if e > ground_eps), 0.0)
                spark.append(round(first_excited, 1))

            # At a fixed reference Dq, name the lowest excited term so the
            # card reports a concrete assignable transition, not just an
            # energy number floating in space.
            from tanabesugano.mcp._compute import compute_point

            ref_terms = compute_point(d, ref_dq, b, c)
            ref_pairs: list[tuple[float, str]] = []
            for term_name, eigs in ref_terms.items():
                for e in eigs:
                    if e > ground_eps:
                        ref_pairs.append((float(e), term_name))
            ref_pairs.sort(key=lambda t: t[0])
            if ref_pairs:
                first_e, first_term = ref_pairs[0]
                ref_label = (
                    f"→ {term_to_unicode(first_term)}: {first_e:,.0f} cm⁻¹"
                    f"  @ 10Dq = {ref_dq * 10:.0f}"
                )
            else:
                ref_label = ""

            cards.append({"d": d, "cfg": cfg, "spark": spark, "ref_label": ref_label})

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(content="Tanabe-Sugano: d² – d⁸ overview", level=2)
            pf.Muted(
                content=(
                    "Per configuration: ground term, matrix size, default Racah "
                    "B/C, representative free ions, and a sparkline of the first "
                    "excited state energy from Dq = 0 to 1500 cm⁻¹ — the lowest "
                    "d-d band an absorption spectrum will show. Use "
                    "`ts_diagram_app` with d_count = N for the full diagram."
                ),
            )
            with pf.Grid(columns=4, gap=4):
                for c_data in cards:
                    d = c_data["d"]
                    cfg = c_data["cfg"]
                    ions = ION_BY_D_COUNT.get(d, ())
                    note = GROUND_STATE_NOTES.get(d, "")
                    # Strip the leading "dN (...):" prefix from the note so the
                    # card subtitle doesn't repeat info already shown above.
                    note_short = note.split(":", 1)[-1].strip() if ":" in note else note
                    e_min = min(c_data["spark"]) if c_data["spark"] else 0.0
                    e_max = max(c_data["spark"]) if c_data["spark"] else 0.0
                    with pf.Card(css_class="p-4"):
                        pf.Heading(content=f"d{d}", level=4)
                        with pf.Grid(columns=2, gap=2):
                            pf.Metric(
                                label="Ground term",
                                value=cfg["ground_term"],
                            )
                            pf.Metric(
                                label="Matrix",
                                value=str(cfg["matrix_size"]),
                                description="terms",
                            )
                        pf.Muted(
                            content=(f"Ions: {', '.join(ions) if ions else '—'}"),
                        )
                        pf.Muted(
                            content=(
                                f"B = {cfg['default_B']:g} cm⁻¹  C = {cfg['default_C']:g} cm⁻¹"
                            ),
                        )
                        pf.Text(
                            content="First excited state (cm⁻¹) vs Dq:",
                            css_class="text-xs text-muted-foreground",
                        )
                        Sparkline(
                            data=c_data["spark"],
                            height=48,
                            variant="default",
                            fill=True,
                        )
                        pf.Muted(
                            content=(f"{e_min:.0f} → {e_max:.0f} cm⁻¹ at 10Dq = 0 → 15 000 cm⁻¹"),
                            css_class="text-xs",
                        )
                        if c_data.get("ref_label"):
                            pf.Text(
                                content=c_data["ref_label"],
                                css_class="text-xs font-mono text-primary",
                            )
                        if note_short:
                            pf.Muted(content=note_short, css_class="text-xs")
        return app


def _register_compare(mcp: FastMCP) -> None:
    """Compare diagrams via Chart.js: each d-count's terms drawn as its own
    series on one shared (10Dq/B, E/B) axis set. Replaces the previous
    Prefab small-multiples grid that did not render in Claude Desktop."""

    @mcp.tool(
        name="ts_compare_app",
        title="Compare Tanabe-Sugano diagrams",
        version=_pkg_version,
        tags={"tanabesugano", "compare", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_compare_app(
        d_counts: list[int],
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 40,
        normalize: bool = True,
        energy_unit: str = "cm1",
    ) -> ToolResult:
        """Overlay the diagrams of multiple d-configurations on one Chart.js panel.

        Each term gets a series prefixed by its d-count (e.g. ``d3 ⁴T₁g``) so the
        user can read off hole-particle symmetry pairs (d²/d⁸, d³/d⁷, d⁴/d⁶)
        directly. For the side-by-side small-multiples view that the previous
        implementation attempted, use multiple separate ``ts_diagram_app``
        calls — both render correctly now they share the Chart.js path.
        """
        import json as _json

        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
        from tanabesugano.mcp.tools._shared import resolve_bc
        from tanabesugano.plot_style import color_for
        from tanabesugano.plot_style import term_to_unicode

        valid = [d for d in d_counts if d in SUPPORTED_D_COUNTS]
        if not valid:
            valid = [3, 5, 8]

        all_series: list[dict] = []
        x_label = y_label = ""
        for d in valid:
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
            for s in series:
                data = [{"x": row[x_key], "y": row.get(s.data_key)} for row in rows]
                all_series.append(
                    {
                        "label": f"d{d} {term_to_unicode(s.data_key.rsplit('_', 1)[0])}",
                        "color": s.color or color_for(s.data_key.rsplit("_", 1)[0]),
                        "data": data,
                    },
                )

        title = f"Compare: {', '.join(f'd{d}' for d in valid)}"
        payload = _json.dumps(
            {
                "title": title,
                "x_label": x_label,
                "y_label": y_label,
                "series": all_series,
            },
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


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
    ) -> ToolResult:
        """Sweep Racah B × C at fixed Dq and render a Chart.js heatmap of energies.

        Picks the `level`-th eigenvalue of *term* at every (B, C) grid cell.
        Accepts either octahedral keys (``"6_A_1"``, ``"3_T_1"``) or the
        free-ion notation surfaced by the dashboard (``"6S"``, ``"3F"``):
        ``resolve_term_key`` normalises both. Returns a JSON payload that the
        Chart.js + chartjs-chart-matrix view at ``ui://tanabesugano/heatmap.html``
        consumes via ``content[0].text``.
        """
        import json as _json

        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp.tools._shared import resolve_term_key

        solver_term = resolve_term_key(d_count, term)

        # Quick existence probe so an unsupported term fails LOUDLY with a
        # useful error message instead of silently filling the heatmap with
        # NaN (which then corrupts the JSON payload — NaN is not valid JSON).
        probe = compute_point(d_count, Dq, b_min, c_min)
        if solver_term not in probe:
            available = sorted(probe.keys())
            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text=_json.dumps(
                            {
                                "title": "Error",
                                "x_label": "",
                                "y_label": "",
                                "cells": [],
                                "x_values": [],
                                "y_values": [],
                                "error": (
                                    f"Unknown term {term!r} for d{d_count}. "
                                    f"Available octahedral terms: {available}. "
                                    f"You may also pass the free-ion ground-term "
                                    f"alias from ts_dashboard_app."
                                ),
                            },
                        ),
                    ),
                ],
                is_error=True,
            )

        b_vals = [b_min + (b_max - b_min) * i / max(steps - 1, 1) for i in range(steps)]
        c_vals = [c_min + (c_max - c_min) * j / max(steps - 1, 1) for j in range(steps)]
        cells: list[dict] = []
        for b in b_vals:
            for c in c_vals:
                try:
                    terms = compute_point(d_count, Dq, b, c)
                    energies = terms.get(solver_term, [])
                    # JSON does not allow NaN — emit null so clients (Chart.js
                    # included) parse cleanly and skip non-finite cells.
                    v: float | None = (
                        round(float(energies[level]), 1) if level < len(energies) else None
                    )
                except Exception:  # noqa: BLE001 — solver may LinAlgError
                    v = None
                cells.append({"x": round(b, 1), "y": round(c, 1), "v": v})

        payload = {
            "title": f"d{d_count} {solver_term} (level {level}) at Dq={Dq:g}",
            "cells": cells,
            "x_label": "Racah B (cm⁻¹)",
            "y_label": "Racah C (cm⁻¹)",
            "x_values": [round(b, 1) for b in b_vals],
            "y_values": [round(c, 1) for c in c_vals],
        }
        return ToolResult(
            content=[_mcp_types.TextContent(type="text", text=_json.dumps(payload))],
        )

    @mcp.resource(
        HEATMAP_URI,
        # MCP Apps spec — UI resources must use the profiled MIME type.
        # Claude Desktop advertises ``extensions.io.modelcontextprotocol/ui``
        # with ``mimeTypes: ["text/html;profile=mcp-app"]`` in initialize;
        # plain ``text/html`` is rejected with "Unsupported UI resource
        # content format". Reference:
        # https://modelcontextprotocol.io/extensions/apps/overview
        mime_type="text/html;profile=mcp-app",
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
                    },
                )

        title_overlay = f"Overlay: {', '.join(f'd{d}' for d in valid)}"
        payload = _json.dumps(
            {
                "title": title_overlay,
                "x_label": x_label,
                "y_label": y_label,
                "series": all_series,
            },
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

        if not results:
            with PrefabApp() as app, pf.Column(gap=3, css_class="p-6"):
                pf.Heading(content="No fit found", level=3)
                pf.Text(
                    content="The grid search produced no candidates. Try relaxing the search bounds.",
                    css_class="text-sm text-muted-foreground",
                )
            return app

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
                    },
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
                    ),
                ],
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
                    / len(comp_ratios),
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
                            },
                        ),
                    ),
                ],
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
                {"label": s.label or s.data_key, "color": s.color or "#888", "data": data},
            )
        # Add vertical marker series at the fitted Dq.
        all_series.append(
            {
                "label": f"Fitted 10Dq/B = {x_fit_norm:g}",
                "color": "#FF0000",
                "data": [{"x": x_fit_norm, "y": 0}, {"x": x_fit_norm, "y": 150}],
                "borderDash": [6, 3],
            },
        )

        title_custom = f"Custom TS d{d_count}: Dq={best_dq:.1f}, B={b_fit:.1f} cm⁻¹"
        payload = _json.dumps(
            {"title": title_custom, "x_label": x_label, "y_label": y_label, "series": all_series},
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
                },
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
            },
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])

    @mcp.resource(
        SPECTRUM_URI,
        # MCP Apps spec — UI resources must use the profiled MIME type.
        # Claude Desktop advertises ``extensions.io.modelcontextprotocol/ui``
        # with ``mimeTypes: ["text/html;profile=mcp-app"]`` in initialize;
        # plain ``text/html`` is rejected with "Unsupported UI resource
        # content format". Reference:
        # https://modelcontextprotocol.io/extensions/apps/overview
        mime_type="text/html;profile=mcp-app",
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


def _register_oxidation_landscape(mcp: FastMCP) -> None:
    """Energy-state landscape across all supported d-configurations.

    For a fixed (Dq, B, C), plot every eigenvalue of every d^n (d²–d⁸) on a
    single Chart.js chart — x = d-electron count, y = energy. One series per
    spin multiplicity (singlet, triplet, …). Lets the user see at a glance
    how the term-energy spread evolves across the d-block at fixed
    crystal-field strength.
    """
    # Colour-blind-safe palette keyed by spin multiplicity (2S+1).
    _MULT_COLOR: dict[int, str] = {
        1: "#888888",  # singlet
        2: "#0072B2",  # doublet
        3: "#009E73",  # triplet
        4: "#D55E00",  # quartet
        5: "#CC79A7",  # quintet
        6: "#E69F00",  # sextet
    }

    @mcp.tool(
        name="ts_oxidation_landscape_app",
        title="Energies across d² – d⁸ at fixed Racah (Dq, B, C)",
        version=_pkg_version,
        tags={"tanabesugano", "compare", "interactive", "oxidation"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_oxidation_landscape_app(
        Dq: float = 1000.0,
        B: float = 900.0,
        C: float = 4000.0,
        max_energy_cm: float = 40000.0,
        style: str = "scatter",
        broadening_cm: float = 800.0,
        n_energy_points: int = 200,
    ) -> ToolResult:
        """Plot every eigenvalue of d² – d⁸ at the same (Dq, B, C) on one chart.

        Each point is one term-symbol level. X is the d-electron count (the
        bottom axis), Y is energy (the left axis). Series are grouped by spin
        multiplicity so the user can read off how spin-allowed vs forbidden
        bands shift across the periodic d-block.

        Args:
            Dq: Octahedral crystal-field parameter (cm⁻¹). Default 1000 is
                mid-range for first-row transition metals.
            B, C: Racah parameters (cm⁻¹). Defaults give an "average" 3d
                metal; pick values from `_defaults.py` for specific ions.
            max_energy_cm: Clip points above this energy so the visible
                window stays within typical UV-Vis range (default 40 000
                cm⁻¹, just past the UV cutoff).
            style: "scatter" (default) draws each eigenvalue as a discrete
                dot — independent d-counts are *not* joined by lines. Use
                "density" to render a Gaussian-broadened 2D heatmap where
                each (d, E) cell intensity = Σᵢ exp(-(E − Eᵢ)² / 2σ²) over
                that d-count's eigenvalues, σ = broadening_cm.
            broadening_cm: Gaussian σ for the density mode (cm⁻¹, default
                800 — a typical d-d band FWHM is roughly 2.355σ ≈ 1900 cm⁻¹).
                Ignored when style="scatter".
            n_energy_points: Vertical resolution of the density grid
                (default 200 cells per d-count). Ignored when style="scatter".

        """
        import json as _json
        import math

        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
        from tanabesugano.mcp._compute import compute_point

        if style not in ("scatter", "density"):
            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text=_json.dumps(
                            {
                                "title": "Error",
                                "x_label": "",
                                "y_label": "",
                                "series": [],
                                "error": f"style must be 'scatter' or 'density', got {style!r}",
                            },
                        ),
                    ),
                ],
                is_error=True,
            )

        # Per-d-count list of (raw) eigenvalues above the ground manifold,
        # within the visible energy window. Used by both modes.
        per_d_energies: dict[int, list[float]] = {}
        for d in SUPPORTED_D_COUNTS:
            terms = compute_point(d, Dq, B, C)
            es: list[float] = []
            for eigs in terms.values():
                for e in eigs:
                    e_f = float(e)
                    if e_f <= 1.0 or e_f > max_energy_cm:
                        continue
                    es.append(e_f)
            per_d_energies[d] = es

        title = f"d²–d⁸ energy landscape at Dq={Dq:g}, B={B:g}, C={C:g} cm⁻¹" + (
            f"  [density σ={broadening_cm:g}]" if style == "density" else ""
        )

        if style == "density":
            # Build a regular (d, E) grid and sum a Gaussian over every
            # eigenvalue for that d-count. The cell value is unitless
            # density; the consumer (heatmap.html) colour-maps it.
            sigma = max(broadening_cm, 1.0)
            two_sigma_sq = 2.0 * sigma * sigma
            n_y = max(n_energy_points, 2)
            energies_grid = [max_energy_cm * i / (n_y - 1) for i in range(n_y)]
            cells: list[dict[str, float]] = []
            for d in SUPPORTED_D_COUNTS:
                eigs = per_d_energies[d]
                for e_grid in energies_grid:
                    if eigs:
                        density = sum(
                            math.exp(-((e_grid - e_i) ** 2) / two_sigma_sq) for e_i in eigs
                        )
                    else:
                        density = 0.0
                    cells.append(
                        {"x": float(d), "y": round(e_grid, 1), "v": round(density, 4)},
                    )
            payload: dict[str, object] = {
                "title": title,
                "x_label": "d-electron count",
                "y_label": "Energy E (cm⁻¹)",
                "chart_type": "heatmap",
                "cells": cells,
            }
        else:
            # Scatter: one Chart.js series per spin multiplicity, each
            # series tagged style="scatter" so the renderer disables line
            # interpolation between independent d-counts.
            buckets: dict[int, list[dict[str, float]]] = {}
            for d in SUPPORTED_D_COUNTS:
                terms = compute_point(d, Dq, B, C)
                for term_name, eigs in terms.items():
                    mult = _multiplicity_of(term_name)
                    if mult <= 0:
                        continue
                    for e in eigs:
                        e_f = float(e)
                        if e_f <= 1.0 or e_f > max_energy_cm:
                            continue
                        buckets.setdefault(mult, []).append(
                            {"x": float(d), "y": round(e_f, 1)},
                        )

            series = [
                {
                    "label": f"{mult}·(2S+1)",
                    "color": _MULT_COLOR.get(mult, "#888"),
                    "style": "scatter",
                    "data": sorted(pts, key=lambda p: (p["x"], p["y"])),
                }
                for mult, pts in sorted(buckets.items())
            ]
            payload = {
                "title": title,
                "x_label": "d-electron count",
                "y_label": "Energy E (cm⁻¹)",
                "series": series,
            }

        return ToolResult(
            content=[_mcp_types.TextContent(type="text", text=_json.dumps(payload))],
        )


def _register_compute_table(mcp: FastMCP) -> None:
    """Sortable DataTable of every eigenvalue at one (Dq, B, C).

    Solves the readability problem of raw eigenvalue dicts: a flat dict
    keyed by term symbol with nested lists is impossible to scan. The table
    sorts ascending by energy and adds spin-multiplicity / E/B columns. For
    a visual scatter across d² – d⁸ see ``ts_oxidation_landscape_app``.
    """

    @mcp.tool(
        name="ts_compute_app",
        title="Term-energy table at one (Dq, B, C)",
        version=_pkg_version,
        tags={"tanabesugano", "compute", "table", "interactive"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=True,
    )
    def ts_compute_app(
        d_count: int,
        Dq: float,
        B: float | None = None,
        C: float | None = None,
        max_energy_cm: float = 60000.0,
    ) -> PrefabApp:
        """Compute term energies and render them as a sortable, multiplicity-labelled table.

        Produces the eigenvalues of the d^n ligand-field Hamiltonian at one
        ``(Dq, B, C)`` point, sorted ascending by energy with multiplicity
        and E/B columns. See ``ts_oxidation_landscape_app`` for a visual
        scatter across d² – d⁸.

        Args:
            d_count: d-electron count (2–8).
            Dq: Crystal-field parameter (cm⁻¹).
            B, C: Racah parameters (cm⁻¹); per-configuration defaults if omitted.
            max_energy_cm: Clip table above this energy (default
                60 000 cm⁻¹; raise it to see deep-UV high-multiplicity levels).

        """
        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc
        from tanabesugano.plot_style import color_for
        from tanabesugano.plot_style import term_to_unicode

        if d_count not in DEFAULTS:
            with PrefabApp() as app, pf.Column(gap=3, css_class="p-6"):
                pf.Heading(content="Invalid d_count", level=3)
                pf.Muted(content=f"d_count must be 2..8, got {d_count}")
            return app

        b_val, c_val = resolve_bc(d_count, B, C)
        terms = compute_point(d_count, Dq, b_val, c_val)

        # Flatten to rows {term, level, energy_cm, energy_over_B, mult, color}.
        rows: list[dict] = []
        for term_name, eigs in terms.items():
            mult = _multiplicity_of(term_name)
            for level, e in enumerate(eigs):
                e_f = float(e)
                if e_f > max_energy_cm:
                    continue
                rows.append(
                    {
                        "term": term_to_unicode(term_name),
                        "term_raw": term_name,
                        "level": level,
                        "energy_cm": round(e_f, 1),
                        "energy_over_B": round(e_f / b_val, 3) if b_val else 0.0,
                        "mult": str(mult),
                        "color": color_for(term_name),
                    },
                )
        rows.sort(key=lambda r: (r["energy_cm"], r["term_raw"], r["level"]))

        # Strip plot: x = level multiplicity (jittered horizontally per term),
        # y = energy. One series per spin manifold for legend filtering. Keep
        # x distinct so points within one multiplicity don't overlap visually.
        buckets: dict[int, list[dict]] = {}
        for row in rows:
            try:
                m = int(row["mult"])
            except ValueError:
                continue
            buckets.setdefault(m, []).append(
                {"x": float(m), "y": row["energy_cm"], "term": row["term"]},
            )
        chart_series = [
            {
                "label": f"{m}·(2S+1)",
                "color": {
                    1: "#888888",
                    2: "#0072B2",
                    3: "#009E73",
                    4: "#D55E00",
                    5: "#CC79A7",
                    6: "#E69F00",
                }.get(m, "#666"),
                "data": pts,
            }
            for m, pts in sorted(buckets.items())
        ]

        # Build the table headers explicitly so the column widths are stable.
        ground_term_oct = next(
            (r["term_raw"] for r in rows if r["energy_cm"] <= 1.0),
            "—",
        )

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(
                content=f"d{d_count} levels at Dq={Dq:g}, B={b_val:g}, C={c_val:g} cm⁻¹",
                level=3,
            )
            with pf.Grid(columns=3, gap=4):
                pf.Metric(
                    label="Ground term",
                    value=term_to_unicode(ground_term_oct),
                    description=f"{DEFAULTS[d_count]['ground_term']} (free-ion)",
                )
                pf.Metric(
                    label="Levels",
                    value=str(len(rows)),
                    description=f"≤ {max_energy_cm:,.0f} cm⁻¹",
                )
                pf.Metric(
                    label="Highest",
                    value=f"{rows[-1]['energy_cm']:,.0f}" if rows else "—",
                    description="cm⁻¹",
                )
            pf.Muted(
                content=(
                    "Sortable table of every level at this (Dq, B, C). For a "
                    "visual scatter across d² – d⁸ use "
                    "ts_oxidation_landscape_app; for the full Tanabe-Sugano "
                    "diagram use ts_diagram_app."
                ),
            )
            # Note: Prefab LineChart renders as a black canvas in current
            # Claude Desktop builds (verified empirically), so the strip plot
            # is delivered through ts_oxidation_landscape_app (Chart.js)
            # instead. This tool stays Prefab-native because the Metric +
            # DataTable components render correctly.
            _ = chart_series  # noqa: F841 — kept for future Chart.js variant
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="term", header="Term", sortable=True),
                    pf.DataTableColumn(key="level", header="Lvl", sortable=True),
                    pf.DataTableColumn(key="energy_cm", header="E (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="energy_over_B", header="E/B", sortable=True),
                    pf.DataTableColumn(key="mult", header="2S+1", sortable=True),
                ],
                rows=rows,
                search=True,
            )
        return app


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
  <script src="https://cdn.jsdelivr.net/npm/chartjs-chart-matrix@2.0.1/dist/chartjs-chart-matrix.min.js"></script>
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

      // Heatmap mode: payload carries `chart_type: "heatmap"` + `cells: [{x,y,v}]`.
      // Used by ts_oxidation_landscape_app(style="density") to render a
      // Gaussian-broadened density per d-count via chartjs-chart-matrix.
      if (p.chart_type === 'heatmap') {
        const cells = p.cells || [];
        const vs = cells.map(c => c.v).filter(v => Number.isFinite(v));
        const vmin = vs.length ? Math.min(...vs) : 0;
        const vmax = vs.length ? Math.max(...vs) : 1;
        const xVals = Array.from(new Set(cells.map(c => c.x))).sort((a, b) => a - b);
        const yVals = Array.from(new Set(cells.map(c => c.y))).sort((a, b) => a - b);
        const colorAt = (v) => {
          if (!Number.isFinite(v)) return 'rgba(0,0,0,0)';
          const t = (v - vmin) / (vmax - vmin || 1);
          // viridis-ish: dark purple → teal → yellow.
          const r = Math.round(68 + (253 - 68) * t);
          const g = Math.round(1  + (231 - 1)  * t);
          const b = Math.round(84 + (37  - 84) * t);
          return `rgb(${r},${g},${b})`;
        };
        chart = new Chart(ctx, {
          type: 'matrix',
          data: {
            datasets: [{
              label: p.title || 'density',
              data: cells,
              backgroundColor: (cx) => colorAt(cx.raw.v),
              width: ({chart}) =>
                (chart.chartArea?.width  || 1) / Math.max(xVals.length, 1) - 1,
              height: ({chart}) =>
                (chart.chartArea?.height || 1) / Math.max(yVals.length, 1) - 1,
            }],
          },
          options: {
            responsive: true,
            animation: false,
            plugins: {
              legend: { display: false },
              title: { display: !!p.title, text: p.title || '', font: { size: 14 } },
              tooltip: { callbacks: { label: (i) =>
                `${p.x_label || 'x'}=${i.raw.x}  ${p.y_label || 'y'}=${i.raw.y}: ${i.raw.v.toFixed?.(3) ?? i.raw.v}` } },
            },
            scales: {
              x: { type: 'linear', title: { display: true, text: p.x_label || '', font: { size: 12 } } },
              y: { type: 'linear', title: { display: true, text: p.y_label || '', font: { size: 12 } } },
            },
          },
        });
        return;
      }

      // Default line/scatter mode. Per-series `style: "scatter"` disables
      // the line interpolation and shows filled dots — used by
      // ts_oxidation_landscape_app(style="scatter") so independent
      // d-counts don't get joined by misleading sawtooth segments.
      const datasets = (p.series || []).map(s => {
        const isScatter = s.style === 'scatter';
        return {
          label: s.label || '',
          data: s.data || [],
          borderColor: s.color || '#888',
          backgroundColor: isScatter ? (s.color || '#888') : 'transparent',
          borderWidth: 1.5,
          pointRadius: isScatter ? 4 : 0,
          showLine: !isScatter,
          borderDash: s.borderDash || [],
          tension: 0.3,
        };
      });
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
