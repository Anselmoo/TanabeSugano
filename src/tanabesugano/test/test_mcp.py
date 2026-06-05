"""Smoke + behavior tests for the FastMCP server.

Skips cleanly when the optional `[mcp]` extra (fastmcp) is not installed.
"""

from __future__ import annotations

import asyncio

import pytest


fastmcp = pytest.importorskip("fastmcp", reason="install with `pip install tanabesugano[mcp]`")

pytestmark = pytest.mark.mcp

from tanabesugano.mcp._compute import compute_point  # noqa: E402
from tanabesugano.mcp._compute import sweep_dq  # noqa: E402
from tanabesugano.mcp.server import create_server  # noqa: E402


def test_compute_point_returns_term_dict() -> None:
    terms = compute_point(d_count=3, Dq=900.0, B=918.0, C=4133.0)
    assert isinstance(terms, dict)
    assert terms  # non-empty
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


def test_create_server_registers_tools() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}
    expected = {
        "ts_supported_configs",
        "ts_compute",
        "ts_diagram",
        "ts_plot_png",
        "ts_plot_view",
        "ts_explain",
    }
    assert expected <= tool_names


def test_ts_plot_view_returns_plotly_payload() -> None:
    import json as _json

    from fastmcp import Client

    server = create_server()

    async def _call():  # noqa: ANN202
        async with Client(server) as client:
            return await client.call_tool(
                "ts_plot_view",
                {"d_count": 3, "steps": 5},
            )

    result = asyncio.run(_call())
    text_items = [c for c in result.content if getattr(c, "type", None) == "text"]
    assert text_items, "ts_plot_view must emit a TextContent payload"
    payload = _json.loads(text_items[0].text)
    assert payload["d_count"] == 3
    assert payload["series"], "payload.series must be non-empty"
    assert all({"name", "x", "y"} <= set(s) for s in payload["series"])


def test_interactive_view_resource_present() -> None:
    server = create_server()
    resources = asyncio.run(server.list_resources())
    uris = {str(r.uri) for r in resources}
    assert "ui://tanabesugano/diagram.html" in uris


def test_ts_compute_via_in_process_client() -> None:
    from fastmcp import Client

    server = create_server()

    async def _call():  # noqa: ANN202
        async with Client(server) as client:
            return await client.call_tool(
                "ts_compute",
                {"d_count": 3, "Dq": 900.0},
            )

    result = asyncio.run(_call())
    # FastMCP returns a CallToolResult; the structured payload sits in .data.
    data = result.data
    assert data is not None
    assert data.d_count == 3
    assert data.Dq == 900.0
    assert data.terms


def test_ts_plot_png_returns_image() -> None:
    from fastmcp import Client

    server = create_server()

    async def _call():  # noqa: ANN202
        async with Client(server) as client:
            return await client.call_tool(
                "ts_plot_png",
                {"d_count": 3, "steps": 6},
            )

    result = asyncio.run(_call())
    content = result.content if hasattr(result, "content") else result
    assert any(
        getattr(item, "type", None) == "image" or getattr(item, "mimeType", "") == "image/png"
        for item in content
    )
