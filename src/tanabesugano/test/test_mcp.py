"""Smoke + behavior tests for the FastMCP server.

Skips cleanly when the optional `[mcp]` extra (fastmcp) is not installed.
"""

from __future__ import annotations

import asyncio

import pytest


pytest.importorskip("fastmcp", reason="install with `pip install tanabesugano[mcp]`")

pytestmark = pytest.mark.mcp

from tanabesugano.mcp._compute import compute_point  # noqa: E402
from tanabesugano.mcp._compute import sweep_dq  # noqa: E402
from tanabesugano.mcp.server import create_server  # noqa: E402


# ─────────────────────────── core numeric tools ──────────────────────────


def test_compute_point_returns_term_dict() -> None:
    terms = compute_point(d_count=3, Dq=900.0, B=918.0, C=4133.0)
    assert isinstance(terms, dict)
    assert terms
    for values in terms.values():
        assert isinstance(values, list)
        for v in values:
            assert isinstance(v, float)


def test_sweep_dq_shapes() -> None:
    dq_values, points = sweep_dq(
        d_count=2,
        dq_min=0.0,
        dq_max=1000.0,
        steps=5,
        B=860.0,
        C=3801.0,
    )
    assert len(dq_values) == 5
    assert len(points) == 5
    keys = set(points[0].keys())
    for pt in points[1:]:
        assert set(pt.keys()) == keys


# ─────────────────────────── server registration ─────────────────────────


def test_create_server_registers_expected_tools() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}

    expected = {
        # numeric
        "ts_supported_configs",
        "ts_terms_table_data",
        # plotting
        "ts_plot_png",
        "ts_plot_view",
        "ts_diagram_app",
        "ts_dashboard_app",
        "ts_compare_app",
        "ts_orgel_diagram_app",
        # docs
        "ts_explain",
    }
    assert expected <= tool_names, sorted(expected - tool_names)


def test_generative_ui_tools_are_absent() -> None:
    """The wrong-domain GenerativeUI tools must NOT show up in our server.

    They previously appeared because `register_apps` registered the
    GenerativeUI provider. We've removed it deliberately -- this test
    pins that decision.
    """
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "generate_prefab_ui" not in names
    assert "search_prefab_components" not in names


def test_interactive_resources_present() -> None:
    server = create_server()
    resources = asyncio.run(server.list_resources())
    uris = {str(r.uri) for r in resources}
    # Chart.js diagram resource serves every Chart.js-backed app tool
    # (ts_diagram_app, ts_plot_view, ts_overlay_app, ts_compare_app,
    # ts_oxidation_landscape_app, ts_orgel_diagram_app, …).
    assert "ui://tanabesugano/diagram.html" in uris


def test_ui_resources_advertise_mcp_app_profile_mime() -> None:
    """MCP Apps spec requires UI HTML resources to use
    ``text/html;profile=mcp-app``; Claude Desktop announces exactly this
    MIME during ``initialize`` (``extensions.io.modelcontextprotocol/ui``)
    and rejects plain ``text/html`` with "Unsupported UI resource content
    format". Pinning this so the profile suffix can't be dropped again.
    """
    from fastmcp import Client

    server = create_server()

    async def go() -> list:
        async with Client(server) as client:
            return await client.list_resources()

    resources = asyncio.run(go())
    ui_resources = [r for r in resources if str(r.uri).startswith("ui://tanabesugano/")]
    assert ui_resources, "no ui://tanabesugano/* resources registered"
    for r in ui_resources:
        assert r.mimeType == "text/html;profile=mcp-app", (
            f"{r.uri} declares mimeType={r.mimeType!r}, "
            f"needs 'text/html;profile=mcp-app' for Claude Desktop to render the iframe"
        )


