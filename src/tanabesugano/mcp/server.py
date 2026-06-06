"""TanabeSugano FastMCP server entry point."""

from __future__ import annotations

import argparse
import sys

from typing import TYPE_CHECKING
from typing import Any

from tanabesugano import __version__


if TYPE_CHECKING:
    from fastmcp import FastMCP

_INSTALL_HINT = (
    "FastMCP is not installed. Install the MCP extra:\n"
    "    pip install 'tanabesugano[mcp]'\n"
    "    # or: uv add 'tanabesugano[mcp]'\n"
)


def _make_unwrap_data_middleware():  # noqa: ANN202 — fastmcp types not importable when extra missing
    """Build a middleware that defensively unwraps ``{"data": {...}}`` tool args.

    Our published inputSchemas are flat (``{d_count, dq_min, ...}``), but some
    MCP clients (a recent Claude Desktop build was observed doing this) wrap
    the args once in a ``data`` envelope. Pydantic then rejects the call with
    a confusing dual error — both *"Unexpected keyword argument: data"* and
    *"Missing required argument: d_count"*. Detecting the envelope here keeps
    the user-visible behaviour identical regardless of the client's quirk.
    """
    from fastmcp.server.middleware import Middleware

    class UnwrapDataMiddleware(Middleware):  # type: ignore[misc]
        async def on_call_tool(self, context, call_next):  # type: ignore[override]
            params = context.message
            args = getattr(params, "arguments", None) or {}
            # Only unwrap when the args are exactly ``{"data": <dict>}`` —
            # never touch tools that legitimately take a ``data`` argument.
            if isinstance(args, dict) and len(args) == 1 and isinstance(args.get("data"), dict):
                params.arguments = args["data"]  # type: ignore[attr-defined]
            return await call_next(context)

    return UnwrapDataMiddleware()


def create_server() -> FastMCP[Any]:
    """Build and configure the TanabeSugano FastMCP server."""
    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(_INSTALL_HINT) from exc

    from tanabesugano.mcp.apps import register_apps
    from tanabesugano.mcp.prompts import register_prompts
    from tanabesugano.mcp.resources import register_resources
    from tanabesugano.mcp.tools import register_tools

    mcp: FastMCP[Any] = FastMCP(
        name="tanabesugano",
        instructions=(
            "MCP server for TanabeSugano. Exposes d2-d8 Tanabe-Sugano and "
            "energy-correlation diagram computation, term-symbol eigenvalues, "
            "and interactive in-chat charts. Use ts_supported_configs to "
            "discover what is available. For numeric data use "
            "ts_terms_table_data (sorted rows at one point) or "
            "ts_fit_spectrum (back-out Dq and B from observed peaks). For "
            "visualisation: ts_diagram_app, ts_plot_view, ts_overlay_app, "
            "ts_compare_app, ts_spectrum_app, ts_oxidation_landscape_app, "
            "ts_orgel_diagram_app, ts_reverse_fit_app, and ts_ratio_fit_app "
            "all render as in-chat Chart.js; ts_compute_app and "
            "ts_dashboard_app render as Prefab-native cards + tables; "
            "ts_plot_png is a matplotlib PNG fallback for non-capable "
            "clients. Do NOT call ts_compute or ts_diagram — they were "
            "removed in favour of the app and table tools above."
        ),
        version=__version__,
    )

    mcp.add_middleware(_make_unwrap_data_middleware())

    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    register_apps(mcp)
    return mcp


def main() -> None:
    """Console-script entry point for `tanabesugano-mcp`."""
    parser = argparse.ArgumentParser(
        prog="tanabesugano-mcp",
        description="Run the TanabeSugano MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio, for Claude Desktop and similar).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for HTTP transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport (default: 8000).",
    )
    args = parser.parse_args()

    try:
        server = create_server()
    except SystemExit as exc:
        sys.stderr.write(str(exc))
        sys.exit(1)

    if args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
