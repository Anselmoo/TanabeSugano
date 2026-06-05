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
    ],
)
def test_app_tools_return_non_empty_payload(tool: str, args: dict) -> None:
    result = _call(tool, args)
    assert not result.is_error, f"{tool} returned is_error=True"  # type: ignore[attr-defined]
    assert result.content, f"{tool} returned empty content"  # type: ignore[attr-defined]


# ─────────────────────────── chemistry sanity ────────────────────────────


def test_ts_explain_includes_why_rationale() -> None:
    result = _call("ts_explain", {"d_count": 5})
    data = result.data  # type: ignore[attr-defined]
    text = str(data)
    assert "Racah B" in text
    assert "Tanabe" in text