def test_ui_resources_request_clipboard_write_permission() -> None:
    """The MCP Apps host sandboxes every UI iframe with no Permissions
    Policy by default, so ``navigator.clipboard.write`` is rejected unless
    the resource explicitly declares ``_meta.ui.permissions.clipboardWrite``.
    Without it the in-iframe "Copy to clipboard" button fails for every
    user. Pin the declaration so the permission can't be silently dropped.

    Reference: github.com/modelcontextprotocol/ext-apps
    specification/2026-01-26/apps.mdx — supported permission set is
    ``{camera, microphone, geolocation, clipboardWrite}``.
    """
    from fastmcp import Client

    server = create_server()

    async def read_each() -> dict[str, list]:
        async with Client(server) as client:
            resources = await client.list_resources()
            out: dict[str, list] = {}
            for r in resources:
                if not str(r.uri).startswith("ui://tanabesugano/"):
                    continue
                read = await client.read_resource(r.uri)
                out[str(r.uri)] = list(read)
            return out

    contents_by_uri = asyncio.run(read_each())
    assert contents_by_uri, "no ui://tanabesugano/* resources registered"
    for uri, contents in contents_by_uri.items():
        # FastMCP exposes the resource _meta on each ResourceContents entry.
        metas = [getattr(c, "meta", None) for c in contents]
        assert any(metas), f"{uri} declares no _meta — clipboardWrite not requested"
        for meta in metas:
            if meta is None:
                continue
            ui_meta = meta.get("ui") or {}
            perms = ui_meta.get("permissions") or {}
            assert "clipboardWrite" in perms, (
                f"{uri} _meta.ui.permissions = {perms!r}; must request "
                f"'clipboardWrite' for the in-iframe Copy button to work"
            )


def test_ts_emit_png_echoes_image_content() -> None:
    """The in-iframe "Send PNG to chat" button calls back via
    ``app.callServerTool('ts_emit_png', {png_base64})`` to push the rendered
    chart back into the conversation as an MCP image attachment — this
    is the only spec-compliant export path (the MCP Apps sandbox has no
    "downloads" permission, so ``<a download>`` is suppressed). Pin the
    contract.
    """
    import base64 as _b64

    # Minimal valid PNG bytes (a 1×1 transparent pixel).
    png_bytes = _b64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    b64 = _b64.b64encode(png_bytes).decode()
    result = _call("ts_emit_png", {"png_base64": b64, "title": "d6 Dq=900"})
    assert not result.is_error  # type: ignore[attr-defined]
    images = [
        c
        for c in result.content  # type: ignore[attr-defined]
        if getattr(c, "type", None) == "image"
    ]
    assert len(images) == 1, "ts_emit_png must return exactly one ImageContent"
    assert getattr(images[0], "mimeType", "") == "image/png"
    assert getattr(images[0], "data", "") == b64

    # Reject malformed input — must be a clean error, not a crash.
    bad = _call("ts_emit_png", {"png_base64": "not base64 !!!"})
    msgs = [
        getattr(c, "text", "")
        for c in bad.content  # type: ignore[attr-defined]
        if getattr(c, "type", None) == "text"
    ]
    assert any("base64" in m.lower() for m in msgs), (
        f"ts_emit_png must reject invalid input with a clear message; got {msgs!r}"
    )

    # Empty-string input — must return a text message, not raise.
    empty_result = _call("ts_emit_png", {"png_base64": ""})
    empty_texts = [
        getattr(c, "text", "")
        for c in empty_result.content  # type: ignore[attr-defined]
        if getattr(c, "type", None) == "text"
    ]
    assert any("empty" in t.lower() for t in empty_texts), (
        f"ts_emit_png must describe empty input; got {empty_texts!r}"
    )

    # data-URI input — header must be stripped; payload must equal raw base64.
    data_uri = f"data:image/png;base64,{b64}"
    uri_result = _call("ts_emit_png", {"png_base64": data_uri})
    uri_images = [
        c
        for c in uri_result.content  # type: ignore[attr-defined]
        if getattr(c, "type", None) == "image"
    ]
    assert len(uri_images) == 1, "data-URI input must produce one ImageContent"
    assert getattr(uri_images[0], "data", "") == b64, (
        "data-URI header must be stripped; payload must equal raw base64"
    )


# ─────────────────────────── tool invocations ────────────────────────────


def _call(tool: str, args: dict) -> object:
    from fastmcp import Client

    server = create_server()

    async def go():  # noqa: ANN202
        async with Client(server) as client:
            return await client.call_tool(tool, args)

    return asyncio.run(go())


