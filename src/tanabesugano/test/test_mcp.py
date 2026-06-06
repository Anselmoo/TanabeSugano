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
