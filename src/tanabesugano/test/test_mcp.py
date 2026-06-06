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
        "ts_compute",
        "ts_diagram",
        "ts_terms_table_data",
        # plotting
        "ts_plot_png",
        "ts_plot_view",
        "ts_diagram_app",
        "ts_dashboard_app",
        "ts_compare_app",
        "ts_parameter_heatmap_app",
        "ts_explore_app",
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
    # Heatmap HTML resource for the Chart.js view.
    assert "ui://tanabesugano/heatmap.html" in uris


# ─────────────────────────── tool invocations ────────────────────────────


def _call(tool: str, args: dict) -> object:
    from fastmcp import Client

    server = create_server()

    async def go():  # noqa: ANN202
        async with Client(server) as client:
            return await client.call_tool(tool, args)

    return asyncio.run(go())


def test_ts_compute_returns_typed_payload() -> None:
    result = _call("ts_compute", {"d_count": 3, "Dq": 900.0})
    data = result.data  # type: ignore[attr-defined]
    assert data is not None
    assert data.d_count == 3
    assert data.Dq == 900.0
    assert data.terms


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
        ("ts_parameter_heatmap_app", {"d_count": 5, "term": "6_A_1", "steps": 4}),
        ("ts_explore_app", {}),
        ("ts_overlay_app", {"d_counts": [4, 6], "steps": 8}),
        ("ts_spectrum_app", {"d_count": 6, "Dq": 800.0, "n_points": 50}),
        (
            "ts_reverse_fit_app",
            {"d_count": 7, "observed_peaks": [8500.0, 15400.0], "grid_steps": 6},
        ),
        ("ts_ratio_fit_app", {"d_count": 3, "v1": 17000.0, "v2": 24000.0, "grid_steps": 6}),
    ],
)
def test_app_tools_return_non_empty_payload(tool: str, args: dict) -> None:
    result = _call(tool, args)
    assert not result.is_error, f"{tool} returned is_error=True"  # type: ignore[attr-defined]
    assert result.content, f"{tool} returned empty content"  # type: ignore[attr-defined]


def test_heatmap_emits_finite_numbers_no_nan_no_textbook_placeholder() -> None:
    """Pins three regressions reported by the user against ts_parameter_heatmap_app:

    1. The tool used to return ``PrefabApp`` whose ``content[0].text`` is the
       literal string ``"[Rendered Prefab UI]"``. The Chart.js HTML at
       ui://tanabesugano/heatmap.html does ``JSON.parse(content[0].text)`` and
       failed with "Unexpected token R". content[0].text must be valid JSON.
    2. With the free-ion ground term passed verbatim ("6S" surfaced by the
       dashboard for d5), the solver lookup returned [] and every cell got
       ``round(NaN, 1) == NaN``. NaN is not valid JSON. Cells now contain
       either a finite number or ``null``.
    3. An unknown term used to give a silent all-NaN heatmap; it now returns
       a structured error naming the available octahedral keys.
    """
    import json
    import math

    # 1. Free-ion alias → octahedral key
    r = _call(
        "ts_parameter_heatmap_app",
        {
            "d_count": 5,
            "term": "6S",
            "Dq": 900.0,
            "level": 0,
            "b_min": 600.0,
            "b_max": 1200.0,
            "c_min": 3000.0,
            "c_max": 5500.0,
            "steps": 6,
        },
    )
    assert not r.is_error, "free-ion ground term '6S' must resolve to 6_A_1"  # type: ignore[attr-defined]
    text = r.content[0].text  # type: ignore[attr-defined]
    assert text != "[Rendered Prefab UI]", (
        "heatmap must return ToolResult with JSON text, not a PrefabApp placeholder"
    )
    payload = json.loads(text)  # must not raise — JSON spec disallows NaN
    cells = payload["cells"]
    assert cells, "heatmap must produce cells"
    for c in cells:
        v = c["v"]
        # JSON does not allow NaN — values must be either finite or null.
        assert v is None or (isinstance(v, (int, float)) and math.isfinite(v)), (
            f"non-finite cell value {v!r} would crash strict JSON parsers"
        )
    assert "6_A_1" in payload["title"], "free-ion '6S' must be resolved to '6_A_1' in title"

    # 2. Excited term should have varying finite energies
    r = _call(
        "ts_parameter_heatmap_app",
        {"d_count": 5, "term": "4_T_1", "Dq": 900.0, "steps": 6},
    )
    cells = json.loads(r.content[0].text)["cells"]  # type: ignore[attr-defined]
    vs = [c["v"] for c in cells if c["v"] is not None]
    assert len(vs) == len(cells), "all cells finite for excited term"
    assert max(vs) - min(vs) > 100, (
        f"excited-state heatmap should vary across (B, C), got range {max(vs) - min(vs):.0f}"
    )

    # 3. Unknown term must produce a structured error, not a silent NaN grid
    with pytest.raises(Exception) as exc_info:  # noqa: PT011, BLE001
        _call("ts_parameter_heatmap_app", {"d_count": 5, "term": "XYZ", "Dq": 900.0, "steps": 4})
    err_msg = str(exc_info.value)
    assert "XYZ" in err_msg and "Available" in err_msg, (
        f"invalid term must name itself and list valid alternatives, got {err_msg!r}"
    )


def test_diagram_app_chart_carries_varying_data() -> None:
    """Pins the diagram_app payload: the LineChart series must contain enough
    structure that a renderer can draw lines, not collapse to a single value.
    Catches the regression class where the chart "appears black" because every
    series is constant or all coordinates collapse to the origin.
    """
    r = _call("ts_diagram_app", {"d_count": 5, "dq_max": 1500.0, "steps": 8, "normalize": True})
    view = (r.structured_content or {}).get("view")  # type: ignore[attr-defined]

    def find_linechart(node: object) -> dict | None:
        if isinstance(node, dict):
            if node.get("type") == "LineChart":
                return node
            for ch in node.get("children") or []:
                found = find_linechart(ch)
                if found:
                    return found
        return None

    lc = find_linechart(view)
    assert lc, "ts_diagram_app must render a LineChart"
    rows = lc.get("data") or []
    series = lc.get("series") or []
    assert len(rows) >= 4, f"chart needs enough rows to draw lines, got {len(rows)}"
    assert len(series) >= 2, f"d5 has multiple term symbols, got {len(series)} series"
    # xAxis must be set (camelCase) — Pydantic would silently drop snake_case.
    assert lc.get("xAxis") == "x", f"xAxis must be 'x', got {lc.get('xAxis')!r}"
    # At least one series must vary across the sweep — otherwise the chart
    # is just horizontal lines which is what triggered the "black screen"
    # impression originally.
    varying_series = 0
    for s in series:
        key = s.get("dataKey") or s.get("data_key")
        ys = [row.get(key) for row in rows if row.get(key) is not None]
        if ys and max(ys) - min(ys) > 0.1:
            varying_series += 1
    assert varying_series >= 1, (
        f"no series varies across Dq for d5 — chart would be flat. "
        f"series={[s.get('dataKey') for s in series]}"
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