def test_ts_compute_app_returns_sorted_table_and_chart() -> None:
    """ts_compute was removed because its raw nested dict was unusable.
    ts_compute_app replaces it with a sortable DataTable of eigenvalues."""
    result = _call("ts_compute_app", {"d_count": 5, "Dq": 980.0, "B": 1350.0, "C": 4000.0})
    assert not result.is_error  # type: ignore[attr-defined]
    view = (result.structured_content or {}).get("view")  # type: ignore[attr-defined]

    # Find the DataTable rows
    def find_first(node: object, type_name: str) -> dict | None:
        if isinstance(node, dict):
            if node.get("type") == type_name:
                return node
            for ch in node.get("children") or []:
                found = find_first(ch, type_name)
                if found:
                    return found
        return None

    table = find_first(view, "DataTable")
    assert table, "ts_compute_app must render a DataTable"
    rows = table.get("rows") or []
    assert len(rows) >= 5, f"d5 at Dq=980 should produce many levels, got {len(rows)}"
    energies = [r["energy_cm"] for r in rows]
    assert energies == sorted(energies), "rows must be sorted ascending by energy"
    # Multiplicity column populated
    mults = {r.get("mult") for r in rows}
    assert mults & {"2", "4", "6"}, f"d5 should produce mixed multiplicities, got {mults}"


def test_ts_terms_table_returns_sorted_rows() -> None:
    result = _call("ts_terms_table_data", {"d_count": 3, "Dq": 900.0})
    data = result.data  # type: ignore[attr-defined]
    rows = data.rows
    assert rows, "table must be non-empty"
    energies = [r.energy_cm for r in rows]
    assert energies == sorted(energies), "rows must be sorted ascending"
    assert sum(1 for r in rows if r.is_ground) == 1


def test_ts_plot_png_returns_image() -> None:
    result = _call("ts_plot_png", {"d_count": 3, "steps": 6})
    content = result.content  # type: ignore[attr-defined]
    assert any(
        getattr(c, "type", None) == "image" or getattr(c, "mimeType", "") == "image/png"
        for c in content
    )


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("ts_plot_view", {"d_count": 3, "steps": 5}),
        ("ts_diagram_app", {"d_count": 5, "steps": 8}),
        ("ts_dashboard_app", {}),
        ("ts_compare_app", {"d_counts": [3, 5, 8]}),
        ("ts_orgel_diagram_app", {"d_count": 5, "steps": 8}),
        ("ts_overlay_app", {"d_counts": [4, 6], "steps": 8}),
        ("ts_spectrum_app", {"d_count": 6, "Dq": 800.0, "n_points": 50}),
        (
            "ts_reverse_fit_app",
            {"d_count": 7, "observed_peaks": [8500.0, 15400.0], "grid_steps": 6},
        ),
        ("ts_ratio_fit_app", {"d_count": 3, "v1": 17000.0, "v2": 24000.0, "grid_steps": 6}),
        ("ts_oxidation_landscape_app", {"Dq": 1000.0, "B": 900.0, "C": 4000.0}),
        ("ts_correlation_diagram_app", {"d_count": 3}),
        ("ts_spin_crossover_app", {"d_count": 5, "steps": 6}),
    ],
)
def test_app_tools_return_non_empty_payload(tool: str, args: dict) -> None:
    result = _call(tool, args)
    assert not result.is_error, f"{tool} returned is_error=True"  # type: ignore[attr-defined]
    assert result.content, f"{tool} returned empty content"  # type: ignore[attr-defined]


def test_heatmap_tool_was_removed() -> None:
    """ts_parameter_heatmap_app was removed: a fixed-Dq sweep of Racah (B, C)
    of a single eigenvalue is not a literature visualisation, and the default
    user call against a ground term level returned 0 cm⁻¹ everywhere. Replaced
    with ts_orgel_diagram_app, ts_spin_crossover_app, ts_correlation_diagram_app.
    """
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "ts_parameter_heatmap_app" not in names


