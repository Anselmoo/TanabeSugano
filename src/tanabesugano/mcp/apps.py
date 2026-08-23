"""FastMCP tools for the TanabeSugano server (Prefab + Chart.js).

Two rendering pipelines coexist:

* **Chart.js iframes**: ts_diagram_app, ts_plot_view, ts_overlay_app,
  ts_compare_app, ts_spectrum_app, ts_oxidation_landscape_app,
  ts_orgel_diagram_app, ts_spin_crossover_app, ts_correlation_diagram_app,
  ts_reverse_fit_app, ts_ratio_fit_app. Each declares
  ``app=AppConfig(resource_uri=...)`` pointing at one of two hand-registered
  ``ui://tanabesugano/{diagram,spectrum}.html`` resources (MIME
  ``text/html;profile=mcp-app`` per the MCP Apps spec) and returns a
  ``ToolResult`` carrying a JSON Chart.js payload.
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

from tanabesugano.plot_style import ANNOTATION_COLORS
from tanabesugano.plot_style import color_for_multiplicity


log = logging.getLogger(__name__)

DIAGRAM_URI = "ui://tanabesugano/diagram.html"
SPECTRUM_URI = "ui://tanabesugano/spectrum.html"

# ── Optional Prefab / FastMCP apps API ───────────────────────────────────
try:
    from fastmcp.apps import AppConfig
    from fastmcp.apps import ResourceCSP
    from fastmcp.apps import ResourcePermissions
    from fastmcp.tools import ToolResult
    from mcp import types as _mcp_types
    from mcp.types import ToolAnnotations
    from prefab_ui import components as pf
    from prefab_ui.app import PrefabApp
    from prefab_ui.components.charts import ChartSeries  # used by _sweep_payload
    from prefab_ui.components.charts import Sparkline  # used by ts_dashboard_app

    from tanabesugano import __version__ as _pkg_version
    from tanabesugano.mcp._compute import SpinState
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
    _register_overlay(mcp)
    _register_reverse_fit(mcp)
    _register_ratio_fit(mcp)
    _register_spectrum(mcp)
    _register_oxidation_landscape(mcp)
    _register_orgel(mcp)
    _register_spin_crossover(mcp)
    _register_fit_plot(mcp)
    _register_correlation_diagram(mcp)
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
) -> tuple[list[dict], list[ChartSeries], str, str, str, str]:
    """Compute one sweep and return Prefab-shaped data: rows + ChartSeries list.

    Returns:
        (rows, series, title, x_axis_key, x_label, y_label) where `rows` is a
        list of dicts keyed by x-axis value and one column per unique term
        (level-0 only, so Prefab LineChart doesn't collapse).

    There is deliberately no ground-state y value here. It used to be derived
    by taking ``min(points[0], ...)`` -- the Dq = 0 sample, where every
    octahedral component of the free-ion ground term is exactly degenerate, so
    the tie-break named an arbitrary one (``5_E`` for d6, whose weak-field
    ground term is ``5_T_2``; also wrong for d2 and d7). Every one of the seven
    call sites discarded it, which is why a wrong value survived the pass that
    corrected three sibling call sites. Anything that needs a ground term must
    call :func:`_compute.reference_ground_term`, which probes a field strong
    enough to have lifted the degeneracy.

    """
    from tanabesugano.mcp._compute import sweep_dq
    from tanabesugano.plot_style import color_for
    from tanabesugano.plot_style import term_to_unicode

    dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, b_val, c_val)
    if not points:
        return [], [], "", "x", "x", "y"
    if normalize and b_val <= 0:
        raise ValueError(f"normalize=True requires positive Racah B, got B={b_val!r}")

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
    return rows, series, title, x_key, x_label, y_label


def _chartjs_series_payload(
    rows: list[dict],
    series: list[ChartSeries],
    x_key: str,
    *,
    title: str,
    x_label: str,
    y_label: str,
    bounds: dict[str, float] | None = None,
) -> str:
    """Build the JSON payload for the Chart.js diagram / overlay HTML views.

    Args:
        rows: list of dicts (x + per-term y values).
        series: list of ChartSeries with data_key, label, color.
        x_key: the dict key for x values.
        title, x_label, y_label: display strings.
        bounds: optional axis crop, any subset of ``x_min``/``x_max``/
            ``y_min``/``y_max``. Only the keys actually supplied are emitted,
            so a renderer keeps autoscaling on every axis nobody pinned.

    Returns:
        JSON string with ``{title, x_label, y_label, series}`` plus whichever
        bounds were given, where each series entry is
        ``{label, color, data: [{x, y}]}``.

    """
    import json as _json

    chart_series = []
    for s in series:
        data = [{"x": row[x_key], "y": row.get(s.data_key)} for row in rows]
        chart_series.append(
            {"label": s.label or s.data_key, "color": s.color or "#888", "data": data},
        )
    payload: dict[str, object] = {
        "title": title,
        "x_label": x_label,
        "y_label": y_label,
        "series": chart_series,
    }
    payload.update(bounds or {})
    return _json.dumps(payload)


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
        rows, series, title, x_key, x_label, y_label = _sweep_payload(
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
            # MCP Apps spec: the host sandboxes every UI iframe with no
            # Permissions Policy by default — ``navigator.clipboard.write``
            # is rejected unless the resource explicitly requests it via
            # ``_meta.ui.permissions.clipboardWrite``. Required for the
            # in-iframe "Copy to clipboard" button to succeed.
            # https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx
            permissions=ResourcePermissions(clipboard_write={}),
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
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
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
            x_min, x_max, y_min, y_max: Crop the drawn axes, in the units of
                the axis as drawn -- 10Dq/B and E/B when ``normalize=True``,
                otherwise 10Dq in cm⁻¹ and ``energy_unit``. Use these to put
                two ions on identical axes: their normalised extents differ
                with B, so matching them by tuning ``dq_max`` per ion is
                arithmetic that cannot work for the y-axis at all. Cropping
                does not re-sweep -- the curves run through the window rather
                than stopping at it. Any axis left unset keeps autoscaling.

        """
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp.tools._shared import resolve_bc

        b_val, c_val = resolve_bc(d_count, B, C)
        rows, series, _title, x_key, x_label, y_label = _sweep_payload(
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
            bounds={
                key: value
                for key, value in (
                    ("x_min", x_min),
                    ("x_max", x_max),
                    ("y_min", y_min),
                    ("y_max", y_max),
                )
                if value is not None
            },
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


def _first_excited_curve(
    d_count: int,
    B: float,
    C: float,
    *,
    dq_min: float | None = None,
    dq_max: float = 1500.0,
    steps: int = 30,
    ground_eps: float = 1.0,
) -> list[float]:
    """Lowest eigenvalue above the ground manifold at each Dq of a sweep.

    Extracted from ``ts_dashboard_app`` so the curve can be asserted on
    directly; the tool body renders whatever this returns.

    ``ground_eps`` is the threshold above which an eigenvalue counts as a real
    excited state -- the solvers zero the ground manifold, so anything at or
    below it is the ground state itself rather than a band.

    ``dq_min`` defaults to one grid step, **not** to zero, and that is the
    whole point of the parameter. At Dq = 0 the ligand field vanishes and every
    octahedral component of the free-ion ground term is exactly degenerate, so
    the entire ground manifold sits inside ``ground_eps``; the search for "the
    first level above it" then falls through to the next free-ion term
    altogether and reports a gap tens of thousands of cm-1 above the curve it
    belongs to. Measured at the defaults, that put the first point 26x-48x
    above the second for every configuration except d5 -- whose 6S ground term
    is an orbital singlet, has nothing to split, and never spiked.

    Deriving the offset as ``dq_max / steps`` rather than hardcoding it keeps
    the grid uniform for any sweep: with the defaults the points fall on
    50, 100, ... 1500, the same lattice the old sweep used with the singular
    point at its origin simply omitted. Dropping that sample afterwards would
    have silenced the symptom too, but it would hand the caller one point fewer
    than they asked for.
    """
    from tanabesugano.mcp._compute import sweep_dq

    start = dq_max / steps if dq_min is None else dq_min
    _dq_values, points = sweep_dq(d_count, start, dq_max, steps, B, C)
    curve: list[float] = []
    for point in points:
        all_e = sorted(float(e) for term in point.values() for e in term)
        curve.append(round(next((e for e in all_e if e > ground_eps), 0.0), 1))
    return curve


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
        Sparkline of the **first excited state energy** across a 50–1500 cm⁻¹
        Dq sweep — the band that an absorption spectrum would actually show.
        The sweep starts one grid step above zero, not at zero: see
        :func:`_first_excited_curve` for why Dq = 0 cannot be sampled.
        Useful as a 'home page' before drilling into one configuration with
        `ts_diagram_app`.
        """
        from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
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
            # First excited state energy at each Dq step: the lowest eigenvalue
            # above the ground manifold across all term symbols. This gives a
            # curve that meaningfully tracks the lowest d-d absorption band as
            # crystal-field strength grows.
            spark = _first_excited_curve(d, b, c, ground_eps=ground_eps)

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
                    "excited state energy from Dq = 50 to 1500 cm⁻¹ — the lowest "
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
    Prefab small-multiples grid that did not render in Claude Desktop.
    """

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
            rows, series, _title, x_key, x_label, y_label = _sweep_payload(
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


# ts_parameter_heatmap_app was removed: a fixed-Dq sweep of Racah (B, C) for
# a single eigenvalue is not a standard coordination-chemistry visualisation
# (no entry in Cotton, Figgis & Hitchman, Bertini, or Lever), and the
# user-facing default trivially returns zero whenever the chosen term is the
# ground term (level 0 of the ground term is 0 by construction). Replaced
# with three literature-canonical Tanabe-Sugano companions:
#   * ts_orgel_diagram_app    — Orgel diagram (E vs Δ, unnormalised)
#   * ts_spin_crossover_app   — HS↔LS critical-Dq map for d⁴–d⁷
#   * ts_correlation_diagram_app — free-ion → weak field → strong field
# HEATMAP_URI / _HEATMAP_HTML went with it. They were kept on the theory that
# an external client still referencing the URI would get "a clean not found
# rather than an import error", but that does not survive testing: an
# unregistered URI and one that never existed both raise
# `NotFoundError: Unknown resource`, byte for byte. Resource lookup never
# consults a module-level constant, and a client does not import this module,
# so "import error" was never among the outcomes. What the dead copy did carry
# was its own un-oriented y-axis -- the F7 bug, one re-registration away from
# coming back.


def _register_orgel(mcp: FastMCP) -> None:
    """Orgel diagram (E vs Δ, *un-normalised*) — the canonical companion to ts_diagram_app.

    Wikipedia: "The Tanabe-Sugano diagram is an adaptation of an Orgel
    diagram which takes better account of electron-electron repulsion …".
    Cotton, Figgis & Hitchman, and the LibreTexts Crystal-Field-Theory
    module all introduce the Orgel diagram before the TS form because the
    physical (cm⁻¹) axes are easier to read against measured spectra.
    """

    @mcp.tool(
        name="ts_orgel_diagram_app",
        title="Orgel diagram (E vs Δ)",
        version=_pkg_version,
        tags={"tanabesugano", "plot", "orgel", "pedagogy"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_orgel_diagram_app(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 80,
        B: float | None = None,
        C: float | None = None,
    ) -> ToolResult:
        """Render an Orgel diagram: term energies (cm⁻¹) vs Δ = 10·Dq (cm⁻¹).

        Identical compute path as ``ts_diagram_app`` but with both axes in
        absolute cm⁻¹ instead of normalised by Racah B. For d²/d³/d⁸ the
        diagram is smooth (no spin crossover); for d⁴–d⁷ the ground term
        flips spin at the critical Δ and the diagram shows a downward
        kink — see ``ts_spin_crossover_app`` for a focussed view of that
        crossing.

        Args:
            d_count: d-electron count (2–8).
            dq_min, dq_max: Dq sweep bounds in cm⁻¹.
            steps: Number of Dq grid points.
            B, C: Racah parameters (cm⁻¹); per-configuration defaults if
                omitted.

        """
        from tanabesugano.mcp.tools._shared import resolve_bc

        b_val, c_val = resolve_bc(d_count, B, C)
        rows, series, _title, x_key, _x_label, _y_label = _sweep_payload(
            d_count,
            dq_min,
            dq_max,
            steps,
            b_val,
            c_val,
            normalize=False,
            energy_unit="cm1",
        )

        has_crossover = d_count in (4, 5, 6, 7)
        note = (
            "Orgel-like (kink at the HS↔LS crossover)"
            if has_crossover
            else "Orgel diagram (no spin crossover)"
        )
        title = f"d{d_count} {note} — B={b_val:g}, C={c_val:g} cm⁻¹"
        payload = _chartjs_series_payload(
            rows,
            series,
            x_key,
            title=title,
            x_label="Δ = 10·Dq  (cm⁻¹)",
            y_label="E  (cm⁻¹)",
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


def _register_spin_crossover(mcp: FastMCP) -> None:
    """High-spin ↔ low-spin critical-Δ map for d⁴ – d⁷.

    Wikipedia (Tanabe-Sugano): "diagrams for d4, d5, d6, and d7 metal ions
    have a discontinuity in energies as the ligand field is varied …
    represented by a vertical line." LibreTexts gives the textbook
    critical values: Dq/B ≈ 2 for d⁶, ≈ 2.1 for d⁷, ≈ 3 for d⁵, and
    ≈ 2.7 for d⁴. We compute the actual crossing for the user's chosen
    (B, C) instead of citing the table values, so the answer is exact
    for their complex.
    """

    @mcp.tool(
        name="ts_spin_crossover_app",
        title="High-spin ↔ low-spin critical Dq (d⁴ – d⁷)",
        version=_pkg_version,
        tags={"tanabesugano", "spin-crossover", "sco", "ground-term"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_spin_crossover_app(
        d_count: int,
        B: float | None = None,
        C: float | None = None,
        dq_max: float = 3500.0,
        steps: int = 100,
    ) -> ToolResult:
        """Plot the ground-term energies of the two candidate spin states vs Δ.

        Sweeps Dq from 0 to ``dq_max`` (default 3500 cm⁻¹ — past the
        crossing for all four configurations), computes the ground-term
        energy of every term at each Dq, and tags each term by spin
        multiplicity. The two relevant curves are: lowest *high-spin*
        term (the ground term at small Dq) and lowest *low-spin* term
        (the ground term at large Dq). Their crossing is the critical
        Δ for this complex. The chart also draws a vertical dashed
        marker at the crossing.

        Only valid for d⁴, d⁵, d⁶, d⁷. Other d-counts return a
        structured error.

        Args:
            d_count: must be 4, 5, 6, or 7.
            B, C: Racah parameters (cm⁻¹); per-configuration defaults if
                omitted.
            dq_max: Upper **Dq** bound for the sweep (cm⁻¹) -- that is
                Δ/10, not Δ. The chart's own x-axis is Δ = 10·Dq, so a value
                read off a published Δ must be divided by ten before it is
                passed here; do it the other way and the sweep covers ten
                times the intended range without complaint. At the default
                Racah parameters the crossing sits at Dq ≈ 2106 (d⁷),
                2135 (d⁶), 2433 (d⁵) and 2639 (d⁴) cm⁻¹, so 3500 clears
                the highest by ~30%. The previous default of 2500 put d⁴'s
                crossing outside the swept range entirely and the tool
                reported no crossing at all. Raise this for large B: the
                critical Dq scales roughly with B, so B ≈ 1400 pushes d⁴
                past 3800.
            steps: Sweep resolution.

        """
        import json as _json

        from tanabesugano.mcp._compute import CROSSOVER_TOL_DQ_CM1
        from tanabesugano.mcp._compute import crossover_dq
        from tanabesugano.mcp._compute import ground_term
        from tanabesugano.mcp._compute import sweep_dq
        from tanabesugano.mcp.tools._shared import resolve_bc

        if d_count not in (4, 5, 6, 7):
            return ToolResult(
                content=[
                    _mcp_types.TextContent(
                        type="text",
                        text=_json.dumps(
                            {
                                "title": "No spin crossover",
                                "x_label": "",
                                "y_label": "",
                                "series": [],
                                "error": (
                                    f"ts_spin_crossover_app is only meaningful for d⁴, "
                                    f"d⁵, d⁶, d⁷ (configurations with a HS↔LS ground-term "
                                    f"discontinuity), got d{d_count}. For d{d_count} the "
                                    f"ground term is fixed; use ts_diagram_app or "
                                    f"ts_orgel_diagram_app instead."
                                ),
                            },
                        ),
                    ),
                ],
                is_error=True,
            )

        b_val, c_val = resolve_bc(d_count, B, C)
        dq_values, points = sweep_dq(d_count, 0.0, dq_max, steps, b_val, c_val)

        # For each Dq step, find the lowest eigenvalue grouped by spin
        # multiplicity. The HS curve = lowest eigenvalue with the highest
        # multiplicity present at Dq=0; the LS curve = lowest eigenvalue
        # with the lowest multiplicity that becomes ground at large Dq.
        # Solver pre-subtracts the ground term so the absolute lowest is
        # always 0 — work with the *un-zeroed* per-multiplicity minima
        # instead by reading each term's actual eigenvalue array.
        per_step_mult_min: list[dict[int, float]] = []
        for point in points:
            mult_to_min: dict[int, float] = {}
            for term_name, eigs in point.items():
                if not eigs:
                    continue
                mult = _multiplicity_of(term_name)
                e = float(min(eigs))
                if mult not in mult_to_min or e < mult_to_min[mult]:
                    mult_to_min[mult] = e
            per_step_mult_min.append(mult_to_min)

        all_mults = sorted({m for d in per_step_mult_min for m in d})
        # The HS candidate is the multiplicity that is the ground at Dq=0;
        # the LS candidate is the multiplicity that becomes ground at the
        # final Dq step. Per textbook physics these are the two extremes
        # in `all_mults` for d⁴–d⁷.
        hs_mult = max(per_step_mult_min[0], key=lambda m: -per_step_mult_min[0][m])
        ls_mult = max(per_step_mult_min[-1], key=lambda m: -per_step_mult_min[-1][m])
        # If both ends agree, fall back to (highest, lowest) of the
        # multiplicities present anywhere.
        if hs_mult == ls_mult and len(all_mults) >= 2:
            hs_mult, ls_mult = all_mults[-1], all_mults[0]

        hs_curve = []
        ls_curve = []
        for i, dq in enumerate(dq_values):
            x = float(dq) * 10.0
            mm = per_step_mult_min[i]
            if hs_mult in mm:
                hs_curve.append({"x": round(x, 1), "y": round(mm[hs_mult], 1)})
            if ls_mult in mm:
                ls_curve.append({"x": round(x, 1), "y": round(mm[ls_mult], 1)})

        # Locate the crossing by bisection, NOT by scanning the sweep.
        #
        # The grid above is for *drawing* the two curves. Reading the critical
        # Dq off it quantises the answer to the sweep spacing: at steps=100 that
        # is 303 cm-1 in delta over a 0..3000 sweep, and 354 cm-1 over the
        # current 0..3500 default. Measured against an exact bisection, the grid
        # answer overshot the true crossing by 167-450 cm-1 and -- worse -- made
        # the reported number a function of `steps`, a parameter whose whole
        # documented job is drawing resolution. `crossover_dq` bisects the same
        # predicate to CROSSOVER_TOL_DQ_CM1, so the answer stops moving.
        #
        # It is anchored on the strong-field ground term rather than on "the
        # ground term differs from Dq=0": at Dq=0 the field vanishes, so all
        # crystal-field components of the free-ion ground term are exactly
        # degenerate and the tie-break names an arbitrary one (d6 gives 5_E,
        # not the weak-field 5_T_2). See crossover_dq's docstring.
        crossing_dq: float | None = None
        ls_reference = ground_term(points[-1])[0]
        if _multiplicity_of(ls_reference) < hs_mult:
            dq_root = crossover_dq(
                d_count,
                b_val,
                c_val,
                ls_reference,
                hi=float(dq_max),
                tol=CROSSOVER_TOL_DQ_CM1,
            )
            # crossover_dq returns `hi` when the flip is not strictly inside
            # the swept range, which is the "no crossing here" signal.
            if dq_root < float(dq_max):
                crossing_dq = dq_root * 10.0

        crossing_label = (
            f"critical Δ ≈ {crossing_dq:,.0f} cm⁻¹ (Dq/B ≈ {(crossing_dq / 10.0) / b_val:.2f})"
            if crossing_dq is not None
            else "no crossing detected in this Dq range"
        )
        title = f"d{d_count} HS↔LS crossover — {crossing_label} — B={b_val:g} cm⁻¹"

        series: list[dict] = [
            {
                # Both curves are ground terms of a known multiplicity, so
                # their colour is a lookup, not a choice. Hardcoded, the LS
                # curve of d6 -- a singlet -- drew in the triplet blue.
                "label": f"HS ground ({hs_mult}·(2S+1))",
                "color": color_for_multiplicity(hs_mult),
                "data": hs_curve,
            },
            {
                "label": f"LS ground ({ls_mult}·(2S+1))",
                "color": color_for_multiplicity(ls_mult),
                "data": ls_curve,
            },
        ]
        if crossing_dq is not None:
            # Vertical dashed marker at the crossing — Chart.js renders this
            # as a two-point dataset with borderDash.
            y_top = max(pt["y"] for s in series for pt in s["data"] if pt["y"] is not None)
            series.append(
                {
                    "label": "critical Δ",
                    "color": "#666",
                    "borderDash": [4, 4],
                    "data": [
                        {"x": round(crossing_dq, 1), "y": 0.0},
                        {"x": round(crossing_dq, 1), "y": float(y_top)},
                    ],
                },
            )

        # ``crossing_dq`` is the value on the x-axis (Δ = 10·Dq in cm⁻¹).
        # Emit both: ``critical_delta_cm1`` matches the axis label and is
        # what a viewer reads off the chart; ``critical_Dq_cm1`` is the
        # raw Dq parameter, which is what spectrum-fit clients want when
        # they compute Dq/B ratios. Previously this field carried Δ
        # under the Dq name, which was 10× the textbook value.
        payload = _json.dumps(
            {
                "title": title,
                "x_label": "Δ = 10·Dq  (cm⁻¹)",
                "y_label": "Ground-term energy  (cm⁻¹)",
                "series": series,
                "critical_delta_cm1": crossing_dq,
                "critical_Dq_cm1": (crossing_dq / 10.0) if crossing_dq is not None else None,
            },
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


def _register_fit_plot(mcp: FastMCP) -> None:
    """Observed vs computed band positions for a spectral fit.

    The counterpart of ``ts_fit_script`` for the inline surface. Same numbers,
    same assignments, same estimator -- one is a chart in the conversation, the
    other is source a reviewer can run. Neither recomputes the ligand-field
    problem; both read a single :func:`fit_spectrum` result.
    """

    @mcp.tool(
        name="ts_fit_plot_app",
        title="Observed vs computed bands for a spectral fit",
        version=_pkg_version,
        tags={"tanabesugano", "fit", "residuals", "spectrum"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_fit_plot_app(
        d_count: int,
        observed_peaks: list[float],
        C: float | None = None,
        spin_state: SpinState = "high",
        include_spin_forbidden: bool = False,
    ) -> ToolResult:
        """Plot how far each computed band sits from the band that was measured.

        The y axis is the residual, computed minus observed, NOT the raw band
        position. That is deliberate: over a d-d spectrum spanning roughly
        8,000 to 26,000 cm⁻¹ a good fit's misfit is a hundred-odd cm⁻¹, which
        is narrower than a plot marker. A chart of raw positions would show the
        observed and computed points on top of each other and tell the reader
        nothing about fit quality. Residuals put the disagreement on its own
        scale, and the raw positions travel in the structured payload.

        Bands are labelled with free-ion parentage — ³A₂g → ³T₁g(P), not
        ³A₂g → ³T₁g(b) — so a chart and a manuscript caption agree.

        For a figure to put in a paper, use ``ts_fit_script`` instead: it emits
        runnable matplotlib source carrying these same numbers. Nothing can be
        downloaded from an inline chart, because the MCP Apps sandbox strips
        ``allow-downloads`` from every UI iframe.

        Args:
            d_count: 2..8.
            observed_peaks: measured band maxima in cm⁻¹.
            C: Racah C; per-configuration default when omitted.
            spin_state: which side of a spin crossover to pin the fit to.
            include_spin_forbidden: required for high-spin d5, whose d-d bands
                are all spin-forbidden.

        """
        import json as _json

        from tanabesugano.mcp._compute import fit_spectrum
        from tanabesugano.script_export import labelled_bands

        try:
            fit = fit_spectrum(
                d_count,
                [float(p) for p in observed_peaks],
                C,
                spin_state=spin_state,
                include_spin_forbidden=include_spin_forbidden,
            )
            bands = labelled_bands(fit, d_count, [float(p) for p in observed_peaks])
        except (ValueError, KeyError) as exc:
            return ToolResult(
                content=[_mcp_types.TextContent(type="text", text=str(exc))],
                is_error=True,
            )

        # `assignment_unicode`, not `assignment`: the latter is mathtext for
        # the matplotlib exporter, and Chart.js renders no mathtext -- a chart
        # fed it would print a literal `$^{3}A_{2g} \rightarrow ...$`.
        residual_points = [
            {
                "x": round(band["observed_cm1"], 1),
                "y": round(band["residual_cm1"], 1),
                "label": band["assignment_unicode"],
            }
            for band in bands
        ]
        xs = [point["x"] for point in residual_points]
        # The zero line has to span the data, otherwise a reader cannot tell a
        # residual's sign from the chart alone. Pad so end points are not
        # sitting on the axis edge.
        pad = max((max(xs) - min(xs)) * 0.05, 100.0) if xs else 100.0
        series: list[dict] = [
            {
                "label": "zero (perfect fit)",
                "color": ANNOTATION_COLORS["reference_rule"],
                "borderDash": [4, 4],
                "data": [
                    {"x": round(min(xs) - pad, 1), "y": 0},
                    {"x": round(max(xs) + pad, 1), "y": 0},
                ],
            },
            {
                "label": "residual (computed − observed)",
                "color": ANNOTATION_COLORS["computed"],
                "data": residual_points,
            },
        ]

        title = (
            f"d{d_count} fit — Dq = {fit.Dq:,.0f}, B = {fit.B:,.0f} cm⁻¹, "
            f"RMSE = {fit.rmse_cm1:,.0f} cm⁻¹ ({fit.ground_term} ground)"
        )
        payload = _json.dumps(
            {
                "title": title,
                "x_label": "observed band position  (cm⁻¹)",
                "y_label": "residual, computed − observed  (cm⁻¹)",
                "series": series,
                "Dq_cm1": fit.Dq,
                "B_cm1": fit.B,
                "C_cm1": fit.C,
                "rmse_cm1": fit.rmse_cm1,
                "ground_term": str(fit.ground_term),
                "spin_state": str(fit.spin_state),
                "warnings": list(fit.warnings),
                "bands": bands,
            },
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


def _register_correlation_diagram(mcp: FastMCP) -> None:
    """Three-axis correlation diagram (free ion / weak field / strong field).

    The Tsuchida-style correlation diagram is the classical pedagogical
    bridge between free-ion term symbols (left axis) and strong-field
    configurations like t₂g^x e_g^y (right axis), with the intermediate
    weak-field crystal-field-split terms in the middle. Featured in
    Cotton's *Chemical Applications of Group Theory* and Figgis &
    Hitchman's *Ligand Field Theory and Its Applications* §4.
    """

    @mcp.tool(
        name="ts_correlation_diagram_app",
        title="Correlation diagram (free ion / weak field / strong field)",
        version=_pkg_version,
        tags={"tanabesugano", "correlation", "pedagogy", "term-symbols"},
        annotations=_READONLY_ANNOTATIONS,
        meta=_TS_META,
        app=AppConfig(resource_uri=DIAGRAM_URI),
    )
    def ts_correlation_diagram_app(
        d_count: int,
        B: float | None = None,
        C: float | None = None,
        strong_field_Dq: float = 2000.0,
    ) -> ToolResult:
        """Render a three-axis correlation diagram.

        - **Left (x = 0)**: free-ion term energies at Δ = 0.
        - **Middle (x = 1)**: terms at a moderate Δ (Dq = 800 cm⁻¹) —
          the weak-field region.
        - **Right (x = 2)**: terms at strong Δ (Dq = ``strong_field_Dq``) —
          the strong-field region where t₂g^x e_g^y configurations
          dominate.

        Each term symbol becomes one Chart.js series with three points
        at (0, E_free), (1, E_weak), (2, E_strong), so the renderer
        draws lines connecting equivalent terms across the three
        regimes. Term colours follow the existing `plot_style.color_for`
        palette; labels use ``term_to_unicode``.

        Args:
            d_count: d-electron count (2–8).
            B, C: Racah parameters (cm⁻¹); per-configuration defaults if
                omitted.
            strong_field_Dq: Dq value (cm⁻¹) defining the strong-field
                column (default 2000 — well into the strong-field limit
                for any first-row transition metal).

        """
        import json as _json

        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp.tools._shared import resolve_bc
        from tanabesugano.plot_style import color_for
        from tanabesugano.plot_style import term_to_unicode

        b_val, c_val = resolve_bc(d_count, B, C)
        free_terms = compute_point(d_count, 0.0, b_val, c_val)
        weak_terms = compute_point(d_count, 800.0, b_val, c_val)
        strong_terms = compute_point(d_count, strong_field_Dq, b_val, c_val)

        # All three points share the same key set (solver always emits
        # the full term list per d_count); collect by term name then
        # take the lowest eigenvalue per term to keep the chart readable.
        all_term_names = sorted(
            set(free_terms) | set(weak_terms) | set(strong_terms),
            key=lambda n: (_multiplicity_of(n), n),
        )
        series: list[dict] = []
        for term_name in all_term_names:

            def lowest(d: dict[str, list[float]], k: str = term_name) -> float | None:
                eigs = d.get(k) or []
                return round(float(min(eigs)), 1) if eigs else None

            data = [
                {"x": 0, "y": lowest(free_terms)},
                {"x": 1, "y": lowest(weak_terms)},
                {"x": 2, "y": lowest(strong_terms)},
            ]
            # Only drop terms the solver couldn't evaluate at all — the
            # ground manifold's flat near-zero line *is* the pedagogical
            # point of a correlation diagram (ground-term continuity from
            # free-ion through weak field to strong field), so we no
            # longer filter on a span threshold.
            ys = [pt["y"] for pt in data if pt["y"] is not None]
            if not ys:
                continue
            series.append(
                {
                    "label": term_to_unicode(term_name),
                    "color": color_for(term_name),
                    "data": data,
                },
            )

        title = (
            f"d{d_count} correlation diagram — "
            f"free ion / weak field (Dq=800) / strong field (Dq={strong_field_Dq:g}) — "
            f"B={b_val:g}, C={c_val:g} cm⁻¹"
        )
        payload = _json.dumps(
            {
                "title": title,
                "x_label": "Free ion  →  Weak field  →  Strong field",
                "y_label": "E  (cm⁻¹)",
                "series": series,
            },
        )
        return ToolResult(content=[_mcp_types.TextContent(type="text", text=payload)])


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
            rows, series, title, x_key, x_label, y_label = _sweep_payload(
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


def _as_tool_result(app: PrefabApp, structured: dict) -> ToolResult:
    """Serialise a Prefab card so its child tree survives the wire.

    `ToolResult(content=app)` serialises the PrefabApp via `model_dump()`, which
    drops everything the `with` block built and emits an empty card. `to_json()`
    preserves it. Every branch returning a card must go through here -- the
    happy paths already did, and the error branches did not, so a user with bad
    input saw a blank widget instead of the reason.
    """
    import json as _json

    return ToolResult(
        content=[_mcp_types.TextContent(type="text", text=_json.dumps(app.to_json()))],
        structured_content=structured,
    )


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
        dq_max_search: float | None = None,
        b_min: float = 400.0,
        b_max: float = 1600.0,
        grid_steps: int = 25,
    ) -> ToolResult:
        """Grid-search Dq and Racah B to best-fit observed absorption peak positions.

        Performs a coarse grid search over (Dq, B) space, comparing computed
        spin-allowed transitions (same ground-state multiplicity) against the
        observed peak positions. Returns best-fit parameters plus a residuals table.

        Args:
            d_count: d-electron count (2–8).
            observed_peaks: Measured absorption maxima in the chosen energy_unit.
            energy_unit: Unit of observed_peaks: "cm1" (default), "eV", or "nm".
            dq_max_search: Upper Dq search limit in cm^-1. Defaults to 3x the
                physics estimate min(peaks)/10, which adapts to the complex; the
                previous fixed 2500 silently truncated any complex with a lowest
                band above 25000 cm^-1.
            b_min, b_max: Racah B search range (cm^-1).
            grid_steps: Grid resolution per axis (total grid_steps² evaluations).

        """
        import json as _json

        import numpy as _np

        from tanabesugano.levels import LevelSet
        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._compute import peak_rmse
        from tanabesugano.mcp._compute import reference_ground_term
        from tanabesugano.mcp._compute import transition_candidates
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
                pf.Text(
                    content="Supply at least one absorption maximum greater than zero.",
                    css_class="text-sm text-muted-foreground",
                )
            return _as_tool_result(app, {"d_count": d_count, "error": "no valid peaks"})

        default_C = DEFAULTS[d_count]["default_C"]
        ground_key = reference_ground_term(d_count, *resolve_bc(d_count, None, None))
        ground_mult = _multiplicity_of(ground_key)

        best_dq = best_b = best_rms = float("inf")
        results: list[dict] = []

        if dq_max_search is None:
            dq_max_search = peaks_cm[0] / 10.0 * 3.0
        dq_grid = [dq_max_search * i / max(grid_steps - 1, 1) for i in range(grid_steps)]
        b_grid = [b_min + (b_max - b_min) * j / max(grid_steps - 1, 1) for j in range(grid_steps)]

        observed_arr = _np.asarray(peaks_cm, dtype=float)
        for dq in dq_grid:
            for b in b_grid:
                try:
                    found_ground, candidates = transition_candidates(
                        compute_point(d_count, dq, b, default_C),
                    )
                except (ValueError, KeyError):
                    continue
                # Pin the spin regime: the low-spin manifolds are far denser, so
                # a nearest-neighbour residual is minimised by crossing over.
                if found_ground != ground_key or not candidates:
                    continue
                rms = peak_rmse(
                    observed_arr,
                    _np.array([e for e, _a, _s in candidates]),
                )
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
            return _as_tool_result(app, {"d_count": d_count, "error": "no fit found"})

        _, best_c = resolve_bc(d_count, best_b, None)

        # Build best-fit terms table.
        try:
            best_terms = compute_point(d_count, best_dq, best_b, best_c)
        except (ValueError, RuntimeError):
            best_terms = {}
        # LevelSet names each level and sorts by energy; doing either by hand
        # here is how the two 3T1g rows ended up indistinguishable in the card.
        best_manifold = LevelSet.from_states(best_terms) if best_terms else None
        table_rows: list[dict] = [
            {
                "label": lv.label,
                "term": lv.term.value,
                "level": lv.index,
                "energy_cm": round(lv.energy_cm1, 1),
                "spin_allowed": lv.multiplicity == ground_mult,
            }
            for lv in (best_manifold.levels if best_manifold else ())
        ]

        results.sort(key=lambda r: r["RMS"])
        top_results = results[:20]

        # Per-peak residuals. The docstring has always promised "best-fit
        # parameters plus a residuals table"; the parameters were rendered as
        # Metrics but the residuals table did not exist.
        best_allowed = sorted(
            float(e)
            for term_key, energies in best_terms.items()
            for e in energies
            if float(e) > 0 and _multiplicity_of(term_key) == ground_mult
        )
        residual_rows: list[dict] = []
        for pk in peaks_cm:
            if not best_allowed:
                break
            closest = min(best_allowed, key=lambda e, pk=pk: abs(e - pk))
            residual_rows.append(
                {
                    "observed_cm": round(pk, 1),
                    "predicted_cm": round(closest, 1),
                    "delta_cm": round(closest - pk, 1),
                },
            )

        with PrefabApp() as app, pf.Column(gap=4, css_class="p-6"):
            pf.Heading(content=f"Reverse fit: d{d_count}", level=3)
            with pf.Grid(columns=3, gap=4):
                pf.Metric(label="Best Dq", value=f"{best_dq:.1f} cm⁻¹")
                pf.Metric(label="Best B", value=f"{best_b:.1f} cm⁻¹")
                pf.Metric(label="RMS residual", value=f"{best_rms:.1f} cm⁻¹")
            pf.Text(
                content=f"Ground term: {ground_key} (high-spin)",
                css_class="text-sm text-muted-foreground",
            )
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
            pf.Heading(content="Residuals at best fit", level=4)
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="observed_cm", header="Observed (cm⁻¹)"),
                    pf.DataTableColumn(key="predicted_cm", header="Predicted (cm⁻¹)"),
                    pf.DataTableColumn(key="delta_cm", header="Δ (cm⁻¹)"),
                ],
                rows=residual_rows,
                search=False,
            )
            pf.Separator()
            pf.Heading(content="Term energies at best-fit Dq", level=4)
            pf.DataTable(
                columns=[
                    pf.DataTableColumn(key="label", header="Term", sortable=True),
                    pf.DataTableColumn(key="level", header="Level", sortable=True),
                    pf.DataTableColumn(key="energy_cm", header="E (cm⁻¹)", sortable=True),
                    pf.DataTableColumn(key="spin_allowed", header="Spin-allowed"),
                ],
                rows=table_rows,
                search=True,
            )

        # Return the rendered card AND a machine-readable payload. The docstring
        # promises "best-fit parameters plus a residuals table"; a PrefabApp is a
        # widget, so an agent calling this tool previously got no numbers at all.
        # test_reverse_fit_contract.py pins the card's structure so this
        # return-type change cannot silently break the rendering.
        fit_data = {
            "d_count": d_count,
            "Dq": round(best_dq, 1),
            "B": round(best_b, 1),
            "C": round(float(best_c), 1),
            "rmse_cm1": round(best_rms, 1),
            "ground_term": ground_key,
            "spin_state": "high",
            "residuals": [
                {
                    "observed_cm1": row["observed_cm"],
                    "predicted_cm1": row["predicted_cm"],
                    "delta_cm1": row["delta_cm"],
                }
                for row in residual_rows
            ],
            "grid_candidates": top_results,
        }
        # NOTE: pass the card as app.to_json(), NOT as the PrefabApp object.
        # ToolResult serialises a bare PrefabApp via model_dump(), which drops
        # the child tree built by the `with` context manager and emits an empty
        # card. to_json() preserves it. Caught by test_reverse_fit_contract.py.
        return ToolResult(
            content=[_mcp_types.TextContent(type="text", text=_json.dumps(app.to_json()))],
            structured_content=fit_data,
        )


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
        from tanabesugano.mcp._compute import reference_ground_term
        from tanabesugano.mcp._compute import transition_candidates
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
        ground_key = reference_ground_term(d_count, *resolve_bc(d_count, None, None))
        default_C = DEFAULTS[d_count]["default_C"]
        # Dq is of order nu1/10, not nu1: for [Ni(H2O)6]2+ nu1 = 8500 cm^-1 and
        # Dq = 850. Searching out to 2*nu1 spread 30 grid points over a range 20x
        # too wide, making the spacing (586 cm^-1) larger than Dq itself. Bound
        # the search at 3x the physics estimate instead.
        dq_max_search = obs[0] / 10.0 * 3.0

        best_dq = best_b = float("inf")
        best_score = float("inf")

        dq_grid = [dq_max_search * i / max(grid_steps - 1, 1) for i in range(grid_steps)]
        b_grid = [b_min + (b_max - b_min) * j / max(grid_steps - 1, 1) for j in range(grid_steps)]

        min_allowed_for_ratio = 2
        for dq in dq_grid:
            for b in b_grid:
                try:
                    found_ground, candidates = transition_candidates(
                        compute_point(d_count, dq, b, default_C),
                    )
                except (ValueError, KeyError):
                    continue
                # Pin the spin regime, as fit_spectrum does: the ratio metric is
                # just as easily gamed by a denser low-spin manifold.
                if found_ground != ground_key:
                    continue
                allowed = [e for e, _a, _s in candidates]
                if len(allowed) < min_allowed_for_ratio:
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
            rows, series, title, x_key, x_label, y_label = _sweep_payload(
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
                "color": ANNOTATION_COLORS["marker"],
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
        from tanabesugano.mcp._compute import reference_ground_term
        from tanabesugano.mcp.tools._shared import resolve_bc

        b_val, c_val = resolve_bc(d_count, B, C)
        terms = compute_point(d_count, Dq, b_val, c_val)
        ground_mult = _multiplicity_of(
            reference_ground_term(d_count, *resolve_bc(d_count, None, None)),
        )

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
                "series": [
                    {
                        "label": "Simulated spectrum",
                        "color": ANNOTATION_COLORS["computed"],
                        "data": data,
                    },
                ],
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
            # MCP Apps spec: the host sandboxes every UI iframe with no
            # Permissions Policy by default — ``navigator.clipboard.write``
            # is rejected unless the resource explicitly requests it via
            # ``_meta.ui.permissions.clipboardWrite``. Required for the
            # in-iframe "Copy to clipboard" button to succeed.
            # https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx
            permissions=ResourcePermissions(clipboard_write={}),
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
    # The palette lives in plot_style.SPIN_COLORS. A copy here had drifted by
    # one multiplicity, so a quartet drew vermillion in this chart and green in
    # every matplotlib figure.

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

        Both modes plot **excited states only**. Every level at or below
        1 cm⁻¹ is dropped, which is each d-count's whole ground manifold: the
        solvers zero the ground state by construction, so it would otherwise
        draw as a row of points along E = 0 carrying no information. The
        consequence worth knowing is that a reader counting levels here
        against a term table will come up one manifold short per
        configuration, and that this is a display choice rather than a
        property of the calculation.

        No selection rule is applied either. Every eigenvalue counts the same,
        whether or not a transition to it from the ground state is spin
        allowed, so neither mode is a simulated spectrum: the density is a
        density of *states*, not of absorption. In scatter mode the
        multiplicity colouring is bookkeeping, not intensity.
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
            # density; the chart resource colour-maps it.
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
                # The extent the grid was actually built over, sent explicitly
                # so the axis is pinned by the request rather than inferred
                # from whichever cells happen to carry density.
                "y_min": 0.0,
                "y_max": float(max_energy_cm),
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
                    "color": color_for_multiplicity(mult),
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
        from tanabesugano.levels import LevelSet
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
        # LevelSet already sorts by (energy, term, level) and renders the
        # multiplet ordinal, so the Term cell identifies its row on its own.
        manifold = LevelSet.from_states(terms, d_count=d_count, dq=Dq, b=b_val, c=c_val)
        rows: list[dict] = [
            {
                "term": lv.unicode,
                "term_raw": lv.term.value,
                "uid": lv.uid,
                "level": lv.index,
                "energy_cm": round(lv.energy_cm1, 1),
                "energy_over_B": round(lv.energy_over_b(b_val), 3) if b_val else 0.0,
                "mult": str(lv.multiplicity),
                "color": color_for(lv.term.value),
            }
            for lv in manifold.levels
            if lv.energy_cm1 <= max_energy_cm
        ]

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
                # Second copy of the same table, shifted the same way.
                "color": color_for_multiplicity(m),
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
            _ = chart_series
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
    """Spin multiplicity of an octahedral solver key. Raises on free-ion notation.

    Delegates to _compute.term_multiplicity. The previous local implementation
    returned 0 for anything it could not parse, which silently disabled the
    spin-allowed comparison at every call site that passed a free-ion string.
    """
    from tanabesugano.mcp._compute import term_multiplicity

    return term_multiplicity(term)


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
    #toolbar {
      display: none;
      gap: 6px;
      padding: 4px 4px 6px 4px;
      font-family: -apple-system, system-ui, sans-serif;
      font-size: 12px;
      align-items: center;
    }
    #toolbar button {
      background: rgba(127,127,127,0.10);
      color: inherit;
      border: 1px solid rgba(127,127,127,0.35);
      border-radius: 4px;
      padding: 3px 9px;
      cursor: pointer;
      font: inherit;
      line-height: 1.4;
    }
    #toolbar button:hover { background: rgba(127,127,127,0.20); }
    #toolbar button:active { background: rgba(127,127,127,0.30); }
    #toolbar .flash { opacity: 0; transition: opacity .2s; margin-left: 4px; color: #4a8; }
    #toolbar .flash.err { color: #c64; }
    #toolbar .flash.show { opacity: 1; }
  </style>
</head>
<body>
  <div id="wrap">
    <div id="toolbar">
      <button id="btn-png" type="button" title="Send the rendered chart to the conversation as a PNG image (you can save it from there)">Send PNG to chat</button>
      <button id="btn-clip" type="button" title="Copy the rendered chart to the clipboard as a PNG image">Copy to clipboard</button>
      <span id="flash" class="flash"></span>
    </div>
    <canvas id="chart"></canvas>
  </div>
  <div id="hint" class="hint">Waiting for result…</div>
  <script type="module">
    import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";
    const app = new App({ name: "TS Chart", version: "1.0.0" });
    let chart = null;
    let lastTitle = "tanabesugano-chart";

    const toolbar = document.getElementById('toolbar');
    const flash = document.getElementById('flash');
    const slug = (s) => (s || 'chart')
      .toString().trim().toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '').slice(0, 80) || 'chart';
    const showFlash = (msg, isErr) => {
      flash.textContent = msg;
      flash.classList.toggle('err', !!isErr);
      flash.classList.add('show');
      setTimeout(() => flash.classList.remove('show'), 1800);
    };
    // Both buttons rely on Chart.js' built-in ``toBase64Image()`` to capture
    // the current canvas, but they exit the sandbox in different ways:
    //
    //   * "Send PNG to chat" calls back via ``app.callServerTool('ts_emit_png')``
    //     so the server echoes the PNG as ImageContent in the conversation.
    //     This is the only spec-compliant way to get a file *out* of the
    //     iframe: the MCP Apps spec deliberately omits a "downloads"
    //     permission (supported set is camera, microphone, geolocation,
    //     clipboardWrite — see
    //     github.com/modelcontextprotocol/ext-apps specification/2026-01-26).
    //   * "Copy to clipboard" uses canvas.toBlob() + ClipboardItem, which
    //     works once the resource declares ``_meta.ui.permissions.clipboardWrite``
    //     (we declare that via ResourcePermissions on the @mcp.resource).
    document.getElementById('btn-png').addEventListener('click', async () => {
      if (!chart) return;
      try {
        const dataUrl = chart.toBase64Image('image/png', 1.0);
        const b64 = (dataUrl.split(',', 2)[1] || dataUrl);
        showFlash('Sending…');
        await app.callServerTool({ name: 'ts_emit_png', arguments: { png_base64: b64, title: lastTitle } });
        showFlash('Sent to chat');
      } catch (e) {
        showFlash('Send failed', true);
      }
    });
    document.getElementById('btn-clip').addEventListener('click', () => {
      if (!chart) return;
      const canvas = document.getElementById('chart');
      if (!canvas || !canvas.toBlob) { showFlash('Copy unsupported', true); return; }
      canvas.toBlob(async (blob) => {
        if (!blob) { showFlash('Copy failed', true); return; }
        try {
          if (!navigator.clipboard || !window.ClipboardItem) {
            showFlash('Clipboard unavailable', true);
            return;
          }
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
          showFlash('Copied!');
        } catch (e) {
          // The resource declares ``_meta.ui.permissions.clipboardWrite``,
          // so Claude Desktop adds ``allow="clipboard-write"`` to the
          // iframe. Firefox still rejects image/png clipboard writes from
          // any iframe — treat that as a graceful fallback path.
          showFlash('Copy denied (use Send PNG to chat)', true);
        }
      }, 'image/png');
    });

    app.ontoolresult = ({ content }) => {
      const txt = (content || []).find(c => c.type === 'text');
      if (!txt) return;
      let p;
      try { p = JSON.parse(txt.text); } catch(e) {
        document.getElementById('hint').textContent = 'Parse error: ' + e.message;
        return;
      }
      document.getElementById('hint').style.display = 'none';
      toolbar.style.display = 'flex';
      if (p && p.title) lastTitle = p.title;
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
              // `reverse: false` is load-bearing, not decoration: the matrix
              // controller lays cells out row-major like a spreadsheet, so an
              // unconstrained scale puts 0 cm-1 at the TOP and the figure then
              // asserts that energy decreases upward. Bounds come from the
              // payload so the extent tracks max_energy_cm, not the cells.
              y: { type: 'linear', reverse: false, min: p.y_min, max: p.y_max,
                   title: { display: true, text: p.y_label || '', font: { size: 12 } } },
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
              min: p.x_min, max: p.x_max,
              title: { display: true, text: p.x_label || '', font: { size: 12 } },
              ticks: { maxTicksLimit: 10 },
            },
            y: {
              // Already correct by default; stated so it cannot drift, and so
              // both branches of this file answer the question the same way.
              reverse: false,
              // Undefined when the caller pinned nothing, which Chart.js reads
              // as "autoscale" -- so this scale stays shared with every other
              // line/scatter tool, none of which send bounds.
              min: p.y_min, max: p.y_max,
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