def test_spin_crossover_app_detects_critical_dq_for_d4_through_d7() -> None:
    """For each of d⁴/d⁵/d⁶/d⁷ the tool should detect a HS↔LS crossing in the
    swept range. LibreTexts textbook values: Dq/B ≈ 2 for d⁶, ≈ 2.1 for d⁷,
    ≈ 3 for d⁵, ≈ 2.7 for d⁴.

    Pins the unit contract introduced in the bug-fix commit: the payload now
    carries both ``critical_delta_cm1`` (what the x-axis shows, Δ in cm⁻¹)
    and ``critical_Dq_cm1`` (the raw Dq parameter, exactly Δ/10). The pre-fix
    code put Δ under the ``critical_Dq_cm1`` name, so values were 10× the
    textbook number — this test fixes the regression in place.
    """
    import json

    from tanabesugano.mcp._defaults import DEFAULTS

    for d in (4, 5, 6, 7):
        r = _call("ts_spin_crossover_app", {"d_count": d, "dq_max": 3000.0, "steps": 60})
        assert not r.is_error, f"d{d} must produce a payload"  # type: ignore[attr-defined]
        p = json.loads(r.content[0].text)  # type: ignore[attr-defined]
        crit_dq = p.get("critical_Dq_cm1")
        crit_delta = p.get("critical_delta_cm1")
        assert crit_dq is not None and crit_dq > 0, (
            f"d{d} must report a finite critical Dq, got {crit_dq!r}"
        )
        assert crit_delta is not None and crit_delta > 0, (
            f"d{d} must report a finite critical Δ, got {crit_delta!r}"
        )
        assert abs(crit_delta - 10.0 * crit_dq) < 1.0, (
            f"d{d}: critical_delta_cm1 ({crit_delta}) must equal 10·Dq ({10 * crit_dq})"
        )
        b_val = float(DEFAULTS[d]["default_B"])
        ratio = crit_dq / b_val
        assert 1.5 <= ratio <= 3.5, (
            f"d{d} Dq/B = {ratio:.2f} is outside the textbook 1.5–3.5 band — unit bug regression?"
        )


def test_spin_crossover_app_rejects_non_sco_d_counts() -> None:
    """d²/d³/d⁸ have no spin-crossover discontinuity — tool must return a
    structured error pointing at ts_diagram_app / ts_orgel_diagram_app.
    """
    from fastmcp.exceptions import ToolError

    for d in (2, 3, 8):
        with pytest.raises(ToolError) as exc_info:
            _call("ts_spin_crossover_app", {"d_count": d})
        msg = str(exc_info.value)
        assert "no spin crossover" in msg.lower() or "only meaningful" in msg.lower(), (
            f"d{d} error must explain why; got {msg!r}"
        )


def test_correlation_diagram_app_emits_three_panels() -> None:
    """Three-axis correlation diagram must produce series with exactly three
    x-positions per series (x=0 free ion, x=1 weak field, x=2 strong field).
    """
    import json

    r = _call("ts_correlation_diagram_app", {"d_count": 3})
    assert not r.is_error  # type: ignore[attr-defined]
    p = json.loads(r.content[0].text)  # type: ignore[attr-defined]
    assert p["series"], "correlation diagram must produce at least one series"
    for s in p["series"]:
        xs = {pt["x"] for pt in s["data"]}
        assert xs == {0, 1, 2}, f"series {s['label']!r} has x-positions {xs}, must be {{0, 1, 2}}"
    # X-axis label must call out the three regimes
    label = p["x_label"]
    assert "Free ion" in label and "Weak" in label and "Strong" in label
    # Bug-fix regression pin: the ground term must appear in the diagram.
    # d³'s ground term is ⁴A₂g (a quartet A-state) — without it the
    # diagram is missing its pedagogical anchor (ground-term continuity
    # across the three regimes is *the* reason the diagram exists). A
    # pre-fix span-based filter (max-min < 1.0 cm⁻¹) silently dropped any
    # series whose three points all sat at zero, which is exactly the
    # ground manifold in normalised solver output.
    labels_joined = " | ".join(s["label"] for s in p["series"])
    assert "⁴A₂" in labels_joined, (
        f"d³ correlation diagram must include the ⁴A₂ ground term in its series list; "
        f"got: {labels_joined!r}"
    )


def test_orgel_diagram_app_returns_unnormalised_payload() -> None:
    """Orgel diagram must use absolute cm⁻¹ axes (no E/B normalisation) — that
    is the entire point of the Orgel-vs-TS distinction in the literature.
    """
    import json

    r = _call("ts_orgel_diagram_app", {"d_count": 3, "steps": 12})
    assert not r.is_error  # type: ignore[attr-defined]
    payload = json.loads(r.content[0].text)  # type: ignore[attr-defined]
    assert "cm⁻¹" in payload["x_label"] and "cm⁻¹" in payload["y_label"], (
        f"Orgel axes must be in absolute cm⁻¹, got x={payload['x_label']!r} y={payload['y_label']!r}"
    )
    assert payload["series"], "Orgel must produce at least one term series"
    # Highest energy must be in the cm⁻¹ regime, not the E/B regime (~1-100)
    for s in payload["series"]:
        ys = [pt["y"] for pt in s["data"]]
        if ys and max(ys) > 1000:
            break
    else:
        raise AssertionError("no series reaches >1000 — chart is normalised, not Orgel")


def test_diagram_app_returns_chartjs_payload_with_varying_series() -> None:
    """Pins ts_diagram_app's payload after the migration off Prefab LineChart.

    The previous implementation returned a Prefab ``PrefabApp`` containing a
    ``LineChart``; that component renders as a black canvas in current Claude
    Desktop builds even with valid data. ts_diagram_app now returns a
    ``ToolResult`` carrying the same JSON shape as ts_plot_view / ts_overlay_app
    (Chart.js), consumed by ui://tanabesugano/diagram.html.
    """
    import json

    r = _call("ts_diagram_app", {"d_count": 5, "dq_max": 1500.0, "steps": 8, "normalize": True})
    assert not r.is_error, "ts_diagram_app must not error on a normal d5 sweep"  # type: ignore[attr-defined]
    text = r.content[0].text  # type: ignore[attr-defined]
    assert text != "[Rendered Prefab UI]", (
        "ts_diagram_app must return a Chart.js JSON payload, not the Prefab placeholder"
    )
    payload = json.loads(text)
    assert "series" in payload and "x_label" in payload and "y_label" in payload
    series = payload["series"]
    assert len(series) >= 2, f"d5 has multiple term symbols, got {len(series)} series"
    # At least one series must vary across the sweep — flat lines are what
    # the user originally perceived as a "black" chart.
    varying = 0
    for s in series:
        ys = [pt["y"] for pt in s.get("data") or [] if pt.get("y") is not None]
        if ys and max(ys) - min(ys) > 0.1:
            varying += 1
    assert varying >= 1, (
        f"no series varies across Dq for d5 — chart would be flat. "
        f"series labels: {[s.get('label') for s in series]}"
    )


def test_app_tools_accept_stringified_arguments() -> None:
    """Claude Desktop sends numeric/bool args as JSON strings; FastMCP+Pydantic
    must coerce them transparently. Pinning this prevents silent regressions.
    """
    typed = _call(
        "ts_diagram_app",
        {"d_count": 5, "dq_min": 0.0, "dq_max": 1500.0, "steps": 8, "normalize": True},
    )
    stringified = _call(
        "ts_diagram_app",
        {"d_count": "5", "dq_min": "0.0", "dq_max": "1500.0", "steps": "8", "normalize": "true"},
    )
    assert not stringified.is_error, "stringified args must coerce, not error"  # type: ignore[attr-defined]
    assert stringified.content  # type: ignore[attr-defined]
    # Output sizes match → coercion produces identical computation.
    typed_len = len(str(typed.structured_content))  # type: ignore[attr-defined]
    string_len = len(str(stringified.structured_content))  # type: ignore[attr-defined]
    assert typed_len == string_len, f"stringified output diverged: {typed_len} vs {string_len}"


def test_wrapped_data_args_are_unwrapped() -> None:
    """Some clients (a recent Claude Desktop build was observed doing this) wrap
    flat tool args in a ``{"data": {...}}`` envelope. The unwrap middleware in
    create_server() normalises that back to flat so Pydantic does not reject
    the call with the confusing dual "missing d_count" + "unexpected data" error.
    """
    flat = _call(
        "ts_diagram_app",
        {"d_count": 5, "dq_max": 1500.0, "steps": 6, "normalize": True},
    )
    wrapped = _call(
        "ts_diagram_app",
        {"data": {"d_count": 5, "dq_max": 1500.0, "steps": 6, "normalize": True}},
    )
    assert not wrapped.is_error, "wrapped {data: ...} must be unwrapped"  # type: ignore[attr-defined]
    assert wrapped.content  # type: ignore[attr-defined]
    # Output sizes match → unwrap produces identical computation.
    flat_len = len(str(flat.structured_content))  # type: ignore[attr-defined]
    wrap_len = len(str(wrapped.structured_content))  # type: ignore[attr-defined]
    assert flat_len == wrap_len, f"unwrapped output diverged: {flat_len} vs {wrap_len}"


def test_dashboard_sparklines_show_meaningful_data() -> None:
    """Pins the dashboard fix: each d-card's Sparkline must vary (not flat zero)
    because it now plots the first excited state energy across the Dq sweep,
    not the ground-term energy (which is always 0 by construction).
    """
    result = _call("ts_dashboard_app", {})
    assert not result.is_error  # type: ignore[attr-defined]

    sparks: list[list[float]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "Sparkline":
                sparks.append(node.get("data") or [])
            for child in node.get("children") or []:
                walk(child)

    view = (result.structured_content or {}).get("view")  # type: ignore[attr-defined]
    walk(view)

    assert len(sparks) == 7, f"expected one sparkline per d-config, got {len(sparks)}"
    for d, spark in zip(range(2, 9), sparks, strict=True):
        assert spark, f"d{d} sparkline is empty"
        assert max(spark) > 100, f"d{d} sparkline never rises above 100 cm⁻¹ — still flat zero?"


def test_oxidation_landscape_scatter_does_not_connect_d_counts() -> None:
    """Scatter mode flags every series with ``style: "scatter"`` so the renderer
    disables line interpolation. Without it, Chart.js zig-zags between d=2, 3,
    4 … points, suggesting physically meaningless continuity across
    independent d-configurations (the user reported the sawtooth artefact).
    """
    import json

    r = _call(
        "ts_oxidation_landscape_app",
        {"Dq": 1000.0, "B": 860.0, "C": 1300.0, "style": "scatter"},
    )
    assert not r.is_error  # type: ignore[attr-defined]
    payload = json.loads(r.content[0].text)  # type: ignore[attr-defined]
    assert payload.get("series"), "scatter mode must populate series"
    for s in payload["series"]:
        assert s.get("style") == "scatter", (
            f"series {s.get('label')!r} missing style=scatter — chart would draw lines"
        )
    # Multiple d-counts represented inside each series (otherwise the series
    # is degenerate and the bug wouldn't surface).
    for s in payload["series"]:
        d_counts = {pt["x"] for pt in s.get("data") or []}
        assert len(d_counts) >= 2, (
            f"series {s.get('label')!r} only has data at one d-count: {d_counts}"
        )


def test_oxidation_landscape_density_returns_varying_heatmap() -> None:
    """Density mode reuses the chartjs-chart-matrix renderer via
    ``chart_type: "heatmap"`` and populates a ``cells`` grid with the Gaussian
    sum at each (d, E). The grid must contain finite, varying values across
    both axes — a uniform grid means the broadening swallowed all features.
    """
    import json
    import math

    r = _call(
        "ts_oxidation_landscape_app",
        {
            "Dq": 1000.0,
            "B": 860.0,
            "C": 1300.0,
            "style": "density",
            "broadening_cm": 800.0,
            "n_energy_points": 50,
        },
    )
    assert not r.is_error  # type: ignore[attr-defined]
    payload = json.loads(r.content[0].text)  # type: ignore[attr-defined]
    assert payload.get("chart_type") == "heatmap", (
        "density mode must declare chart_type=heatmap so the HTML routes to the matrix renderer"
    )
    cells = payload.get("cells") or []
    assert len(cells) >= 7 * 50, (
        f"expected ~7×50 cells (d² – d⁸ × n_energy_points), got {len(cells)}"
    )
    vs = [c["v"] for c in cells]
    assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in vs), (
        "density values must all be finite (no NaN — JSON would be invalid)"
    )
    assert max(vs) - min(vs) > 0.1, (
        f"density grid is flat (range={max(vs) - min(vs):.3f}) — Gaussian sum produced no contrast"
    )


def test_explore_app_is_removed() -> None:
    """ts_explore_app's Prefab Form rendered as a frozen panel in Claude
    Desktop and its on_submit=CallTool wiring became stale after the
    diagram_app migration. The tool was deleted; this pins that it does
    not come back via an accidental re-registration.
    """
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "ts_explore_app" not in names


def test_invalid_d_count_surfaces_clear_error() -> None:
    """Invalid d_count must surface as a clear ToolError, not a raw KeyError.

    resolve_bc validates d_count centrally; this pins the user-visible behavior
    for every ts_*_app that funnels through resolve_bc. Before the validation
    was added, the error was an opaque ``KeyError: 99``.
    """
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError) as exc_info:
        _call("ts_diagram_app", {"d_count": 99, "steps": 4})
    msg = str(exc_info.value)
    assert "d_count" in msg and "99" in msg, (
        f"invalid d_count must produce a clear error message, got: {msg!r}"
    )


# ─────────────────────────── chemistry sanity ────────────────────────────


def test_ts_explain_includes_why_rationale() -> None:
    result = _call("ts_explain", {"d_count": 5})
    data = result.data  # type: ignore[attr-defined]
    text = str(data)
    assert "Racah B" in text
    assert "Tanabe" in text
